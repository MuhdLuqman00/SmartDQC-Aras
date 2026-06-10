"""
KKM Data Cleaning Backend Module
================================
Provides cleaning functions for KPM, MyVASS, and NCDC data.
Integrates with WHO z-score calculations using daily LMS tables.
"""

import io
import math
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


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Weight / height bounds (biologically plausible for 0–5 years)
BERAT_MIN_INFANT, BERAT_MAX_INFANT = 0.5, 35.0      # kg (0-5 years)
TINGGI_MIN_INFANT, TINGGI_MAX_INFANT = 30.0, 130.0  # cm (0-5 years)

# Weight / height bounds for KPM (school age 6-8 years)
BERAT_MIN_SCHOOL, BERAT_MAX_SCHOOL = 12.0, 50.0     # kg
TINGGI_MIN_SCHOOL, TINGGI_MAX_SCHOOL = 100.0, 160.0 # cm

BMI_MAX = 40.0
AGE_MAX_MONTHS_INFANT = 60  # under 5 years

# Gender mapping
GENDER_MAP = {
    "LELAKI": "Male", "PEREMPUAN": "Female",
    "L": "Male", "P": "Female",
    "M": "Male", "F": "Female",
    "MALE": "Male", "FEMALE": "Female",
}

# WHO BIV thresholds
BIV = {
    "WAZ": (-6.0, +5.0),
    "HAZ": (-6.0, +6.0),
    "BAZ": (-5.0, +5.0),
}


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


def _review_rule_on(code, enabled_rules) -> bool:
    """Review-flag rules default ON. A caller selection only constrains them once
    it actually manages review rules (contains at least one review_* code); a
    drop-only or legacy selection leaves every review rule ON, so flags never
    silently vanish when a user has saved a drop-rule selection."""
    if enabled_rules is None:
        return True
    if any(str(c).startswith("review_") for c in enabled_rules):
        return code in enabled_rules
    return True


def _apply_review_flags(df, source, src_cols, find_col, enabled_rules):
    """Phase B review-for-review flags (Families 1-4).

    Each block guards on the presence of its trigger column(s) so clean data
    yields zero flags. Flags use _flag() (review_reason) and NEVER change
    `analyzable`. Dual-column rules read raw source values via src_cols
    (captured before canonical Gender/Tarikh_Lahir were derived).
    """
    def _on(code):
        return _review_rule_on(code, enabled_rules)

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
                        & (df["Age_Months"] < AGE_MAX_MONTHS_INFANT)
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
    # Phase C/D (Families 5-11) extend here, before return.
    return


# ═══════════════════════════════════════════════════════════════════════════════
# MYVASS CLEANING
# ═══════════════════════════════════════════════════════════════════════════════

def clean_myvass(df: pd.DataFrame, enabled_rules=None) -> tuple[pd.DataFrame, dict]:
    """Clean MyVASS data and compute WHO z-scores.

    Flag-then-filter: rows that fail quality rules are tagged with
    `analyzable=False` and `exclude_reason` instead of being physically
    dropped. The full frame is returned so callers can offer both a
    full-flagged download and an analysis-ready filtered view.

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
    bad_date = (df["Tarikh_Lahir"].notna() &
                df["Tarikh_Ukur"].notna() &
                (df["Tarikh_Ukur"] < df["Tarikh_Lahir"]))
    if _on("dropped_date_before_dob"):
        stats["dropped_date_before_dob"] = int((bad_date & df["analyzable"]).sum())
        _exclude(df, bad_date, "dropped_date_before_dob")
    else:
        stats["dropped_date_before_dob"] = 0

    # Compute age in days
    has_both_dates = df["Tarikh_Lahir"].notna() & df["Tarikh_Ukur"].notna()
    df["Age_Days"] = np.where(
        has_both_dates,
        (df["Tarikh_Ukur"] - df["Tarikh_Lahir"]).dt.days,
        np.nan
    )
    df["Age_Months"] = (df["Age_Days"] / 30.4375).round(2)

    # Rule 3: Flag age >= 60 months
    age_invalid = df["Age_Months"].notna() & (df["Age_Months"] >= AGE_MAX_MONTHS_INFANT)
    if _on("dropped_age_over5"):
        stats["dropped_age_over5"] = int((age_invalid & df["analyzable"]).sum())
        _exclude(df, age_invalid, "dropped_age_over5")
    else:
        stats["dropped_age_over5"] = 0

    # Convert measurements to numeric
    if weight_col:
        df["Berat_kg"] = pd.to_numeric(df[weight_col], errors="coerce")
    else:
        df["Berat_kg"] = np.nan

    if height_col:
        df["Tinggi_cm"] = pd.to_numeric(df[height_col], errors="coerce")
    else:
        df["Tinggi_cm"] = np.nan

    # Rule 2: Flag measurement outliers
    berat_bad = (df["Berat_kg"] < BERAT_MIN_INFANT) | (df["Berat_kg"] > BERAT_MAX_INFANT)
    tinggi_bad = (df["Tinggi_cm"] < TINGGI_MIN_INFANT) | (df["Tinggi_cm"] > TINGGI_MAX_INFANT)

    outlier_mask = (berat_bad & df["Berat_kg"].notna()) | (tinggi_bad & df["Tinggi_cm"].notna())
    if _on("dropped_measurement_outlier"):
        stats["dropped_measurement_outlier"] = int((outlier_mask & df["analyzable"]).sum())
        _exclude(df, outlier_mask, "dropped_measurement_outlier")
    else:
        stats["dropped_measurement_outlier"] = 0

    # Rule 6: Flag rows with both measurements null
    no_meas = df["Berat_kg"].isna() & df["Tinggi_cm"].isna()
    if _on("dropped_no_measurement"):
        stats["dropped_no_measurement"] = int((no_meas & df["analyzable"]).sum())
        _exclude(df, no_meas, "dropped_no_measurement")
    else:
        stats["dropped_no_measurement"] = 0

    # Drop raw BMI column from source (e.g. BMI_KG_M2) — will recalculate
    raw_bmi_cols = [c for c in df.columns if "bmi" in c.lower() and c != "BMI"]
    if raw_bmi_cols:
        df = df.drop(columns=raw_bmi_cols)

    # Calculate BMI from weight and height
    valid_both = df["Berat_kg"].notna() & df["Tinggi_cm"].notna() & (df["Tinggi_cm"] > 0)
    df["BMI"] = np.where(
        valid_both,
        (df["Berat_kg"] / ((df["Tinggi_cm"] / 100) ** 2)).round(2),
        np.nan
    )

    # Rule 5: Flag implausible BMI > 40
    bmi_bad = df["BMI"].notna() & (df["BMI"] > BMI_MAX)
    if _on("dropped_bmi_outlier"):
        stats["dropped_bmi_outlier"] = int((bmi_bad & df["analyzable"]).sum())
        _exclude(df, bmi_bad, "dropped_bmi_outlier")
    else:
        stats["dropped_bmi_outlier"] = 0

    # Calculate WHO Z-scores (using daily LMS tables from Excel)
    if ZSCORE_AVAILABLE:
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
    else:
        stats["dropped_null_zscore"] = 0

    # Age category column
    if "Age_Days" in df.columns:
        df["Kategori_Umur"] = np.where(
            df["Age_Days"] < 730, "Bawah 2 Tahun",
            np.where(df["Age_Days"] < 1826, "Bawah 5 Tahun", "5 Tahun ke Atas")
        )

    # Final stats — final_count = analyzable rows, not len(df)
    _apply_review_flags(df, "myvass", _src_cols, find_col, enabled_rules)
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

def clean_ncdc(df: pd.DataFrame, enabled_rules=None) -> tuple[pd.DataFrame, dict]:
    """Clean NCDC (TASKA) data and compute WHO z-scores.

    Flag-then-filter: rows that fail quality rules are tagged with
    `analyzable=False` and `exclude_reason` instead of being physically
    dropped.

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
        pendapatan_x = df[income_col].astype(str).str.upper().str.strip() == "X"
        if _on("dropped_pendapatan_x"):
            stats["dropped_pendapatan_x"] = int((pendapatan_x & df["analyzable"]).sum())
            _exclude(df, pendapatan_x, "dropped_pendapatan_x")
        else:
            stats["dropped_pendapatan_x"] = 0
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
    if _on("dropped_null_dob"):
        _mask = df["Tarikh_Lahir"].isna()
        stats["dropped_null_dob"] = int((_mask & df["analyzable"]).sum())
        _exclude(df, _mask, "dropped_null_dob")
    else:
        stats["dropped_null_dob"] = 0

    # Rule 4: Flag where measurement < DOB
    bad_date = (df["Tarikh_Lahir"].notna() &
                df["Tarikh_Pengukuran"].notna() &
                (df["Tarikh_Pengukuran"] < df["Tarikh_Lahir"]))
    if _on("dropped_date_before_dob"):
        stats["dropped_date_before_dob"] = int((bad_date & df["analyzable"]).sum())
        _exclude(df, bad_date, "dropped_date_before_dob")
    else:
        stats["dropped_date_before_dob"] = 0

    # Compute age
    has_both = df["Tarikh_Lahir"].notna() & df["Tarikh_Pengukuran"].notna()
    df["Age_Days"] = np.where(has_both, (df["Tarikh_Pengukuran"] - df["Tarikh_Lahir"]).dt.days, np.nan)
    df["Age_Months"] = (df["Age_Days"] / 30.4375).round(2)

    # Rule 3: Flag negative age or age >= 60 months
    age_invalid = (df["Age_Days"] < 0) | (df["Age_Months"] >= AGE_MAX_MONTHS_INFANT)
    if _on("dropped_age_invalid"):
        _mask = age_invalid & df["Age_Months"].notna()
        stats["dropped_age_invalid"] = int((_mask & df["analyzable"]).sum())
        _exclude(df, _mask, "dropped_age_invalid")
    else:
        stats["dropped_age_invalid"] = 0

    # Convert measurements
    df["Berat_kg"] = pd.to_numeric(df.get("Berat_kg"), errors="coerce")
    df["Tinggi_cm"] = pd.to_numeric(df.get("Tinggi_cm"), errors="coerce")

    # Rule 2: Flag measurement outliers
    berat_bad = (df["Berat_kg"] < BERAT_MIN_INFANT) | (df["Berat_kg"] > BERAT_MAX_INFANT)
    tinggi_bad = (df["Tinggi_cm"] < TINGGI_MIN_INFANT) | (df["Tinggi_cm"] > TINGGI_MAX_INFANT)

    outlier_mask = (berat_bad & df["Berat_kg"].notna()) | (tinggi_bad & df["Tinggi_cm"].notna())
    if _on("dropped_measurement_outlier"):
        stats["dropped_measurement_outlier"] = int((outlier_mask & df["analyzable"]).sum())
        _exclude(df, outlier_mask, "dropped_measurement_outlier")
    else:
        stats["dropped_measurement_outlier"] = 0

    # Rule 6: Flag no measurements
    no_meas = df["Berat_kg"].isna() & df["Tinggi_cm"].isna()
    if _on("dropped_no_measurement"):
        stats["dropped_no_measurement"] = int((no_meas & df["analyzable"]).sum())
        _exclude(df, no_meas, "dropped_no_measurement")
    else:
        stats["dropped_no_measurement"] = 0

    # Drop raw BMI column from source — will recalculate
    raw_bmi_cols = [c for c in df.columns if "bmi" in c.lower() and c != "BMI"]
    if raw_bmi_cols:
        df = df.drop(columns=raw_bmi_cols)

    # Calculate BMI from weight and height
    valid_both = df["Berat_kg"].notna() & df["Tinggi_cm"].notna() & (df["Tinggi_cm"] > 0)
    df["BMI"] = np.where(valid_both, (df["Berat_kg"] / ((df["Tinggi_cm"] / 100) ** 2)).round(2), np.nan)

    # Rule 5: Flag implausible BMI
    bmi_bad = df["BMI"].notna() & (df["BMI"] > BMI_MAX)
    if _on("dropped_bmi_outlier"):
        stats["dropped_bmi_outlier"] = int((bmi_bad & df["analyzable"]).sum())
        _exclude(df, bmi_bad, "dropped_bmi_outlier")
    else:
        stats["dropped_bmi_outlier"] = 0

    # Rule 8 + placeholder guard: duplicate MyKid handling.
    # Same MyKid with the SAME DOB = one child re-measured -> keep most recent,
    # drop the older record (dropped_duplicate_mykid). Same MyKid with DIFFERING
    # DOB = a shared placeholder across different children -> flag every row,
    # drop none (review_mykid_shared_placeholder). Prevents wrongly dropping
    # placeholder rows (e.g. 12/13 rows sharing one stand-in MyKid).
    if mykid_col and "Tarikh_Pengukuran" in df.columns:
        _placeholder = pd.Series(False, index=df.index)
        _dropdup = pd.Series(False, index=df.index)
        for _key, _grp in df.groupby(mykid_col):
            if len(_grp) < 2:
                continue
            if _grp["Tarikh_Lahir"].nunique(dropna=True) > 1:
                _placeholder.loc[_grp.index] = True
            else:
                _order = _grp.sort_values("Tarikh_Pengukuran", ascending=False)
                _dropdup.loc[_order.index[1:]] = True
        if _on("dropped_duplicate_mykid"):
            stats["dropped_duplicate_mykid"] = int((_dropdup & df["analyzable"]).sum())
            _exclude(df, _dropdup, "dropped_duplicate_mykid")
        else:
            stats["dropped_duplicate_mykid"] = 0
        if _review_rule_on("review_mykid_shared_placeholder", enabled_rules):
            _flag(df, _placeholder, "review_mykid_shared_placeholder")
    else:
        stats["dropped_duplicate_mykid"] = 0

    # Calculate WHO Z-scores (using daily LMS tables from Excel)
    if ZSCORE_AVAILABLE:
        df["WAZ"] = None
        df["HAZ"] = None
        df["BAZ"] = None

        for idx in df.index:
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

        # Indicator flags
        df["Ind_Kurang_Berat_Badan"] = df["WAZ"].apply(lambda z: z < -2 if pd.notna(z) else False)
        df["Ind_Bantut"] = df["HAZ"].apply(lambda z: z < -2 if pd.notna(z) else False)
        df["Ind_Susut"] = df["BAZ"].apply(lambda z: z < -2 if pd.notna(z) else False)
        df["Ind_Berlebihan_BB"] = df["BAZ"].apply(lambda z: z > 1 if pd.notna(z) else False)
        df["Ind_Obes"] = df["BAZ"].apply(lambda z: z > 2 if pd.notna(z) else False)

        # Rule 7: Flag rows with null z-scores (locked — always runs)
        null_zscore = df["WAZ"].isna() | df["HAZ"].isna() | df["BAZ"].isna()
        stats["dropped_null_zscore"] = int((null_zscore & df["analyzable"]).sum())
        _exclude(df, null_zscore, "dropped_null_zscore")

        df["Ind_Normal"] = ~(df["Ind_Kurang_Berat_Badan"] | df["Ind_Bantut"] | df["Ind_Susut"])

        _a = df["analyzable"]
        stats["ind_kurang_berat"] = int(df.loc[_a, "Ind_Kurang_Berat_Badan"].sum())
        stats["ind_bantut"] = int(df.loc[_a, "Ind_Bantut"].sum())
        stats["ind_susut"] = int(df.loc[_a, "Ind_Susut"].sum())
        stats["ind_berlebihan_bb"] = int(df.loc[_a, "Ind_Berlebihan_BB"].sum())
        stats["ind_obes"] = int(df.loc[_a, "Ind_Obes"].sum())
        stats["ind_normal"] = int(df.loc[_a, "Ind_Normal"].sum())
    else:
        stats["dropped_null_zscore"] = 0

    # Age category column
    if "Age_Days" in df.columns:
        df["Kategori_Umur"] = np.where(
            df["Age_Days"] < 730, "Bawah 2 Tahun",
            np.where(df["Age_Days"] < 1826, "Bawah 5 Tahun", "5 Tahun ke Atas")
        )

    # Final stats — final_count = analyzable rows, not len(df)
    _apply_review_flags(df, "ncdc", _src_cols, find_col, enabled_rules)
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

def clean_kpm(df: pd.DataFrame, enabled_rules=None) -> tuple[pd.DataFrame, dict]:
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
        if _on("dropped_ragu_gender"):
            _mask = df["Jantina_Raw"] == "RAGU"
            stats["dropped_ragu_gender"] = int((_mask & df["analyzable"]).sum())
            _exclude(df, _mask, "dropped_ragu_gender")
        else:
            stats["dropped_ragu_gender"] = 0

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

    # Rule 6 & 7: Flag measurement outliers
    berat_bad = (df["Berat_kg"] < BERAT_MIN_SCHOOL) | (df["Berat_kg"] > BERAT_MAX_SCHOOL)
    tinggi_bad = (df["Tinggi_cm"] < TINGGI_MIN_SCHOOL) | (df["Tinggi_cm"] > TINGGI_MAX_SCHOOL)

    outlier_mask = (berat_bad & df["Berat_kg"].notna()) | (tinggi_bad & df["Tinggi_cm"].notna())
    if _on("dropped_measurement_outlier"):
        stats["dropped_measurement_outlier"] = int((outlier_mask & df["analyzable"]).sum())
        _exclude(df, outlier_mask, "dropped_measurement_outlier")
    else:
        stats["dropped_measurement_outlier"] = 0

    # Calculate BMI
    valid_both = df["Berat_kg"].notna() & df["Tinggi_cm"].notna() & (df["Tinggi_cm"] > 0)
    df["BMI"] = np.where(valid_both, (df["Berat_kg"] / ((df["Tinggi_cm"] / 100) ** 2)).round(2), np.nan)

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

def clean_general(df: pd.DataFrame, enabled_rules=None) -> tuple[pd.DataFrame, dict]:
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

    def _on(code: str) -> bool:
        return _rule_on(code, enabled_rules)
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

    gender_col = find_col(["jantina", "gender", "sex"])
    dob_col = find_col(["tarikh lahir", "dob", "date of birth", "birth"])
    measure_date_col = find_col(
        ["tarikh ukur", "tarikh antropometri", "tarikh pengukuran",
         "measurement date", "assessment date", "tarikh assessment"]
    )
    weight_col = find_col(["berat kg", "berat", "weight"])
    height_col = find_col(["tinggi cm", "tinggi", "panjang", "height", "length"])
    age_col = find_col(["age months", "umur bulan", "age", "umur"])

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

    # Gender — never drop on missing.
    if gender_col:
        df["Gender"] = df[gender_col].astype(str).str.upper().str.strip().map(GENDER_MAP)
    else:
        df["Gender"] = None

    df["Tarikh_Lahir"] = _parse_date(df[dob_col]) if dob_col else pd.NaT
    df["Tarikh_Ukur"] = _parse_date(df[measure_date_col]) if measure_date_col else pd.NaT

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

    # Only genuine logical garbage is flagged, and only when both dates exist.
    bad_date = (
        df["Tarikh_Lahir"].notna()
        & df["Tarikh_Ukur"].notna()
        & (df["Tarikh_Ukur"] < df["Tarikh_Lahir"])
    )
    if _on("dropped_date_before_dob"):
        stats["dropped_date_before_dob"] = int((bad_date & df["analyzable"]).sum())
        _exclude(df, bad_date, "dropped_date_before_dob")
    else:
        stats["dropped_date_before_dob"] = 0

    df["Berat_kg"] = pd.to_numeric(df[weight_col], errors="coerce") if weight_col else np.nan
    df["Tinggi_cm"] = pd.to_numeric(df[height_col], errors="coerce") if height_col else np.nan

    # Null implausible values — keep the row.
    if weight_col:
        df.loc[
            (df["Berat_kg"] < BERAT_MIN_INFANT) | (df["Berat_kg"] > BERAT_MAX_INFANT),
            "Berat_kg",
        ] = np.nan
    if height_col:
        df.loc[
            (df["Tinggi_cm"] < TINGGI_MIN_INFANT) | (df["Tinggi_cm"] > TINGGI_MAX_INFANT),
            "Tinggi_cm",
        ] = np.nan

    valid_both = df["Berat_kg"].notna() & df["Tinggi_cm"].notna() & (df["Tinggi_cm"] > 0)
    df["BMI"] = np.where(
        valid_both, (df["Berat_kg"] / ((df["Tinggi_cm"] / 100) ** 2)).round(2), np.nan
    )
    df.loc[df["BMI"] > BMI_MAX, "BMI"] = np.nan

    # Gate indicator computation on its required inputs (dataset-level).
    base_ok = ZSCORE_AVAILABLE and coverage["jantina"] and coverage["age"]
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
        else:
            unavailable[name] = "missing/ambiguous measurement input"

    if base_ok:
        df["WAZ"] = np.nan
        df["HAZ"] = np.nan
        df["BAZ"] = np.nan
        for idx in df.index:
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

    indicators_available = sorted(
        n for n in ("underweight", "stunting", "wasting", "overweight")
        if n not in unavailable
    )

    stats["final_count"] = int(df["analyzable"].sum())
    stats["total_dropped"] = stats["raw_count"] - stats["final_count"]
    stats["coverage"] = coverage
    stats["assumptions"] = assumptions
    stats["indicators_available"] = indicators_available
    stats["indicators_unavailable"] = unavailable
    return df, stats


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CLEANING DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

def clean_data(df: pd.DataFrame, data_type: str, enabled_rules=None) -> tuple[pd.DataFrame, dict]:
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

    Returns:
        tuple: (cleaned_dataframe, statistics_dict)
    """
    from backend.config import normalize_schema_type
    data_type = normalize_schema_type(data_type)
    if data_type == "kpm":
        return clean_kpm(df, enabled_rules)
    elif data_type == "myvass":
        return clean_myvass(df, enabled_rules)
    elif data_type == "ncdc":
        return clean_ncdc(df, enabled_rules)
    # general / any unsupported schema → conservative general cleaner (never
    # ValueError, never silently mis-routed to clean_myvass).
    return clean_general(df, enabled_rules)


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
        "dropped_date_before_dob",
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
        "desc_en": "Remove rows with a negative or out-of-range computed age.",
        "desc_bm": "Buang baris dengan umur terkira negatif atau luar julat.",
        "locked": False,
    },
    "dropped_measurement_outlier": {
        "en": "Drop measurement outliers", "bm": "Buang pencilan pengukuran",
        "desc_en": "Remove biologically implausible weight or height values.",
        "desc_bm": "Buang nilai berat atau tinggi yang mustahil secara biologi.",
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


def rules_for_source(data_type: str) -> list[dict]:
    """Registry view for one source type, in cleaner-execution order. Used by the
    Settings tab and the pipeline rule panel so both list the SAME real rules."""
    codes = EVALUATED_RULES.get(data_type, EVALUATED_RULES["general"])
    return [{"code": c, **RULE_REGISTRY[c]} for c in codes if c in RULE_REGISTRY]


REVIEW_RULE_REGISTRY: dict[str, dict] = {
    "review_ic_malformed": {"en": "Malformed IC", "bm": "IC tidak sah format"},
    "review_ic_dob_mismatch": {"en": "IC birth date != DOB", "bm": "Tarikh IC != tarikh lahir"},
    "review_ic_gender_mismatch": {"en": "IC gender digit != gender", "bm": "Digit jantina IC != jantina"},
    "review_ic_age_contradiction": {"en": "IC implies adult", "bm": "IC menunjukkan dewasa"},
    "review_duplicate_ic": {"en": "Duplicate IC", "bm": "IC berganda"},
    "review_mykid_shared_placeholder": {"en": "Shared/placeholder MyKid", "bm": "MyKid kongsi/pemegang tempat"},
    "review_mykid_invalid": {"en": "Invalid MyKid format", "bm": "Format MyKid tidak sah"},
    "review_name_gender_mismatch": {"en": "Name honorific != gender", "bm": "Gelaran nama != jantina"},
    "review_gender_cols_disagree": {"en": "Gender columns disagree", "bm": "Lajur jantina tidak sepadan"},
    "review_future_measure_date": {"en": "Future measurement date", "bm": "Tarikh ukur akan datang"},
    "review_year_mismatch": {"en": "Year != measurement year", "bm": "Tahun != tahun ukur"},
    "review_dob_dual_mismatch": {"en": "DOB columns disagree", "bm": "Lajur tarikh lahir tidak sepadan"},
    "review_dose_date_mismatch": {"en": "Dose date != measure date", "bm": "Tarikh dos != tarikh ukur"},
    "review_age_source_mismatch": {"en": "Source age != computed", "bm": "Umur sumber != kiraan"},
    "review_age_band_mismatch": {"en": "Age band label wrong", "bm": "Label kumpulan umur salah"},
    "review_age_vacc_range": {"en": "Vaccination age out of range", "bm": "Umur vaksinasi luar julat"},
    "review_daerah_null": {"en": "District missing", "bm": "Daerah hilang"},
    "review_daerah_not_in_negeri": {"en": "District not in state", "bm": "Daerah bukan dalam negeri"},
    "review_bahagian_null": {"en": "Division missing", "bm": "Bahagian hilang"},
    "review_geo_out_of_bounds": {"en": "Coordinates outside Malaysia", "bm": "Koordinat luar Malaysia"},
    "review_height_unit_suspect": {"en": "Height unit suspect", "bm": "Unit tinggi diragui"},
    "review_ghost_bmi": {"en": "Unverifiable source BMI", "bm": "BMI sumber tak boleh sah"},
    "review_dual_measure_mismatch": {"en": "Duplicate measurement cols disagree", "bm": "Lajur ukuran berganda tidak sepadan"},
    "review_ghost_class": {"en": "Classification without score", "bm": "Klasifikasi tanpa skor"},
    "review_class_range_mismatch": {"en": "Class != z-score range", "bm": "Kelas != julat z-skor"},
    "review_zscore_biv": {"en": "Z-score out of range", "bm": "Z-skor luar julat"},
    "review_indicator_class_mismatch": {"en": "Indicator != classification", "bm": "Penunjuk != klasifikasi"},
    "review_pendapatan_null": {"en": "Income missing", "bm": "Pendapatan hilang"},
    "review_pendapatan_invalid": {"en": "Unknown income group", "bm": "Kumpulan pendapatan tidak sah"},
    "review_vaccine_unknown": {"en": "Unknown vaccine", "bm": "Vaksin tidak dikenali"},
    "review_agensi_unknown": {"en": "Unknown agency", "bm": "Agensi tidak dikenali"},
    "review_taska_blank": {"en": "TASKA name missing", "bm": "Nama taska hilang"},
    "review_ethnicity_unknown": {"en": "Unknown ethnicity", "bm": "Etnik tidak dikenali"},
    "review_facility_unknown": {"en": "Unknown facility type", "bm": "Jenis fasiliti tidak dikenali"},
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
        "review_daerah_null",
        "review_daerah_not_in_negeri",
        "review_geo_out_of_bounds",
        "review_height_unit_suspect",
        "review_ghost_bmi",
        "review_dual_measure_mismatch",
        "review_ghost_class",
        "review_class_range_mismatch",
        "review_zscore_biv",
        "review_indicator_class_mismatch",
        "review_pendapatan_null",
        "review_pendapatan_invalid",
        "review_ethnicity_unknown",
        "review_facility_unknown",
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
        "review_class_range_mismatch",
        "review_zscore_biv",
        "review_indicator_class_mismatch",
        "review_pendapatan_null",
        "review_pendapatan_invalid",
        "review_vaccine_unknown",
        "review_agensi_unknown",
        "review_taska_blank",
    ],
    "general": [],
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
