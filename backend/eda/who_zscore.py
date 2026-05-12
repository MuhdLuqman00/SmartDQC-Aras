# WHO 2006 Child Growth Standards — Z-score computation
# Reference: WHO (2006). WHO Child Growth Standards: Methods and development.
#            Geneva: World Health Organization.
#
# Formula: Z = ((X/M)^L - 1) / (L * S)  when L ≠ 0
#          Z = ln(X / M) / S              when L = 0
#
# LMS tables are loaded from the official WHO expanded daily tables (Excel).
# Each file has columns: Day, L, M, S, SD4neg … SD4
# Coverage: day 0–1856 (≈ 0–61 months)

import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
# Default path to the folder containing the 6 WHO Excel files.
# Can be overridden by setting the WHO_ZSCORE_DIR environment variable.
_DEFAULT_ZSCORE_DIR = os.environ.get("WHO_ZSCORE_DIR", "/app/data/zscore")
ZSCORE_DIR = _DEFAULT_ZSCORE_DIR

# Expected filenames
_FILES = {
    ("M", "WAZ"): "wfa-boys-zscore-expanded-tables.xlsx",
    ("F", "WAZ"): "wfa-girls-zscore-expanded-tables.xlsx",
    ("M", "HAZ"): "lhfa-boys-zscore-expanded-tables.xlsx",
    ("F", "HAZ"): "lhfa-girls-zscore-expanded-tables.xlsx",
    ("M", "BAZ"): "bfa-boys-zscore-expanded-tables.xlsx",
    ("F", "BAZ"): "bfa-girls-zscore-expanded-tables.xlsx",
}


# ─── LOAD LMS TABLES FROM EXCEL ──────────────────────────────────────────────

def _load_lms_tables(zscore_dir: str) -> dict:
    """
    Load all 6 WHO expanded daily LMS tables from Excel files.
    Returns: dict keyed by (sex_code, indicator) → dict[day → (L, M, S)]
    """
    tables = {}
    for key, filename in _FILES.items():
        filepath = os.path.join(zscore_dir, filename)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(
                f"WHO z-score file not found: {filepath}\n"
                f"Please download from https://www.who.int/tools/child-growth-standards"
            )
        df = pd.read_excel(filepath, usecols=["Day", "L", "M", "S"])
        # Build day → (L, M, S) lookup dict
        lms_dict = {}
        for _, row in df.iterrows():
            day = int(row["Day"])
            lms_dict[day] = (float(row["L"]), float(row["M"]), float(row["S"]))
        tables[key] = lms_dict
    return tables


# Load once at module import
try:
    _LMS_TABLES = _load_lms_tables(ZSCORE_DIR)
    _MAX_DAY = max(max(t.keys()) for t in _LMS_TABLES.values())
    ZSCORE_AVAILABLE = True
except Exception as e:
    import warnings
    warnings.warn(f"WHO z-score Excel files could not be loaded: {e}")
    _LMS_TABLES = {}
    _MAX_DAY = 0
    ZSCORE_AVAILABLE = False


# ─── Z-SCORE COMPUTATION ──────────────────────────────────────────────────────

def _get_lms(sex: str, indicator: str, age_days: int):
    """
    Return (L, M, S) for the given sex, indicator, and age in days.
    Uses exact daily lookup from the WHO expanded tables.
    """
    sex_code = "M" if str(sex).strip().upper() in ("M", "MALE", "LELAKI", "1") else "F"
    table = _LMS_TABLES.get((sex_code, indicator))
    if table is None:
        return None
    day = int(round(age_days))
    day = max(0, min(_MAX_DAY, day))
    return table.get(day)


def compute_zscore(measurement: float, sex: str, age_days: float, indicator: str):
    """
    Compute WHO 2006 z-score using daily LMS tables.

    Parameters:
        measurement: weight (kg), height (cm), or BMI
        sex: "M"/"Male"/"LELAKI" or "F"/"Female"/"PEREMPUAN"
        age_days: child's age in days
        indicator: "WAZ" | "HAZ" | "BAZ"

    Returns: float z-score rounded to 3 dp, or None if inputs are invalid.
    """
    try:
        if measurement is None or math.isnan(measurement):
            return None
        if age_days is None or math.isnan(age_days):
            return None
        lms = _get_lms(sex, indicator, age_days)
        if lms is None:
            return None
        L, M, S = lms
        if M <= 0 or S <= 0:
            return None
        if L == 0 or abs(L) < 1e-6:
            z = math.log(measurement / M) / S
        else:
            z = ((measurement / M) ** L - 1) / (L * S)
        # WHO recommends capping at ±6 for implausible values
        if abs(z) > 6:
            return None
        return round(z, 3)
    except Exception:
        return None


# ─── CLASSIFICATION ───────────────────────────────────────────────────────────

# BIV (Biologically Implausible Values) thresholds per WHO/UNICEF
_BIV = {
    "WAZ": (-6, 5),    # WAZ < -6 or > +5
    "HAZ": (-6, 6),    # HAZ < -6 or > +6
    "BAZ": (-5, 5),    # BAZ < -5 or > +5
}

def _is_biv(z, indicator: str) -> bool:
    """Return True if z-score is biologically implausible."""
    if z is None:
        return False
    lo, hi = _BIV.get(indicator, (-99, 99))
    return z < lo or z > hi

def classify_waz(z):
    """Weight-for-Age Z-score classification (KKM / WHO 2006)."""
    if z is None:        return None
    if z < -3:           return "kurang_berat_badan_teruk"
    if z < -2:           return "kurang_berat_badan"
    if z < -1:           return "risiko_kurang_berat_badan"
    if z <= 2:           return "berat_badan_normal"
    return "mungkin_masalah_pertumbuhan"

def classify_haz(z):
    """Height/Length-for-Age Z-score classification (KKM / WHO 2006)."""
    if z is None:        return None
    if z < -3:           return "bantut_teruk"
    if z < -2:           return "bantut"
    if z < -1:           return "risiko_bantut"
    if z <= 3:           return "normal"
    return "mungkin_masalah_endokrin"

def classify_baz(z):
    """BMI-for-Age Z-score classification (KKM / WHO 2006)."""
    if z is None:        return None
    if z < -3:           return "susut_teruk"
    if z < -2:           return "susut"
    if z < -1:           return "berisiko_susut"
    if z <= 1:           return "normal"
    if z <= 2:           return "risiko_lebih_berat_badan"
    if z <= 3:           return "berlebihan_berat_badan"
    return "obes"

# KKM indicator groupings (which WHO classifications trigger each KKM indicator)
WHO_TO_KKM_INDICATOR = {
    "ind_kurang_berat": lambda waz_cls: waz_cls in ("kurang_berat_badan", "kurang_berat_badan_teruk"),
    "ind_bantut":       lambda haz_cls: haz_cls in ("bantut", "bantut_teruk"),
    "ind_susut":        lambda baz_cls: baz_cls in ("susut", "susut_teruk"),
    "ind_obes":         lambda baz_cls: baz_cls in ("berlebihan_berat_badan", "obes"),
}

# Mapping from source data label → expected WHO classification (for comparison)
SOURCE_LABEL_TO_WHO = {
    # WAZ
    "kurang berat badan teruk":     "kurang_berat_badan_teruk",
    "kurang berat badan":           "kurang_berat_badan",
    "risiko kurang berat badan":    "risiko_kurang_berat_badan",
    "normal":                       "berat_badan_normal",
    "berat badan normal":           "berat_badan_normal",
    "berlebihan berat badan":       "mungkin_masalah_pertumbuhan",
    "lebihan berat badan":          "mungkin_masalah_pertumbuhan",
    "pemantauan lanjut":            "berat_badan_normal",
    # HAZ
    "bantut teruk":                 "bantut_teruk",
    "bantut":                       "bantut",
    "risiko bantut":                "risiko_bantut",
    "tinggi normal":                "normal",
    "tinggi":                       "mungkin_masalah_endokrin",
    # BAZ
    "susut teruk":                  "susut_teruk",
    "susut":                        "susut",
    "berisiko susut":               "berisiko_susut",
    "risiko lebih berat badan":     "risiko_lebih_berat_badan",
    "risiko berlebihan berat badan":"risiko_lebih_berat_badan",
    "obes":                         "obes",
}


# ─── BATCH COMPUTATION FOR A DATAFRAME ────────────────────────────────────────

def add_who_zscores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add WHO 2006 z-score columns and derived classifications to a DataFrame.
    Requires: berat_kg, tinggi_cm, bmi (optional), age_months_computed, jantina
    Adds columns:
      waz, haz, baz           — raw z-scores
      waz_class, haz_class, baz_class  — WHO classifications
      ind_waz_*, ind_haz_*, ind_baz_*  — boolean indicator flags (from z-score)
      status_label_mismatch_*  — comparison with source labels
    """
    required = {"age_months_computed", "jantina"}
    if not required.issubset(df.columns):
        return df

    sex_series = df["jantina"].astype(str).str.strip()
    age_series = pd.to_numeric(df["age_months_computed"], errors="coerce")
    # Convert months to days for daily lookup
    age_days_series = (age_series * 30.4375).round(0)

    # WAZ
    if "berat_kg" in df.columns:
        w = pd.to_numeric(df["berat_kg"], errors="coerce")
        df["waz"] = [
            compute_zscore(float(w.iloc[i]), sex_series.iloc[i], float(age_days_series.iloc[i]), "WAZ")
            if pd.notna(w.iloc[i]) and pd.notna(age_days_series.iloc[i]) else None
            for i in range(len(df))
        ]
        df["flag_biv_waz"] = df["waz"].apply(lambda z: _is_biv(z, "WAZ"))
        df.loc[df["flag_biv_waz"], "waz"] = None  # nullify BIV z-scores
        df["waz_class"] = df["waz"].apply(classify_waz)
        df["ind_kurang_berat_zscore"] = df["waz_class"].apply(
            lambda c: WHO_TO_KKM_INDICATOR["ind_kurang_berat"](c) if c else False)

    # HAZ
    if "tinggi_cm" in df.columns:
        h = pd.to_numeric(df["tinggi_cm"], errors="coerce")
        df["haz"] = [
            compute_zscore(float(h.iloc[i]), sex_series.iloc[i], float(age_days_series.iloc[i]), "HAZ")
            if pd.notna(h.iloc[i]) and pd.notna(age_days_series.iloc[i]) else None
            for i in range(len(df))
        ]
        df["flag_biv_haz"] = df["haz"].apply(lambda z: _is_biv(z, "HAZ"))
        df.loc[df["flag_biv_haz"], "haz"] = None
        df["haz_class"] = df["haz"].apply(classify_haz)
        df["ind_bantut_zscore"] = df["haz_class"].apply(
            lambda c: WHO_TO_KKM_INDICATOR["ind_bantut"](c) if c else False)

    # BAZ
    bmi_col = pd.to_numeric(df.get("bmi", pd.Series(dtype=float)), errors="coerce")
    if "bmi" in df.columns or ("berat_kg" in df.columns and "tinggi_cm" in df.columns):
        if "bmi" not in df.columns:
            w2 = pd.to_numeric(df["berat_kg"], errors="coerce")
            h2 = pd.to_numeric(df["tinggi_cm"], errors="coerce")
            bmi_col = w2 / ((h2 / 100) ** 2)
        df["baz"] = [
            compute_zscore(float(bmi_col.iloc[i]), sex_series.iloc[i], float(age_days_series.iloc[i]), "BAZ")
            if pd.notna(bmi_col.iloc[i]) and pd.notna(age_days_series.iloc[i]) else None
            for i in range(len(df))
        ]
        df["flag_biv_baz"] = df["baz"].apply(lambda z: _is_biv(z, "BAZ"))
        df.loc[df["flag_biv_baz"], "baz"] = None
        df["baz_class"] = df["baz"].apply(classify_baz)
        df["ind_susut_zscore"] = df["baz_class"].apply(
            lambda c: WHO_TO_KKM_INDICATOR["ind_susut"](c) if c else False)
        df["ind_obes_zscore"] = df["baz_class"].apply(
            lambda c: WHO_TO_KKM_INDICATOR["ind_obes"](c) if c else False)

    # Compare z-score classification vs source labels
    _add_label_mismatch(df)
    return df


def _add_label_mismatch(df: pd.DataFrame):
    """Flag rows where source label contradicts WHO z-score classification."""
    pairs = [
        ("status_berat",  "waz_class"),
        ("status_tinggi", "haz_class"),
        ("status_bmi",    "baz_class"),
    ]
    for src_col, zscore_col in pairs:
        if src_col not in df.columns or zscore_col not in df.columns:
            continue
        mismatch_col = f"flag_{src_col}_vs_zscore"
        def check_mismatch(row, sc=src_col, zc=zscore_col):
            src = str(row.get(sc, "") or "").strip().lower()
            zscl = row.get(zc)
            if not src or zscl is None:
                return False
            expected_who = SOURCE_LABEL_TO_WHO.get(src)
            if expected_who is None:
                return False  # Unknown label — can't compare
            return expected_who != zscl
        df[mismatch_col] = df.apply(check_mismatch, axis=1)


def zscore_mismatch_report(df: pd.DataFrame) -> dict:
    """Return a summary of z-score vs source-label mismatches."""
    result = {}
    for col in ["flag_status_berat_vs_zscore", "flag_status_tinggi_vs_zscore",
                "flag_status_bmi_vs_zscore"]:
        if col not in df.columns:
            continue
        n_mismatch = int(df[col].sum())
        n_total = int(df[col].notna().sum())
        indicator = col.replace("flag_", "").replace("_vs_zscore", "")
        result[indicator] = {
            "n_mismatch": n_mismatch,
            "n_total": n_total,
            "pct_mismatch": round(n_mismatch / n_total * 100, 2) if n_total > 0 else 0,
            "severity": "high" if n_mismatch / max(n_total, 1) > 0.1 else "low",
            "note": f"{n_mismatch} rekod: label sumber tidak sepadan dengan z-skor WHO 2006",
        }
    return result
