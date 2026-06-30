"""
Weight & Height source-specific cleaning logic.
Extracted from the original weight/height cleaner — unique rules not present in backend/eda/cleaning.py.

Key differences vs generic cleaning:
  - BMI thresholds for 7-year-old cohort (WHO 2007): 13.5 / 16.5 / 18.5
  - Height-for-age stunting categories: <112cm = Stunted, >132cm = Tall
  - 2024 data: all measurement dates forced to 31/12/2024 (data owner clarification)
  - Drop strategy is year-conditional: 2024 = FLAG rows; 2025 = DROP rows
  - Composite quality flag builder (semicolon-separated issues per row)
  - Age range: 6-8 years (school cohort, not 0-5)
  - Weight/height bounds: 12-50 kg, 100-160 cm
"""

import pandas as pd
import numpy as np
from backend.clinical_ranges import get_range as _cr_get_range, get_val as _cr_get_val

# ---------------------------------------------------------------------------
# Constants — sourced from clinical_ranges registry (Phase 2 rewire).
# Override via global settings or per-run range_overrides.
# ---------------------------------------------------------------------------

BERAT_MIN, BERAT_MAX   = _cr_get_range("school_weight")
TINGGI_MIN, TINGGI_MAX = _cr_get_range("school_height")
AGE_MIN_YEARS          = _cr_get_val("school_age_min")
AGE_MAX_YEARS          = _cr_get_val("school_age_max")

BMI_UNDERWEIGHT = _cr_get_val("bmi_underweight")
BMI_OVERWEIGHT  = _cr_get_val("bmi_overweight")
BMI_OBESE       = _cr_get_val("bmi_obese")

STUNTED_THRESHOLD = _cr_get_val("stunted_threshold")
TALL_THRESHOLD    = _cr_get_val("tall_threshold")

VALID_NEGERI = {
    "JOHOR", "KEDAH", "KELANTAN", "MELAKA", "NEGERI SEMBILAN",
    "PAHANG", "PERAK", "PERLIS", "PULAU PINANG", "SABAH",
    "SARAWAK", "SELANGOR", "TERENGGANU",
    "WP KUALA LUMPUR", "WP LABUAN", "WP PUTRAJAYA",
    "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WILAYAH PERSEKUTUAN LABUAN",
    "WILAYAH PERSEKUTUAN PUTRAJAYA",
}

COLUMN_RENAME = {
    "TAHUN PERSEKOLAHAN":                "Tahun_Persekolahan",
    "NEGERI":                            "Negeri",
    "DAERAH":                            "Daerah",
    "NAMA SEKOLAH":                      "Nama_Sekolah",
    "LOKASI (BANDAR/LUAR BANDAR)":       "Lokasi",
    "JENIS SEKOLAH":                     "Jenis_Sekolah",
    "THN_TING":                          "Thn_Ting",
    "JANTINA":                           "Jantina",
    "ID_MURID":                          "ID_Murid",
    "TARIKH LAHIR":                      "Tarikh_Lahir_Raw",
    "TARIKH PENGUKURAN BERAT/ TINGGI":   "Tarikh_Pengukuran_Raw",
    "BERAT (kg)":                        "Berat_kg_Raw",
    "TINGGI (cm)":                       "Tinggi_cm_Raw",
}


# ---------------------------------------------------------------------------
# Category helpers
# ---------------------------------------------------------------------------

def bmi_category(bmi: float) -> str:
    """BMI category for 7-year-old school cohort (WHO 2007)."""
    if pd.isna(bmi):
        return "Unknown"
    if bmi < BMI_UNDERWEIGHT: return "Underweight"
    if bmi < BMI_OVERWEIGHT:  return "Normal"
    if bmi < BMI_OBESE:       return "Overweight"
    return "Obese"


def height_category(height: float) -> str:
    """Height-for-age category using 7-year-old WHO approximate ±2 SD thresholds."""
    if pd.isna(height):
        return "Unknown"
    if height < STUNTED_THRESHOLD: return "Stunted"
    if height > TALL_THRESHOLD:    return "Tall"
    return "Normal"


def _build_quality_flag(df: pd.DataFrame) -> pd.Series:
    """
    Build composite quality flag per row.
    Issues are concatenated with '; ' separator. Rows with no issues get 'Valid'.
    """
    conditions = [
        (~df["Has_Complete_Measurements"], "Missing Measurements"),
        (~df["Is_Valid_Age"],              "Invalid Age"),
        (~df["Is_Valid_Measurement_Date"], "Invalid Date"),
        (df["Gender"] == "Unknown",        "Unknown Gender"),
        (df["Is_Duplicate_ID"],            "Duplicate ID"),
    ]
    parts = [mask.astype(int).map({0: "", 1: label}) for mask, label in conditions]
    combined = parts[0].copy()
    for part in parts[1:]:
        sep = (combined != "") & (part != "")
        combined = combined + sep.map({True: "; ", False: ""}) + part
    return combined.replace("", "Valid")


# ---------------------------------------------------------------------------
# Main cleaning function
# ---------------------------------------------------------------------------

def clean_weight_height(df: pd.DataFrame, year: int, drop_invalid: bool | None = None) -> tuple[pd.DataFrame, dict]:
    """
    Apply all weight/height cleaning rules.
    Returns (cleaned_df, stats_dict).

    drop_invalid=None (default): auto-detect from year
      year == 2024 -> FLAG rows (keep with Data_Quality_Flag column)
      year == 2025 -> DROP rows failing any rule

    Rules:
      BR-02  Duplicate ID_MURID — flag only (not dropped)
      BR-03  Drop invalid gender
      BR-04  Age outside 6-8 years — flag/drop
      BR-05  Invalid measurement date — flag/drop
      BR-06  Weight out of 12-50 kg — flag/drop
      BR-07  Height out of 100-160 cm — flag/drop
      BR-13  BMI recalculated from weight/height
    Special: 2024 measurement dates all forced to 31/12/2024
    """
    if drop_invalid is None:
        drop_invalid = (year == 2025)

    stats: dict = {"year": year, "raw_count": len(df), "mode": "drop" if drop_invalid else "flag"}
    out = df.copy()

    # ── Normalise column names ────────────────────────────────────────────
    out.columns = out.columns.str.replace(r"\s+", " ", regex=True).str.strip()
    out = out.rename(columns={k: v for k, v in COLUMN_RENAME.items() if k in out.columns})

    # ── Text normalisation ────────────────────────────────────────────────
    for col in ["Negeri", "Daerah", "Jantina", "Jenis_Sekolah", "Thn_Ting"]:
        if col in out.columns:
            out[col] = out[col].astype(str).str.upper().str.strip()
    for col in ["Nama_Sekolah", "ID_Murid"]:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip()
    if "Lokasi" in out.columns:
        out["Lokasi"] = out["Lokasi"].astype(str).str.upper().str.strip()

    # ── BR-03: Gender ─────────────────────────────────────────────────────
    gender_map = {"LELAKI": "Male", "PEREMPUAN": "Female"}
    out["Gender"] = out["Jantina"].map(gender_map).fillna("Unknown")
    stats["ragu_gender"]    = int((out["Jantina"] == "RAGU").sum())
    stats["unknown_gender"] = int((out["Gender"] == "Unknown").sum())

    # ── Parse dates ───────────────────────────────────────────────────────
    out["Tarikh_Lahir"]      = pd.to_datetime(out.get("Tarikh_Lahir_Raw"),      dayfirst=True, errors="coerce")
    out["Tarikh_Pengukuran"] = pd.to_datetime(out.get("Tarikh_Pengukuran_Raw"), dayfirst=True, errors="coerce")
    stats["null_tarikh_lahir"] = int(out["Tarikh_Lahir"].isna().sum())

    # ── BR-05: Flag bad measurement dates ────────────────────────────────
    epoch_mask  = out["Tarikh_Pengukuran"].dt.normalize() == pd.Timestamp("1970-01-01")
    pre20_mask  = out["Tarikh_Pengukuran"] < pd.Timestamp("2020-01-01")
    future_mask = out["Tarikh_Pengukuran"] > pd.Timestamp.now()
    bad_date    = epoch_mask | pre20_mask | future_mask
    stats["bad_dates"] = int(bad_date.sum())

    if drop_invalid:
        out = out[~bad_date].copy()
    else:
        out.loc[bad_date, "Tarikh_Pengukuran"] = pd.NaT

    # Special: 2024 — force all dates to 31/12/2024
    if year == 2024:
        out["Tarikh_Pengukuran"] = pd.Timestamp("2024-12-31")
        stats["standardized_to_31dec2024"] = len(out)

    # ── BR-04: Age ────────────────────────────────────────────────────────
    has_both = out["Tarikh_Lahir"].notna() & out["Tarikh_Pengukuran"].notna()
    out["Age_Days"]  = np.where(has_both, (out["Tarikh_Pengukuran"] - out["Tarikh_Lahir"]).dt.days, np.nan)
    out["Age_Years"] = (out["Age_Days"] / 365.25).round(4)
    age_valid = out["Age_Years"].notna()
    age_bad   = age_valid & ((out["Age_Years"] < AGE_MIN_YEARS) | (out["Age_Years"] > AGE_MAX_YEARS))
    stats["invalid_age"] = int(age_bad.sum())

    # ── Measurements ──────────────────────────────────────────────────────
    out["Berat_kg"]  = pd.to_numeric(out.get("Berat_kg_Raw"),  errors="coerce").round(1)
    out["Tinggi_cm"] = pd.to_numeric(out.get("Tinggi_cm_Raw"), errors="coerce").round(1)
    stats["null_berat_original"]  = int(out["Berat_kg"].isna().sum())
    stats["null_tinggi_original"] = int(out["Tinggi_cm"].isna().sum())

    # ── BR-06: Weight range ───────────────────────────────────────────────
    berat_bad = (out["Berat_kg"] < BERAT_MIN) | (out["Berat_kg"] > BERAT_MAX)
    stats["berat_out_of_range"] = int(berat_bad.sum())
    if drop_invalid:
        out = out[~berat_bad].copy()
    else:
        out.loc[berat_bad, "Berat_kg"] = np.nan

    # ── BR-07: Height range ───────────────────────────────────────────────
    tinggi_bad = (out["Tinggi_cm"] < TINGGI_MIN) | (out["Tinggi_cm"] > TINGGI_MAX)
    stats["tinggi_out_of_range"] = int(tinggi_bad.sum())
    if drop_invalid:
        out = out[~tinggi_bad].copy()
    else:
        out.loc[tinggi_bad, "Tinggi_cm"] = np.nan

    # ── BR-13: BMI recalculation ──────────────────────────────────────────
    valid_meas = out["Berat_kg"].notna() & out["Tinggi_cm"].notna() & (out["Tinggi_cm"] > 0)
    out["BMI"] = np.where(
        valid_meas,
        (out["Berat_kg"] / ((out["Tinggi_cm"] / 100) ** 2)).round(2),
        np.nan,
    )
    out["BMI_Category"]    = out["BMI"].apply(bmi_category)
    out["Height_Category"] = out["Tinggi_cm"].apply(height_category)

    # ── Completeness flags ────────────────────────────────────────────────
    out["Has_Complete_Measurements"] = out["Berat_kg"].notna() & out["Tinggi_cm"].notna()
    out["Is_Valid_Age"]              = age_valid & ~age_bad
    out["Is_Valid_Measurement_Date"] = out["Tarikh_Pengukuran"].notna()

    # ── BR-02: Duplicate ID flag ──────────────────────────────────────────
    id_clean = out["ID_Murid"].replace({"nan": np.nan, "": np.nan})
    out["Is_Duplicate_ID"] = id_clean.duplicated(keep=False) & id_clean.notna()
    stats["duplicate_ic"] = int(out["Is_Duplicate_ID"].sum())

    # ── Composite quality flag ────────────────────────────────────────────
    out["Data_Quality_Flag"] = _build_quality_flag(out)
    stats["valid_records"]   = int((out["Data_Quality_Flag"] == "Valid").sum())
    stats["flagged_records"] = int((out["Data_Quality_Flag"] != "Valid").sum())
    stats["final_count"]     = len(out)
    stats["total_dropped"]   = stats["raw_count"] - len(out)

    return out, stats
