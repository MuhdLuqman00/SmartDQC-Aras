"""
WHO 2006/2007 Child Growth Standards — Daily Z-score computation
=================================================================
Reference: WHO (2006). WHO Child Growth Standards: Methods and development.
           Geneva: World Health Organization.

Formula: Z = ((X/M)^L - 1) / (L × S)  when L ≠ 0
         Z = ln(X / M) / S              when L = 0

This module loads daily LMS tables (Day 0 to ~1856) from Excel files
and computes z-scores based on exact age in DAYS (not months).

LMS table files required in ZSCORE folder:
  - wfa-boys-zscore-expanded-tables.xlsx
  - wfa-girls-zscore-expanded-tables.xlsx
  - lhfa-boys-zscore-expanded-tables.xlsx
  - lhfa-girls-zscore-expanded-tables.xlsx
  - bfa-boys-zscore-expanded-tables.xlsx
  - bfa-girls-zscore-expanded-tables.xlsx
"""

import math
from pathlib import Path
import pandas as pd
import numpy as np

# ── LMS TABLE PATHS ───────────────────────────────────────────────────────
ZSCORE_DIR = Path(__file__).parent.parent.parent / "data" / "ZSCORE"

LMS_FILES = {
    "WAZ": {
        "Male": ZSCORE_DIR / "wfa-boys-zscore-expanded-tables.xlsx",
        "Female": ZSCORE_DIR / "wfa-girls-zscore-expanded-tables.xlsx",
    },
    "HAZ": {
        "Male": ZSCORE_DIR / "lhfa-boys-zscore-expanded-tables.xlsx",
        "Female": ZSCORE_DIR / "lhfa-girls-zscore-expanded-tables.xlsx",
    },
    "BAZ": {
        "Male": ZSCORE_DIR / "bfa-boys-zscore-expanded-tables.xlsx",
        "Female": ZSCORE_DIR / "bfa-girls-zscore-expanded-tables.xlsx",
    },
}

# ── GLOBAL CACHE FOR LMS TABLES ───────────────────────────────────────────
_LMS_CACHE = {}

def _load_lms_table(indicator: str, sex: str) -> pd.DataFrame:
    """
    Load LMS table from Excel file and cache it.
    Returns DataFrame with columns: Day, L, M, S
    """
    cache_key = f"{indicator}_{sex}"
    
    if cache_key in _LMS_CACHE:
        return _LMS_CACHE[cache_key]
    
    file_path = LMS_FILES.get(indicator, {}).get(sex)
    if not file_path or not file_path.exists():
        raise FileNotFoundError(
            f"LMS table not found: {file_path}\n"
            f"Required file: {indicator} for {sex}"
        )
    
    df = pd.read_excel(file_path, usecols=["Day", "L", "M", "S"])
    df = df.set_index("Day")
    
    _LMS_CACHE[cache_key] = df
    return df


def _get_lms(indicator: str, sex: str, age_days: int) -> tuple:
    """
    Get L, M, S parameters for given indicator, sex, and age in days.
    Returns (L, M, S) or (None, None, None) if not found.
    """
    try:
        df = _load_lms_table(indicator, sex)
        
        # Ensure age_days is within valid range
        min_day = df.index.min()
        max_day = df.index.max()
        
        if age_days < min_day or age_days > max_day:
            return (None, None, None)
        
        # Get LMS values for exact day
        if age_days in df.index:
            row = df.loc[age_days]
            return (row["L"], row["M"], row["S"])
        else:
            return (None, None, None)
            
    except Exception as e:
        print(f"Warning: Failed to get LMS for {indicator}/{sex}/day {age_days}: {e}")
        return (None, None, None)


def compute_zscore(indicator: str, value: float, age_days: int, sex: str) -> float | None:
    """
    Compute WHO z-score for a given anthropometric indicator.
    
    Parameters:
    -----------
    indicator : str
        One of: "WAZ" (Weight-for-Age), "HAZ" (Height-for-Age), "BAZ" (BMI-for-Age)
    value : float
        The measurement value (weight in kg, height in cm, or BMI in kg/m²)
    age_days : int
        Age in days (0 to ~1856 for 0-5 years)
    sex : str
        "Male" or "Female"
    
    Returns:
    --------
    float or None
        The z-score, or None if calculation is not possible
        
    Formula:
    --------
    Z = ((X/M)^L - 1) / (L × S)  when L ≠ 0
    Z = ln(X / M) / S              when L = 0
    
    where X = value, L/M/S = WHO LMS parameters for the given day and sex
    """
    if value is None or age_days is None or sex is None:
        return None
    
    if pd.isna(value) or pd.isna(age_days):
        return None
    
    if value <= 0:
        return None
    
    # Get LMS parameters
    L, M, S = _get_lms(indicator, sex, int(age_days))
    
    if L is None or M is None or S is None:
        return None
    
    if M <= 0 or S <= 0:
        return None
    
    try:
        if abs(L) < 1e-10:  # L ≈ 0, use natural log
            z = math.log(value / M) / S
        else:
            # Standard Box-Cox transformation
            z = ((value / M) ** L - 1) / (L * S)
        
        return round(z, 4)
        
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def classify_waz(z: float | None) -> str:
    """
    Classify Weight-for-Age z-score per WHO 2006.
    
    Returns:
    --------
    - "kurang_berat_badan_teruk" (Severely Underweight): z < -3
    - "kurang_berat_badan" (Underweight): -3 ≤ z < -2
    - "risiko_kurang_berat_badan" (Risk of Underweight): -2 ≤ z < -1
    - "berat_badan_normal" (Normal): -1 ≤ z ≤ 2
    - "mungkin_masalah_pertumbuhan" (Possible Growth Problem): z > 2
    """
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return None
    if z < -3:
        return "kurang_berat_badan_teruk"
    if z < -2:
        return "kurang_berat_badan"
    if z < -1:
        return "risiko_kurang_berat_badan"
    if z <= 2:
        return "berat_badan_normal"
    return "mungkin_masalah_pertumbuhan"


def classify_haz(z: float | None) -> str:
    """
    Classify Height-for-Age z-score per WHO 2006.
    
    Returns:
    --------
    - "bantut_teruk" (Severely Stunted): z < -3
    - "bantut" (Stunted): -3 ≤ z < -2
    - "risiko_bantut" (Risk of Stunting): -2 ≤ z < -1
    - "normal": -1 ≤ z ≤ 3
    - "mungkin_masalah_endokrin" (Possible Endocrine Problem): z > 3
    """
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return None
    if z < -3:
        return "bantut_teruk"
    if z < -2:
        return "bantut"
    if z < -1:
        return "risiko_bantut"
    if z <= 3:
        return "normal"
    return "mungkin_masalah_endokrin"


def classify_baz(z: float | None) -> str:
    """
    Classify BMI-for-Age z-score per WHO 2006.
    
    Returns:
    --------
    - "susut_teruk" (Severely Wasted): z < -3
    - "susut" (Wasted): -3 ≤ z < -2
    - "berisiko_susut" (Risk of Wasting): -2 ≤ z < -1
    - "normal": -1 ≤ z ≤ 1
    - "risiko_lebih_berat_badan" (Risk of Overweight): 1 < z ≤ 2
    - "berlebihan_berat_badan" (Overweight): 2 < z ≤ 3
    - "obes" (Obese): z > 3
    """
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return None
    if z < -3:
        return "susut_teruk"
    if z < -2:
        return "susut"
    if z < -1:
        return "berisiko_susut"
    if z <= 1:
        return "normal"
    if z <= 2:
        return "risiko_lebih_berat_badan"
    if z <= 3:
        return "berlebihan_berat_badan"
    return "obes"


# ── VALIDATION: WHO BIV (Biologically Implausible Values) ─────────────────
BIV_BOUNDS = {
    "WAZ": (-6.0, +5.0),
    "HAZ": (-6.0, +6.0),
    "BAZ": (-5.0, +5.0),
}

def is_biv(indicator: str, z: float | None) -> bool:
    """
    Check if z-score is Biologically Implausible (outside WHO BIV bounds).
    
    Returns True if z-score is OUTSIDE the valid range (i.e., implausible).
    """
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return True  # Null is implausible
    
    lo, hi = BIV_BOUNDS.get(indicator, (-6, 6))
    return z < lo or z > hi
