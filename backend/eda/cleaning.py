"""
KKM Data Cleaning Backend Module
================================
Provides cleaning functions for KPM, MyVASS, and NCDC data.
Integrates with WHO z-score calculations using daily LMS tables.
"""

import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Try to import WHO z-score module (daily LMS tables from Excel)
try:
    from .who_zscore import compute_zscore, classify_waz, classify_haz, classify_baz
    ZSCORE_AVAILABLE = True
except Exception:
    ZSCORE_AVAILABLE = False

from ..utils.ic_validator import extract_ic_gender_digit, validate_ic, extract_ic_birthdate
from ..config import INCOME_VALID, VACCINE_SET, AGENSI_SET, FACILITY_SET, ETHNIC_VALID


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
#
# ── Aliases from clinical_ranges registry (Phase 2) ─────────────────────────
# Values sourced from backend/clinical_ranges.py; names kept for backward compat.
# Provenance (tier, source, recommended value + why) is in clinical_ranges.py
# and Docs/clinical_ranges_provenance.md. Change via Settings / per-run override.
from backend.clinical_ranges import (
    get_range as _cr_get_range,
    get_val   as _cr_get_val,
    get_biv   as _cr_get_biv,
)

BERAT_MIN_INFANT,  BERAT_MAX_INFANT  = _cr_get_range("infant_weight")
TINGGI_MIN_INFANT, TINGGI_MAX_INFANT = _cr_get_range("infant_height")
BERAT_MIN_SCHOOL,  BERAT_MAX_SCHOOL  = _cr_get_range("school_weight")
TINGGI_MIN_SCHOOL, TINGGI_MAX_SCHOOL = _cr_get_range("school_height")

BMI_MAX               = _cr_get_val("bmi_max")
AGE_MAX_MONTHS_INFANT = int(_cr_get_val("infant_age_cap"))

# Gender mapping
GENDER_MAP = {
    "LELAKI": "Male", "PEREMPUAN": "Female",
    "L": "Male", "P": "Female",
    "M": "Male", "F": "Female",
    "MALE": "Male", "FEMALE": "Female",
}

# biv_waz / biv_haz / biv_baz — WHO, doc §2. Collapsed true-dup with who_zscore._BIV.
BIV = _cr_get_biv()  # {WAZ/HAZ/BAZ: (lo, hi)} — from clinical_ranges registry


# ═══════════════════════════════════════════════════════════════════════════════
# COHORT PROFILES
# ═══════════════════════════════════════════════════════════════════════════════
# Class-B (cohort-dependent) cleaning rules — weight/height plausibility bounds —
# read from a CohortProfile rather than module-level constants so one shared rule
# battery can serve infants (0-5y, WHO z-scores) and school-age children
# (6-10y, BMI categories). Named cleaners use a fixed preset; the general
# cleaner selects/builds its profile from the data (Phase 3+). The min/max
# values are unchanged from the original constants — extracting them here is a
# behaviour-preserving refactor (golden snapshots pin this).

# CohortProfile is defined in clinical_ranges; re-export for backward compat.
from backend.clinical_ranges import CohortProfile, make_infant_profile, make_school_profile

# Default profiles — override-unaware (backward compat). Use make_*_profile(overrides)
# inside cleaners when a per-run override needs to be honoured.
PROFILE_INFANT = make_infant_profile()
PROFILE_SCHOOL = make_school_profile()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_bmi_school(bmi: float) -> str:
    """Classify BMI for school-age children (6-8 years)."""
    if bmi is None or (isinstance(bmi, float) and math.isnan(bmi)):
        return None
    if bmi < 13.5:
        return "Kurus"
    elif bmi < 16.5:
        return "Normal"
    elif bmi < 18.5:
        return "Berlebihan Berat Badan"
    else:
        return "Obes"


def _normalize_gender(value: str) -> Optional[str]:
    """Normalize gender value to Male/Female."""
    if not value:
        return None
    return GENDER_MAP.get(str(value).upper().strip())


def _parse_date(series: pd.Series) -> pd.Series:
    """Parse dates robustly.

    Processed exports store ISO "YYYY-MM-DD[ HH:MM:SS]"; raw sources use
    day-first "dd/mm/yyyy". A blanket dayfirst=True silently MISPARSES ISO
    dates (2023-02-08 -> 2023-08-02) and corrupts the computed age. Parse
    unambiguous/ISO first, then fall back to day-first only for values the
    first pass could not parse (genuine dd/mm/yyyy)."""
    s = series.astype(str)
    is_iso = s.str.match(r"^\s*\d{4}-\d{1,2}-\d{1,2}")
    # Parse each shape group on its own (homogeneous) values so pandas does
    # not infer one format across mixed inputs and coerce the rest to NaT.
    iso = pd.to_datetime(series.where(is_iso), errors="coerce")
    other = pd.to_datetime(series.where(~is_iso), dayfirst=True, errors="coerce")
    return iso.where(is_iso, other)


def _exclude(df: pd.DataFrame, mask: pd.Series, code: str) -> None:
    """Tag rows matching mask as non-analyzable instead of dropping them.

    `analyzable` and `exclude_reason` columns must already exist on `df`.
    Count stats with `(mask & df["analyzable"]).sum()` BEFORE calling this so
    each row is attributed to the first rule that excludes it."""
    if not mask.any():
        return
    df.loc[mask, "analyzable"] = False
    prev = df.loc[mask, "exclude_reason"]
    df.loc[mask, "exclude_reason"] = prev.apply(lambda r: f"{r}; {code}" if r else code)


def _flag(df, mask, code):
    """Tag rows for review without removing from analysis. review_reason must exist."""
    if not mask.any():
        return
    prev = df.loc[mask, "review_reason"]
    df.loc[mask, "review_reason"] = prev.apply(lambda r: f"{r}; {code}" if r else code)


# Sentinel added to enabled_rules when the caller has explicitly configured review
# rules (even if all are disabled). Without it, an empty review selection looks
# identical to a drop-only selection and _review_rule_on would default all ON.
_REVIEW_MANAGED_SENTINEL = "__reviews_managed"

# Vocabulary/whitelist review rules whose reference-set COMPLETENESS cannot be
# grounded in the only authoritative sample we have (Docs/Contoh data.xlsx).
# Disabled 2026-06-16 until KKM supplies the canonical lists. Keeping them on
# produces false "needs review" flags on legitimate values — e.g. FACILITY_SET is
# demonstrably missing real categories ("Hospital Kerajaan", "Klinik Swasta"), and
# ETHNIC_VALID / AGENSI_SET completeness is unprovable from a 19+13-row sample.
# Force-OFF on every path (incl. the legacy all-on default); also removed from
# REVIEW_EVALUATED_RULES so they are not ghost toggles. Bodies kept for revival.
_DISABLED_REVIEW_RULES = frozenset({
    "review_facility_unknown",
    "review_ethnicity_unknown",
    "review_agensi_unknown",
})


def _review_rule_on(code, enabled_rules) -> bool:
    """Review-flag rules default ON. A caller selection only constrains them once
    it actually manages review rules (contains at least one review_* code OR the
    sentinel); a drop-only or legacy selection leaves every review rule ON, so
    flags never silently vanish when a user has saved a drop-rule selection."""
    if code in _DISABLED_REVIEW_RULES:
        return False
    if enabled_rules is None:
        return True
    if _REVIEW_MANAGED_SENTINEL in enabled_rules or any(
        str(c).startswith("review_") for c in enabled_rules
    ):
        return code in enabled_rules
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED RULE BATTERY (Phase 2)
# ═══════════════════════════════════════════════════════════════════════════════
# Per-rule bodies hoisted verbatim out of the named cleaners so the same logic
# can serve every cohort (named presets now, the general superset in Phase 4).
# Each helper mutates df/stats in place and takes an `on(code) -> bool` gate so
# the caller's enabled_rules selection is honoured. Order is still owned by the
# caller: these are called in the cleaner's existing sequence, preserving the
# first-rule-wins exclusion attribution that the golden snapshots pin.

def _apply_measurement_outlier(df, stats, profile, on) -> None:
    """Flag rows whose weight/height fall outside the cohort plausibility bounds."""
    berat_bad = (df["Berat_kg"] < profile.berat_min) | (df["Berat_kg"] > profile.berat_max)
    tinggi_bad = (df["Tinggi_cm"] < profile.tinggi_min) | (df["Tinggi_cm"] > profile.tinggi_max)
    outlier_mask = (berat_bad & df["Berat_kg"].notna()) | (tinggi_bad & df["Tinggi_cm"].notna())
    if on("dropped_measurement_outlier"):
        stats["dropped_measurement_outlier"] = int((outlier_mask & df["analyzable"]).sum())
        _exclude(df, outlier_mask, "dropped_measurement_outlier")
    else:
        stats["dropped_measurement_outlier"] = 0


def _apply_no_measurement(df, stats, on) -> None:
    """Flag rows that carry neither a weight nor a height."""
    no_meas = df["Berat_kg"].isna() & df["Tinggi_cm"].isna()
    if on("dropped_no_measurement"):
        stats["dropped_no_measurement"] = int((no_meas & df["analyzable"]).sum())
        _exclude(df, no_meas, "dropped_no_measurement")
    else:
        stats["dropped_no_measurement"] = 0


def _compute_bmi(df: pd.DataFrame, *, drop_raw: bool = True) -> pd.DataFrame:
    """Recompute BMI from weight/height. When drop_raw, source BMI columns are
    discarded first (returns a new frame, so callers must reassign df)."""
    if drop_raw:
        raw_bmi_cols = [c for c in df.columns if "bmi" in c.lower() and c != "BMI"]
        if raw_bmi_cols:
            df = df.drop(columns=raw_bmi_cols)
    valid_both = df["Berat_kg"].notna() & df["Tinggi_cm"].notna() & (df["Tinggi_cm"] > 0)
    df["BMI"] = np.where(
        valid_both, (df["Berat_kg"] / ((df["Tinggi_cm"] / 100) ** 2)).round(2), np.nan
    )
    return df


def _apply_bmi_outlier(df, stats, on, bmi_max=BMI_MAX) -> None:
    """Flag implausibly high BMI (> bmi_max). `bmi_max` is override-aware per run
    (registry key `bmi_max`); defaults to the module constant for back-compat."""
    bmi_bad = df["BMI"].notna() & (df["BMI"] > bmi_max)
    if on("dropped_bmi_outlier"):
        stats["dropped_bmi_outlier"] = int((bmi_bad & df["analyzable"]).sum())
        _exclude(df, bmi_bad, "dropped_bmi_outlier")
    else:
        stats["dropped_bmi_outlier"] = 0


# ── Schema-specific portable drop-rule helpers (Phase 5C) ─────────────────────
# Each _apply_* encapsulates the inline rule logic from clean_myvass/ncdc/kpm.
# Call sites stay at the SAME pipeline stage — pure relocation, no logic change.
# Each _trigger_* is a predicate over a PREPARED frame (canonical columns already
# present) for the recommend endpoint (Phase 5C step 4).

def _apply_dropped_date_before_dob(df, stats, _on, *, date_col: str) -> None:
    bad_date = (
        df["Tarikh_Lahir"].notna()
        & df[date_col].notna()
        & (df[date_col] < df["Tarikh_Lahir"])
    )
    if _on("dropped_date_before_dob"):
        stats["dropped_date_before_dob"] = int((bad_date & df["analyzable"]).sum())
        _exclude(df, bad_date, "dropped_date_before_dob")
    else:
        stats["dropped_date_before_dob"] = 0


def _trigger_date_before_dob(df: pd.DataFrame, *, date_col: str = "Tarikh_Ukur") -> pd.Series:
    if "Tarikh_Lahir" not in df.columns or date_col not in df.columns:
        return pd.Series(False, index=df.index)
    return (
        df["Tarikh_Lahir"].notna()
        & df[date_col].notna()
        & (df[date_col] < df["Tarikh_Lahir"])
    )


def _apply_dropped_age_over5(df, stats, _on, *, age_cap: float) -> None:
    age_invalid = df["Age_Months"].notna() & (df["Age_Months"] >= age_cap)
    if _on("dropped_age_over5"):
        stats["dropped_age_over5"] = int((age_invalid & df["analyzable"]).sum())
        _exclude(df, age_invalid, "dropped_age_over5")
    else:
        stats["dropped_age_over5"] = 0


def _trigger_age_over5(df: pd.DataFrame, *, age_cap: float = 60.0) -> pd.Series:
    if "Age_Months" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["Age_Months"].notna() & (df["Age_Months"] >= age_cap)


def _apply_dropped_pendapatan_x(df, stats, _on, *, income_col: str) -> None:
    pendapatan_x = df[income_col].astype(str).str.upper().str.strip() == "X"
    if _on("dropped_pendapatan_x"):
        stats["dropped_pendapatan_x"] = int((pendapatan_x & df["analyzable"]).sum())
        _exclude(df, pendapatan_x, "dropped_pendapatan_x")
    else:
        stats["dropped_pendapatan_x"] = 0


def _trigger_pendapatan_x(df: pd.DataFrame) -> pd.Series:
    for col in df.columns:
        if "pendapatan" in col.lower() or "income" in col.lower():
            return df[col].astype(str).str.upper().str.strip() == "X"
    return pd.Series(False, index=df.index)


def _apply_dropped_null_dob(df, stats, _on) -> None:
    _mask = df["Tarikh_Lahir"].isna()
    if _on("dropped_null_dob"):
        stats["dropped_null_dob"] = int((_mask & df["analyzable"]).sum())
        _exclude(df, _mask, "dropped_null_dob")
    else:
        stats["dropped_null_dob"] = 0


def _trigger_null_dob(df: pd.DataFrame) -> pd.Series:
    if "Tarikh_Lahir" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["Tarikh_Lahir"].isna()


def _apply_dropped_duplicate_mykid(
    df, stats, _on, enabled_rules, *, mykid_col: str,
    sort_date_col: str = "Tarikh_Pengukuran"
) -> None:
    _placeholder = pd.Series(False, index=df.index)
    _dropdup = pd.Series(False, index=df.index)
    for _key, _grp in df.groupby(mykid_col):
        if len(_grp) < 2:
            continue
        if _grp["Tarikh_Lahir"].nunique(dropna=True) > 1:
            _placeholder.loc[_grp.index] = True
        else:
            _order = _grp.sort_values(sort_date_col, ascending=False)
            _dropdup.loc[_order.index[1:]] = True
    if _on("dropped_duplicate_mykid"):
        stats["dropped_duplicate_mykid"] = int((_dropdup & df["analyzable"]).sum())
        _exclude(df, _dropdup, "dropped_duplicate_mykid")
    else:
        stats["dropped_duplicate_mykid"] = 0
    if _review_rule_on("review_mykid_shared_placeholder", enabled_rules):
        _flag(df, _placeholder, "review_mykid_shared_placeholder")


def _trigger_duplicate_mykid(df: pd.DataFrame) -> pd.Series:
    mykid_col = next(
        (c for c in df.columns
         if "mykid" in c.lower().replace(" ", "").replace(".", "")),
        None,
    )
    if not mykid_col or "Tarikh_Lahir" not in df.columns:
        return pd.Series(False, index=df.index)
    date_col = next(
        (c for c in ("Tarikh_Pengukuran", "Tarikh_Ukur") if c in df.columns), None
    )
    if not date_col:
        return pd.Series(False, index=df.index)
    result = pd.Series(False, index=df.index)
    for _key, _grp in df.groupby(mykid_col):
        if len(_grp) < 2:
            continue
        if _grp["Tarikh_Lahir"].nunique(dropna=True) <= 1:
            _order = _grp.sort_values(date_col, ascending=False)
            result.loc[_order.index[1:]] = True
    return result


def _apply_dropped_ragu_gender(df, stats, _on) -> None:
    """Assumes Jantina_Raw is already set on df."""
    _mask = df["Jantina_Raw"] == "RAGU"
    if _on("dropped_ragu_gender"):
        stats["dropped_ragu_gender"] = int((_mask & df["analyzable"]).sum())
        _exclude(df, _mask, "dropped_ragu_gender")
    else:
        stats["dropped_ragu_gender"] = 0


def _trigger_ragu_gender(df: pd.DataFrame) -> pd.Series:
    for col in df.columns:
        nc = col.lower()
        if "jantina" in nc or "gender" in nc or nc == "sex":
            return df[col].astype(str).str.upper().str.strip() == "RAGU"
    return pd.Series(False, index=df.index)


def _set_kategori_umur(df: pd.DataFrame) -> None:
    """Bilingual age band column derived from Age_Days."""
    if "Age_Days" in df.columns:
        df["Kategori_Umur"] = np.where(
            df["Age_Days"] < 730, "Bawah 2 Tahun",
            np.where(df["Age_Days"] < 1826, "Bawah 5 Tahun", "5 Tahun ke Atas")
        )


def _compute_zscores_indicators(df, stats) -> None:
    """WHO WAZ/HAZ/BAZ (BIV-clamped, rounded 2dp) + status classifications +
    indicator flags + null-z-score exclusion (Rule 7, locked) + analyzable-only
    indicator counts. Shared by the infant cleaners (myvass/ncdc) and reused by
    the general infant cohort in Phase 4. Mutates df and stats in place. When
    WHO tables are unavailable it records a zero null-z-score drop and returns,
    matching the original `else` branch."""
    if not ZSCORE_AVAILABLE:
        stats["dropped_null_zscore"] = 0
        return

    df["WAZ"] = None
    df["HAZ"] = None
    df["BAZ"] = None

    for idx in df.index:
        # Skip already-excluded rows — z-scores on junk inputs are meaningless
        if not df.loc[idx, "analyzable"]:
            continue
        age_days = df.loc[idx, "Age_Days"]
        sex = df.loc[idx, "Gender"]
        weight = df.loc[idx, "Berat_kg"]
        height = df.loc[idx, "Tinggi_cm"]
        bmi = df.loc[idx, "BMI"]

        if pd.notna(age_days) and pd.notna(sex):
            if pd.notna(weight):
                waz = compute_zscore(weight, sex, age_days, "WAZ")
                if waz is not None and BIV["WAZ"][0] <= waz <= BIV["WAZ"][1]:
                    df.loc[idx, "WAZ"] = round(waz, 2)

            if pd.notna(height):
                haz = compute_zscore(height, sex, age_days, "HAZ")
                if haz is not None and BIV["HAZ"][0] <= haz <= BIV["HAZ"][1]:
                    df.loc[idx, "HAZ"] = round(haz, 2)

            if pd.notna(bmi):
                baz = compute_zscore(bmi, sex, age_days, "BAZ")
                if baz is not None and BIV["BAZ"][0] <= baz <= BIV["BAZ"][1]:
                    df.loc[idx, "BAZ"] = round(baz, 2)

    df["WAZ_Status"] = df["WAZ"].apply(lambda z: classify_waz(z) if pd.notna(z) else None)
    df["HAZ_Status"] = df["HAZ"].apply(lambda z: classify_haz(z) if pd.notna(z) else None)
    df["BAZ_Status"] = df["BAZ"].apply(lambda z: classify_baz(z) if pd.notna(z) else None)

    # Indicator flags (computed on all rows; excluded rows get False which is
    # fine — they are never used in analytics)
    df["Ind_Kurang_Berat_Badan"] = df["WAZ"].apply(lambda z: z < -2 if pd.notna(z) else False)
    df["Ind_Bantut"] = df["HAZ"].apply(lambda z: z < -2 if pd.notna(z) else False)
    df["Ind_Susut"] = df["BAZ"].apply(lambda z: z < -2 if pd.notna(z) else False)
    df["Ind_Berlebihan_BB"] = df["BAZ"].apply(lambda z: z > 1 if pd.notna(z) else False)
    df["Ind_Obes"] = df["BAZ"].apply(lambda z: z > 2 if pd.notna(z) else False)

    # Rule 7: Flag rows with null z-scores (locked — always runs)
    null_zscore = df["WAZ"].isna() | df["HAZ"].isna() | df["BAZ"].isna()
    stats["dropped_null_zscore"] = int((null_zscore & df["analyzable"]).sum())
    _exclude(df, null_zscore, "dropped_null_zscore")

    # Normal indicator
    df["Ind_Normal"] = ~(df["Ind_Kurang_Berat_Badan"] | df["Ind_Bantut"] | df["Ind_Susut"])

    _a = df["analyzable"]
    stats["ind_kurang_berat"] = int(df.loc[_a, "Ind_Kurang_Berat_Badan"].sum())
    stats["ind_bantut"] = int(df.loc[_a, "Ind_Bantut"].sum())
    stats["ind_susut"] = int(df.loc[_a, "Ind_Susut"].sum())
    stats["ind_berlebihan_bb"] = int(df.loc[_a, "Ind_Berlebihan_BB"].sum())
    stats["ind_obes"] = int(df.loc[_a, "Ind_Obes"].sum())
    stats["ind_normal"] = int(df.loc[_a, "Ind_Normal"].sum())


def _apply_review_flags(df, source, src_cols, find_col, enabled_rules, src_raw=None,
                        age_cap=AGE_MAX_MONTHS_INFANT):
    """Review-for-review flags (Families 1-11).

    Each block guards on the presence of its trigger column(s) so clean data
    yields zero flags. Flags use _flag() (review_reason) and NEVER change
    `analyzable`. Dual-column rules read raw source values via src_cols
    (captured before canonical Gender/Tarikh_Lahir were derived).

    `src_raw` is a copy of the frame taken BEFORE recompute overwrites the
    source BMI / z-score / status columns — Families 7-8 (source-integrity
    flags) must read the uploaded values, not the recomputed canonical ones.
    """
    def _on(code):
        return _review_rule_on(code, enabled_rules)

    # Normalised lookup of the pre-recompute source columns (Families 7-9).
    def _norm(s):
        return s.lower().replace("-", " ").replace("_", " ").strip()
    _rawmap = {}
    if src_raw is not None:
        for _c in src_raw.columns:
            _rawmap.setdefault(_norm(_c), src_raw[_c])

    def _raw(*names):
        """First raw source Series matching any normalised name, else None."""
        for n in names:
            s = _rawmap.get(_norm(n))
            if s is not None:
                return s
        return None

    # review_future_measure_date (Family 4): measurement dated after today.
    _mcol = "Tarikh_Ukur" if "Tarikh_Ukur" in df.columns else "Tarikh_Pengukuran"
    if _mcol in df.columns and _on("review_future_measure_date"):
        _today = pd.Timestamp.now().normalize()
        _flag(df, df[_mcol].notna() & (df[_mcol] > _today), "review_future_measure_date")
    # review_duplicate_ic (Family 1, myvass): same IC across rows (flag, not drop).
    if source == "myvass" and _on("review_duplicate_ic"):
        _ic = find_col(["ic_no_passport", "no kp", "kad pengenalan", "passport"])
        if _ic:
            _icn = df[_ic].astype(str).str.strip()
            _valid = (_icn != "") & (~_icn.str.lower().isin(["nan", "none", "<na>"]))
            _flag(df, _valid & _icn.duplicated(keep=False), "review_duplicate_ic")
    # review_ic_gender_mismatch (Family 1, myvass): IC final-digit sex != Gender.
    if source == "myvass" and _on("review_ic_gender_mismatch") and "Gender" in df.columns:
        _ic = find_col(["ic_no_passport", "no kp", "kad pengenalan", "passport"])
        if _ic:
            _icsex = df[_ic].apply(extract_ic_gender_digit)
            _flag(
                df,
                _icsex.notna() & df["Gender"].notna() & (_icsex != df["Gender"]),
                "review_ic_gender_mismatch",
            )
    # review_name_gender_mismatch (Family 2): name honorific contradicts Gender.
    if _on("review_name_gender_mismatch") and "Gender" in df.columns:
        _nm_col = find_col(["nama", "name"])
        if _nm_col:
            _nm = " " + df[_nm_col].astype(str).str.lower().str.strip() + " "
            _fem = _nm.str.contains(r" binti | bt | a/p ", regex=True)
            _mal = _nm.str.contains(r" bin | a/l ", regex=True) & ~_fem
            _implied = pd.Series(pd.NA, index=df.index, dtype="object")
            _implied[_mal] = "Male"
            _implied[_fem] = "Female"
            _nmask = (_implied.notna() & df["Gender"].notna() & (_implied != df["Gender"]))
            _flag(df, _nmask.fillna(False).astype(bool), "review_name_gender_mismatch")
    # review_gender_cols_disagree (Family 3): two raw gender columns conflict.
    if _on("review_gender_cols_disagree"):
        def _is_gender(c):
            n = c.lower().replace("_", " ").replace("-", " ")
            return any(k in n for k in ("jantina", "gender", "sex"))
        _gcols = [c for c in src_cols if _is_gender(c) and c in df.columns]
        if len(_gcols) >= 2:
            _ga = df[_gcols[0]].astype(str).str.upper().str.strip().map(GENDER_MAP)
            _gb = df[_gcols[1]].astype(str).str.upper().str.strip().map(GENDER_MAP)
            _flag(df, _ga.notna() & _gb.notna() & (_ga != _gb), "review_gender_cols_disagree")
    # review_year_mismatch (Family 4): stated year != measurement-date year.
    _mcol2 = "Tarikh_Ukur" if "Tarikh_Ukur" in df.columns else "Tarikh_Pengukuran"
    if source == "ncdc" and "Year" in df.columns:
        _ycol = "Year"
    else:
        _ycol = find_col(["tahun ukur", "tahun_ukur", "tahun"])
    if _mcol2 in df.columns and _ycol and _ycol in df.columns and _on("review_year_mismatch"):
        _ystated = pd.to_numeric(df[_ycol], errors="coerce")
        _ydate = df[_mcol2].dt.year
        _flag(df, _ystated.notna() & _ydate.notna() & (_ystated != _ydate), "review_year_mismatch")
    # review_dob_dual_mismatch (Family 4): two DOB columns disagree.
    if _on("review_dob_dual_mismatch"):
        def _is_dob(c):
            n = c.lower().replace("_", " ").replace("-", " ")
            return ("tarikh lahir" in n) or ("date of birth" in n) or (" dob" in (" " + n)) or n.endswith("birth")
        _dcols = [c for c in src_cols if _is_dob(c) and c in df.columns]
        if len(_dcols) >= 2:
            _da = _parse_date(df[_dcols[0]])
            _db = _parse_date(df[_dcols[1]])
            _flag(df, _da.notna() & _db.notna() & (_da != _db), "review_dob_dual_mismatch")
    # review_ic_* (Family 1, myvass): one validate_ic pass feeds three flags.
    if source == "myvass":
        _ic = find_col(["ic_no_passport", "no kp", "kad pengenalan", "passport"])
        _need_ic = _ic and (
            _on("review_ic_malformed")
            or _on("review_ic_dob_mismatch")
            or _on("review_ic_age_contradiction")
        )
        if _need_ic:
            _icres = df[_ic].apply(validate_ic)
            if _on("review_ic_malformed"):
                _bad = _icres.apply(lambda r: (not r["valid"]) and r["type"] != "missing")
                _flag(df, _bad.astype(bool), "review_ic_malformed")
            if _on("review_ic_dob_mismatch") or _on("review_ic_age_contradiction"):
                _icdob = pd.to_datetime(
                    _icres.apply(lambda r: extract_ic_birthdate(r.get("cleaned"))), errors="coerce"
                )
                if _on("review_ic_dob_mismatch") and "Tarikh_Lahir" in df.columns:
                    _mm = _icdob.notna() & df["Tarikh_Lahir"].notna() & (
                        _icdob.dt.normalize() != df["Tarikh_Lahir"].dt.normalize()
                    )
                    _flag(df, _mm.fillna(False).astype(bool), "review_ic_dob_mismatch")
                if _on("review_ic_age_contradiction") and "Age_Months" in df.columns:
                    _mref = df["Tarikh_Ukur"] if "Tarikh_Ukur" in df.columns else None
                    if _mref is not None:
                        _ic_age_yrs = (_mref - _icdob).dt.days / 365.25
                    else:
                        _now = pd.Timestamp.now().normalize()
                        _ic_age_yrs = (_now - _icdob).dt.days / 365.25
                    _contra = (
                        _icdob.notna()
                        & (_ic_age_yrs >= 18)
                        & df["Age_Months"].notna()
                        & (df["Age_Months"] < age_cap)
                    )
                    _flag(df, _contra.fillna(False).astype(bool), "review_ic_age_contradiction")
    # review_mykid_invalid (Family 1, ncdc): MyKid uses the 12-digit format too.
    if source == "ncdc" and _on("review_mykid_invalid"):
        _mk = find_col(["mykid", "no. mykid", "no mykid"])
        if _mk:
            _mkres = df[_mk].apply(validate_ic)
            _mkbad = _mkres.apply(lambda r: (not r["valid"]) and r["type"] != "missing")
            _flag(df, _mkbad.astype(bool), "review_mykid_invalid")
    # review_dose_date_mismatch (Family 4, contoh-only): DOSE_DATE != measure date.
    if source == "myvass" and _on("review_dose_date_mismatch") and "Tarikh_Ukur" in df.columns:
        _dose = next((c for c in src_cols if c.lower().replace("-", "_") == "dose_date"), None)
        if _dose and _dose in df.columns:
            _dd = _parse_date(df[_dose])
            _flag(
                df,
                _dd.notna() & df["Tarikh_Ukur"].notna() & (_dd.dt.normalize() != df["Tarikh_Ukur"].dt.normalize()),
                "review_dose_date_mismatch",
            )
    # ── Phase C: Families 5-9 (source-integrity / geographic / socioeconomic) ──

    # Family 5 — AGE (source vs recomputed; recompute is canonical, source = flag)
    if "Age_Months" in df.columns:
        _src_age = _raw("age_months_computed", "age_months")
        if _src_age is not None and _on("review_age_source_mismatch"):
            _sa = pd.to_numeric(_src_age, errors="coerce")
            _ra = pd.to_numeric(df["Age_Months"], errors="coerce")
            _flag(df, _sa.notna() & _ra.notna() & ((_sa - _ra).abs() > 1.0),
                  "review_age_source_mismatch")
        _src_band = _raw("kategori_umur", "kumpulan_umur")
        if _src_band is not None and _on("review_age_band_mismatch"):
            def _band_from_months(m):
                if pd.isna(m):
                    return None
                return "u2" if m < 24 else ("u5" if m < age_cap else "o5")
            def _band_from_label(v):
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return None
                t = str(v).lower().replace("-", " ")
                if "bawah 2" in t or "0 2" in t or "bawah dua" in t:
                    return "u2"
                if "bawah 5" in t or "2 5" in t or "bawah lima" in t:
                    return "u5"
                if "5" in t and ("atas" in t or "ke atas" in t):
                    return "o5"
                return None
            # Internal-consistency check: does the source band label match the
            # source's OWN age figure? (audit measured 19/14 on source age, not
            # the recomputed canonical age — using the latter conflates label
            # errors with date-recompute drift.)
            _age_for_band = _raw("age_months_computed", "age_months")
            if _age_for_band is None:
                _age_for_band = df["Age_Months"]
            _exp = pd.to_numeric(_age_for_band, errors="coerce").apply(_band_from_months)
            _got = _src_band.apply(_band_from_label)
            _flag(df, (_exp.notna() & _got.notna() & (_exp != _got)).fillna(False).astype(bool),
                  "review_age_band_mismatch")
        # AGE_AT_VACCINATION (MyVASS contoh). Unit is ASSUMED completed years
        # (contoh values are 0-3, consistent with an under-5 cohort) — not
        # independently confirmed. [0,5] is the plausible band; revisit if a
        # source documents the unit as months or dose-count.
        _vacc = _raw("age_at_vaccination")
        if _vacc is not None and _on("review_age_vacc_range"):
            _v = pd.to_numeric(_vacc, errors="coerce")
            _flag(df, _v.notna() & ((_v < 0) | (_v > 5)), "review_age_vacc_range")

    # Family 6 — GEOGRAPHIC
    if _on("review_daerah_null"):
        _dcol = find_col(["daerah", "district"])
        if _dcol and _dcol in df.columns:
            _dv = df[_dcol].astype(str).str.strip()
            _flag(df, df[_dcol].isna() | _dv.isin(["", "nan", "none", "<NA>", "<na>"]),
                  "review_daerah_null")
    if source == "ncdc" and _on("review_bahagian_null"):
        _bcol = find_col(["bahagian", "division"])
        if _bcol and _bcol in df.columns:
            _bv = df[_bcol].astype(str).str.strip()
            _flag(df, df[_bcol].isna() | _bv.isin(["", "nan", "none", "<NA>", "<na>"]),
                  "review_bahagian_null")
    if _on("review_geo_out_of_bounds"):
        _lat = _raw("latitude", "lat")
        _lon = _raw("longitude", "lon", "long")
        if _lat is not None and _lon is not None:
            _la = pd.to_numeric(_lat, errors="coerce")
            _lo = pd.to_numeric(_lon, errors="coerce")
            # geo_bounds — GEO, doc §7. Malaysia's national lat/lon extent.
            _oob = (_la.notna() & ((_la < 1.0) | (_la > 7.5))) | \
                   (_lo.notna() & ((_lo < 99.5) | (_lo > 119.5)))
            _flag(df, _oob.fillna(False).astype(bool), "review_geo_out_of_bounds")

    # Family 7 — MEASUREMENTS (source-integrity; recompute owns the canonical value)
    if _on("review_height_unit_suspect"):
        _h = _raw("tinggi_cm", "tinggi", "height", "panjang", "length", "length_height_cm")
        if _h is not None:
            _hv = pd.to_numeric(_h, errors="coerce")
            # height_unit_suspect — DOM, doc §6. >200 cm for a child ⇒ likely cm/m error.
            _flag(df, _hv.notna() & (_hv > 200), "review_height_unit_suspect")
    if _on("review_ghost_bmi"):
        _b = _raw("bmi", "bmi_kg_m2")
        _w = _raw("berat_kg", "berat", "weight", "weight_kg")
        _h2 = _raw("tinggi_cm", "tinggi", "height", "length_height_cm")
        if _b is not None and (_w is not None or _h2 is not None):
            _bv = pd.to_numeric(_b, errors="coerce")
            _wn = pd.to_numeric(_w, errors="coerce") if _w is not None else None
            _hn = pd.to_numeric(_h2, errors="coerce") if _h2 is not None else None
            _wmiss = _wn.isna() if _wn is not None else True
            _hmiss = _hn.isna() if _hn is not None else True
            _flag(df, (_bv.notna() & (_wmiss | _hmiss)).fillna(False).astype(bool),
                  "review_ghost_bmi")
    if _on("review_dual_measure_mismatch"):
        _pairs = [("length_height_cm", "tinggi_cm"), ("weight_kg", "berat_kg"), ("bmi_kg_m2", "bmi")]
        _dual = pd.Series(False, index=df.index)
        _any_dual = False
        for _a_name, _b_name in _pairs:
            _ca, _cb = _raw(_a_name), _raw(_b_name)
            if _ca is not None and _cb is not None:
                _any_dual = True
                _na = pd.to_numeric(_ca, errors="coerce")
                _nb = pd.to_numeric(_cb, errors="coerce")
                _dual = _dual | (_na.notna() & _nb.notna() & ((_na - _nb).abs() > 0.01))
        if _any_dual:
            _flag(df, _dual.fillna(False).astype(bool), "review_dual_measure_mismatch")

    # Family 8 — Z-SCORES & CLASSIFICATIONS (all source-integrity flags)
    _zaxes = [("waz", "waz_class"), ("haz", "haz_class"), ("baz", "baz_class")]
    if _on("review_ghost_class"):
        _ghost = pd.Series(False, index=df.index)
        for _z, _cls in _zaxes:
            _zv, _cv = _raw(_z), _raw(_cls)
            if _zv is not None and _cv is not None:
                _zn = pd.to_numeric(_zv, errors="coerce")
                _cvalid = _cv.notna() & ~_cv.astype(str).str.strip().str.lower().isin(["", "nan", "none"])
                _ghost = _ghost | (_zn.isna() & _cvalid)
        _flag(df, _ghost.fillna(False).astype(bool), "review_ghost_class")
    if _on("review_zscore_biv"):
        _biv = pd.Series(False, index=df.index)
        for _z, _ in _zaxes:
            _zv = _raw(_z)
            if _zv is not None:
                _zn = pd.to_numeric(_zv, errors="coerce")
                _biv = _biv | (_zn.notna() & (_zn.abs() > 6))
        _flag(df, _biv.fillna(False).astype(bool), "review_zscore_biv")
    # review_class_range_mismatch is DEFERRED: it needs the source's exact
    # per-axis z-score->label cutoff system (WAZ/HAZ/BAZ "high" boundaries differ
    # and are unspecified). Guessing the cutoffs silently false-flags valid rows
    # (clinical-safety: never mis-flag a real record). Removed from
    # REVIEW_EVALUATED_RULES so it is not a ghost toggle; revisit once the
    # canonical cutoff table is confirmed.
    if _on("review_indicator_class_mismatch"):
        # Indicator (ind_*_zscore 0/1) must agree with the corresponding WHO
        # _class column. Missing class with a positive indicator counts as a
        # mismatch (the row asserts a condition the classification doesn't show).
        _ind_pairs = [
            ("ind_bantut_zscore", "haz_class", "stunted"),
            ("ind_obes_zscore", "baz_class", "obese"),
            ("ind_kurang_berat_zscore", "waz_class", "underweight"),
            ("ind_susut_zscore", "baz_class", "wasted"),
        ]
        _imm = pd.Series(False, index=df.index)
        for _flagc, _clsc, _kw in _ind_pairs:
            _fv, _cv = _raw(_flagc), _raw(_clsc)
            if _fv is not None and _cv is not None:
                _fb = pd.to_numeric(_fv, errors="coerce") == 1
                _pos = _cv.astype(str).str.lower().str.contains(_kw, na=False)
                _imm = _imm | (_fv.notna() & (_fb != _pos))
        _flag(df, _imm.fillna(False).astype(bool), "review_indicator_class_mismatch")

    # Family 9 — SOCIOECONOMIC
    _inc = find_col(["pendapatan", "income", "pendapatan_keluarga"])
    if _inc and _inc in df.columns:
        _iv = df[_inc].astype(str).str.strip()
        _imiss = df[_inc].isna() | _iv.isin(["", "nan", "none", "<NA>", "<na>"])
        if _on("review_pendapatan_null"):
            _flag(df, _imiss, "review_pendapatan_null")
        if _on("review_pendapatan_invalid"):
            _norm_inc = _iv.str.upper().str.replace(" ", "", regex=False)
            _flag(df, (~_imiss) & (~_norm_inc.isin(INCOME_VALID)) & (_norm_inc != "X"),
                  "review_pendapatan_invalid")

    # ── Phase D: Families 10-11 (categorical vocabularies) ────────────────────

    def _unknown_mask(col_series, valid_set):
        """True where a non-blank value is outside valid_set (case-insensitive)."""
        _s = col_series.astype(str).str.strip()
        _present = col_series.notna() & ~_s.str.lower().isin(["", "nan", "none", "<na>"])
        _known = _s.str.lower().isin(valid_set)
        return _present & ~_known

    # Family 10 — NCDC-SPECIFIC
    if source == "ncdc":
        if _on("review_vaccine_unknown"):
            _vc = find_col(["vaccine_name", "vaksin", "vaccine"])
            if _vc and _vc in df.columns:
                _flag(df, _unknown_mask(df[_vc], VACCINE_SET), "review_vaccine_unknown")
        if _on("review_agensi_unknown"):
            _ac = find_col(["agensi", "agency"])
            if _ac and _ac in df.columns:
                _flag(df, _unknown_mask(df[_ac], AGENSI_SET), "review_agensi_unknown")
        if _on("review_taska_blank"):
            _ac = find_col(["agensi", "agency"])
            _tc = find_col(["nama_taska", "taska", "nama taska"])
            if _ac and _tc and _ac in df.columns and _tc in df.columns:
                _av = df[_ac].astype(str).str.strip()
                _ap = df[_ac].notna() & ~_av.str.lower().isin(["", "nan", "none", "<na>"])
                _tv = df[_tc].astype(str).str.strip()
                _tblank = df[_tc].isna() | _tv.str.lower().isin(["", "nan", "none", "<na>"])
                _flag(df, _ap & _tblank, "review_taska_blank")

    # Family 11 — MyVASS-SPECIFIC
    if source == "myvass":
        if _on("review_ethnicity_unknown"):
            _ec = find_col(["ethnicity", "etnik", "kaum", "bangsa"])
            if _ec and _ec in df.columns:
                _flag(df, _unknown_mask(df[_ec], ETHNIC_VALID), "review_ethnicity_unknown")
        if _on("review_facility_unknown"):
            _fc = find_col(["kategori_fasiliti", "fasiliti", "facility", "kategori fasiliti"])
            if _fc and _fc in df.columns:
                _flag(df, _unknown_mask(df[_fc], FACILITY_SET), "review_facility_unknown")

    return


# ═══════════════════════════════════════════════════════════════════════════════
# MYVASS CLEANING
# ═══════════════════════════════════════════════════════════════════════════════

def clean_myvass(df: pd.DataFrame, enabled_rules=None, range_overrides: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Clean MyVASS data and compute WHO z-scores.

    Flag-then-filter: rows that fail quality rules are tagged with
    `analyzable=False` and `exclude_reason` instead of being physically
    dropped. The full frame is returned so callers can offer both a
    full-flagged download and an analysis-ready filtered view.

    Args:
        range_overrides: optional {registry_key: {min,max}|{value}} that
            overrides clinical_ranges defaults for this run only.

    Returns:
        tuple: (cleaned_dataframe, statistics_dict)
    """
    stats = {"raw_count": len(df), "data_type": "myvass"}
    df = df.copy()
    df["analyzable"] = True
    df["exclude_reason"] = ""
    df["review_reason"] = ""

    def _on(code: str) -> bool:
        return _rule_on(code, enabled_rules)

    # Normalize column names
    df.columns = df.columns.str.strip()

    # Find key columns (case- and separator-insensitive: already-processed
    # exports use underscores e.g. "Tarikh_Lahir" / "Tarikh_Pengukuran",
    # raw sources use spaces — both must match the same patterns).
    def find_col(patterns):
        def norm(s: str) -> str:
            return s.lower().replace("_", " ").replace("-", " ")
        for col in df.columns:
            nc = norm(col)
            for p in patterns:
                if norm(p) in nc:
                    return col
        return None

    _src_cols = list(df.columns)
    _src_raw = df.copy()  # pre-recompute snapshot for source-integrity flags (Fam 7-8)
    # Override-aware operational bounds (DOM-tier; default to module constants).
    _bmi_max = _cr_get_val("bmi_max", range_overrides)
    _age_cap = _cr_get_val("infant_age_cap", range_overrides)
    gender_col = find_col(["jantina", "gender", "sex"])
    dob_col = find_col(["tarikh lahir", "dob", "date_of_birth", "birth"])
    weight_col = find_col(["berat", "weight"])
    height_col = find_col(["panjang", "tinggi", "height", "length"])
    measure_date_col = find_col(["tarikh antropometri", "tarikh ukur", "tarikh pengukuran", "pengukuran", "measurement date", "dose_date"])
    state_col = find_col(["negeri", "state"])

    # Rule 1: Standardize and filter gender
    if gender_col:
        df["Gender"] = df[gender_col].astype(str).str.upper().str.strip().map(GENDER_MAP)
        if _on("dropped_invalid_gender"):
            _mask = df["Gender"].isna()
            stats["dropped_invalid_gender"] = int((_mask & df["analyzable"]).sum())
            _exclude(df, _mask, "dropped_invalid_gender")
        else:
            stats["dropped_invalid_gender"] = 0
    else:
        df["Gender"] = None
        stats["dropped_invalid_gender"] = 0

    # Parse dates
    if dob_col:
        df["Tarikh_Lahir"] = _parse_date(df[dob_col])
    else:
        df["Tarikh_Lahir"] = pd.NaT

    if measure_date_col:
        df["Tarikh_Ukur"] = _parse_date(df[measure_date_col])
    else:
        df["Tarikh_Ukur"] = pd.NaT

    # Rule 4: Flag where measurement < DOB
    _apply_dropped_date_before_dob(df, stats, _on, date_col="Tarikh_Ukur")

    # Compute age in days
    has_both_dates = df["Tarikh_Lahir"].notna() & df["Tarikh_Ukur"].notna()
    df["Age_Days"] = np.where(
        has_both_dates,
        (df["Tarikh_Ukur"] - df["Tarikh_Lahir"]).dt.days,
        np.nan
    )
    df["Age_Months"] = (df["Age_Days"] / 30.4375).round(2)

    # Rule 3: Flag age >= 60 months
    _apply_dropped_age_over5(df, stats, _on, age_cap=_age_cap)

    # Convert measurements to numeric
    if weight_col:
        df["Berat_kg"] = pd.to_numeric(df[weight_col], errors="coerce")
    else:
        df["Berat_kg"] = np.nan

    if height_col:
        df["Tinggi_cm"] = pd.to_numeric(df[height_col], errors="coerce")
    else:
        df["Tinggi_cm"] = np.nan

    # Rules 2/6/5: measurement outliers, no-measurement, BMI recompute + outlier
    # (infant cohort bounds). Shared battery; caller-owned order preserved.
    profile = make_infant_profile(range_overrides)
    _apply_measurement_outlier(df, stats, profile, _on)
    _apply_no_measurement(df, stats, _on)
    df = _compute_bmi(df, drop_raw=True)
    _apply_bmi_outlier(df, stats, _on, _bmi_max)

    # WHO z-scores + indicator flags + null-z-score exclusion (shared battery).
    _compute_zscores_indicators(df, stats)

    # Age category column
    _set_kategori_umur(df)

    # Final stats — final_count = analyzable rows, not len(df)
    _apply_review_flags(df, "myvass", _src_cols, find_col, enabled_rules, src_raw=_src_raw,
                        age_cap=_age_cap)
    stats["final_count"] = int(df["analyzable"].sum())
    stats["total_dropped"] = stats["raw_count"] - stats["final_count"]
    stats["review_count"] = int((df["review_reason"] != "").sum())

    # Gender breakdown over analyzable rows only
    if "Gender" in df.columns:
        gender_counts = df.loc[df["analyzable"], "Gender"].value_counts().to_dict()
        stats["gender_male"] = gender_counts.get("Male", 0)
        stats["gender_female"] = gender_counts.get("Female", 0)

    return df, stats


# ═══════════════════════════════════════════════════════════════════════════════
# NCDC CLEANING
# ═══════════════════════════════════════════════════════════════════════════════

def clean_ncdc(df: pd.DataFrame, enabled_rules=None, range_overrides: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Clean NCDC (TASKA) data and compute WHO z-scores.

    Flag-then-filter: rows that fail quality rules are tagged with
    `analyzable=False` and `exclude_reason` instead of being physically
    dropped.

    Args:
        range_overrides: optional {registry_key: {min,max}|{value}} for this run.

    Returns:
        tuple: (cleaned_dataframe, statistics_dict)
    """
    stats = {"raw_count": len(df), "data_type": "ncdc"}
    df = df.copy()
    df["analyzable"] = True
    df["exclude_reason"] = ""
    df["review_reason"] = ""

    def _on(code: str) -> bool:
        return _rule_on(code, enabled_rules)

    # Normalize column names
    df.columns = df.columns.str.strip()

    # Find key columns
    def find_col(patterns):
        def norm(s: str) -> str:
            return s.lower().replace("_", " ").replace("-", " ")
        for col in df.columns:
            nc = norm(col)
            for p in patterns:
                if norm(p) in nc:
                    return col
        return None

    gender_col = find_col(["jantina", "gender", "sex"])
    dob_col = find_col(["tarikh lahir", "dob", "birth"])
    state_col = find_col(["negeri", "state"])
    mykid_col = find_col(["mykid", "no. mykid", "ic"])
    income_col = find_col(["pendapatan", "income"])

    # Find year-specific columns
    years = []
    weight_cols = {}
    height_cols = {}
    date_cols = {}

    for col in df.columns:
        import re
        match = re.match(r"(\d{4})\s*(Berat|Tinggi|Tarikh)", col, re.IGNORECASE)
        if match:
            year = int(match.group(1))
            col_type = match.group(2).lower()
            if year not in years:
                years.append(year)
            if "berat" in col_type:
                weight_cols[year] = col
            elif "tinggi" in col_type:
                height_cols[year] = col
            elif "tarikh" in col_type:
                date_cols[year] = col

    # Reshape wide to long if year columns exist (then re-init flag columns on
    # the new long frame since row count changed)
    if years:
        all_records = []
        base_cols = [c for c in df.columns if not any(str(y) in c for y in years)]

        for _, row in df.iterrows():
            for year in years:
                w_col = weight_cols.get(year)
                h_col = height_cols.get(year)
                d_col = date_cols.get(year)

                weight = row.get(w_col) if w_col else None
                height = row.get(h_col) if h_col else None

                if pd.notna(weight) or pd.notna(height):
                    record = {c: row[c] for c in base_cols if c in row}
                    record["Year"] = year
                    record["Berat_kg"] = weight
                    record["Tinggi_cm"] = height
                    record["Tarikh_Pengukuran"] = row.get(d_col) if d_col else None
                    all_records.append(record)

        df = pd.DataFrame(all_records)
        df["analyzable"] = True
        df["exclude_reason"] = ""
        df["review_reason"] = ""
        stats["years_found"] = years
        stats["raw_count"] = len(df)
    else:
        df["Year"] = None
    _src_cols = list(df.columns)
    _src_raw = df.copy()  # pre-recompute snapshot for source-integrity flags (Fam 7-8)
    # Override-aware operational bounds (DOM-tier; default to module constants).
    _bmi_max = _cr_get_val("bmi_max", range_overrides)
    _age_cap = _cr_get_val("infant_age_cap", range_overrides)

    # Rule 1: Standardize and filter gender
    if gender_col:
        df["Gender"] = df[gender_col].astype(str).str.upper().str.strip().map(GENDER_MAP)
        if _on("dropped_invalid_gender"):
            _mask = df["Gender"].isna()
            stats["dropped_invalid_gender"] = int((_mask & df["analyzable"]).sum())
            _exclude(df, _mask, "dropped_invalid_gender")
        else:
            stats["dropped_invalid_gender"] = 0
    else:
        df["Gender"] = None
        stats["dropped_invalid_gender"] = 0

    # Rule 9: Exclude Pendapatan = 'X'
    if income_col:
        _apply_dropped_pendapatan_x(df, stats, _on, income_col=income_col)
    else:
        stats["dropped_pendapatan_x"] = 0

    # Parse dates
    if dob_col:
        df["Tarikh_Lahir"] = _parse_date(df[dob_col])
    else:
        df["Tarikh_Lahir"] = pd.NaT

    if "Tarikh_Pengukuran" in df.columns:
        df["Tarikh_Pengukuran"] = _parse_date(df["Tarikh_Pengukuran"])
    else:
        df["Tarikh_Pengukuran"] = pd.NaT

    # Flag null DOB
    _apply_dropped_null_dob(df, stats, _on)

    # Rule 4: Flag where measurement < DOB
    _apply_dropped_date_before_dob(df, stats, _on, date_col="Tarikh_Pengukuran")

    # Compute age
    has_both = df["Tarikh_Lahir"].notna() & df["Tarikh_Pengukuran"].notna()
    df["Age_Days"] = np.where(has_both, (df["Tarikh_Pengukuran"] - df["Tarikh_Lahir"]).dt.days, np.nan)
    df["Age_Months"] = (df["Age_Days"] / 30.4375).round(2)

    # Rule 3: Flag negative age or age >= 60 months
    age_invalid = (df["Age_Days"] < 0) | (df["Age_Months"] >= _age_cap)
    if _on("dropped_age_invalid"):
        _mask = age_invalid & df["Age_Months"].notna()
        stats["dropped_age_invalid"] = int((_mask & df["analyzable"]).sum())
        _exclude(df, _mask, "dropped_age_invalid")
    else:
        stats["dropped_age_invalid"] = 0

    # Convert measurements
    df["Berat_kg"] = pd.to_numeric(df.get("Berat_kg"), errors="coerce")
    df["Tinggi_cm"] = pd.to_numeric(df.get("Tinggi_cm"), errors="coerce")

    # Rules 2/6/5: measurement outliers, no-measurement, BMI recompute + outlier
    # (infant cohort bounds). Shared battery; caller-owned order preserved.
    profile = make_infant_profile(range_overrides)
    _apply_measurement_outlier(df, stats, profile, _on)
    _apply_no_measurement(df, stats, _on)
    df = _compute_bmi(df, drop_raw=True)
    _apply_bmi_outlier(df, stats, _on, _bmi_max)

    # Rule 8 + placeholder guard: duplicate MyKid handling.
    # Same MyKid with the SAME DOB = one child re-measured -> keep most recent,
    # drop the older record (dropped_duplicate_mykid). Same MyKid with DIFFERING
    # DOB = a shared placeholder across different children -> flag every row,
    # drop none (review_mykid_shared_placeholder). Prevents wrongly dropping
    # placeholder rows (e.g. 12/13 rows sharing one stand-in MyKid).
    if mykid_col and "Tarikh_Pengukuran" in df.columns:
        _apply_dropped_duplicate_mykid(df, stats, _on, enabled_rules, mykid_col=mykid_col)
    else:
        stats["dropped_duplicate_mykid"] = 0

    # WHO z-scores + indicator flags + null-z-score exclusion (shared battery).
    _compute_zscores_indicators(df, stats)

    # Age category column
    _set_kategori_umur(df)

    # Final stats — final_count = analyzable rows, not len(df)
    _apply_review_flags(df, "ncdc", _src_cols, find_col, enabled_rules, src_raw=_src_raw,
                        age_cap=_age_cap)
    stats["final_count"] = int(df["analyzable"].sum())
    stats["total_dropped"] = stats["raw_count"] - stats["final_count"]
    stats["review_count"] = int((df["review_reason"] != "").sum())

    if "Gender" in df.columns:
        gender_counts = df.loc[df["analyzable"], "Gender"].value_counts().to_dict()
        stats["gender_male"] = gender_counts.get("Male", 0)
        stats["gender_female"] = gender_counts.get("Female", 0)

    if "Year" in df.columns:
        stats["year_counts"] = df.loc[df["analyzable"], "Year"].value_counts().to_dict()

    return df, stats


# ═══════════════════════════════════════════════════════════════════════════════
# KPM CLEANING
# ═══════════════════════════════════════════════════════════════════════════════

def clean_kpm(df: pd.DataFrame, enabled_rules=None, range_overrides: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Clean KPM (school) data and calculate BMI categories.

    Flag-then-filter: rows that fail quality rules are tagged with
    `analyzable=False` and `exclude_reason` instead of being physically
    dropped.

    Note: KPM data is for 7-year-olds (school age), which is beyond WHO infant
    z-score tables, so we use BMI thresholds instead of z-scores.

    Returns:
        tuple: (cleaned_dataframe, statistics_dict)
    """
    stats = {"raw_count": len(df), "data_type": "kpm"}
    df = df.copy()
    df["analyzable"] = True
    df["exclude_reason"] = ""

    def _on(code: str) -> bool:
        return _rule_on(code, enabled_rules)

    # Normalize column names
    df.columns = df.columns.str.strip()

    # Find key columns
    def find_col(patterns):
        def norm(s: str) -> str:
            return s.lower().replace("_", " ").replace("-", " ")
        for col in df.columns:
            nc = norm(col)
            for p in patterns:
                if norm(p) in nc:
                    return col
        return None

    gender_col = find_col(["jantina", "gender", "sex"])
    dob_col = find_col(["tarikh lahir", "dob", "birth"])
    weight_col = find_col(["berat", "weight"])
    height_col = find_col(["tinggi", "height"])
    measure_date_col = find_col(["tarikh pengukuran", "tarikh ukur"])
    state_col = find_col(["negeri", "state"])
    school_col = find_col(["nama sekolah", "sekolah", "school"])
    student_id_col = find_col(["id_murid", "student_id", "id"])
    year_col = find_col(["thn_ting", "tahun", "year"])

    # Rule 3: Standardize gender (flag RAGU)
    if gender_col:
        df["Jantina_Raw"] = df[gender_col].astype(str).str.upper().str.strip()
        _apply_dropped_ragu_gender(df, stats, _on)

        df["Gender"] = df["Jantina_Raw"].map(GENDER_MAP)
        if _on("dropped_invalid_gender"):
            _mask = df["Gender"].isna()
            stats["dropped_invalid_gender"] = int((_mask & df["analyzable"]).sum())
            _exclude(df, _mask, "dropped_invalid_gender")
        else:
            stats["dropped_invalid_gender"] = 0
    else:
        df["Gender"] = None
        stats["dropped_ragu_gender"] = 0
        stats["dropped_invalid_gender"] = 0

    # Rule 2: Flag duplicate ID_MURID (keep first; flag later duplicates)
    if student_id_col and _on("dropped_duplicate_id"):
        dup_mask = df.duplicated(subset=[student_id_col], keep="first")
        stats["dropped_duplicate_id"] = int((dup_mask & df["analyzable"]).sum())
        _exclude(df, dup_mask, "dropped_duplicate_id")
    else:
        stats["dropped_duplicate_id"] = 0

    # Parse dates
    if dob_col:
        df["Tarikh_Lahir"] = _parse_date(df[dob_col])
    else:
        df["Tarikh_Lahir"] = pd.NaT

    if measure_date_col:
        df["Tarikh_Pengukuran"] = _parse_date(df[measure_date_col])
    else:
        df["Tarikh_Pengukuran"] = pd.NaT

    # Rule 5: Flag invalid dates (future or before DOB)
    today = pd.Timestamp.now()
    invalid_date = (
        (df["Tarikh_Pengukuran"] > today) |
        (df["Tarikh_Pengukuran"] < df["Tarikh_Lahir"])
    )
    if _on("dropped_invalid_date"):
        _mask = invalid_date & df["Tarikh_Pengukuran"].notna()
        stats["dropped_invalid_date"] = int((_mask & df["analyzable"]).sum())
        _exclude(df, _mask, "dropped_invalid_date")
    else:
        stats["dropped_invalid_date"] = 0

    # Calculate age
    has_both = df["Tarikh_Lahir"].notna() & df["Tarikh_Pengukuran"].notna()
    df["Age_Days"] = np.where(has_both, (df["Tarikh_Pengukuran"] - df["Tarikh_Lahir"]).dt.days, np.nan)
    df["Age_Years"] = (df["Age_Days"] / 365.25).round(1)

    # Rule 4: Flag age outside 5–10 years for school cohort
    age_invalid = df["Age_Years"].notna() & ((df["Age_Years"] < 5) | (df["Age_Years"] > 10))
    if _on("dropped_age_invalid"):
        stats["dropped_age_invalid"] = int((age_invalid & df["analyzable"]).sum())
        _exclude(df, age_invalid, "dropped_age_invalid")
    else:
        stats["dropped_age_invalid"] = 0

    # Convert measurements
    if weight_col:
        df["Berat_kg"] = pd.to_numeric(df[weight_col], errors="coerce")
    else:
        df["Berat_kg"] = np.nan

    if height_col:
        df["Tinggi_cm"] = pd.to_numeric(df[height_col], errors="coerce")
    else:
        df["Tinggi_cm"] = np.nan

    # Rule 6 & 7: Flag measurement outliers (school-age cohort bounds)
    profile = make_school_profile(range_overrides)
    _apply_measurement_outlier(df, stats, profile, _on)

    # Calculate BMI (KPM source carries no raw BMI column to discard)
    df = _compute_bmi(df, drop_raw=False)

    # Rule 9: BMI Categories
    df["BMI_Category"] = df["BMI"].apply(_classify_bmi_school)
    df["BMI_Category_EN"] = df["BMI_Category"].map({
        "Kurus": "Underweight",
        "Normal": "Normal",
        "Berlebihan Berat Badan": "Overweight",
        "Obes": "Obese"
    })

    # Indicator flags
    df["Ind_Kurus"] = df["BMI_Category"] == "Kurus"
    df["Ind_Normal"] = df["BMI_Category"] == "Normal"
    df["Ind_Berlebihan"] = df["BMI_Category"] == "Berlebihan Berat Badan"
    df["Ind_Obes"] = df["BMI_Category"] == "Obes"

    # Flag rows with no computable BMI (locked — required for BMI categories)
    no_bmi = df["BMI"].isna()
    stats["dropped_no_bmi"] = int((no_bmi & df["analyzable"]).sum())
    _exclude(df, no_bmi, "dropped_no_bmi")

    # Final stats — final_count = analyzable rows, not len(df)
    stats["final_count"] = int(df["analyzable"].sum())
    stats["total_dropped"] = stats["raw_count"] - stats["final_count"]

    _a = df["analyzable"]
    stats["ind_kurus"] = int(df.loc[_a, "Ind_Kurus"].sum())
    stats["ind_normal"] = int(df.loc[_a, "Ind_Normal"].sum())
    stats["ind_berlebihan"] = int(df.loc[_a, "Ind_Berlebihan"].sum())
    stats["ind_obes"] = int(df.loc[_a, "Ind_Obes"].sum())

    if "Gender" in df.columns:
        gender_counts = df.loc[_a, "Gender"].value_counts().to_dict()
        stats["gender_male"] = gender_counts.get("Male", 0)
        stats["gender_female"] = gender_counts.get("Female", 0)

    return df, stats


# ═══════════════════════════════════════════════════════════════════════════════
# GENERIC CLEANING (unknown / near-known schemas)
# ═══════════════════════════════════════════════════════════════════════════════

def clean_general(df: pd.DataFrame, enabled_rules=None, range_overrides: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Conservative cleaner for general / "almost-the-same-as-known" schemas.

    Assumes column mapping has already renamed columns toward the canonical
    schema. Unlike the source-specific cleaners it is *honest, not silent*:

    - It NEVER drops every row when a field is absent. Missing inputs leave
      the affected indicator UNCOMPUTED (a reported gap) rather than wiping
      the dataset to 0 rows / 0% (the documented drop-all failure).
    - Implausible measurements are nulled, not row-dropped.
    - An indicator column is only created when its required inputs exist for
      the dataset; otherwise it is listed in stats["indicators_unavailable"]
      with a reason — never fabricated as a 0% number.
    - stats carries a coverage report so the gap is visible to the user.
    """
    stats: dict = {"raw_count": len(df), "data_type": "general"}
    df = df.copy()
    df["analyzable"] = True
    df["exclude_reason"] = ""
    df["review_reason"] = ""

    def _on(code: str) -> bool:
        return _rule_on(code, enabled_rules)

    def _optin(code: str) -> bool:
        # Portable rules absent from general's baseline (EVALUATED_RULES["general"])
        # fire only when EXPLICITLY enabled — never on the legacy all-on None path.
        # Guards the documented drop-all failure (e.g. dropped_age_over5 with the
        # infant 5y cap would otherwise exclude every school-age row by default).
        return enabled_rules is not None and code in enabled_rules
    df.columns = df.columns.str.strip()

    def _norm(s: str) -> str:
        return s.lower().replace("_", " ").replace("-", " ")

    def find_col(patterns):
        for col in df.columns:
            nc = _norm(col)
            for p in patterns:
                if _norm(p) in nc:
                    return col
        return None

    _src_cols = list(df.columns)
    _src_raw = df.copy()  # pre-recompute snapshot for review-flag source-integrity checks
    # Override-aware operational bounds (DOM-tier; default to module constants).
    # Locals are independent of cohort_profile, so the None-profile path stays safe.
    _bmi_max = _cr_get_val("bmi_max", range_overrides)
    _age_cap = _cr_get_val("infant_age_cap", range_overrides)

    gender_col = find_col(["jantina", "gender", "sex"])
    dob_col = find_col(["tarikh lahir", "dob", "date of birth", "birth"])
    measure_date_col = find_col(
        ["tarikh ukur", "tarikh antropometri", "tarikh pengukuran",
         "measurement date", "assessment date", "tarikh assessment"]
    )
    weight_col = find_col(["berat kg", "berat", "weight"])
    height_col = find_col(["tinggi cm", "tinggi", "panjang", "height", "length"])
    age_col = find_col(["age months", "umur bulan", "age", "umur"])
    income_col = find_col(["pendapatan", "income"])
    mykid_col = find_col(["mykid"])

    has_age = bool(dob_col and measure_date_col) or bool(age_col)
    coverage = {
        "jantina": bool(gender_col),
        "tarikh_lahir": bool(dob_col),
        "tarikh_ukur": bool(measure_date_col),
        "berat_kg": bool(weight_col),
        "tinggi_cm": bool(height_col),
        "age": has_age,
    }
    assumptions: list[str] = []

    # Gender (Class A universal): flag rows whose sex is present but unmappable.
    # Never flag on a MISSING column — that is an honest gap, not bad data.
    if gender_col:
        df["Jantina_Raw"] = df[gender_col].astype(str).str.upper().str.strip()
        _apply_dropped_ragu_gender(df, stats, _optin)
        df["Gender"] = df["Jantina_Raw"].map(GENDER_MAP)
        if _on("dropped_invalid_gender"):
            _gmask = df["Gender"].isna()
            stats["dropped_invalid_gender"] = int((_gmask & df["analyzable"]).sum())
            _exclude(df, _gmask, "dropped_invalid_gender")
        else:
            stats["dropped_invalid_gender"] = 0
    else:
        df["Gender"] = None
        stats["dropped_ragu_gender"] = 0
        stats["dropped_invalid_gender"] = 0

    if income_col:
        _apply_dropped_pendapatan_x(df, stats, _optin, income_col=income_col)
    else:
        stats["dropped_pendapatan_x"] = 0

    df["Tarikh_Lahir"] = _parse_date(df[dob_col]) if dob_col else pd.NaT
    if dob_col:
        _apply_dropped_null_dob(df, stats, _optin)
    else:
        stats["dropped_null_dob"] = 0

    df["Tarikh_Ukur"] = _parse_date(df[measure_date_col]) if measure_date_col else pd.NaT

    if mykid_col and dob_col and measure_date_col:
        _apply_dropped_duplicate_mykid(
            df, stats, _optin, enabled_rules,
            mykid_col=mykid_col, sort_date_col="Tarikh_Ukur",
        )
    else:
        stats["dropped_duplicate_mykid"] = 0

    both_dates = df["Tarikh_Lahir"].notna() & df["Tarikh_Ukur"].notna()
    age_days = pd.Series(np.nan, index=df.index, dtype="float64")
    if both_dates.any():
        age_days = age_days.mask(
            both_dates, (df["Tarikh_Ukur"] - df["Tarikh_Lahir"]).dt.days
        )
    elif age_col:
        vals = pd.to_numeric(df[age_col], errors="coerce")
        med = vals.dropna().median() if vals.notna().any() else None
        if med is not None and med <= 18:
            age_days = vals * 365.25
            assumptions.append(f"age column '{age_col}' interpreted as YEARS")
        else:
            age_days = vals * 30.4375
            assumptions.append(f"age column '{age_col}' interpreted as MONTHS")
    df["Age_Days"] = age_days
    df["Age_Months"] = (df["Age_Days"] / 30.4375).round(2)

    _apply_dropped_age_over5(df, stats, _optin, age_cap=_age_cap)

    # Only genuine logical garbage is flagged, and only when both dates exist.
    _apply_dropped_date_before_dob(df, stats, _on, date_col="Tarikh_Ukur")

    df["Berat_kg"] = pd.to_numeric(df[weight_col], errors="coerce") if weight_col else np.nan
    df["Tinggi_cm"] = pd.to_numeric(df[height_col], errors="coerce") if height_col else np.nan

    # Cohort detection (statistical, never LLM): choose plausibility bounds from
    # the data's own age distribution so school-age datasets are not mis-nulled
    # against infant bounds. median age < 5y -> infant; >= 5y -> school; no
    # determinable age -> unknown (skip the cohort-dependent bounds rather than
    # guess and reintroduce the infant-bounds mis-flagging bug).
    _valid_age = df["Age_Months"].dropna()
    if len(_valid_age) == 0:
        cohort = "unknown"
        cohort_profile = None
    elif _valid_age.median() < _age_cap:
        cohort = "infant"
        cohort_profile = make_infant_profile(range_overrides)
    else:
        cohort = "school"
        cohort_profile = make_school_profile(range_overrides)

    # Implausible weight/height (Class B, cohort-dependent): flag the row out
    # against the detected cohort's bounds — non-destructive, like the named
    # cleaners (recoverable in the full download). Only fires on values that are
    # PRESENT but out of range; a missing measurement is never flagged here.
    # When the cohort is indeterminate this rule is skipped (values retained,
    # gap recorded) so general stays honest rather than guessing.
    if cohort_profile is not None:
        _apply_measurement_outlier(df, stats, cohort_profile, _on)
    else:
        stats["dropped_measurement_outlier"] = 0
        if weight_col or height_col:
            assumptions.append(
                "cohort indeterminate (no usable age) — measurement plausibility "
                "bounds skipped; implausible values retained"
            )

    # BMI recompute (no raw-BMI column expected) + implausible-BMI exclusion
    # (Class A universal): a BMI > BMI_MAX with present measurements is garbage,
    # so flag the row out like the named cleaners instead of nulling the value.
    df = _compute_bmi(df, drop_raw=False)
    _apply_bmi_outlier(df, stats, _on, _bmi_max)

    # Gate indicator computation on its required inputs (dataset-level). WHO
    # z-scores are infant (0-5y) references, so they only apply to the infant
    # cohort; school-age indicators come from BMI categories (Phase 4) and are
    # honestly reported as unavailable until then rather than computed wrong.
    base_ok = (
        ZSCORE_AVAILABLE and coverage["jantina"] and coverage["age"]
        and cohort == "infant"
    )
    can_waz = base_ok and coverage["berat_kg"]
    can_haz = base_ok and coverage["tinggi_cm"]
    can_baz = base_ok and coverage["berat_kg"] and coverage["tinggi_cm"]

    unavailable: dict[str, str] = {}

    def _gap(name: str):
        if not ZSCORE_AVAILABLE:
            unavailable[name] = "WHO z-score tables unavailable"
        elif not coverage["jantina"]:
            unavailable[name] = "missing/ambiguous field: jantina (sex)"
        elif not coverage["age"]:
            unavailable[name] = "missing/ambiguous field: age (tarikh_lahir/tarikh_ukur)"
        elif cohort != "infant":
            unavailable[name] = f"{cohort}-age cohort: WHO infant z-scores not applicable"
        else:
            unavailable[name] = "missing/ambiguous measurement input"

    if base_ok:
        df["WAZ"] = np.nan
        df["HAZ"] = np.nan
        df["BAZ"] = np.nan
        for idx in df.index:
            # Skip rows already flagged out — z-scores on junk are meaningless.
            if not df.loc[idx, "analyzable"]:
                continue
            ad = df.loc[idx, "Age_Days"]
            sx = df.loc[idx, "Gender"]
            if pd.isna(ad) or pd.isna(sx):
                continue
            w = df.loc[idx, "Berat_kg"]
            h = df.loc[idx, "Tinggi_cm"]
            b = df.loc[idx, "BMI"]
            if can_waz and pd.notna(w):
                z = compute_zscore(w, sx, ad, "WAZ")
                if z is not None and BIV["WAZ"][0] <= z <= BIV["WAZ"][1]:
                    df.loc[idx, "WAZ"] = round(z, 2)
            if can_haz and pd.notna(h):
                z = compute_zscore(h, sx, ad, "HAZ")
                if z is not None and BIV["HAZ"][0] <= z <= BIV["HAZ"][1]:
                    df.loc[idx, "HAZ"] = round(z, 2)
            if can_baz and pd.notna(b):
                z = compute_zscore(b, sx, ad, "BAZ")
                if z is not None and BIV["BAZ"][0] <= z <= BIV["BAZ"][1]:
                    df.loc[idx, "BAZ"] = round(z, 2)

    if can_waz:
        df["Ind_Kurang_Berat_Badan"] = df["WAZ"].apply(lambda z: z < -2 if pd.notna(z) else False)
    else:
        _gap("underweight")
    if can_haz:
        df["Ind_Bantut"] = df["HAZ"].apply(lambda z: z < -2 if pd.notna(z) else False)
    else:
        _gap("stunting")
    if can_baz:
        df["Ind_Susut"] = df["BAZ"].apply(lambda z: z < -2 if pd.notna(z) else False)
        df["Ind_Berlebihan_BB"] = df["BAZ"].apply(lambda z: z > 1 if pd.notna(z) else False)
        df["Ind_Obes"] = df["BAZ"].apply(lambda z: z > 2 if pd.notna(z) else False)
    else:
        _gap("wasting")
        _gap("overweight")

    # School-age cohort: BMI categories (KPM-style) replace WHO infant z-scores.
    # Emit the same Ind_* / BMI_Category columns clean_kpm produces so analytics
    # treat general school-age data identically. Requires both measurements.
    if cohort == "school" and coverage["berat_kg"] and coverage["tinggi_cm"]:
        df["BMI_Category"] = df["BMI"].apply(_classify_bmi_school)
        df["BMI_Category_EN"] = df["BMI_Category"].map({
            "Kurus": "Underweight",
            "Normal": "Normal",
            "Berlebihan Berat Badan": "Overweight",
            "Obes": "Obese",
        })
        df["Ind_Kurus"] = df["BMI_Category"] == "Kurus"
        df["Ind_Normal"] = df["BMI_Category"] == "Normal"
        df["Ind_Berlebihan"] = df["BMI_Category"] == "Berlebihan Berat Badan"
        df["Ind_Obes"] = df["BMI_Category"] == "Obes"
        # BMI categories cover under-/over-weight for this cohort; the
        # weight/height-for-age z-score indicators stay unavailable.
        for _n in ("underweight", "overweight"):
            unavailable.pop(_n, None)
        for _n in ("stunting", "wasting"):
            unavailable[_n] = (
                "school-age cohort: weight/height-for-age z-scores not "
                "applicable (BMI categories used instead)"
            )

    indicators_available = sorted(
        n for n in ("underweight", "stunting", "wasting", "overweight")
        if n not in unavailable
    )

    _apply_review_flags(df, "general", _src_cols, find_col, enabled_rules, src_raw=_src_raw,
                        age_cap=_age_cap)
    stats["final_count"] = int(df["analyzable"].sum())
    stats["total_dropped"] = stats["raw_count"] - stats["final_count"]
    stats["review_count"] = int((df["review_reason"] != "").sum())
    stats["cohort"] = cohort
    stats["coverage"] = coverage
    stats["assumptions"] = assumptions
    stats["indicators_available"] = indicators_available
    stats["indicators_unavailable"] = unavailable
    return df, stats


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CLEANING DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

def clean_data(
    df: pd.DataFrame,
    data_type: str,
    enabled_rules=None,
    range_overrides: dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Clean data based on data type.

    Args:
        df: Raw DataFrame
        data_type: 'kpm', 'myvass', 'ncdc', or 'general' (any unsupported schema)
            which routes to the conservative general cleaner. Legacy values
            'unknown' and 'generic' are normalised to 'general'.
        enabled_rules: optional set/collection of rule codes the user kept on
            (B3). None ⇒ every rule runs (legacy behaviour). Locked rules in
            RULE_REGISTRY always run regardless.
        range_overrides: optional dict of {registry_key: {min, max} or {value}}
            that overrides clinical_ranges defaults for THIS run only. Merged on
            top of any global settings. None ⇒ registry defaults apply.

    Returns:
        tuple: (cleaned_dataframe, statistics_dict)
    """
    from backend.config import normalize_schema_type
    data_type = normalize_schema_type(data_type)
    if data_type == "kpm":
        return clean_kpm(df, enabled_rules, range_overrides)
    elif data_type == "myvass":
        return clean_myvass(df, enabled_rules, range_overrides)
    elif data_type == "ncdc":
        return clean_ncdc(df, enabled_rules, range_overrides)
    # general / any unsupported schema → conservative general cleaner (never
    # ValueError, never silently mis-routed to clean_myvass).
    return clean_general(df, enabled_rules, range_overrides)


# ── Evaluated-rule registry ──────────────────────────────────────────────────
# Every rule code a cleaner can fire, including checks that may produce a
# count of zero (passed). Used by /clean/run to build `rules_evaluated` so
# the Quality Report "Rules Applied" card shows the full check set, not just
# the ones that found problems.
EVALUATED_RULES: dict[str, list[str]] = {
    "myvass": [
        "dropped_invalid_gender",
        "dropped_date_before_dob",
        "dropped_age_over5",
        "dropped_measurement_outlier",
        "dropped_no_measurement",
        "dropped_bmi_outlier",
        "dropped_null_zscore",
    ],
    "ncdc": [
        "dropped_invalid_gender",
        "dropped_pendapatan_x",
        "dropped_null_dob",
        "dropped_date_before_dob",
        "dropped_age_invalid",
        "dropped_measurement_outlier",
        "dropped_no_measurement",
        "dropped_bmi_outlier",
        "dropped_duplicate_mykid",
        "dropped_null_zscore",
    ],
    "kpm": [
        "dropped_ragu_gender",
        "dropped_invalid_gender",
        "dropped_duplicate_id",
        "dropped_invalid_date",
        "dropped_age_invalid",
        "dropped_measurement_outlier",
        "dropped_no_bmi",
    ],
    "general": [
        "dropped_invalid_gender",
        "dropped_date_before_dob",
        "dropped_measurement_outlier",
        "dropped_bmi_outlier",
    ],
}


# ── Rule registry (B3) ────────────────────────────────────────────────────────
# Single source of truth for the interactive cleaning-rule toggles. Keyed by the
# same stat codes as EVALUATED_RULES so the pipeline, the Settings tab and the
# /clean/run rules_evaluated all speak ONE vocabulary (replaces the inert
# rules.all set that the cleaners never read). `locked` marks structural gates
# that must always run — disabling them would corrupt indicators/KPIs.
RULE_REGISTRY: dict[str, dict] = {
    "dropped_invalid_gender": {
        "en": "Drop invalid gender", "bm": "Buang jantina tidak sah",
        "desc_en": "Remove rows whose gender is not L/P (Male/Female).",
        "desc_bm": "Buang baris yang jantinanya bukan L/P (Lelaki/Perempuan).",
        "locked": False,
    },
    "dropped_ragu_gender": {
        "en": "Drop ambiguous gender (RAGU)", "bm": "Buang jantina meragukan (RAGU)",
        "desc_en": "Remove rows with RAGU / uncertain gender before mapping.",
        "desc_bm": "Buang baris dengan jantina RAGU / tidak pasti sebelum pemetaan.",
        "locked": False,
    },
    "dropped_pendapatan_x": {
        "en": "Drop income = X", "bm": "Buang pendapatan = X",
        "desc_en": "Remove rows where household income is recorded as 'X'.",
        "desc_bm": "Buang baris yang pendapatan isi rumahnya direkod sebagai 'X'.",
        "locked": False,
    },
    "dropped_null_dob": {
        "en": "Drop missing birth date", "bm": "Buang tarikh lahir hilang",
        "desc_en": "Remove rows with no date of birth (age cannot be derived).",
        "desc_bm": "Buang baris tanpa tarikh lahir (umur tidak boleh dikira).",
        "locked": False,
    },
    "dropped_date_before_dob": {
        "en": "Drop measurement before birth", "bm": "Buang ukuran sebelum lahir",
        "desc_en": "Remove rows where the measurement date precedes the birth date.",
        "desc_bm": "Buang baris yang tarikh pengukurannya sebelum tarikh lahir.",
        "locked": False,
    },
    "dropped_invalid_date": {
        "en": "Drop invalid dates", "bm": "Buang tarikh tidak sah",
        "desc_en": "Remove rows with a future measurement date or a date before birth.",
        "desc_bm": "Buang baris dengan tarikh pengukuran akan datang atau sebelum lahir.",
        "locked": False,
    },
    "dropped_age_over5": {
        "en": "Drop age ≥ 5 years", "bm": "Buang umur ≥ 5 tahun",
        "desc_en": "Remove rows aged 60 months or older (under-5 cohort only).",
        "desc_bm": "Buang baris berumur 60 bulan ke atas (kohort bawah 5 tahun sahaja).",
        "locked": False,
    },
    "dropped_age_invalid": {
        "en": "Drop out-of-range age", "bm": "Buang umur luar julat",
        "desc_en": "Remove rows with a negative age (measurement date before birth date), or age outside the expected range — for under-5 data: above 60 months; for school-age data: outside 5–10 years.",
        "desc_bm": "Buang baris dengan umur negatif (tarikh pengukuran sebelum tarikh lahir), atau umur di luar julat — data bawah-5: melebihi 60 bulan; data usia sekolah: di luar 5–10 tahun.",
        "locked": False,
    },
    "dropped_measurement_outlier": {
        "en": "Drop measurement outliers", "bm": "Buang pencilan pengukuran",
        "desc_en": "Remove records where weight or height is outside the biologically plausible range. Under-5 cohort: weight 0.5–35 kg, height 30–130 cm. School-age cohort: weight 12–50 kg, height 100–160 cm.",
        "desc_bm": "Buang rekod yang berat atau tingginya berada di luar julat biologi yang munasabah. Kohort bawah-5: berat 0.5–35 kg, tinggi 30–130 cm. Kohort usia sekolah: berat 12–50 kg, tinggi 100–160 cm.",
        "locked": False,
    },
    "dropped_no_measurement": {
        "en": "Drop rows with no measurement", "bm": "Buang baris tanpa pengukuran",
        "desc_en": "Remove rows missing both weight and height.",
        "desc_bm": "Buang baris yang kekurangan kedua-dua berat dan tinggi.",
        "locked": False,
    },
    "dropped_bmi_outlier": {
        "en": "Drop BMI outliers", "bm": "Buang pencilan BMI",
        "desc_en": "Remove rows with BMI above the plausible maximum (40).",
        "desc_bm": "Buang baris dengan BMI melebihi maksimum munasabah (40).",
        "locked": False,
    },
    "dropped_duplicate_mykid": {
        "en": "Drop duplicate MyKid", "bm": "Buang MyKid berganda",
        "desc_en": "Keep only the most recent record per MyKid number.",
        "desc_bm": "Simpan hanya rekod terkini bagi setiap nombor MyKid.",
        "locked": False,
    },
    "dropped_duplicate_id": {
        "en": "Drop duplicate student ID", "bm": "Buang ID murid berganda",
        "desc_en": "Keep only the first record per student ID.",
        "desc_bm": "Simpan hanya rekod pertama bagi setiap ID murid.",
        "locked": False,
    },
    "dropped_no_bmi": {
        "en": "Require valid BMI", "bm": "Perlukan BMI sah",
        "desc_en": "Remove rows without a computable BMI — needed for BMI categories.",
        "desc_bm": "Buang baris tanpa BMI boleh kira — diperlukan untuk kategori BMI.",
        "locked": True,
    },
    "dropped_null_zscore": {
        "en": "Require valid z-scores", "bm": "Perlukan z-skor sah",
        "desc_en": "Remove rows without valid WHO z-scores — needed for indicators/KPIs.",
        "desc_bm": "Buang baris tanpa z-skor WHO sah — diperlukan untuk penunjuk/KPI.",
        "locked": True,
    },
}

# Codes that always run regardless of the user's selection (structural gates).
LOCKED_RULES: frozenset[str] = frozenset(
    c for c, m in RULE_REGISTRY.items() if m.get("locked")
)


# ── Schema-specific portable drop-rule registry (Phase 5C) ────────────────────
# Keyed by rule code.  fn/trigger_fn reference the extracted helpers above.
# trigger_fn expects a PREPARED frame (Tarikh_Lahir, Tarikh_Ukur, Age_Months,
# Jantina_Raw already derived).  Bilingual labels live in RULE_REGISTRY[code].
DROP_RULE_REGISTRY: dict[str, dict] = {
    "dropped_date_before_dob": {
        "fn": _apply_dropped_date_before_dob,
        "trigger_fn": _trigger_date_before_dob,
        "applicable_schemas": ["myvass", "ncdc"],
    },
    "dropped_age_over5": {
        "fn": _apply_dropped_age_over5,
        "trigger_fn": _trigger_age_over5,
        "applicable_schemas": ["myvass"],
    },
    "dropped_pendapatan_x": {
        "fn": _apply_dropped_pendapatan_x,
        "trigger_fn": _trigger_pendapatan_x,
        "applicable_schemas": ["ncdc"],
    },
    "dropped_null_dob": {
        "fn": _apply_dropped_null_dob,
        "trigger_fn": _trigger_null_dob,
        "applicable_schemas": ["ncdc"],
    },
    "dropped_duplicate_mykid": {
        "fn": _apply_dropped_duplicate_mykid,
        "trigger_fn": _trigger_duplicate_mykid,
        "applicable_schemas": ["ncdc"],
    },
    "dropped_ragu_gender": {
        "fn": _apply_dropped_ragu_gender,
        "trigger_fn": _trigger_ragu_gender,
        "applicable_schemas": ["kpm"],
    },
}


def _prep_frame_for_triggers(df: pd.DataFrame) -> pd.DataFrame:
    """Minimal preparation of a raw frame for DROP_RULE_REGISTRY trigger_fns.

    Derives the canonical columns trigger predicates expect (Tarikh_Lahir,
    Tarikh_Ukur, Age_Months) using the same fuzzy column-finding logic as
    clean_general.  Non-destructive — operates on a copy; source columns intact."""
    df = df.copy()
    df.columns = df.columns.str.strip()

    def _norm(s: str) -> str:
        return s.lower().replace("_", " ").replace("-", " ")

    def find_col(patterns):
        for col in df.columns:
            nc = _norm(col)
            for p in patterns:
                if _norm(p) in nc:
                    return col
        return None

    dob_col = find_col(["tarikh lahir", "dob", "date of birth", "birth"])
    measure_date_col = find_col(
        ["tarikh ukur", "tarikh antropometri", "tarikh pengukuran",
         "measurement date", "assessment date", "tarikh assessment"]
    )
    age_col = find_col(["age months", "umur bulan", "age", "umur"])

    # Only add canonical columns when the source column exists.
    # Absence of a column (not in df) is the sentinel that trigger_fns use to
    # return all-False; forcing NaT on every row causes false positives.
    if dob_col:
        df["Tarikh_Lahir"] = _parse_date(df[dob_col])
    if measure_date_col:
        df["Tarikh_Ukur"] = _parse_date(df[measure_date_col])

    age_days = pd.Series(np.nan, index=df.index, dtype="float64")
    if "Tarikh_Lahir" in df.columns and "Tarikh_Ukur" in df.columns:
        both_dates = df["Tarikh_Lahir"].notna() & df["Tarikh_Ukur"].notna()
        if both_dates.any():
            age_days = age_days.mask(
                both_dates, (df["Tarikh_Ukur"] - df["Tarikh_Lahir"]).dt.days
            )
    elif age_col:
        vals = pd.to_numeric(df[age_col], errors="coerce")
        med = vals.dropna().median() if vals.notna().any() else None
        if med is not None:
            age_days = vals * (365.25 if med <= 18 else 30.4375)
    if age_days.notna().any():
        df["Age_Months"] = (age_days / 30.4375).round(2)
    return df


def recommend_drop_rules(df: pd.DataFrame) -> list[dict]:
    """Run every DROP_RULE_REGISTRY trigger_fn against a raw general frame.

    Returns a rule card for each rule that would flag at least one row.
    Cards carry kind='rule', code, count, applicable_schemas, bilingual labels."""
    prepared = _prep_frame_for_triggers(df)
    cards: list[dict] = []
    for code, entry in DROP_RULE_REGISTRY.items():
        try:
            mask = entry["trigger_fn"](prepared)
        except Exception:
            continue
        count = int(mask.sum())
        if count == 0:
            continue
        meta = RULE_REGISTRY.get(code, {})
        cards.append({
            "kind": "rule",
            "code": code,
            "count": count,
            "applicable_schemas": entry["applicable_schemas"],
            "en": meta.get("en", code),
            "bm": meta.get("bm", code),
            "rationale_en": meta.get("desc_en", ""),
            "rationale_bm": meta.get("desc_bm", ""),
        })
    return cards


def rules_for_source(data_type: str) -> list[dict]:
    """Registry view for one source type, in cleaner-execution order. Used by the
    Settings tab and the pipeline rule panel so both list the SAME real rules."""
    codes = EVALUATED_RULES.get(data_type, EVALUATED_RULES["general"])
    return [{"code": c, **RULE_REGISTRY[c]} for c in codes if c in RULE_REGISTRY]


REVIEW_RULE_REGISTRY: dict[str, dict] = {
    "review_ic_malformed": {
        "en": "Malformed IC", "bm": "IC tidak sah format",
        "desc_en": "IC number isn't a valid 12-digit NRIC (too short, contains letters, or malformed).",
        "desc_bm": "Nombor IC bukan NRIC 12 digit yang sah (terlalu pendek, mengandungi huruf, atau tidak sah format).",
    },
    "review_ic_dob_mismatch": {
        "en": "IC birth date != DOB", "bm": "Tarikh IC != tarikh lahir",
        "desc_en": "Birth date encoded in the IC (YYMMDD) does not match the recorded Tarikh_Lahir.",
        "desc_bm": "Tarikh lahir dalam IC (YYMMDD) tidak sepadan dengan Tarikh_Lahir yang direkod.",
    },
    "review_ic_gender_mismatch": {
        "en": "IC gender digit != gender", "bm": "Digit jantina IC != jantina",
        "desc_en": "IC's final-digit sex indicator (odd=M / even=F) contradicts the recorded gender.",
        "desc_bm": "Penunjuk jantina digit terakhir IC (ganjil=L / genap=P) bercanggah dengan jantina yang direkod.",
    },
    "review_ic_age_contradiction": {
        "en": "IC implies adult", "bm": "IC menunjukkan dewasa",
        "desc_en": "IC implies the person is an adult (≥18 years) but the record is in a child dataset (<60 months).",
        "desc_bm": "IC menunjukkan individu dewasa (≥18 tahun) tetapi rekod berada dalam set data kanak-kanak (<60 bulan).",
    },
    "review_duplicate_ic": {
        "en": "Duplicate IC", "bm": "IC berganda",
        "desc_en": "Same IC number appears on more than one row (possible revaccination or duplicate entry).",
        "desc_bm": "Nombor IC yang sama muncul pada lebih daripada satu baris (kemungkinan vaksinasi semula atau entri berganda).",
    },
    "review_mykid_shared_placeholder": {
        "en": "Shared/placeholder MyKid", "bm": "MyKid kongsi/pemegang tempat",
        "desc_en": "One MyKid number is shared across rows with different names or birth dates (placeholder or data error).",
        "desc_bm": "Satu nombor MyKid dikongsi pada baris dengan nama atau tarikh lahir yang berbeza (pemegang tempat atau ralat data).",
    },
    "review_mykid_invalid": {
        "en": "Invalid MyKid format", "bm": "Format MyKid tidak sah",
        "desc_en": "MyKid number isn't a valid 12-digit number.",
        "desc_bm": "Nombor MyKid bukan nombor 12 digit yang sah.",
    },
    "review_name_gender_mismatch": {
        "en": "Name honorific != gender", "bm": "Gelaran nama != jantina",
        "desc_en": "Name honorific (bin / binti / a/l / a/p) contradicts the recorded gender.",
        "desc_bm": "Gelaran nama (bin / binti / a/l / a/p) bercanggah dengan jantina yang direkod.",
    },
    "review_gender_cols_disagree": {
        "en": "Gender columns disagree", "bm": "Lajur jantina tidak sepadan",
        "desc_en": "Two gender columns in the file disagree after normalising to Male / Female.",
        "desc_bm": "Dua lajur jantina dalam fail tidak sepadan selepas penormalan kepada Lelaki / Perempuan.",
    },
    "review_future_measure_date": {
        "en": "Future measurement date", "bm": "Tarikh ukur akan datang",
        "desc_en": "Measurement date is in the future (after today's date).",
        "desc_bm": "Tarikh pengukuran adalah pada masa hadapan (selepas tarikh hari ini).",
    },
    "review_year_mismatch": {
        "en": "Year != measurement year", "bm": "Tahun != tahun ukur",
        "desc_en": "Stated year column does not match the year of the measurement date.",
        "desc_bm": "Lajur tahun yang dinyatakan tidak sepadan dengan tahun tarikh pengukuran.",
    },
    "review_dob_dual_mismatch": {
        "en": "DOB columns disagree", "bm": "Lajur tarikh lahir tidak sepadan",
        "desc_en": "Two birth-date columns in the file disagree with each other.",
        "desc_bm": "Dua lajur tarikh lahir dalam fail tidak sepadan antara satu sama lain.",
    },
    "review_dose_date_mismatch": {
        "en": "Dose date != measure date", "bm": "Tarikh dos != tarikh ukur",
        "desc_en": "DOSE_DATE does not match the measurement date (common in contoh exports).",
        "desc_bm": "DOSE_DATE tidak sepadan dengan tarikh pengukuran (biasa dalam eksport contoh).",
    },
    "review_age_source_mismatch": {
        "en": "Source age != computed", "bm": "Umur sumber != kiraan",
        "desc_en": "File's own age figure differs by more than 1 month from the computed age.",
        "desc_bm": "Angka umur dalam fail berbeza lebih daripada 1 bulan daripada umur yang dikira.",
    },
    "review_age_band_mismatch": {
        "en": "Age band label wrong", "bm": "Label kumpulan umur salah",
        "desc_en": "Age-band label (e.g. 'Bawah 2 Tahun') does not match the actual computed age.",
        "desc_bm": "Label kumpulan umur (cth. 'Bawah 2 Tahun') tidak sepadan dengan umur sebenar yang dikira.",
    },
    "review_age_vacc_range": {
        "en": "Vaccination age out of range", "bm": "Umur vaksinasi luar julat",
        "desc_en": "The child's recorded age at vaccination is negative or greater than 5 years — outside the expected range for this programme.",
        "desc_bm": "Umur kanak-kanak semasa vaksinasi yang direkod adalah negatif atau melebihi 5 tahun — di luar julat yang dijangkakan untuk program ini.",
    },
    "review_daerah_null": {
        "en": "District missing", "bm": "Daerah hilang",
        "desc_en": "District (daerah) field is missing or blank.",
        "desc_bm": "Medan daerah kosong atau hilang.",
    },
    "review_daerah_not_in_negeri": {
        "en": "District not in state", "bm": "Daerah bukan dalam negeri",
        "desc_en": "District name is not found in the recorded state (daerah not in negeri). Deferred — no authoritative district→state map yet.",
        "desc_bm": "Nama daerah tidak ditemui dalam negeri yang direkod. Ditangguhkan — tiada peta daerah→negeri yang sah lagi.",
    },
    "review_bahagian_null": {
        "en": "Division missing", "bm": "Bahagian hilang",
        "desc_en": "Division (Bahagian) field is missing or blank.",
        "desc_bm": "Medan Bahagian kosong atau hilang.",
    },
    "review_geo_out_of_bounds": {
        "en": "Coordinates outside Malaysia", "bm": "Koordinat luar Malaysia",
        "desc_en": "Latitude / longitude coordinates fall outside Malaysia's geographic bounding box.",
        "desc_bm": "Koordinat latitud / longitud berada di luar kotak sempadan geografi Malaysia.",
    },
    "review_height_unit_suspect": {
        "en": "Height unit suspect", "bm": "Unit tinggi diragui",
        "desc_en": "Height value exceeds 200, which is implausible for a child — likely entered in centimetres when metres were expected (e.g. 175 instead of 1.75), or an extra digit was added by mistake.",
        "desc_bm": "Nilai tinggi melebihi 200, yang tidak munasabah untuk kanak-kanak — kemungkinan dimasukkan dalam sentimeter apabila meter dijangkakan (cth. 175 berbanding 1.75), atau digit tambahan dimasukkan secara tidak sengaja.",
    },
    "review_ghost_bmi": {
        "en": "Unverifiable source BMI", "bm": "BMI sumber tak boleh sah",
        "desc_en": "A source BMI value is present but weight or height is missing so it cannot be verified.",
        "desc_bm": "Nilai BMI sumber ada tetapi berat atau tinggi hilang sehingga tidak dapat disahkan.",
    },
    "review_dual_measure_mismatch": {
        "en": "Duplicate measurement cols disagree", "bm": "Lajur ukuran berganda tidak sepadan",
        "desc_en": "Duplicate measurement columns (e.g. LENGTH_HEIGHT_CM and Tinggi_cm) disagree.",
        "desc_bm": "Lajur pengukuran pendua (cth. LENGTH_HEIGHT_CM dan Tinggi_cm) tidak sepadan.",
    },
    "review_ghost_class": {
        "en": "Classification without score", "bm": "Klasifikasi tanpa skor",
        "desc_en": "A classification column is filled but the corresponding source z-score is blank.",
        "desc_bm": "Lajur klasifikasi diisi tetapi z-skor sumber yang sepadan kosong.",
    },
    "review_class_range_mismatch": {
        "en": "Class != z-score range", "bm": "Kelas != julat z-skor",
        "desc_en": "Classification label does not match the z-score range. Deferred — per-axis cutoffs not confirmed.",
        "desc_bm": "Label klasifikasi tidak sepadan dengan julat z-skor. Ditangguhkan — ambang setiap paksi belum disahkan.",
    },
    "review_zscore_biv": {
        "en": "Z-score biologically implausible", "bm": "Z-skor tidak munasabah biologi",
        "desc_en": "A WHO growth z-score (weight-for-age WAZ, height-for-age HAZ, or BMI-for-age BAZ) from the source file exceeds the biological implausibility limit (|value| > 6), suggesting a data entry error rather than a truly extreme measurement.",
        "desc_bm": "Z-skor pertumbuhan WHO (berat-untuk-umur WAZ, tinggi-untuk-umur HAZ, atau BMI-untuk-umur BAZ) dari fail sumber melebihi had plausibiliti biologi (|nilai| > 6), menunjukkan kemungkinan kesilapan kemasukan data berbanding pengukuran sebenar yang melampau.",
    },
    "review_indicator_class_mismatch": {
        "en": "Indicator != classification", "bm": "Penunjuk != klasifikasi",
        "desc_en": "An indicator flag (e.g. stunted=1) disagrees with its corresponding classification column.",
        "desc_bm": "Tanda penunjuk (cth. stunted=1) bercanggah dengan lajur klasifikasi yang sepadan.",
    },
    "review_pendapatan_null": {
        "en": "Income missing", "bm": "Pendapatan hilang",
        "desc_en": "Income group field is missing or blank.",
        "desc_bm": "Medan kumpulan pendapatan kosong atau hilang.",
    },
    "review_pendapatan_invalid": {
        "en": "Unknown income group", "bm": "Kumpulan pendapatan tidak sah",
        "desc_en": "Income group value is not one of the recognised categories (B40 / M40 / T20).",
        "desc_bm": "Nilai kumpulan pendapatan bukan salah satu kategori yang diiktiraf (B40 / M40 / T20).",
    },
    "review_vaccine_unknown": {
        "en": "Unknown vaccine", "bm": "Vaksin tidak dikenali",
        "desc_en": "Vaccine name is not in the KKM childhood immunisation schedule.",
        "desc_bm": "Nama vaksin tidak terdapat dalam jadual imunisasi kanak-kanak KKM.",
    },
    "review_agensi_unknown": {
        "en": "Unknown agency", "bm": "Agensi tidak dikenali",
        "desc_en": "Agency code is not a recognised programme agency.",
        "desc_bm": "Kod agensi bukan agensi program yang diiktiraf.",
    },
    "review_taska_blank": {
        "en": "TASKA name missing", "bm": "Nama taska hilang",
        "desc_en": "TASKA name is blank while an agency code is present.",
        "desc_bm": "Nama TASKA kosong walaupun kod agensi ada.",
    },
    "review_ethnicity_unknown": {
        "en": "Unknown ethnicity", "bm": "Etnik tidak dikenali",
        "desc_en": "Ethnicity value is not a recognised Malaysian ethnic category.",
        "desc_bm": "Nilai etnik bukan kategori etnik Malaysia yang diiktiraf.",
    },
    "review_facility_unknown": {
        "en": "Unknown facility type", "bm": "Jenis fasiliti tidak dikenali",
        "desc_en": "Facility type is not a recognised KKM facility type.",
        "desc_bm": "Jenis fasiliti bukan jenis fasiliti KKM yang diiktiraf.",
    },
}

REVIEW_EVALUATED_RULES: dict[str, list[str]] = {
    "myvass": [
        "review_ic_malformed",
        "review_ic_dob_mismatch",
        "review_ic_gender_mismatch",
        "review_ic_age_contradiction",
        "review_duplicate_ic",
        "review_name_gender_mismatch",
        "review_gender_cols_disagree",
        "review_future_measure_date",
        "review_year_mismatch",
        "review_dob_dual_mismatch",
        "review_dose_date_mismatch",
        "review_age_source_mismatch",
        "review_age_band_mismatch",
        "review_age_vacc_range",
        "review_daerah_null",
        # review_daerah_not_in_negeri — DEFERRED (no authoritative district->state map)
        "review_geo_out_of_bounds",
        "review_height_unit_suspect",
        "review_ghost_bmi",
        "review_dual_measure_mismatch",
        "review_ghost_class",
        # review_class_range_mismatch — DEFERRED (unspecified per-axis z->label cutoffs)
        "review_zscore_biv",
        "review_indicator_class_mismatch",
        "review_pendapatan_null",
        "review_pendapatan_invalid",
        # review_ethnicity_unknown — DISABLED 2026-06-16 (ETHNIC_VALID completeness unprovable from contoh)
        # review_facility_unknown  — DISABLED 2026-06-16 (FACILITY_SET demonstrably incomplete; real categories missing)
    ],
    "ncdc": [
        "review_mykid_shared_placeholder",
        "review_mykid_invalid",
        "review_name_gender_mismatch",
        "review_gender_cols_disagree",
        "review_future_measure_date",
        "review_year_mismatch",
        "review_age_source_mismatch",
        "review_age_band_mismatch",
        "review_age_vacc_range",
        "review_daerah_null",
        "review_bahagian_null",
        "review_height_unit_suspect",
        "review_ghost_bmi",
        "review_ghost_class",
        # review_class_range_mismatch — DEFERRED (unspecified per-axis z->label cutoffs)
        "review_zscore_biv",
        "review_indicator_class_mismatch",
        "review_pendapatan_null",
        "review_pendapatan_invalid",
        "review_vaccine_unknown",
        # review_agensi_unknown — DISABLED 2026-06-16 (AGENSI_SET completeness unprovable from contoh)
        "review_taska_blank",
    ],
    "general": [
        "review_future_measure_date",
        "review_name_gender_mismatch",
        "review_gender_cols_disagree",
        "review_year_mismatch",
        "review_dob_dual_mismatch",
        "review_age_source_mismatch",
        "review_age_band_mismatch",
        "review_age_vacc_range",
        "review_daerah_null",
        "review_geo_out_of_bounds",
        "review_height_unit_suspect",
        "review_ghost_bmi",
        "review_dual_measure_mismatch",
        "review_ghost_class",
        "review_zscore_biv",
        "review_indicator_class_mismatch",
        "review_pendapatan_null",
        "review_pendapatan_invalid",
    ],
}


def review_rules_for_source(data_type: str) -> list[dict]:
    """Registry view of review-flag rules for one source type.

    Used by the Settings panel and Quality Report alongside rules_for_source()."""
    codes = REVIEW_EVALUATED_RULES.get(data_type, REVIEW_EVALUATED_RULES["general"])
    return [{"code": c, **REVIEW_RULE_REGISTRY[c]} for c in codes if c in REVIEW_RULE_REGISTRY]


def _rule_on(code: str, enabled_rules) -> bool:
    """A drop step runs when it is locked, or when no selection is given
    (enabled_rules is None ⇒ legacy all-on behaviour), or when explicitly enabled."""
    if code in LOCKED_RULES:
        return True
    return enabled_rules is None or code in enabled_rules


def detect_data_type(columns: list[str], filename: str = "") -> str:
    """
    Auto-detect data type from column names and filename.
    
    Returns:
        str: 'kpm', 'myvass', 'ncdc', or 'general'
    """
    col_set = set(c.upper() for c in columns)
    fname = filename.lower()
    
    # Check for NCDC pattern (year-prefixed columns)
    if any("2023" in c or "2024" in c or "2025" in c for c in columns):
        return "ncdc"
    
    # Check for KPM pattern
    if any(p in col_set for p in ["ID_MURID", "THN_TING", "NAMA SEKOLAH"]):
        return "kpm"
    if "kpm" in fname or ("berat" in fname and "tinggi" in fname):
        return "kpm"
    
    # Check for MyVASS pattern
    if any(p in col_set for p in ["VACCINE_NAME", "NAMA KLINIK", "PANJANG LAHIR (KG)"]):
        return "myvass"
    if any(p in col_set for p in ["IC_NO_PASSPORT", "DOSE_DATE", "FACILITY_NAME"]):
        return "myvass"
    if "myvass" in fname or "gis" in fname:
        return "myvass"
    if "pemakanan" in fname or "anthropometry" in fname:
        return "myvass"
    
    return "general"
