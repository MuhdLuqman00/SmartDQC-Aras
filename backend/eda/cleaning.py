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
    """Try multiple date formats."""
    return pd.to_datetime(series, dayfirst=True, errors="coerce")


# ═══════════════════════════════════════════════════════════════════════════════
# MYVASS CLEANING
# ═══════════════════════════════════════════════════════════════════════════════

def clean_myvass(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean MyVASS data and compute WHO z-scores.
    
    Returns:
        tuple: (cleaned_dataframe, statistics_dict)
    """
    stats = {"raw_count": len(df), "data_type": "myvass"}
    df = df.copy()
    
    # Normalize column names
    df.columns = df.columns.str.strip()
    
    # Find key columns (case-insensitive)
    def find_col(patterns):
        for col in df.columns:
            for p in patterns:
                if p.lower() in col.lower():
                    return col
        return None
    
    gender_col = find_col(["jantina", "gender", "sex"])
    dob_col = find_col(["tarikh lahir", "dob", "date_of_birth", "birth"])
    weight_col = find_col(["berat", "weight"])
    height_col = find_col(["panjang", "tinggi", "height", "length"])
    measure_date_col = find_col(["tarikh antropometri", "tarikh ukur", "measurement date", "dose_date"])
    state_col = find_col(["negeri", "state"])
    
    # Rule 1: Standardize and filter gender
    if gender_col:
        df["Gender"] = df[gender_col].astype(str).str.upper().str.strip().map(GENDER_MAP)
        before = len(df)
        df = df[df["Gender"].notna()].copy()
        stats["dropped_invalid_gender"] = before - len(df)
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
    
    # Rule 4: Drop where measurement < DOB
    before = len(df)
    bad_date = (df["Tarikh_Lahir"].notna() & 
                df["Tarikh_Ukur"].notna() & 
                (df["Tarikh_Ukur"] < df["Tarikh_Lahir"]))
    stats["dropped_date_before_dob"] = int(bad_date.sum())
    df = df[~bad_date].copy()
    
    # Compute age in days
    has_both_dates = df["Tarikh_Lahir"].notna() & df["Tarikh_Ukur"].notna()
    df["Age_Days"] = np.where(
        has_both_dates,
        (df["Tarikh_Ukur"] - df["Tarikh_Lahir"]).dt.days,
        np.nan
    )
    df["Age_Months"] = (df["Age_Days"] / 30.4375).round(2)
    
    # Rule 3: Drop age >= 60 months
    before = len(df)
    age_invalid = df["Age_Months"].notna() & (df["Age_Months"] >= AGE_MAX_MONTHS_INFANT)
    stats["dropped_age_over5"] = int(age_invalid.sum())
    df = df[~age_invalid].copy()
    
    # Convert measurements to numeric
    if weight_col:
        df["Berat_kg"] = pd.to_numeric(df[weight_col], errors="coerce")
    else:
        df["Berat_kg"] = np.nan
        
    if height_col:
        df["Tinggi_cm"] = pd.to_numeric(df[height_col], errors="coerce")
    else:
        df["Tinggi_cm"] = np.nan
    
    # Rule 2: Drop measurement outliers
    berat_bad = (df["Berat_kg"] < BERAT_MIN_INFANT) | (df["Berat_kg"] > BERAT_MAX_INFANT)
    tinggi_bad = (df["Tinggi_cm"] < TINGGI_MIN_INFANT) | (df["Tinggi_cm"] > TINGGI_MAX_INFANT)
    
    outlier_mask = (berat_bad & df["Berat_kg"].notna()) | (tinggi_bad & df["Tinggi_cm"].notna())
    stats["dropped_measurement_outlier"] = int(outlier_mask.sum())
    df = df[~outlier_mask].copy()
    
    # Rule 6: Drop rows with both measurements null
    before = len(df)
    no_meas = df["Berat_kg"].isna() & df["Tinggi_cm"].isna()
    stats["dropped_no_measurement"] = int(no_meas.sum())
    df = df[~no_meas].copy()
    
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
    
    # Rule 5: Drop implausible BMI > 40
    before = len(df)
    bmi_bad = df["BMI"].notna() & (df["BMI"] > BMI_MAX)
    stats["dropped_bmi_outlier"] = int(bmi_bad.sum())
    df = df[~bmi_bad].copy()
    
    # Calculate WHO Z-scores (using daily LMS tables from Excel)
    if ZSCORE_AVAILABLE:
        df["WAZ"] = None
        df["HAZ"] = None
        df["BAZ"] = None
        
        for idx in df.index:
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
        
        # Rule 7: Drop rows with null z-scores
        before = len(df)
        null_zscore = df["WAZ"].isna() | df["HAZ"].isna() | df["BAZ"].isna()
        stats["dropped_null_zscore"] = int(null_zscore.sum())
        df = df[~null_zscore].copy()
        
        # Normal indicator
        df["Ind_Normal"] = ~(df["Ind_Kurang_Berat_Badan"] | df["Ind_Bantut"] | df["Ind_Susut"])
        
        stats["ind_kurang_berat"] = int(df["Ind_Kurang_Berat_Badan"].sum())
        stats["ind_bantut"] = int(df["Ind_Bantut"].sum())
        stats["ind_susut"] = int(df["Ind_Susut"].sum())
        stats["ind_berlebihan_bb"] = int(df["Ind_Berlebihan_BB"].sum())
        stats["ind_obes"] = int(df["Ind_Obes"].sum())
        stats["ind_normal"] = int(df["Ind_Normal"].sum())
    else:
        stats["dropped_null_zscore"] = 0
    
    # Age category column
    if "Age_Days" in df.columns:
        df["Kategori_Umur"] = np.where(
            df["Age_Days"] < 730, "Bawah 2 Tahun",
            np.where(df["Age_Days"] < 1826, "Bawah 5 Tahun", "5 Tahun ke Atas")
        )
    
    # Final stats
    stats["final_count"] = len(df)
    stats["total_dropped"] = stats["raw_count"] - stats["final_count"]
    
    # Gender breakdown
    if "Gender" in df.columns:
        gender_counts = df["Gender"].value_counts().to_dict()
        stats["gender_male"] = gender_counts.get("Male", 0)
        stats["gender_female"] = gender_counts.get("Female", 0)
    
    return df, stats


# ═══════════════════════════════════════════════════════════════════════════════
# NCDC CLEANING
# ═══════════════════════════════════════════════════════════════════════════════

def clean_ncdc(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean NCDC (TASKA) data and compute WHO z-scores.
    
    Returns:
        tuple: (cleaned_dataframe, statistics_dict)
    """
    stats = {"raw_count": len(df), "data_type": "ncdc"}
    df = df.copy()
    
    # Normalize column names
    df.columns = df.columns.str.strip()
    
    # Find key columns
    def find_col(patterns):
        for col in df.columns:
            for p in patterns:
                if p.lower() in col.lower():
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
    
    # Reshape wide to long if year columns exist
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
        stats["years_found"] = years
    else:
        df["Year"] = None
    
    # Rule 1: Standardize and filter gender
    if gender_col:
        df["Gender"] = df[gender_col].astype(str).str.upper().str.strip().map(GENDER_MAP)
        before = len(df)
        df = df[df["Gender"].notna()].copy()
        stats["dropped_invalid_gender"] = before - len(df)
    else:
        df["Gender"] = None
        stats["dropped_invalid_gender"] = 0
    
    # Rule 9: Exclude Pendapatan = 'X'
    if income_col:
        before = len(df)
        pendapatan_x = df[income_col].astype(str).str.upper().str.strip() == "X"
        stats["dropped_pendapatan_x"] = int(pendapatan_x.sum())
        df = df[~pendapatan_x].copy()
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
    
    # Drop null DOB
    before = len(df)
    df = df[df["Tarikh_Lahir"].notna()].copy()
    stats["dropped_null_dob"] = before - len(df)
    
    # Rule 4: Drop where measurement < DOB
    before = len(df)
    bad_date = (df["Tarikh_Lahir"].notna() & 
                df["Tarikh_Pengukuran"].notna() & 
                (df["Tarikh_Pengukuran"] < df["Tarikh_Lahir"]))
    stats["dropped_date_before_dob"] = int(bad_date.sum())
    df = df[~bad_date].copy()
    
    # Compute age
    has_both = df["Tarikh_Lahir"].notna() & df["Tarikh_Pengukuran"].notna()
    df["Age_Days"] = np.where(has_both, (df["Tarikh_Pengukuran"] - df["Tarikh_Lahir"]).dt.days, np.nan)
    df["Age_Months"] = (df["Age_Days"] / 30.4375).round(2)
    
    # Rule 3: Drop age >= 60 months
    before = len(df)
    age_invalid = (df["Age_Days"] < 0) | (df["Age_Months"] >= AGE_MAX_MONTHS_INFANT)
    stats["dropped_age_invalid"] = int((age_invalid & df["Age_Months"].notna()).sum())
    df = df[~(age_invalid & df["Age_Months"].notna())].copy()
    
    # Convert measurements
    df["Berat_kg"] = pd.to_numeric(df.get("Berat_kg"), errors="coerce")
    df["Tinggi_cm"] = pd.to_numeric(df.get("Tinggi_cm"), errors="coerce")
    
    # Rule 2: Drop measurement outliers
    berat_bad = (df["Berat_kg"] < BERAT_MIN_INFANT) | (df["Berat_kg"] > BERAT_MAX_INFANT)
    tinggi_bad = (df["Tinggi_cm"] < TINGGI_MIN_INFANT) | (df["Tinggi_cm"] > TINGGI_MAX_INFANT)
    
    outlier_mask = (berat_bad & df["Berat_kg"].notna()) | (tinggi_bad & df["Tinggi_cm"].notna())
    stats["dropped_measurement_outlier"] = int(outlier_mask.sum())
    df = df[~outlier_mask].copy()
    
    # Rule 6: Drop no measurements
    before = len(df)
    no_meas = df["Berat_kg"].isna() & df["Tinggi_cm"].isna()
    stats["dropped_no_measurement"] = int(no_meas.sum())
    df = df[~no_meas].copy()
    
    # Drop raw BMI column from source — will recalculate
    raw_bmi_cols = [c for c in df.columns if "bmi" in c.lower() and c != "BMI"]
    if raw_bmi_cols:
        df = df.drop(columns=raw_bmi_cols)
    
    # Calculate BMI from weight and height
    valid_both = df["Berat_kg"].notna() & df["Tinggi_cm"].notna() & (df["Tinggi_cm"] > 0)
    df["BMI"] = np.where(valid_both, (df["Berat_kg"] / ((df["Tinggi_cm"] / 100) ** 2)).round(2), np.nan)
    
    # Rule 5: Drop implausible BMI
    before = len(df)
    bmi_bad = df["BMI"].notna() & (df["BMI"] > BMI_MAX)
    stats["dropped_bmi_outlier"] = int(bmi_bad.sum())
    df = df[~bmi_bad].copy()
    
    # Rule 8: Remove duplicate MyKid (keep most recent)
    if mykid_col and "Tarikh_Pengukuran" in df.columns:
        before = len(df)
        df = df.sort_values("Tarikh_Pengukuran", ascending=False)
        df = df.drop_duplicates(subset=[mykid_col], keep="first")
        stats["dropped_duplicate_mykid"] = before - len(df)
    else:
        stats["dropped_duplicate_mykid"] = 0
    
    # Calculate WHO Z-scores (using daily LMS tables from Excel)
    if ZSCORE_AVAILABLE:
        df["WAZ"] = None
        df["HAZ"] = None
        df["BAZ"] = None
        
        for idx in df.index:
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
        
        # Rule 7: Drop rows with null z-scores
        before = len(df)
        null_zscore = df["WAZ"].isna() | df["HAZ"].isna() | df["BAZ"].isna()
        stats["dropped_null_zscore"] = int(null_zscore.sum())
        df = df[~null_zscore].copy()
        
        df["Ind_Normal"] = ~(df["Ind_Kurang_Berat_Badan"] | df["Ind_Bantut"] | df["Ind_Susut"])
        
        stats["ind_kurang_berat"] = int(df["Ind_Kurang_Berat_Badan"].sum())
        stats["ind_bantut"] = int(df["Ind_Bantut"].sum())
        stats["ind_susut"] = int(df["Ind_Susut"].sum())
        stats["ind_berlebihan_bb"] = int(df["Ind_Berlebihan_BB"].sum())
        stats["ind_obes"] = int(df["Ind_Obes"].sum())
        stats["ind_normal"] = int(df["Ind_Normal"].sum())
    else:
        stats["dropped_null_zscore"] = 0
    
    # Age category column
    if "Age_Days" in df.columns:
        df["Kategori_Umur"] = np.where(
            df["Age_Days"] < 730, "Bawah 2 Tahun",
            np.where(df["Age_Days"] < 1826, "Bawah 5 Tahun", "5 Tahun ke Atas")
        )
    
    # Final stats
    stats["final_count"] = len(df)
    stats["total_dropped"] = stats["raw_count"] - stats["final_count"]
    
    if "Gender" in df.columns:
        gender_counts = df["Gender"].value_counts().to_dict()
        stats["gender_male"] = gender_counts.get("Male", 0)
        stats["gender_female"] = gender_counts.get("Female", 0)
    
    if "Year" in df.columns:
        stats["year_counts"] = df["Year"].value_counts().to_dict()
    
    return df, stats


# ═══════════════════════════════════════════════════════════════════════════════
# KPM CLEANING
# ═══════════════════════════════════════════════════════════════════════════════

def clean_kpm(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Clean KPM (school) data and calculate BMI categories.
    
    Note: KPM data is for 7-year-olds (school age), which is beyond WHO infant
    z-score tables, so we use BMI thresholds instead of z-scores.
    
    Returns:
        tuple: (cleaned_dataframe, statistics_dict)
    """
    stats = {"raw_count": len(df), "data_type": "kpm"}
    df = df.copy()
    
    # Normalize column names
    df.columns = df.columns.str.strip()
    
    # Find key columns
    def find_col(patterns):
        for col in df.columns:
            for p in patterns:
                if p.lower() in col.lower():
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
    
    # Rule 3: Standardize gender (drop RAGU)
    if gender_col:
        df["Jantina_Raw"] = df[gender_col].astype(str).str.upper().str.strip()
        before = len(df)
        df = df[df["Jantina_Raw"] != "RAGU"].copy()
        stats["dropped_ragu_gender"] = before - len(df)
        
        df["Gender"] = df["Jantina_Raw"].map(GENDER_MAP)
        before = len(df)
        df = df[df["Gender"].notna()].copy()
        stats["dropped_invalid_gender"] = before - len(df)
    else:
        df["Gender"] = None
        stats["dropped_ragu_gender"] = 0
        stats["dropped_invalid_gender"] = 0
    
    # Rule 2: Drop duplicate ID_MURID (keep first)
    if student_id_col:
        before = len(df)
        df = df.drop_duplicates(subset=[student_id_col], keep="first")
        stats["dropped_duplicate_id"] = before - len(df)
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
    
    # Rule 5: Validate dates (no future, no epoch)
    before = len(df)
    today = pd.Timestamp.now()
    invalid_date = (
        (df["Tarikh_Pengukuran"] > today) |
        (df["Tarikh_Pengukuran"] < df["Tarikh_Lahir"])
    )
    stats["dropped_invalid_date"] = int((invalid_date & df["Tarikh_Pengukuran"].notna()).sum())
    df = df[~(invalid_date & df["Tarikh_Pengukuran"].notna())].copy()
    
    # Calculate age
    has_both = df["Tarikh_Lahir"].notna() & df["Tarikh_Pengukuran"].notna()
    df["Age_Days"] = np.where(has_both, (df["Tarikh_Pengukuran"] - df["Tarikh_Lahir"]).dt.days, np.nan)
    df["Age_Years"] = (df["Age_Days"] / 365.25).round(1)
    
    # Rule 4: Validate age 6-8 years for school
    before = len(df)
    age_invalid = df["Age_Years"].notna() & ((df["Age_Years"] < 5) | (df["Age_Years"] > 10))
    stats["dropped_age_invalid"] = int(age_invalid.sum())
    df = df[~age_invalid].copy()
    
    # Convert measurements
    if weight_col:
        df["Berat_kg"] = pd.to_numeric(df[weight_col], errors="coerce")
    else:
        df["Berat_kg"] = np.nan
    
    if height_col:
        df["Tinggi_cm"] = pd.to_numeric(df[height_col], errors="coerce")
    else:
        df["Tinggi_cm"] = np.nan
    
    # Rule 6 & 7: Drop measurement outliers
    berat_bad = (df["Berat_kg"] < BERAT_MIN_SCHOOL) | (df["Berat_kg"] > BERAT_MAX_SCHOOL)
    tinggi_bad = (df["Tinggi_cm"] < TINGGI_MIN_SCHOOL) | (df["Tinggi_cm"] > TINGGI_MAX_SCHOOL)
    
    outlier_mask = (berat_bad & df["Berat_kg"].notna()) | (tinggi_bad & df["Tinggi_cm"].notna())
    stats["dropped_measurement_outlier"] = int(outlier_mask.sum())
    df = df[~outlier_mask].copy()
    
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
    
    # Drop rows with no BMI
    before = len(df)
    df = df[df["BMI"].notna()].copy()
    stats["dropped_no_bmi"] = before - len(df)
    
    # Final stats
    stats["final_count"] = len(df)
    stats["total_dropped"] = stats["raw_count"] - stats["final_count"]
    
    # Category counts
    stats["ind_kurus"] = int(df["Ind_Kurus"].sum())
    stats["ind_normal"] = int(df["Ind_Normal"].sum())
    stats["ind_berlebihan"] = int(df["Ind_Berlebihan"].sum())
    stats["ind_obes"] = int(df["Ind_Obes"].sum())
    
    if "Gender" in df.columns:
        gender_counts = df["Gender"].value_counts().to_dict()
        stats["gender_male"] = gender_counts.get("Male", 0)
        stats["gender_female"] = gender_counts.get("Female", 0)
    
    return df, stats


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CLEANING DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

def clean_data(df: pd.DataFrame, data_type: str) -> tuple[pd.DataFrame, dict]:
    """
    Clean data based on data type.
    
    Args:
        df: Raw DataFrame
        data_type: One of 'kpm', 'myvass', 'ncdc'
    
    Returns:
        tuple: (cleaned_dataframe, statistics_dict)
    """
    if data_type == "kpm":
        return clean_kpm(df)
    elif data_type == "myvass":
        return clean_myvass(df)
    elif data_type == "ncdc":
        return clean_ncdc(df)
    else:
        raise ValueError(f"Unknown data type: {data_type}")


def detect_data_type(columns: list[str], filename: str = "") -> str:
    """
    Auto-detect data type from column names and filename.
    
    Returns:
        str: 'kpm', 'myvass', 'ncdc', or 'unknown'
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
    
    return "unknown"
