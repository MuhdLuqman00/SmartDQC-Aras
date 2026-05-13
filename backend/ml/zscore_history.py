"""
Historical Z-score trend analysis and next-quarter district risk forecast.
Consumes records from the zscore_archive table.
Uses numpy.polyfit for linear regression — no scipy dependency.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def aggregate_zscore_archive(records: list[dict]) -> pd.DataFrame:
    """
    Aggregate per-child zscore_archive rows into per-district, per-period means.

    Args:
        records: list of dicts with keys: ic_no, period, district, waz, haz, baz

    Returns:
        DataFrame with columns: district, period, waz_mean, haz_mean, baz_mean, n_records
    """
    if not records:
        return pd.DataFrame(
            columns=["district", "period", "waz_mean", "haz_mean", "baz_mean", "n_records"]
        )

    df = pd.DataFrame(records)
    agg = (
        df.groupby(["district", "period"])
        .agg(
            waz_mean=("waz", "mean"),
            haz_mean=("haz", "mean"),
            baz_mean=("baz", "mean"),
            n_records=("ic_no", "count"),
        )
        .round(4)
        .reset_index()
    )
    return agg


def forecast_district_risk(records: list[dict]) -> list[dict]:
    """
    Compute next-quarter district risk forecasts from raw zscore_archive records.

    Args:
        records: list of dicts from zscore_archive (ic_no, period, district, waz, haz, baz)

    Returns:
        list of dicts, one per district:
            district, historical_periods, latest_period,
            waz_mean_forecast, waz_mean_trend, waz_mean_slope,
            haz_mean_forecast, haz_mean_trend, haz_mean_slope,
            next_quarter_risk  ("Low" | "Medium" | "High")
    """
    agg = aggregate_zscore_archive(records)
    if agg.empty:
        return []

    results = []
    for district, grp in agg.groupby("district"):
        grp = grp.sort_values("period").reset_index(drop=True)
        x   = np.arange(len(grp), dtype=float)

        entry: dict = {
            "district":           district,
            "historical_periods": len(grp),
            "latest_period":      grp["period"].iloc[-1],
        }

        for col in ("waz_mean", "haz_mean"):
            if col not in grp.columns or grp[col].isna().all():
                entry[f"{col}_forecast"] = None
                entry[f"{col}_trend"]    = "insufficient_data"
                continue

            y = grp[col].values.astype(float)

            if len(y) < 3:
                entry[f"{col}_forecast"] = None
                entry[f"{col}_trend"]    = "insufficient_data"
                continue

            coeffs    = np.polyfit(x, y, 1)
            slope     = float(coeffs[0])
            intercept = float(coeffs[1])
            forecast  = slope * len(grp) + intercept

            trend = (
                "improving" if slope > 0.05
                else "declining" if slope < -0.05
                else "stable"
            )
            entry[f"{col}_forecast"] = round(forecast, 4)
            entry[f"{col}_trend"]    = trend
            entry[f"{col}_slope"]    = round(slope, 6)

        # Risk tier: lower WAZ = more underweight = higher risk
        waz_f = entry.get("waz_mean_forecast") or 0.0
        entry["next_quarter_risk"] = (
            "High"   if waz_f < -2.0
            else "Medium" if waz_f < -1.5
            else "Low"
        )

        results.append(entry)

    return results
