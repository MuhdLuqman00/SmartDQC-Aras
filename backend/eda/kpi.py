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
    "stunting":    ("stunting", "Ind_Bantut", "ind_bantut_zscore"),
    "wasting":     ("wasting", "Ind_Susut", "ind_susut_zscore"),
    "underweight": ("underweight", "Ind_Kurang_Berat_Badan", "Ind_Kurang_Berat",
                    "ind_kurang_berat_zscore"),
    "overweight":  ("overweight", "Ind_Berlebihan_BB", "Ind_Berlebihan", "Ind_Obes",
                    "ind_obes_zscore"),
}


def _resolve_flag_col(df: pd.DataFrame, flag: str) -> str | None:
    """Return the first column present in `df` that represents `flag`.

    Matching is case-insensitive so a cleaner emitting `ind_bantut_zscore`,
    `Ind_Bantut` or `IND_BANTUT` all resolve — the prior exact-match check
    silently dropped indicators whose casing/suffix differed, leaving the KPI
    dashboard blank for datasets that ship pre-computed `ind_*_zscore` flags."""
    lower = {c.lower(): c for c in df.columns}
    for candidate in _FLAG_ALIASES.get(flag, (flag,)):
        if candidate in df.columns:
            return candidate
        hit = lower.get(candidate.lower())
        if hit is not None:
            return hit
    return None


_DISTRICT_COLS = ["NEGERI", "STATE", "negeri", "state", "Negeri", "State"]
_DAERAH_COLS   = ["daerah", "Daerah", "DAERAH", "district", "District", "kawasan", "Kawasan"]

# Periods ahead to forecast for "will meet 2027 target" check
_FORECAST_PERIODS = 4


def _rag(actual: float, target: float, amber_tolerance: float = 0.20) -> str:
    """Green ≤ target, Amber ≤ target×(1+amber_tolerance), else Red.

    amber_tolerance is configurable (Settings → Thresholds, key
    rag_amber_tolerance). The 0.20 default preserves the historical
    target×1.20 amber band so existing callers are unchanged."""
    if actual <= target:
        return "Green"
    if actual <= target * (1 + amber_tolerance):
        return "Amber"
    return "Red"


def official_targets() -> dict[str, dict[str, float]]:
    """Canonical published targets, used as defaults and the 'reset' baseline.

    NPAN = National Plan of Action for Nutrition 2021–2025; WHO = WHO Global
    Nutrition Targets 2025. Returns only the editable numeric rates per KPI key.
    """
    return {
        "npan": {k: v["target"] for k, v in _NATIONAL_KPIS.items()},
        "who": dict(_WHO_TARGETS),
    }


def _resolve_targets(
    npan: dict[str, float] | None, who: dict[str, float] | None
) -> tuple[dict[str, float], dict[str, float]]:
    """Merge caller-supplied target overrides over the canonical defaults.

    Overrides carry only the editable numeric `target` per KPI key; labels and
    any KPI key the caller omits fall back to the hardcoded official values, so
    a partial or malformed override can never drop an indicator or corrupt a
    label.
    """
    npan_t = {k: v["target"] for k, v in _NATIONAL_KPIS.items()}
    if npan:
        npan_t.update({k: float(v) for k, v in npan.items() if k in npan_t})
    who_t = dict(_WHO_TARGETS)
    if who:
        who_t.update({k: float(v) for k, v in who.items() if k in who_t})
    return npan_t, who_t


def _group_breakdown(
    df: pd.DataFrame, group_col: str, key_name: str, npan_t: dict[str, float],
    amber_tolerance: float = 0.20,
) -> list[dict]:
    """Per-group indicator rates + RAG status, keyed by flag name.

    `key_name` is the label used for the grouping value in each row
    (e.g. "state", "gender", "group"). `npan_t` maps kpi_key -> target rate.
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
            status[flag] = _rag(rate, npan_t[kpi_key], amber_tolerance)
        rows.append({key_name: str(value), "n": int(n),
                     "rates": rates, "status": status})
    return rows


def compute_kpi_dashboard(
    df: pd.DataFrame,
    *,
    npan: dict[str, float] | None = None,
    who: dict[str, float] | None = None,
    amber_tolerance: float = 0.20,
) -> dict:
    empty = {
        "overall_status": "Green",
        "total_children": 0,
        "indicators": [],
        "unavailable_indicators": [],
        "by_state": [],
        "by_daerah": [],
        "by_gender": [],
        "by_income": [],
        "by_age": [],
    }
    if df is None or df.empty:
        return empty

    npan_t, who_t = _resolve_targets(npan, who)

    total = len(df)
    indicators: list[dict] = []
    unavailable: list[dict] = []
    for flag, kpi_key in _FLAG_TO_KPI.items():
        col = _resolve_flag_col(df, flag)
        if col is None:
            # Fail loud, not silent: a missing flag column means the inputs
            # weren't present (e.g. generic-cleaned unknown schema). Surface
            # it as an explicit gap instead of fabricating / omitting it.
            unavailable.append({
                "key":      flag,
                "label_en": _NATIONAL_KPIS[kpi_key]["label_en"],
                "label_bm": _NATIONAL_KPIS[kpi_key]["label_bm"],
                "reason":   "unavailable — required input missing for this dataset",
            })
            continue
        count = int(df[col].fillna(0).astype(bool).sum())
        actual = round(count / total * 100, 2)
        npan_target = npan_t[kpi_key]
        who_target = who_t.get(kpi_key)
        indicators.append({
            "key":          flag,
            "label_en":     _NATIONAL_KPIS[kpi_key]["label_en"],
            "label_bm":     _NATIONAL_KPIS[kpi_key]["label_bm"],
            "actual":       actual,
            "actual_count": count,
            "total":        total,
            "npan_target":  npan_target,
            "who_target":   who_target,
            "gap":          round(actual - npan_target, 2),
            "rag":          _rag(actual, npan_target, amber_tolerance),
            "who_status":   _rag(actual, who_target, amber_tolerance) if who_target is not None else None,
        })

    # by_state — group on the first available state column
    state_col = next((c for c in _DISTRICT_COLS if c in df.columns), None)
    by_state = _group_breakdown(df, state_col, "state", npan_t, amber_tolerance) if state_col else []

    # by_daerah — same shape as by_state, scoped to the district column
    # if present. When the endpoint is called with ?state=X the upstream
    # filter has already narrowed df to that state, so by_daerah here is
    # already state-scoped (or national when unfiltered).
    daerah_col = next((c for c in _DAERAH_COLS if c in df.columns), None)
    by_daerah = _group_breakdown(df, daerah_col, "district", npan_t, amber_tolerance) if daerah_col else []

    # by_gender — tolerant column detection
    gender_col = next(
        (c for c in ["Jantina", "JANTINA", "jantina", "Gender", "GENDER", "gender"]
         if c in df.columns),
        None,
    )
    by_gender = _group_breakdown(df, gender_col, "gender", npan_t, amber_tolerance) if gender_col else []

    # by_income — indicator prevalence cross-cut by income group (B40/M40/T20)
    income_col = next(
        (c for c in ["pendapatan", "Pendapatan", "PENDAPATAN", "kumpulan_pendapatan",
                     "Kumpulan_Pendapatan", "kumpulan pendapatan", "income", "Income",
                     "income_group"]
         if c in df.columns),
        None,
    )
    by_income = _group_breakdown(df, income_col, "income", npan_t, amber_tolerance) if income_col else []

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
        _group_breakdown(age_df, "_age_group", "group", npan_t, amber_tolerance)
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
        "unavailable_indicators": unavailable,
        "by_state": by_state,
        "by_daerah": by_daerah,
        "by_gender": by_gender,
        "by_income": by_income,
        "by_age": by_age,
    }


_TAHUN_COLS = ["tahun_ukur", "Tahun_Ukur", "TAHUN_UKUR", "tahun", "year"]


def compute_district_period_snapshots(df: pd.DataFrame) -> list[dict]:
    """Derive per-district, per-period indicator-rate snapshots from a cleaned
    dataset's measurement-year column, in the shape compute_trajectory_narratives
    consumes: [{district, period, stunting_rate, wasting_rate, ...}].

    Returns [] when there is no year column or no district column — trajectory
    needs >=2 periods per district, which only multi-year datasets provide.
    """
    if df is None or df.empty:
        return []

    year_col = next((c for c in _TAHUN_COLS if c in df.columns), None)
    district_col = (
        next((c for c in _DAERAH_COLS if c in df.columns), None)
        or next((c for c in _DISTRICT_COLS if c in df.columns), None)
    )
    if year_col is None or district_col is None:
        return []

    flag_cols = {
        kpi_key: _resolve_flag_col(df, flag)
        for flag, kpi_key in _FLAG_TO_KPI.items()
    }
    flag_cols = {k: c for k, c in flag_cols.items() if c is not None}
    if not flag_cols:
        return []

    snapshots: list[dict] = []
    for (district, period), grp in df.groupby([district_col, year_col]):
        if pd.isna(period) or pd.isna(district):
            continue
        n = len(grp)
        if n == 0:
            continue
        row = {"district": str(district), "period": str(period)}
        for kpi_key, col in flag_cols.items():
            row[kpi_key] = round(grp[col].fillna(0).astype(bool).sum() / n * 100, 2)
        snapshots.append(row)
    return snapshots


def compute_trajectory_narratives(
    historical_snapshots: list[dict],
    current_breakdown: list[dict],
    npan: dict[str, float] | None = None,
    atrisk_tolerance: float = 0.30,
) -> list[dict]:
    """
    Compute per-district, per-KPI trajectory narratives from historical indicator snapshots.

    Args:
        historical_snapshots: list of dicts from indicator_snapshots table:
            [{district, period, stunting_rate, wasting_rate, underweight_rate, overweight_rate}, ...]
        current_breakdown: district_breakdown from compute_kpi_dashboard (reserved for enrichment)
        npan: optional NPAN target overrides (kpi_key -> target rate). When given,
            the "will meet by 2027" forecast tracks the edited target so the
            trajectory text agrees with the dashboard cards.

    Returns:
        list of dicts, one per (district, kpi_key) with >=2 data points.
    """
    if not historical_snapshots:
        return []

    npan_t, _ = _resolve_targets(npan, None)

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

            target    = npan_t[kpi_key]
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
            elif forecast_rate <= target * (1 + atrisk_tolerance):
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
