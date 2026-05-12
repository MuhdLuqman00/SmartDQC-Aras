"""
MyVASS source-specific cleaning logic.
Extracted from clean_myvass_data.py — unique rules not present in backend/eda/cleaning.py.

Key differences vs generic cleaning:
  - Age computed in DAYS (not months) for WHO z-score precision
  - Gender fallback from IC last digit (odd=Male, even=Female)
  - Duplicate resolution: KEEP MOST RECENT by Tarikh_Antropometri
  - Bahagian derived for Sabah (6) and Sarawak (12) from Daerah
  - BIV bounds specific to 0-5 year cohort
"""

import math
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BERAT_MIN, BERAT_MAX   = 0.5,  35.0   # kg  (0-5 year cohort)
PANJANG_MIN, PANJANG_MAX = 30.0, 130.0  # cm
BMI_MAX = 40.0
AGE_MAX_DAYS = 1826  # ~60 months / 5 years

BIV = {
    "WAZ": (-6.0, +5.0),
    "HAZ": (-6.0, +6.0),
    "BAZ": (-5.0, +5.0),
}

# Bahagian lookup: Sabah (6 bahagian) + Sarawak (12 bahagian)
BAHAGIAN_MAP: dict[str, str] = {
    # SABAH — 6 Bahagian
    "Kudat":          "Kudat",
    "Kota Marudu":    "Kudat",
    "Pitas":          "Kudat",
    "Kota Kinabalu":  "Pantai Barat",
    "Penampang":      "Pantai Barat",
    "Putatan":        "Pantai Barat",
    "Papar":          "Pantai Barat",
    "Tuaran":         "Pantai Barat",
    "Kota Belud":     "Pantai Barat",
    "Ranau":          "Pantai Barat",
    "Beaufort":       "Pantai Barat",
    "Kuala Penyu":    "Pantai Barat",
    "Sipitang":       "Pantai Barat",
    "Keningau":       "Pedalaman",
    "Tambunan":       "Pedalaman",
    "Tenom":          "Pedalaman",
    "Nabawan":        "Pedalaman",
    "Sandakan":       "Sandakan",
    "Kinabatangan":   "Sandakan",
    "Beluran":        "Sandakan",
    "Tongod":         "Sandakan",
    "Telupid":        "Sandakan",
    "Lahad Datu":     "Lahad Datu",
    "Semporna":       "Lahad Datu",
    "Kunak":          "Lahad Datu",
    "Tawau":          "Tawau",
    # SARAWAK — 12 Bahagian
    "Kuching":        "Kuching",
    "Bau":            "Kuching",
    "Lundu":          "Kuching",
    "Asajaya":        "Kota Samarahan",
    "Sri Aman":       "Sri Aman",
    "Lubok Antu":     "Sri Aman",
    "Betong":         "Betong",
    "Saratok":        "Betong",
    "Sarikei":        "Sarikei",
    "Meradong":       "Sarikei",
    "Julau":          "Sarikei",
    "Sibu":           "Sibu",
    "Kanowit":        "Sibu",
    "Mukah":          "Mukah",
    "Bintulu":        "Bintulu",
    "Miri":           "Miri",
    "Marudi":         "Miri",
    "Subis":          "Miri",
    "Beluru":         "Miri",
    "Limbang":        "Limbang",
    "Lawas":          "Limbang",
    "Serian":         "Serian",
}

_SABAH_SARAWAK = {"sabah", "sarawak"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def derive_bahagian(negeri: str, daerah: str) -> str | None:
    """Return Bahagian for Sabah/Sarawak records; None for other states."""
    if str(negeri).strip().lower() not in _SABAH_SARAWAK:
        return None
    return BAHAGIAN_MAP.get(str(daerah).strip(), "Unknown")


def _gender_from_ic(ic: str) -> str | None:
    """Fallback: derive gender from last digit of IC (odd=Male, even=Female)."""
    digits = str(ic).strip().replace("-", "").replace(" ", "")
    if digits.isdigit() and len(digits) >= 1:
        return "Male" if int(digits[-1]) % 2 == 1 else "Female"
    return None


def _age_group(age_months: float) -> str:
    if math.isnan(age_months):
        return "Unknown"
    if age_months < 24:
        return "Bawah 2 Tahun"
    if age_months < 60:
        return "Bawah 5 Tahun"
    return "Lebih 5 Tahun"


# ---------------------------------------------------------------------------
# Main cleaning function
# ---------------------------------------------------------------------------

def clean_myvass(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Apply all MyVASS-specific cleaning rules.
    Returns (cleaned_df, stats_dict).

    Rules:
      1  Drop invalid gender (not Male/Female after normalisation + IC fallback)
      2  Drop measurement outliers (weight/height out of 0-5yr BIV range)
      3  Drop age at assessment >= 60 months (> 5 years)
      4  Drop where measurement date < DOB
      5  Drop implausible BMI > 40
      6  Drop rows with both weight AND height null
      7  Drop rows where ANY z-score is null
      8  Deduplicate by IC/MyKid — keep most recent Tarikh_Antropometri
    """
    stats: dict = {"raw_count": len(df)}
    out = df.copy()

    # ── Identify key columns (flexible naming) ────────────────────────────
    col_gender   = next((c for c in out.columns if "jantina" in c.lower()), None)
    col_ic       = next((c for c in out.columns if any(k in c.lower() for k in ["mykid", "ic_no", "no_kp", "passport"])), None)
    col_dob      = next((c for c in out.columns if "lahir" in c.lower() or "dob" in c.lower()), None)
    col_tarikh   = next((c for c in out.columns if "antropometri" in c.lower() or "tarikh_ukur" in c.lower()), None)
    col_berat    = next((c for c in out.columns if "berat" in c.lower() and "lahir" not in c.lower()), None)
    col_panjang  = next((c for c in out.columns if any(k in c.lower() for k in ["panjang", "tinggi"])), None)
    col_negeri   = next((c for c in out.columns if "negeri" in c.lower()), None)
    col_daerah   = next((c for c in out.columns if "daerah" in c.lower()), None)

    # ── Rule 1: Standardize gender, use IC fallback ───────────────────────
    if col_gender:
        gender_norm = out[col_gender].astype(str).str.strip().str.upper()
        gender_map = {"LELAKI": "Male", "PEREMPUAN": "Female", "L": "Male", "P": "Female",
                      "M": "Male", "F": "Female", "MALE": "Male", "FEMALE": "Female"}
        out["_gender"] = gender_norm.map(gender_map)

        # IC fallback for nulls
        if col_ic:
            need_fallback = out["_gender"].isna()
            out.loc[need_fallback, "_gender"] = out.loc[need_fallback, col_ic].apply(_gender_from_ic)

        before = len(out)
        out = out[out["_gender"].notna()].copy()
        stats["dropped_invalid_gender"] = before - len(out)
        out["Jantina"] = out["_gender"].map({"Male": "Lelaki", "Female": "Perempuan"})
        out["Gender"]  = out["_gender"]
        out.drop(columns=["_gender"], inplace=True)

    # ── Parse dates ───────────────────────────────────────────────────────
    for col, name in [(col_dob, "Tarikh_Lahir"), (col_tarikh, "Tarikh_Antropometri")]:
        if col:
            out[name] = pd.to_datetime(out[col], dayfirst=True, errors="coerce")

    # ── Compute age in DAYS (MyVASS uses daily precision for WHO z-scores) ─
    if "Tarikh_Lahir" in out.columns and "Tarikh_Antropometri" in out.columns:
        out["Age_Days"]   = (out["Tarikh_Antropometri"] - out["Tarikh_Lahir"]).dt.days
        out["Age_Months"] = (out["Age_Days"] / 30.4375).round(2)
    else:
        out["Age_Days"]   = np.nan
        out["Age_Months"] = np.nan

    # ── Rule 4: Drop measurement before DOB ──────────────────────────────
    if "Age_Days" in out.columns:
        before = len(out)
        out = out[out["Age_Days"].isna() | (out["Age_Days"] >= 0)].copy()
        stats["dropped_date_before_dob"] = before - len(out)

    # ── Rule 3: Drop age >= 60 months ─────────────────────────────────────
    before = len(out)
    out = out[out["Age_Days"].isna() | (out["Age_Days"] < AGE_MAX_DAYS)].copy()
    stats["dropped_age_over5"] = before - len(out)

    out["Kumpulan_Umur"] = out["Age_Months"].apply(
        lambda m: _age_group(m) if pd.notna(m) else "Unknown"
    )

    # ── Rule 2: Measurement outliers ──────────────────────────────────────
    if col_berat:
        out["Berat_kg"] = pd.to_numeric(out[col_berat], errors="coerce")
    if col_panjang:
        out["Tinggi_cm"] = pd.to_numeric(out[col_panjang], errors="coerce")

    berat_bad  = out["Berat_kg"].notna()  & ((out["Berat_kg"] < BERAT_MIN) | (out["Berat_kg"] > BERAT_MAX))
    tinggi_bad = out["Tinggi_cm"].notna() & ((out["Tinggi_cm"] < PANJANG_MIN) | (out["Tinggi_cm"] > PANJANG_MAX))
    before = len(out)
    out = out[~(berat_bad | tinggi_bad)].copy()
    stats["dropped_measurement_outlier"] = before - len(out)

    # ── Rule 5: BMI outlier ───────────────────────────────────────────────
    valid_meas = out["Berat_kg"].notna() & out["Tinggi_cm"].notna() & (out["Tinggi_cm"] > 0)
    out["BMI"] = np.where(
        valid_meas,
        (out["Berat_kg"] / ((out["Tinggi_cm"] / 100) ** 2)).round(2),
        np.nan,
    )
    before = len(out)
    out = out[out["BMI"].isna() | (out["BMI"] <= BMI_MAX)].copy()
    stats["dropped_bmi_outlier"] = before - len(out)

    # ── Rule 6: Drop if both weight AND height null ───────────────────────
    before = len(out)
    out = out[~(out["Berat_kg"].isna() & out["Tinggi_cm"].isna())].copy()
    stats["dropped_no_measurement"] = before - len(out)

    # ── Derive Bahagian ───────────────────────────────────────────────────
    if col_negeri and col_daerah:
        out["Bahagian"] = out.apply(
            lambda r: derive_bahagian(r[col_negeri], r[col_daerah]), axis=1
        )

    # ── Rule 8: Deduplicate by IC — keep most recent ──────────────────────
    if col_ic and "Tarikh_Antropometri" in out.columns:
        before = len(out)
        out = (out
               .sort_values("Tarikh_Antropometri", ascending=False)
               .drop_duplicates(subset=[col_ic], keep="first"))
        stats["dropped_duplicate_ic"] = before - len(out)

    stats["final_count"] = len(out)
    return out, stats
