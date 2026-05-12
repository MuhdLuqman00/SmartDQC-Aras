import pandas as pd
import numpy as np
from ..config import BIO_RANGES


def compute_numerical_summary(df: pd.DataFrame) -> dict:
    summary = {}
    cols = ["berat_kg", "tinggi_cm", "bmi", "age_months_computed", "waz", "haz", "baz"]
    labels = {
        "berat_kg": "Berat (kg)", "tinggi_cm": "Tinggi/Panjang (cm)",
        "bmi": "BMI", "age_months_computed": "Umur (bulan)",
        "waz": "WAZ (Weight-for-Age Z)", "haz": "HAZ (Height-for-Age Z)",
        "baz": "BAZ (BMI-for-Age Z)",
    }
    for col in cols:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(s) == 0:
            continue

        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        lo3, hi3 = q1 - 3.0 * iqr, q3 + 3.0 * iqr
        outlier_mask  = (s < lo) | (s > hi)
        extreme_mask  = (s < lo3) | (s > hi3)

        bio_lo, bio_hi = BIO_RANGES.get(col, (None, None))
        bio_outliers = 0
        if bio_lo is not None:
            bio_outliers = int(((s < bio_lo) | (s > bio_hi)).sum())

        z_mean, z_std = float(s.mean()), float(s.std())
        z_outliers = int(((s - z_mean).abs() / z_std > 3).sum()) if z_std > 0 else 0

        mode_vals = s.mode()
        mode_val  = round(float(mode_vals.iloc[0]), 2) if len(mode_vals) > 0 else None

        summary[col] = {
            "label": labels.get(col, col),
            "n": int(len(s)),
            "min": round(float(s.min()), 3), "max": round(float(s.max()), 3),
            "range": round(float(s.max() - s.min()), 3),
            "mean": round(float(s.mean()), 3), "median": round(float(s.median()), 3),
            "mode": mode_val,
            "std": round(float(s.std()), 3),
            "skewness": round(float(s.skew()), 3),
            "kurtosis": round(float(s.kurtosis()), 3),
            "p5":  round(float(s.quantile(0.05)), 3),
            "p25": round(float(q1), 3),
            "p75": round(float(q3), 3),
            "p95": round(float(s.quantile(0.95)), 3),
            "outliers_iqr":        int(outlier_mask.sum()),
            "extreme_outliers_iqr":int(extreme_mask.sum()),
            "outliers_zscore":     z_outliers,
            "outliers_bio":        bio_outliers,
            "bio_range": [bio_lo, bio_hi] if bio_lo is not None else None,
            "iqr_bounds": [round(float(lo), 3), round(float(hi), 3)],
            "boxplot": {
                "q1":     round(float(q1), 3),
                "median": round(float(s.median()), 3),
                "q3":     round(float(q3), 3),
                "whisker_lo": round(float(s[s >= lo].min()), 3) if (s >= lo).any() else round(float(s.min()), 3),
                "whisker_hi": round(float(s[s <= hi].max()), 3) if (s <= hi).any() else round(float(s.max()), 3),
                "outlier_points": sorted(s[outlier_mask].round(3).tolist())[:50],
            },
        }
    return summary
