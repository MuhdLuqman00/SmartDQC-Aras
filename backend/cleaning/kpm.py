"""
KPM (school-age) source-specific cleaning logic.
Extracted from clean_kpm_data_v2.py — unique rules not present in backend/eda/cleaning.py.

Key differences vs generic cleaning:
  - Only HAZ and BAZ computed — WAZ NOT used for school-age children (WHO guidelines)
  - Tahun Satu filter: only Tahun 1 students (with common variant spellings)
  - Age range: 6-8 years (72-96 months), not 0-5 like NCDC/MyVASS
  - Weight/height bounds are school-age (12-50 kg, 100-160 cm)
  - Duplicate resolution: KEEP FIRST occurrence (not most recent)
  - 2024 data: measurement dates set to 31/12/2024 per data owner clarification
"""

import math
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BERAT_MIN, BERAT_MAX   = 12.0,  50.0  # kg (school-age 6-8yr)
TINGGI_MIN, TINGGI_MAX = 100.0, 160.0  # cm
BMI_MAX = 40.0
AGE_MIN_MONTHS = 72   # 6 years
AGE_MAX_MONTHS = 96   # 8 years

# KPM uses HAZ and BAZ ONLY — no WAZ for school-age per WHO guidelines
BIV = {
    "HAZ": (-6.0, +6.0),
    "BAZ": (-5.0, +5.0),
}

GENDER_MAP = {
    "LELAKI": "Male", "PEREMPUAN": "Female",
    "L": "Male", "P": "Female",
    "MALE": "Male", "FEMALE": "Female",
}

# Accepted Tahun Satu values (normalised to upper)
VALID_THN_TING = {
    "TAHUN SATU", "TAHUN 1", "1",
    "TAHUN 1A", "TAHUN 1B", "TAHUN 1C", "TAHUN 1D", "TAHUN 1E",
}

VALID_NEGERI = {
    "JOHOR", "KEDAH", "KELANTAN", "MELAKA", "NEGERI SEMBILAN",
    "PAHANG", "PERAK", "PERLIS", "PULAU PINANG", "SABAH",
    "SARAWAK", "SELANGOR", "TERENGGANU",
    "WP KUALA LUMPUR", "WP LABUAN", "WP PUTRAJAYA",
    "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WILAYAH PERSEKUTUAN LABUAN",
    "WILAYAH PERSEKUTUAN PUTRAJAYA",
}


# ---------------------------------------------------------------------------
# Label functions
# ---------------------------------------------------------------------------

def _haz_label(z) -> str | None:
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return None
    if z < -3: return "Bantut Teruk"
    if z < -2: return "Bantut"
    if z <= 3: return "Tinggi Normal"
    return "Mungkin Masalah Endokrin"


def _baz_label(z) -> str | None:
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return None
    if z < -3: return "Kurus Teruk"
    if z < -2: return "Kurus"
    if z <= 1: return "Berat Badan Normal"
    if z <= 2: return "Berisiko Berlebihan Berat Badan"
    if z <= 3: return "Berlebihan Berat Badan"
    return "Obes"


# ---------------------------------------------------------------------------
# Main cleaning function
# ---------------------------------------------------------------------------

def clean_kpm(df: pd.DataFrame, year: int) -> tuple[pd.DataFrame, dict]:
    """
    Apply all KPM-specific cleaning rules.
    Returns (cleaned_df, stats_dict).

    Rules:
      1  Drop RAGU and invalid gender
      2  Drop non-Tahun Satu (THN_TING filter)
      3  Drop measurement outliers (school-age bounds)
      4  Drop age outside 6-8 years
      5  Drop implausible BMI > 40
      6  Drop both weight AND height null
      7  Deduplicate ID_MURID — keep FIRST occurrence
      8  Drop rows where any z-score null (enforces complete output)
    Special: 2024 dates set to 31/12/2024
    """
    stats: dict = {"raw_count": len(df), "year": year}
    out = df.copy()

    # ── Normalise column names ────────────────────────────────────────────
    out.columns = out.columns.str.replace(r"\s+", " ", regex=True).str.strip()

    # ── Rename to standard names ──────────────────────────────────────────
    rename_map = {
        "TAHUN PERSEKOLAHAN":              "Tahun_Persekolahan",
        "NEGERI":                          "Negeri",
        "DAERAH":                          "Daerah",
        "NAMA SEKOLAH":                    "Nama_Sekolah",
        "LOKASI (BANDAR/LUAR BANDAR)":     "Lokasi",
        "JENIS SEKOLAH":                   "Jenis_Sekolah",
        "THN_TING":                        "Thn_Ting",
        "JANTINA":                         "Jantina_Raw",
        "ID_MURID":                        "ID_Murid",
        "TARIKH LAHIR":                    "Tarikh_Lahir",
        "TARIKH PENGUKURAN BERAT/ TINGGI": "Tarikh_Pengukuran",
        "BERAT (kg)":                      "Berat_kg",
        "TINGGI (cm)":                     "Tinggi_cm",
    }
    out = out.rename(columns={k: v for k, v in rename_map.items() if k in out.columns})
    out["Year"] = year

    # ── Text normalisation ────────────────────────────────────────────────
    for col in ["Negeri", "Daerah", "Jenis_Sekolah", "Thn_Ting", "Lokasi"]:
        if col in out.columns:
            out[col] = out[col].astype(str).str.upper().str.strip()
    for col in ["Nama_Sekolah", "ID_Murid"]:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip()

    # ── Rule 1: Gender ────────────────────────────────────────────────────
    out["Jantina_Raw"] = out["Jantina_Raw"].astype(str).str.upper().str.strip()
    out["Gender"] = out["Jantina_Raw"].map(GENDER_MAP)
    ragu_mask    = out["Jantina_Raw"] == "RAGU"
    invalid_mask = out["Gender"].isna()
    stats["dropped_ragu_gender"]    = int(ragu_mask.sum())
    stats["dropped_invalid_gender"] = int((invalid_mask & ~ragu_mask).sum())
    out = out[~(invalid_mask | ragu_mask)].copy()
    out["Jantina"] = out["Gender"].map({"Male": "Lelaki", "Female": "Perempuan"})

    # ── Rule 2: Tahun Satu filter ─────────────────────────────────────────
    before = len(out)
    tahun_mask = out["Thn_Ting"].isin(VALID_THN_TING)
    stats["dropped_non_tahun_satu"] = int((~tahun_mask).sum())
    stats["non_tahun_satu_values"]  = out.loc[~tahun_mask, "Thn_Ting"].value_counts().to_dict()
    out = out[tahun_mask].copy()

    # ── Rule 7: Deduplicate ID_MURID — keep FIRST ─────────────────────────
    before = len(out)
    out = out.drop_duplicates(subset=["ID_Murid"], keep="first")
    stats["dropped_duplicate_id"] = before - len(out)

    # ── Parse dates ───────────────────────────────────────────────────────
    out["Tarikh_Lahir"]      = pd.to_datetime(out["Tarikh_Lahir"],      dayfirst=True, errors="coerce")
    out["Tarikh_Pengukuran"] = pd.to_datetime(out["Tarikh_Pengukuran"], dayfirst=True, errors="coerce")

    # Special: 2024 — set all measurement dates to 31/12/2024
    if year == 2024:
        out["Tarikh_Pengukuran"] = pd.Timestamp("2024-12-31")
        stats["standardized_to_31dec2024"] = len(out)

    # ── Age at measurement (years) ────────────────────────────────────────
    has_both = out["Tarikh_Lahir"].notna() & out["Tarikh_Pengukuran"].notna()
    out["Age_Days"] = np.where(
        has_both,
        (out["Tarikh_Pengukuran"] - out["Tarikh_Lahir"]).dt.days,
        np.nan,
    )
    out["Age_Years"]  = (out["Age_Days"] / 365.25).round(4)
    out["Age_Months"] = (out["Age_Days"] / 30.4375).round(2)

    # ── Rule 4: Age outside 6-8 years ────────────────────────────────────
    age_valid = out["Age_Months"].notna()
    age_bad   = age_valid & ((out["Age_Months"] < AGE_MIN_MONTHS) | (out["Age_Months"] > AGE_MAX_MONTHS))
    stats["invalid_age"] = int(age_bad.sum())

    # ── Numeric measurements ──────────────────────────────────────────────
    out["Berat_kg"]  = pd.to_numeric(out.get("Berat_kg"),  errors="coerce")
    out["Tinggi_cm"] = pd.to_numeric(out.get("Tinggi_cm"), errors="coerce")

    # ── Rule 3: Measurement outliers (school-age bounds) ─────────────────
    berat_bad  = out["Berat_kg"].notna()  & ((out["Berat_kg"]  < BERAT_MIN)  | (out["Berat_kg"]  > BERAT_MAX))
    tinggi_bad = out["Tinggi_cm"].notna() & ((out["Tinggi_cm"] < TINGGI_MIN) | (out["Tinggi_cm"] > TINGGI_MAX))
    before = len(out)
    out = out[~(berat_bad | tinggi_bad)].copy()
    stats["dropped_measurement_outlier"] = before - len(out)

    # ── Rule 5: BMI outlier ───────────────────────────────────────────────
    valid_meas = out["Berat_kg"].notna() & out["Tinggi_cm"].notna() & (out["Tinggi_cm"] > 0)
    out["BMI"] = np.where(valid_meas, (out["Berat_kg"] / ((out["Tinggi_cm"] / 100) ** 2)).round(2), np.nan)
    before = len(out)
    out = out[out["BMI"].isna() | (out["BMI"] <= BMI_MAX)].copy()
    stats["dropped_bmi_outlier"] = before - len(out)

    # ── Rule 6: Both measurements null ───────────────────────────────────
    before = len(out)
    out = out[~(out["Berat_kg"].isna() & out["Tinggi_cm"].isna())].copy()
    stats["dropped_no_measurement"] = before - len(out)

    # ── Lokasi mapping ────────────────────────────────────────────────────
    if "Lokasi" in out.columns:
        lokasi_map = {"BANDAR": "Urban", "LUAR BANDAR": "Rural"}
        out["Lokasi_EN"] = out["Lokasi"].map(lokasi_map).fillna("Unknown")

    stats["final_count"] = len(out)
    return out, stats
