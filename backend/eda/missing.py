import pandas as pd
import numpy as np
from ..utils.normaliser import severity_score


def compute_missing_values(df: pd.DataFrame) -> dict:
    """Return per-column missing value statistics with row indices (up to 20)."""
    mv = {}
    for col in df.columns:
        n_missing = int(df[col].isna().sum())
        pct = round(n_missing / len(df) * 100, 2) if len(df) > 0 else 0
        sev = "high" if pct > 30 else "medium" if pct > 10 else "low"
        mv[col] = {
            "n_missing": n_missing,
            "pct_missing": pct,
            "severity": sev,
            "severity_score": severity_score(pct),
            "null_row_indices": df.index[df[col].isna()].tolist()[:20] if n_missing > 0 else [],
        }
    return mv


def apply_null_strategy(df: pd.DataFrame, changes: list) -> pd.DataFrame:
    """
    Preserve null semantics — add _was_null flags then fill placeholders.
    Does NOT impute anthropometric values.
    """
    for col in ["negeri", "daerah", "jantina", "pendapatan"]:
        if col not in df.columns:
            continue
        n_null = int(df[col].isna().sum())
        if n_null > 0:
            df[f"{col}_was_null"] = df[col].isna()
            df[col] = df[col].fillna("UNKNOWN")
            changes.append({
                "action": "null_flagged_and_filled",
                "description": f"{n_null} nilai null dalam '{col}' → 'UNKNOWN'",
                "column": col,
                "before": {col: {"n_null": n_null}},
                "after":  {col: {"filled_with": "UNKNOWN"},
                           f"{col}_was_null": "boolean flag added"},
                "impact_pct": round(n_null / len(df) * 100, 1) if len(df) else 0,
                "rows_affected": n_null,
            })

    for col in ["status_berat", "status_tinggi", "status_bmi"]:
        if col not in df.columns:
            continue
        n_null = int(df[col].isna().sum())
        if n_null > 0:
            df[f"{col}_was_null"] = df[col].isna()
            df[col] = df[col].fillna("tiada data")
            changes.append({
                "action": "null_flagged_and_filled",
                "description": f"{n_null} status null dalam '{col}' → 'tiada data'",
                "column": col,
                "before": {col: {"n_null": n_null}},
                "after":  {col: {"filled_with": "tiada data"}},
                "impact_pct": round(n_null / len(df) * 100, 1) if len(df) else 0,
                "rows_affected": n_null,
            })

    anthro = [c for c in ["berat_kg", "tinggi_cm", "bmi"] if c in df.columns]
    if anthro:
        df["is_missing_critical"] = df[anthro].isnull().any(axis=1)
        n_crit = int(df["is_missing_critical"].sum())
        changes.append({
            "action": "flag_missing_critical",
            "description": f"'is_missing_critical': {n_crit} rekod dengan berat/tinggi/BMI kosong",
            "column": "is_missing_critical",
            "before": {}, "after": {"n_flagged": n_crit},
            "impact_pct": round(n_crit / len(df) * 100, 1) if len(df) else 0,
            "rows_affected": n_crit,
        })
    return df
