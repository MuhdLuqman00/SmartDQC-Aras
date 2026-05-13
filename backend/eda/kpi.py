"""
KPI dashboard: indicator flag rates vs NPAN national targets and WHO global targets,
with RAG traffic-light status and district trajectory narratives.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_NATIONAL_KPIS: dict[str, dict] = {
    "stunting_rate":    {"target": 15.0, "label_bm": "Kadar Stunting",         "label_en": "Stunting Rate"},
    "wasting_rate":     {"target": 5.0,  "label_bm": "Kadar Wasting",          "label_en": "Wasting Rate"},
    "underweight_rate": {"target": 12.0, "label_bm": "Kadar Kekurangan Berat", "label_en": "Underweight Rate"},
    "overweight_rate":  {"target": 10.0, "label_bm": "Kadar Berlebihan Berat", "label_en": "Overweight Rate"},
}

# WHO Global Nutrition Targets 2025
_WHO_TARGETS: dict[str, float] = {
    "stunting_rate":    20.0,
    "wasting_rate":     5.0,
    "underweight_rate": 10.0,
    "overweight_rate":  3.0,
}

_FLAG_TO_KPI: dict[str, str] = {
    "stunting":    "stunting_rate",
    "wasting":     "wasting_rate",
    "underweight": "underweight_rate",
    "overweight":  "overweight_rate",
}

_DISTRICT_COLS = ["NEGERI", "STATE", "negeri", "state", "Negeri", "State"]

# Periods ahead to forecast for "will meet 2027 target" check
_FORECAST_PERIODS = 4


def _rag(actual: float, target: float) -> str:
    if actual <= target:
        return "Green"
    if actual <= target * 1.20:
        return "Amber"
    return "Red"


def compute_kpi_dashboard(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"kpis": [], "overall_status": "Green", "district_breakdown": None}

    total = len(df)
    kpis  = []

    for flag_col, kpi_key in _FLAG_TO_KPI.items():
        if flag_col not in df.columns:
            continue
        count       = int(df[flag_col].fillna(0).astype(bool).sum())
        actual      = round(count / total * 100, 2)
        npan_target = _NATIONAL_KPIS[kpi_key]["target"]
        who_target  = _WHO_TARGETS.get(kpi_key)

        kpis.append({
            "kpi":          kpi_key,
            **_NATIONAL_KPIS[kpi_key],
            "actual":       actual,
            "actual_count": count,
            "total":        total,
            "status":       _rag(actual, npan_target),
            "gap":          round(actual - npan_target, 2),
            "who_target":   who_target,
            "who_status":   _rag(actual, who_target) if who_target is not None else None,
            "gap_to_who":   round(actual - who_target, 2) if who_target is not None else None,
        })

    district_col = next((c for c in _DISTRICT_COLS if c in df.columns), None)
    district_breakdown = None
    if district_col and kpis:
        rows = []
        for district, grp in df.groupby(district_col):
            n     = len(grp)
            entry = {"district": str(district), "n_records": n}
            for flag_col, kpi_key in _FLAG_TO_KPI.items():
                if flag_col not in grp.columns:
                    continue
                rate   = round(grp[flag_col].fillna(0).astype(bool).sum() / n * 100, 2)
                npan_t = _NATIONAL_KPIS[kpi_key]["target"]
                who_t  = _WHO_TARGETS.get(kpi_key)
                entry[f"{kpi_key}_rate"]       = rate
                entry[f"{kpi_key}_status"]     = _rag(rate, npan_t)
                entry[f"{kpi_key}_who_status"] = _rag(rate, who_t) if who_t else None
            rows.append(entry)
        district_breakdown = rows

    statuses = [k["status"] for k in kpis]
    overall  = "Red" if "Red" in statuses else ("Amber" if "Amber" in statuses else "Green")

    return {"kpis": kpis, "overall_status": overall, "district_breakdown": district_breakdown}


def compute_trajectory_narratives(
    historical_snapshots: list[dict],
    current_breakdown: list[dict],
) -> list[dict]:
    """
    Compute per-district, per-KPI trajectory narratives from historical indicator snapshots.

    Args:
        historical_snapshots: list of dicts from indicator_snapshots table:
            [{district, period, stunting_rate, wasting_rate, underweight_rate, overweight_rate}, ...]
        current_breakdown: district_breakdown from compute_kpi_dashboard (reserved for enrichment)

    Returns:
        list of dicts, one per (district, kpi_key) with >=2 data points.
    """
    if not historical_snapshots:
        return []

    df = pd.DataFrame(historical_snapshots)

    kpi_rate_cols = {
        "stunting_rate":    "stunting_rate",
        "wasting_rate":     "wasting_rate",
        "underweight_rate": "underweight_rate",
        "overweight_rate":  "overweight_rate",
    }

    results = []
    for district, grp in df.groupby("district"):
        grp = grp.sort_values("period").reset_index(drop=True)
        x   = np.arange(len(grp), dtype=float)

        for kpi_key, rate_col in kpi_rate_cols.items():
            if rate_col not in grp.columns or grp[rate_col].isna().all():
                continue
            y = grp[rate_col].values.astype(float)
            if len(y) < 2:
                continue

            coeffs        = np.polyfit(x, y, 1)
            slope         = float(coeffs[0])
            current_rate  = float(y[-1])
            forecast_rate = slope * (len(grp) - 1 + _FORECAST_PERIODS) + float(coeffs[1])

            target    = _NATIONAL_KPIS[kpi_key]["target"]
            will_meet = forecast_rate <= target

            if will_meet:
                status    = "On Track"
                status_bm = "Menuju Sasaran"
                narrative_en = (
                    f"{district} is projected to meet the {kpi_key} target of {target}% by 2027. "
                    f"At the current trend ({slope:+.2f}pp/period), the rate will reach {forecast_rate:.1f}%."
                )
                narrative_bm = (
                    f"{district} dijangka mencapai sasaran {kpi_key} sebanyak {target}% menjelang 2027. "
                    f"Pada kadar semasa ({slope:+.2f} mata peratusan/tempoh), kadar akan mencapai {forecast_rate:.1f}%."
                )
            elif forecast_rate <= target * 1.30:
                status    = "At Risk"
                status_bm = "Berisiko"
                narrative_en = (
                    f"{district} is at risk of missing the {kpi_key} target of {target}% by 2027. "
                    f"At the current trend ({slope:+.2f}pp/period), the rate is projected at "
                    f"{forecast_rate:.1f}% — {forecast_rate - target:.1f}pp above target."
                )
                narrative_bm = (
                    f"{district} berisiko tidak mencapai sasaran {kpi_key} sebanyak {target}% menjelang 2027. "
                    f"Pada kadar semasa, kadar dijangka {forecast_rate:.1f}%."
                )
            else:
                status    = "Off Track"
                status_bm = "Tidak Menuju Sasaran"
                narrative_en = (
                    f"{district} will NOT meet the {kpi_key} target of {target}% by 2027. "
                    f"At the current trend ({slope:+.2f}pp/period), the rate is projected at "
                    f"{forecast_rate:.1f}% — {forecast_rate - target:.1f}pp above target."
                )
                narrative_bm = (
                    f"{district} TIDAK akan mencapai sasaran {kpi_key} sebanyak {target}% menjelang 2027. "
                    f"Pada kadar semasa, kadar dijangka {forecast_rate:.1f}%."
                )

            results.append({
                "district":             str(district),
                "kpi_key":              kpi_key,
                "current_rate":         round(current_rate, 2),
                "target":               target,
                "forecast_2027":        round(forecast_rate, 2),
                "slope_per_period":     round(slope, 4),
                "will_meet_target":     will_meet,
                "trajectory_status":    status,
                "trajectory_status_bm": status_bm,
                "narrative":            {"en": narrative_en, "bm": narrative_bm},
            })

    return results
