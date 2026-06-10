"""Commit A - detection blocks for the un-wired Family 1/4 review codes.

These were in REVIEW_RULE_REGISTRY / REVIEW_EVALUATED_RULES (visible as toggles)
but had no detection logic, so they were ghost toggles. Each test pins that the
rule FIRES on a triggering row and stays SILENT on a clean row, and that it uses
_flag() (review_reason) only — never _exclude().
"""
import pandas as pd

from backend.eda.cleaning import clean_myvass, clean_ncdc
from backend.utils.ic_validator import extract_ic_birthdate


def _has(reason, code):
    return code in str(reason)


# --- IC birthdate extractor (pure) --------------------------------------------

def test_ic_birthdate_basic():
    d = extract_ic_birthdate("200101010101")
    assert d is not None and d.year == 2020 and d.month == 1 and d.day == 1


def test_ic_birthdate_adult_century():
    d = extract_ic_birthdate("850101010101")
    assert d is not None and d.year == 1985


def test_ic_birthdate_invalid_returns_none():
    assert extract_ic_birthdate("12345") is None
    assert extract_ic_birthdate(None) is None


# --- review_ic_malformed ------------------------------------------------------

def test_ic_malformed_flags_short_ic():
    df = pd.DataFrame({
        "IC_NO_PASSPORT": ["2001010101", "200101010101"],  # 10-digit, 12-digit
        "jantina": ["LELAKI", "LELAKI"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert _has(cleaned.loc[0, "review_reason"], "review_ic_malformed")
    assert not _has(cleaned.loc[1, "review_reason"], "review_ic_malformed")


def test_ic_malformed_does_not_flag_blank():
    df = pd.DataFrame({
        "IC_NO_PASSPORT": ["", "200101010101"],
        "jantina": ["LELAKI", "LELAKI"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    # blank IC is "missing", not "malformed" — must not be flagged here
    assert not _has(cleaned.loc[0, "review_reason"], "review_ic_malformed")


# --- review_ic_dob_mismatch ---------------------------------------------------

def test_ic_dob_mismatch_flagged():
    df = pd.DataFrame({
        "IC_NO_PASSPORT": ["200101010101", "200101010101"],  # IC DOB = 2020-01-01
        "jantina": ["LELAKI", "LELAKI"],
        "Tarikh_Lahir": ["2019-05-05", "2020-01-01"],         # row0 differs, row1 matches
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert _has(cleaned.loc[0, "review_reason"], "review_ic_dob_mismatch")
    assert not _has(cleaned.loc[1, "review_reason"], "review_ic_dob_mismatch")


# --- review_ic_age_contradiction ----------------------------------------------

def test_ic_age_contradiction_parent_ic():
    df = pd.DataFrame({
        "IC_NO_PASSPORT": ["850101010101", "200101010101"],  # adult IC vs child IC
        "jantina": ["LELAKI", "LELAKI"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],         # record is a child (~3y)
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert _has(cleaned.loc[0, "review_reason"], "review_ic_age_contradiction")
    assert not _has(cleaned.loc[1, "review_reason"], "review_ic_age_contradiction")


# --- review_mykid_invalid (ncdc) ----------------------------------------------

def test_mykid_invalid_flagged():
    df = pd.DataFrame({
        "MyKid": ["230208155554", "12345"],  # valid 12-digit, malformed short
        "Jantina": ["Lelaki", "Lelaki"],
        "Tarikh_Lahir": ["2022-02-08", "2022-02-08"],
        "Tarikh_Pengukuran": ["2024-02-08", "2024-02-08"],
        "Berat_kg": [12.0, 12.0],
        "Tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_ncdc(df)
    assert not _has(cleaned.loc[0, "review_reason"], "review_mykid_invalid")
    assert _has(cleaned.loc[1, "review_reason"], "review_mykid_invalid")


# --- review_dose_date_mismatch (myvass, contoh-only) --------------------------

def test_dose_date_mismatch_flagged():
    df = pd.DataFrame({
        "IC_NO_PASSPORT": ["200101010101", "200101010101"],
        "jantina": ["LELAKI", "LELAKI"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "DOSE_DATE": ["2099-12-31", "2023-01-01"],  # row0 differs, row1 same
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert _has(cleaned.loc[0, "review_reason"], "review_dose_date_mismatch")
    assert not _has(cleaned.loc[1, "review_reason"], "review_dose_date_mismatch")


# --- flag-not-drop invariant --------------------------------------------------

def test_family14_flags_never_set_exclude():
    df = pd.DataFrame({
        "IC_NO_PASSPORT": ["2001010101"],  # malformed
        "jantina": ["LELAKI"],
        "Tarikh_Lahir": ["2020-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01"],
        "berat_kg": [12.0],
        "tinggi_cm": [85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert _has(cleaned.loc[0, "review_reason"], "review_ic_malformed")
    # malformed IC alone is a flag, not an exclusion
    assert "review_ic_malformed" not in str(cleaned.loc[0, "exclude_reason"])
