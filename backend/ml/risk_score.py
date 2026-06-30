"""
Composite child nutritional risk score (0-100).

Severity-aware model built on continuous WHO 2006 z-scores (WAZ/HAZ/BAZ) plus
age vulnerability and longitudinal deterioration (consecutive underweight
readings). Unlike the previous boolean flag-sum scorer, this preserves
severity: a severely wasted child (BAZ < -3, i.e. SAM) is scored materially
higher than a moderately wasted one and reliably lands in the High tier.

Scoring is a *capped additive points* model. Each component contributes
``severity (0-1) x max_points``; the score is ``min(100, sum of points)``.
Max-points preserve the clinical ranking acute > composite > chronic:

    wasting (BAZ low, acute)        70   severe wasting alone => High
    underweight (WAZ)               55
    stunting (HAZ, chronic)         45
    overweight (BAZ high)           30
    consecutive underweight         15   sustained deterioration over visits

Age does not add baseline points (a healthy child scores 0 regardless of age);
instead it *amplifies* the nutritional subtotal — younger children with deficits
are more vulnerable: U2 x1.15, U5 x1.05, older x1.0.

Tiers: Low 0-33, Medium 34-66, High 67-100.

Missing data is handled explicitly: a row whose WAZ, HAZ and BAZ are all
missing cannot be scored and is reported in the "Incomplete" tier rather than
silently treated as healthy.

"Number of missed visits" from the original spec is intentionally omitted —
there is no visit-schedule baseline in the pipeline to define "missed".
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.config import DEFAULT_ID_COLUMN

# Component max-point budgets (see module docstring for rationale).
_PTS_WASTING      = 70.0
_PTS_UNDERWEIGHT  = 55.0
_PTS_STUNTING     = 45.0
_PTS_OVERWEIGHT   = 30.0
_PTS_CONSECUTIVE  = 15.0

# Tier cut points on the 0-100 score.
_LOW_MAX    = 33   # 0-33  -> Low
_MEDIUM_MAX = 66   # 34-66 -> Medium ; 67-100 -> High

# Column-name candidates (cleaners emit canonical PascalCase; accept lowercase).
_WAZ_COLS      = ("WAZ", "waz")
_HAZ_COLS      = ("HAZ", "haz")
_BAZ_COLS      = ("BAZ", "baz")
_AGE_COLS      = ("Age_Months", "age_months", "umur_bulan", "Umur_Bulan")
_IC_COLS       = (DEFAULT_ID_COLUMN, "ic_no", "IC", "ic")
_DATE_COLS     = ("Tarikh_Ukur", "tarikh_ukur", "tarikh_antropometri", "visit_date")
_DISTRICT_COLS = ("NEGERI", "STATE", "negeri", "state", "Negeri", "State")
_NAME_COLS     = ("NAMA", "nama", "name")


def _resolve(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    return next((c for c in candidates if c in df.columns), None)


def _deficit_severity(z: pd.Series) -> np.ndarray:
    """Severity (0-1) for a deficit z-score (more negative = worse).

    z > -2          -> 0     (within normal range)
    -3 < z <= -2    -> 0..0.5 linear (moderate)
    z <= -3         -> 0.5..1.0 linear to z=-4, capped at 1.0 (severe)
    NaN             -> 0     (handled as "absent" by the caller's mask)
    """
    zf = pd.to_numeric(z, errors="coerce").to_numpy(dtype=float)
    s = np.zeros_like(zf)
    moderate = (zf <= -2) & (zf > -3)
    severe = zf <= -3
    s[moderate] = (-2.0 - zf[moderate]) * 0.5            # -2->0, -3->0.5
    s[severe] = 0.5 + np.clip(-3.0 - zf[severe], 0, 1) * 0.5  # -3->0.5, <=-4->1.0
    return np.nan_to_num(s, nan=0.0)


def _overweight_severity(baz: pd.Series) -> np.ndarray:
    """Severity (0-1) for high BAZ (overweight/obese; higher = worse)."""
    zf = pd.to_numeric(baz, errors="coerce").to_numpy(dtype=float)
    s = np.zeros_like(zf)
    moderate = (zf >= 1) & (zf < 2)
    severe = zf >= 2
    s[moderate] = (zf[moderate] - 1.0) * 0.5             # +1->0, +2->0.5
    s[severe] = 0.5 + np.clip(zf[severe] - 2.0, 0, 1) * 0.5   # +2->0.5, >=+3->1.0
    return np.nan_to_num(s, nan=0.0)


def _age_multiplier(age_months: pd.Series) -> np.ndarray:
    """Vulnerability amplifier on the nutritional subtotal (does not add points).

    U2 (<24mo) x1.15, U5 (24-59mo) x1.05, older / unknown x1.0.
    """
    a = pd.to_numeric(age_months, errors="coerce").to_numpy(dtype=float)
    m = np.ones_like(a)
    m[a < 24] = 1.15
    m[(a >= 24) & (a < 60)] = 1.05
    return np.nan_to_num(m, nan=1.0)


def _consecutive_underweight(
    df: pd.DataFrame, ic_col: str | None, date_col: str | None, waz_col: str | None
) -> np.ndarray:
    """Per-row trailing count of consecutive underweight (WAZ < -2) visits.

    Requires per-child longitudinal data (IC + visit date). Returns zeros when
    that data is unavailable or each child has a single visit.
    """
    counts = np.zeros(len(df), dtype=float)
    if not (ic_col and date_col and waz_col):
        return counts
    underweight = (pd.to_numeric(df[waz_col], errors="coerce") < -2).fillna(False)
    pos = {idx: i for i, idx in enumerate(df.index)}
    for _, grp in df.groupby(ic_col, sort=False):
        run = 0
        for idx in grp.sort_values(date_col).index:
            run = run + 1 if underweight.loc[idx] else 0
            counts[pos[idx]] = run
    return counts


def compute_risk_scores(df: pd.DataFrame) -> dict:
    """Composite child risk score (0-100) with severity-aware components.

    Returns aggregate analytics only (no per-child roster). Each score is
    explainable by construction — a deterministic sum of named, severity-scaled
    components — though per-child explanation strings are not surfaced here.
    """
    empty = {
        "total_records": 0, "scored_records": 0, "incomplete_count": 0,
        "flags_used": [], "distribution": {}, "avg_risk_score": 0.0,
        "high_risk_count": 0, "district_summary": None,
    }
    if df.empty:
        return empty

    waz_col = _resolve(df, _WAZ_COLS)
    haz_col = _resolve(df, _HAZ_COLS)
    baz_col = _resolve(df, _BAZ_COLS)
    age_col = _resolve(df, _AGE_COLS)
    ic_col = _resolve(df, _IC_COLS)
    date_col = _resolve(df, _DATE_COLS)

    if not (waz_col or haz_col or baz_col):
        # No anthropometric measurements at all — nothing is scorable.
        return {**empty, "total_records": len(df), "incomplete_count": len(df),
                "distribution": {"Incomplete": len(df)}}

    n = len(df)

    sev_uw    = _deficit_severity(df[waz_col]) if waz_col else np.zeros(n)
    sev_stunt = _deficit_severity(df[haz_col]) if haz_col else np.zeros(n)
    sev_wast  = _deficit_severity(df[baz_col]) if baz_col else np.zeros(n)
    sev_over  = _overweight_severity(df[baz_col]) if baz_col else np.zeros(n)
    age_mult  = _age_multiplier(df[age_col]) if age_col else np.ones(n)
    consec_n  = _consecutive_underweight(df, ic_col, date_col, waz_col)
    consec_v  = np.clip(consec_n / 3.0, 0, 1)

    # Nutritional subtotal, then amplified by age vulnerability. A healthy child
    # has a zero subtotal and so scores 0 regardless of age.
    subtotal = (
        sev_wast  * _PTS_WASTING
        + sev_uw    * _PTS_UNDERWEIGHT
        + sev_stunt * _PTS_STUNTING
        + sev_over  * _PTS_OVERWEIGHT
        + consec_v  * _PTS_CONSECUTIVE
    )
    score = np.minimum(100.0, np.round(subtotal * age_mult)).astype(float)

    # A row is "Incomplete" when none of the three anthro z-scores are present.
    anthro = [c for c in (waz_col, haz_col, baz_col) if c]
    present = pd.concat([pd.to_numeric(df[c], errors="coerce").notna() for c in anthro], axis=1).any(axis=1)
    scorable = present.to_numpy()

    risk = pd.Series(np.where(scorable, score, np.nan), index=df.index)
    tier = pd.Series(
        np.where(
            ~scorable, "Incomplete",
            np.where(score <= _LOW_MAX, "Low",
                     np.where(score <= _MEDIUM_MAX, "Medium", "High")),
        ),
        index=df.index,
    )

    distribution = {k: int(v) for k, v in tier.value_counts().items()}
    scored_mask = tier != "Incomplete"
    scored_n = int(scored_mask.sum())
    avg = round(float(risk[scored_mask].mean()), 2) if scored_n else 0.0

    flags_used = [c for c in (waz_col, haz_col, baz_col, age_col) if c]
    if (consec_n > 0).any():
        flags_used.append("consecutive_underweight")

    district_col = _resolve(df, _DISTRICT_COLS)
    district_summary = None
    if district_col:
        tmp = pd.DataFrame({"district": df[district_col], "risk_score": risk})
        tmp = tmp[scored_mask.to_numpy()]
        if not tmp.empty:
            district_summary = (
                tmp.groupby("district")["risk_score"]
                .agg(avg_risk="mean", max_risk="max", n_records="count")
                .round(2)
                .reset_index()
                .to_dict(orient="records")
            )

    return {
        "total_records":   n,
        "scored_records":  scored_n,
        "incomplete_count": int((~scored_mask).sum()),
        "flags_used":      flags_used,
        "distribution":    distribution,
        "avg_risk_score":  avg,
        "high_risk_count": int((tier == "High").sum()),
        "district_summary": district_summary,
    }
