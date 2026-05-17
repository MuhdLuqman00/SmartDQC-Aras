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

# Cleaners (clean_myvass/clean_kpm/clean_ncdc) emit Bahasa Ind_* boolean
# columns; analytics, specs, and tests use the canonical English flags.
# Accept either so the KPI dashboard populates regardless of which cleaner
# produced the frame. Canonical name is tried first so existing callers and
# their expected output keys are unaffected.
_FLAG_ALIASES: dict[str, tuple[str, ...]] = {
    "stunting":    ("stunting", "Ind_Bantut"),
    "wasting":     ("wasting", "Ind_Susut"),
    "underweight": ("underweight", "Ind_Kurang_Berat_Badan"),
    "overweight":  ("overweight", "Ind_Berlebihan_BB"),
}


def _resolve_flag_col(df: pd.DataFrame, flag: str) -> str | None:
    """Return the first column present in `df` that represents `flag`."""
    for candidate in _FLAG_ALIASES.get(flag, (flag,)):
        if candidate in df.columns:
            return candidate
    return None


_DISTRICT_COLS = ["NEGERI", "STATE", "negeri", "state", "Negeri", "State"]

# Periods ahead to forecast for "will meet 2027 target" check
_FORECAST_PERIODS = 4


def _rag(actual: float, target: float) -> str:
    if actual <= target:
        return "Green"
    if actual <= target * 1.20:
        return "Amber"
    return "Red"


def _group_breakdown(df: pd.DataFrame, group_col: str, key_name: str) -> list[dict]:
    """Per-group indicator rates + RAG status, keyed by flag name.

    `key_name` is the label used for the grouping value in each row
    (e.g. "state", "gender", "group").
    """
    rows: list[dict] = []
    if group_col not in df.columns:
        return rows
    for value, grp in df.groupby(group_col):
        n = len(grp)
        if n == 0:
            continue
        rates: dict[str, float] = {}
        status: dict[str, str] = {}
        for flag, kpi_key in _FLAG_TO_KPI.items():
            col = _resolve_flag_col(grp, flag)
            if col is None:
                continue
            rate = round(
                grp[col].fillna(0).astype(bool).sum() / n * 100, 2
            )
            rates[flag] = rate
            status[flag] = _rag(rate, _NATIONAL_KPIS[kpi_key]["target"])
        rows.append({key_name: str(value), "n": int(n),
                     "rates": rates, "status": status})
    return rows


def compute_kpi_dashboard(df: pd.DataFrame) -> dict:
    empty = {
        "overall_status": "Green",
        "total_children": 0,
        "indicators": [],
        "by_state": [],
        "by_gender": [],
        "by_age": [],
    }
    if df is None or df.empty:
        return empty

    total = len(df)
    indicators: list[dict] = []
    for flag, kpi_key in _FLAG_TO_KPI.items():
        col = _resolve_flag_col(df, flag)
        if col is None:
            continue
        count = int(df[col].fillna(0).astype(bool).sum())
        actual = round(count / total * 100, 2)
        npan = _NATIONAL_KPIS[kpi_key]["target"]
        who = _WHO_TARGETS.get(kpi_key)
        indicators.append({
            "key":          flag,
            "label_en":     _NATIONAL_KPIS[kpi_key]["label_en"],
            "label_bm":     _NATIONAL_KPIS[kpi_key]["label_bm"],
            "actual":       actual,
            "actual_count": count,
            "total":        total,
            "npan_target":  npan,
            "who_target":   who,
            "gap":          round(actual - npan, 2),
            "rag":          _rag(actual, npan),
        })

    # by_state — group on the first available state column
    state_col = next((c for c in _DISTRICT_COLS if c in df.columns), None)
    by_state = _group_breakdown(df, state_col, "state") if state_col else []

    # by_gender — tolerant column detection
    gender_col = next(
        (c for c in ["Jantina", "JANTINA", "jantina", "Gender", "GENDER", "gender"]
         if c in df.columns),
        None,
    )
    by_gender = _group_breakdown(df, gender_col, "gender") if gender_col else []

    # by_age — bucket months (<24 => "Bawah 2 Tahun") else "2-5 Tahun";
    # fall back to a year column if no months column exists.
    age_col = next(
        (c for c in ["Age_Months", "AGE_MONTHS", "age_months", "Umur_Bulan"]
         if c in df.columns),
        None,
    )
    if age_col is not None:
        bucket = pd.to_numeric(df[age_col], errors="coerce").map(
            lambda m: "Bawah 2 Tahun" if pd.notna(m) and m < 24 else "2-5 Tahun"
        )
        age_df = df.assign(_age_group=bucket)
    else:
        yr_col = next(
            (c for c in ["Age", "AGE", "age", "Umur", "Age_Years"]
             if c in df.columns),
            None,
        )
        if yr_col is not None:
            bucket = pd.to_numeric(df[yr_col], errors="coerce").map(
                lambda y: "Bawah 2 Tahun" if pd.notna(y) and y < 2 else "2-5 Tahun"
            )
            age_df = df.assign(_age_group=bucket)
        else:
            age_df = None
    by_age = (
        _group_breakdown(age_df, "_age_group", "group")
        if age_df is not None else []
    )

    statuses = [i["rag"] for i in indicators]
    overall = (
        "Red" if "Red" in statuses
        else "Amber" if "Amber" in statuses
        else "Green"
    )
    return {
        "overall_status": overall,
        "total_children": total,
        "indicators": indicators,
        "by_state": by_state,
        "by_gender": by_gender,
        "by_age": by_age,
    }


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
