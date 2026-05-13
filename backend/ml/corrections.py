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
            "row_index":     int(idx),
            "anomaly_score": round(float(scores[idx]), 4),
            "values":        {k: (None if pd.isna(v) else float(v)) for k, v in row_vals.items()},
            "suggestions":   _suggest_corrections(df, num_cols, row_vals),
        })

    flagged.sort(key=lambda r: r["anomaly_score"])
    return {
        "flagged_rows":  flagged,
        "anomaly_count": len(flagged),
        "total_rows":    len(df),
        "contamination": _CONTAMINATION,
        "columns_used":  num_cols,
    }


def _suggest_corrections(df: pd.DataFrame, num_cols: list[str], row: dict) -> list[dict]:
    col_stats = {
        col: {
            "median": float(df[col].median()),
            "q1":     float(df[col].quantile(0.25)),
            "q3":     float(df[col].quantile(0.75)),
        }
        for col in num_cols if df[col].notna().any()
    }

    suggestions = []
    for col in num_cols:
        val = row.get(col)
        if val is None or pd.isna(val):
            continue
        stats  = col_stats.get(col, {})
        q1     = stats.get("q1",     0.0)
        median = stats.get("median", 0.0)
        q3     = stats.get("q3",     0.0)
        iqr    = q3 - q1
        lo, hi = q1 - 3.0 * iqr, q3 + 3.0 * iqr
        if val < lo or val > hi:
            pattern = _detect_decimal_shift(float(val), float(median))
            if pattern is None and _detect_transposition(float(val), float(median)):
                pattern = "digit_transposition"
            if pattern is None:
                pattern = _detect_column_swap(float(val), col, col_stats)
            suggestions.append({
                "column":          col,
                "current_value":   float(val),
                "suggested_value": round(float(median), 4),
                "reason": (
                    f"Value {round(float(val), 4)} is outside the 3x IQR fence "
                    f"[{round(lo, 2)}, {round(hi, 2)}]; column median is {round(float(median), 4)}"
                ),
                "pattern":    pattern,
                "error_type": _classify_error_type(pattern),
            })
    return suggestions


def _detect_decimal_shift(val: float, median: float) -> str | None:
    """Return shift type if val is 10x or /10 of median, else None."""
    if median == 0:
        return None
    ratio = val / median
    if 9.5 <= ratio <= 10.5:
        return "decimal_shift_x10"
    if 0.095 <= ratio <= 0.105:
        return "decimal_shift_div10"
    return None


def _detect_transposition(val: float, median: float) -> bool:
    """True if swapping any two adjacent digits of int(val) gives a number within 5% of median."""
    iv = str(int(abs(val)))
    for i in range(len(iv) - 1):
        swapped = iv[:i] + iv[i + 1] + iv[i] + iv[i + 2:]
        if abs(int(swapped) - median) / max(abs(median), 1) < 0.05:
            return True
    return False


def _detect_column_swap(val: float, current_col: str, col_stats: dict) -> str | None:
    """Return 'column_swap:<other>' if val fits within 1 IQR of another column's median."""
    for other_col, stats in col_stats.items():
        if other_col == current_col:
            continue
        iqr = stats["q3"] - stats["q1"]
        if iqr == 0:
            continue
        if abs(val - stats["median"]) <= iqr:
            return f"column_swap:{other_col}"
    return None


def _classify_error_type(pattern: str | None) -> str:
    if pattern in ("decimal_shift_x10", "decimal_shift_div10", "digit_transposition"):
        return "entry_error"
    if pattern and pattern.startswith("column_swap:"):
        return "entry_error"
    return "unknown"
