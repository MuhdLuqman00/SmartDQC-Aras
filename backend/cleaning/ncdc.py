"""
NCDC (TASKA) source-specific cleaning logic.
Extracted from clean_ncdc_data_v2.py — unique rules not present in backend/eda/cleaning.py.

Key differences vs generic cleaning:
  - Multi-sheet WIDE-to-LONG reshape (year columns per sheet)
  - Data owner clarifications Q-01 through Q-08
  - Three-tier age groups: Bawah 2 Tahun / 2-5 Tahun / Lebih 5 Tahun
  - Duplicate resolution: KEEP MOST RECENT (by Tarikh_Pengukuran)
  - Bahagian derived for Sabah (6) and Sarawak (12) from Daerah
  - Pendapatan: P20 renamed to Miskin Tegar; Pendapatan X excluded
"""

import math
import pandas as pd
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BERAT_MIN, BERAT_MAX   = 0.5,  35.0   # kg
TINGGI_MIN, TINGGI_MAX = 30.0, 130.0  # cm
BMI_MAX = 40.0
AGE_MAX_MONTHS = 60

BIV = {
    "WAZ": (-6.0, +5.0),
    "HAZ": (-6.0, +6.0),
    "BAZ": (-5.0, +5.0),
}

GENDER_MAP = {
    "LELAKI": "Male", "PEREMPUAN": "Female",
    "L": "Male", "P": "Female",
    "M": "Male", "F": "Female",
    "MALE": "Male", "FEMALE": "Female",
}

# Q-03: P20 → Miskin Tegar
PENDAPATAN_MAP = {
    "B40": "B40", "M40": "M40", "T20": "T20",
    "P20": "Miskin Tegar",
}

# Sabah — 6 Bahagian
SABAH_BAHAGIAN: dict[str, str] = {
    "KOTA KINABALU": "Pantai Barat", "PENAMPANG": "Pantai Barat", "PUTATAN": "Pantai Barat",
    "PAPAR": "Pantai Barat", "TUARAN": "Pantai Barat", "KOTA BELUD": "Pantai Barat",
    "RANAU": "Pedalaman", "KUNDASANG": "Pedalaman", "TAMBUNAN": "Pedalaman",
    "KENINGAU": "Pedalaman", "TENOM": "Pedalaman", "NABAWAN": "Pedalaman",
    "SOOK": "Pedalaman", "KEMABONG": "Pedalaman",
    "KUDAT": "Kudat", "KOTA MARUDU": "Kudat", "PITAS": "Kudat", "MATUNGGONG": "Kudat",
    "SANDAKAN": "Sandakan", "KINABATANGAN": "Sandakan", "BELURAN": "Sandakan",
    "TONGOD": "Sandakan", "TELUPID": "Sandakan",
    "TAWAU": "Tawau", "LAHAD DATU": "Tawau", "SEMPORNA": "Tawau", "KUNAK": "Tawau",
    "BEAUFORT": "Beaufort", "KUALA PENYU": "Beaufort", "SIPITANG": "Beaufort", "MEMBAKUT": "Beaufort",
}

# Sarawak — 12 Bahagian
SARAWAK_BAHAGIAN: dict[str, str] = {
    "KUCHING": "Kuching", "BAU": "Kuching", "LUNDU": "Kuching", "PADAWAN": "Kuching",
    "KOTA SAMARAHAN": "Samarahan", "SAMARAHAN": "Samarahan", "ASAJAYA": "Samarahan", "SIMUNJAN": "Samarahan",
    "SERIAN": "Serian", "TEBEDU": "Serian",
    "SRI AMAN": "Sri Aman", "LUBOK ANTU": "Sri Aman", "ENGKILILI": "Sri Aman",
    "BETONG": "Betong", "PUSA": "Betong", "SARATOK": "Betong", "KABONG": "Betong",
    "SARIKEI": "Sarikei", "JULAU": "Sarikei", "MERADONG": "Sarikei", "PAKAN": "Sarikei",
    "SIBU": "Sibu", "SELANGAU": "Sibu", "KANOWIT": "Sibu",
    "MUKAH": "Mukah", "DALAT": "Mukah", "DARO": "Mukah", "MATU": "Mukah", "TANJUNG MANIS": "Mukah",
    "KAPIT": "Kapit", "SONG": "Kapit", "BELAGA": "Kapit", "BUKIT MABONG": "Kapit",
    "BINTULU": "Bintulu", "SEBAUH": "Bintulu", "TATAU": "Bintulu",
    "MIRI": "Miri", "MARUDI": "Miri", "SUBIS": "Miri", "TELANG USAN": "Miri", "BELURU": "Miri",
    "LIMBANG": "Limbang", "LAWAS": "Limbang",
}

_YEARS_TO_EXTRACT = [2023, 2024, 2025]

_BASE_COL_MAP = {
    "Agensi": "Agensi",
    "Negeri": "Negeri",
    "Daerah": "Daerah",
    "Nama TASKA": "Nama_Taska",
    "Nama Anak": "Nama_Anak",
    "No. Mykid": "MyKid",
    "Pendapatan Keluarga": "Pendapatan_Keluarga",
    "Kumpulan Umur": "Kumpulan_Umur_Source",
    "Tarikh Lahir": "Tarikh_Lahir",
    "Jantina": "Jantina_Raw",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_bahagian(negeri: str, daerah: str) -> str | None:
    """Derive Bahagian from Negeri + Daerah. Returns None for peninsular states."""
    n = str(negeri).upper().strip()
    d = str(daerah).upper().strip()
    if n == "SABAH":
        return SABAH_BAHAGIAN.get(d, "Unknown")
    if n == "SARAWAK":
        return SARAWAK_BAHAGIAN.get(d, "Unknown")
    return None


def get_age_group(age_months: float) -> str:
    """Three-tier NCDC age groups."""
    if age_months is None or (isinstance(age_months, float) and math.isnan(age_months)):
        return "Unknown"
    if age_months < 24:
        return "Bawah 2 Tahun"
    if age_months < 60:
        return "2-5 Tahun"
    return "Lebih 5 Tahun"


# ---------------------------------------------------------------------------
# WIDE-to-LONG reshape
# ---------------------------------------------------------------------------

def load_ncdc_all_years(file_path: Path) -> pd.DataFrame:
    """
    Load multi-sheet NCDC Excel file and reshape WIDE -> LONG.
    Each sheet = one Negeri. Year columns: "YYYY Berat (kg)", "YYYY Tinggi (cm)", "YYYY Tarikh Pengukuran".
    One row per child per year with measurements.
    """
    xl = pd.ExcelFile(file_path)
    all_frames = []

    for sheet_name in xl.sheet_names:
        df_sheet = xl.parse(sheet_name)
        if df_sheet.empty:
            continue
        df_sheet.columns = df_sheet.columns.str.strip()

        # Detect year-specific columns
        year_cols: dict[int, dict] = {}
        for year in _YEARS_TO_EXTRACT:
            year_cols[year] = {"berat": None, "tinggi": None, "tarikh": None}
            for col in df_sheet.columns:
                s = str(col)
                if s.startswith(str(year)):
                    low = s.lower()
                    if "berat" in low and "status" not in low:
                        year_cols[year]["berat"] = col
                    elif "tinggi" in low and "status" not in low:
                        year_cols[year]["tinggi"] = col
                    elif "tarikh" in low:
                        year_cols[year]["tarikh"] = col

        sheet_records = []
        for _, row in df_sheet.iterrows():
            base = {dst: row[src] for src, dst in _BASE_COL_MAP.items() if src in df_sheet.columns}
            for year in _YEARS_TO_EXTRACT:
                cols = year_cols[year]
                berat_val  = row[cols["berat"]]  if cols["berat"]  else None
                tinggi_val = row[cols["tinggi"]] if cols["tinggi"] else None
                tarikh_val = row[cols["tarikh"]] if cols["tarikh"] else None
                has_berat  = pd.notna(berat_val)  and berat_val  not in ("", 0)
                has_tinggi = pd.notna(tinggi_val) and tinggi_val not in ("", 0)
                if not has_berat and not has_tinggi:
                    continue
                rec = {**base, "Year": year}
                if has_berat:  rec["Berat_kg"]  = berat_val
                if has_tinggi: rec["Tinggi_cm"] = tinggi_val
                rec["Tarikh_Pengukuran"] = str(tarikh_val) if pd.notna(tarikh_val) else f"{year}-12-31"
                sheet_records.append(rec)

        if sheet_records:
            all_frames.append(pd.DataFrame(sheet_records))

    if not all_frames:
        raise ValueError("No NCDC records found. Check column names in the Excel file.")
    return pd.concat(all_frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Main cleaning function
# ---------------------------------------------------------------------------

def clean_ncdc(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Apply all NCDC-specific cleaning rules including data owner clarifications.
    Returns (cleaned_df, stats_dict).

    Rules:
      1  Drop invalid gender
      2  Drop measurement outliers (0-5yr BIV range)
      3  Drop age >= 60 months (Q-05)
      4  Drop measurement date < DOB
      5  Drop implausible BMI > 40
      6  Drop both weight AND height null
      7  Drop rows where ANY z-score null
      8  Deduplicate by MyKid — keep most recent (Q-07, Q-08)
      9  Exclude Pendapatan = 'X' (Q-02)
      Q03 Rename P20 -> Miskin Tegar
    """
    stats: dict = {"raw_count": len(raw)}
    df = raw.copy()

    # ── Rule 1: Gender ────────────────────────────────────────────────────
    df["Jantina_Raw"] = df["Jantina_Raw"].astype(str).str.upper().str.strip()
    df["Gender"] = df["Jantina_Raw"].map(GENDER_MAP)
    before = len(df)
    df = df[df["Gender"].notna()].copy()
    stats["dropped_invalid_gender"] = before - len(df)
    df["Jantina"] = df["Gender"].map({"Male": "Lelaki", "Female": "Perempuan"})

    # ── Rule 9 (Q-02): Exclude Pendapatan = 'X' ──────────────────────────
    if "Pendapatan_Keluarga" in df.columns:
        df["Pendapatan_Keluarga"] = df["Pendapatan_Keluarga"].astype(str).str.upper().str.strip()
        before = len(df)
        df = df[df["Pendapatan_Keluarga"] != "X"].copy()
        stats["dropped_pendapatan_x"] = before - len(df)
        # Q-03: P20 -> Miskin Tegar
        df["Pendapatan_Keluarga"] = df["Pendapatan_Keluarga"].map(lambda x: PENDAPATAN_MAP.get(x, x))

    # ── Standardize text ──────────────────────────────────────────────────
    for col in ["Negeri", "Daerah", "Agensi"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.upper().str.strip()

    # ── Derive Bahagian ───────────────────────────────────────────────────
    if "Negeri" in df.columns and "Daerah" in df.columns:
        df["Bahagian"] = df.apply(lambda r: get_bahagian(r["Negeri"], r["Daerah"]), axis=1)

    # ── Parse dates ───────────────────────────────────────────────────────
    df["Tarikh_Lahir"]       = pd.to_datetime(df["Tarikh_Lahir"],       dayfirst=True, errors="coerce")
    df["Tarikh_Pengukuran"]  = pd.to_datetime(df["Tarikh_Pengukuran"],  dayfirst=True, errors="coerce")
    df["Tarikh_Lahir"]      = df["Tarikh_Lahir"].dt.normalize()
    df["Tarikh_Pengukuran"] = df["Tarikh_Pengukuran"].dt.normalize()

    before = len(df)
    df = df[df["Tarikh_Lahir"].notna()].copy()
    stats["dropped_null_dob"] = before - len(df)

    # ── Rule 4: measurement before DOB ───────────────────────────────────
    before = len(df)
    df = df[~(df["Tarikh_Pengukuran"] < df["Tarikh_Lahir"])].copy()
    stats["dropped_date_before_dob"] = before - len(df)

    # ── Age in days + months ──────────────────────────────────────────────
    df["Age_Days"]   = (df["Tarikh_Pengukuran"] - df["Tarikh_Lahir"]).dt.days
    df["Age_Months"] = (df["Age_Days"] / 30.4375).round(2)

    # ── Rule 3 (Q-05): Drop age >= 60 months ─────────────────────────────
    before = len(df)
    df = df[(df["Age_Days"] >= 0) & (df["Age_Months"] < AGE_MAX_MONTHS)].copy()
    stats["dropped_age_invalid"] = before - len(df)

    df["Kumpulan_Umur"] = df["Age_Months"].apply(get_age_group)

    # ── Numeric measurements ──────────────────────────────────────────────
    df["Berat_kg"]  = pd.to_numeric(df.get("Berat_kg"),  errors="coerce")
    df["Tinggi_cm"] = pd.to_numeric(df.get("Tinggi_cm"), errors="coerce")

    # ── Rule 2: Measurement outliers ─────────────────────────────────────
    berat_bad  = df["Berat_kg"].notna()  & ((df["Berat_kg"]  < BERAT_MIN)  | (df["Berat_kg"]  > BERAT_MAX))
    tinggi_bad = df["Tinggi_cm"].notna() & ((df["Tinggi_cm"] < TINGGI_MIN) | (df["Tinggi_cm"] > TINGGI_MAX))
    before = len(df)
    df = df[~(berat_bad | tinggi_bad)].copy()
    stats["dropped_measurement_outlier"] = before - len(df)

    # ── Rule 5: BMI outlier ───────────────────────────────────────────────
    valid_meas = df["Berat_kg"].notna() & df["Tinggi_cm"].notna() & (df["Tinggi_cm"] > 0)
    df["BMI"] = np.where(valid_meas, (df["Berat_kg"] / ((df["Tinggi_cm"] / 100) ** 2)).round(2), np.nan)
    before = len(df)
    df = df[df["BMI"].isna() | (df["BMI"] <= BMI_MAX)].copy()
    stats["dropped_bmi_outlier"] = before - len(df)

    # ── Rule 6: Both measurements null ───────────────────────────────────
    before = len(df)
    df = df[~(df["Berat_kg"].isna() & df["Tinggi_cm"].isna())].copy()
    stats["dropped_no_measurement"] = before - len(df)

    # ── Rule 8 (Q-07, Q-08): Deduplicate MyKid — keep most recent ────────
    if "MyKid" in df.columns:
        before = len(df)
        df = (df
              .sort_values("Tarikh_Pengukuran", ascending=False)
              .drop_duplicates(subset=["MyKid"], keep="first"))
        stats["dropped_duplicate_mykid"] = before - len(df)

    stats["final_count"] = len(df)
    return df, stats
