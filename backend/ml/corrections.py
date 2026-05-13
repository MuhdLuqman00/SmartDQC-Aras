import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

_NUMERIC_DTYPES = {"float64", "float32", "int64", "int32", "int16", "int8"}
_CONTAMINATION = 0.05
_MIN_ROWS = 10


def flag_anomalies(df: pd.DataFrame) -> dict:
    num_cols = [
        c for c in df.columns
        if df[c].dtype.name in _NUMERIC_DTYPES and df[c].notna().sum() >= _MIN_ROWS
    ]
    if not num_cols or len(df) < _MIN_ROWS:
        return {"flagged_rows": [], "anomaly_count": 0, "total_rows": len(df), "columns_used": []}

    X = df[num_cols].fillna(df[num_cols].median())

    clf = IsolationForest(contamination=_CONTAMINATION, random_state=42, n_jobs=-1)
    labels = clf.fit_predict(X)
    scores = clf.decision_function(X)

    flagged = []
    for idx in np.where(labels == -1)[0]:
        row_vals = df.iloc[idx][num_cols].to_dict()
        flagged.append({
            "row_index": int(idx),
            "anomaly_score": round(float(scores[idx]), 4),
            "values": {k: (None if pd.isna(v) else float(v)) for k, v in row_vals.items()},
            "suggestions": _suggest_corrections(df, num_cols, row_vals),
        })

    flagged.sort(key=lambda r: r["anomaly_score"])
    return {
        "flagged_rows": flagged,
        "anomaly_count": len(flagged),
        "total_rows": len(df),
        "contamination": _CONTAMINATION,
        "columns_used": num_cols,
    }


def _suggest_corrections(df: pd.DataFrame, num_cols: list[str], row: dict) -> list[dict]:
    suggestions = []
    for col in num_cols:
        val = row.get(col)
        if val is None or pd.isna(val):
            continue
        q1, median, q3 = df[col].quantile([0.25, 0.50, 0.75])
        iqr = q3 - q1
        lo, hi = q1 - 3.0 * iqr, q3 + 3.0 * iqr
        if val < lo or val > hi:
            suggestions.append({
                "column": col,
                "current_value": float(val),
                "suggested_value": round(float(median), 4),
                "reason": (
                    f"Value {round(float(val), 4)} is outside the 3x IQR fence "
                    f"[{round(lo, 2)}, {round(hi, 2)}]; column median is {round(float(median), 4)}"
                ),
            })
    return suggestions
