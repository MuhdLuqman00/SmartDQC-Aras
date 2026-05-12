import pandas as pd
import numpy as np


def check_bmi_consistency(df: pd.DataFrame, threshold: float = 1.0) -> dict:
    """
    Recalculate BMI from weight/height and compare against stored BMI.
    Flags rows where |bmi_calculated - bmi_stored| > threshold.
    """
    result = {"checked": False, "n_checked": 0, "n_mismatch": 0, "pct_mismatch": 0.0}
    if not all(c in df.columns for c in ["berat_kg", "tinggi_cm", "bmi"]):
        return result

    w = pd.to_numeric(df["berat_kg"], errors="coerce")
    h = pd.to_numeric(df["tinggi_cm"], errors="coerce")
    b = pd.to_numeric(df["bmi"],     errors="coerce")
    mask = w.notna() & h.notna() & b.notna() & (h > 0)
    n_checked = int(mask.sum())
    if n_checked == 0:
        return result

    bmi_calc   = w[mask] / ((h[mask] / 100) ** 2)
    diff       = (bmi_calc - b[mask]).abs()
    n_mismatch = int((diff > threshold).sum())

    df["bmi_calc"] = np.nan
    df.loc[mask, "bmi_calc"] = bmi_calc.round(3).values
    df["flag_bmi_mismatch"] = False
    df.loc[mask & (diff > threshold), "flag_bmi_mismatch"] = True

    pct_mis = round(n_mismatch / n_checked * 100, 2)
    return {
        "checked": True,
        "n_checked": n_checked,
        "n_mismatch": n_mismatch,
        "pct_mismatch": pct_mis,
        "threshold_used": threshold,
        "severity": "high"   if pct_mis > 20 else "medium" if pct_mis > 5 else "low",
        "severity_score": 4  if pct_mis > 20 else 2        if pct_mis > 5 else 1,
        "note": f"BMI dikira semula. {n_mismatch} rekod berbeza > {threshold} unit dari nilai asal.",
    }
