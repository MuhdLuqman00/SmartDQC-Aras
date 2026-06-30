"""Phase 5C safety net — positive-path coverage for the 6 schema-specific drop
rules that have zero positive-trigger rows in test_golden_named_cleaners.py.

Each test exercises exactly ONE rule code to confirm it fires (stat counter == 1)
and is attributed in exclude_reason for the triggering row. Keep green throughout
the DROP_RULE_REGISTRY extraction (Phase 5C steps 2–4) — any regression in rule
attribution will fail here.
"""
import os
import pathlib

import pandas as pd

_ZDIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "zscore"
os.environ.setdefault("WHO_ZSCORE_DIR", str(_ZDIR))

from backend.eda import cleaning  # noqa: E402


def _codes(exclude_reason: str) -> set[str]:
    """Split semicolon-joined rule code string into a set."""
    return {c.strip() for c in exclude_reason.split(";") if c.strip()}


# ── 1. dropped_age_over5 — wide_multiyear ─────────────────────────────────────────────

def test_dropped_age_over5_wide_multiyear():
    """Child born 2014-01-01, measured 2023-01-01 is ~108 months → excluded."""
    df = pd.DataFrame({
        "JANTINA":           ["LELAKI", "LELAKI"],
        "TARIKH LAHIR":      ["2021-01-01", "2014-01-01"],
        "TARIKH PENGUKURAN": ["2023-01-01", "2023-01-01"],
        "BERAT (KG)":        [12.0, 12.0],
        "TINGGI (CM)":       [85.0, 85.0],
    })
    cleaned, stats = cleaning.clean_data(df, "wide_multiyear")
    assert stats["dropped_age_over5"] == 1
    # Anchor row (24 months) is still analyzable.
    assert cleaned.iloc[0]["analyzable"]
    # Target row (108 months) excluded with the right code.
    assert not cleaned.iloc[1]["analyzable"]
    assert "dropped_age_over5" in _codes(str(cleaned.iloc[1]["exclude_reason"]))


# ── 2. dropped_date_before_dob — wide_multiyear ───────────────────────────────────────

def test_dropped_date_before_dob_wide_multiyear():
    """Measurement date 2020-01-01 is before DOB 2021-01-01 → excluded."""
    df = pd.DataFrame({
        "JANTINA":           ["LELAKI", "LELAKI"],
        "TARIKH LAHIR":      ["2021-01-01", "2021-01-01"],
        "TARIKH PENGUKURAN": ["2023-01-01", "2020-01-01"],
        "BERAT (KG)":        [12.0, 12.0],
        "TINGGI (CM)":       [85.0, 85.0],
    })
    cleaned, stats = cleaning.clean_data(df, "wide_multiyear")
    assert stats["dropped_date_before_dob"] == 1
    assert cleaned.iloc[0]["analyzable"]
    assert not cleaned.iloc[1]["analyzable"]
    assert "dropped_date_before_dob" in _codes(str(cleaned.iloc[1]["exclude_reason"]))


# ── 3. dropped_pendapatan_x — wide_registry ────────────────────────────────────────────

def test_dropped_pendapatan_x_wide_registry():
    """Income coded 'X' → excluded."""
    df = pd.DataFrame({
        "JANTINA":      ["L", "P"],
        "TARIKH LAHIR": ["2019-01-01", "2019-01-01"],
        "Pendapatan":   ["3000", "X"],
        "2022 Berat":   [16.0, 16.0],
        "2022 Tinggi":  [105.0, 105.0],
        "2022 Tarikh":  ["2022-06-01", "2022-06-01"],
    })
    cleaned, stats = cleaning.clean_data(df, "wide_registry")
    assert stats["dropped_pendapatan_x"] == 1
    flagged = cleaned[cleaned["exclude_reason"].str.contains("dropped_pendapatan_x", na=False)]
    assert len(flagged) == 1


# ── 4. dropped_null_dob — wide_registry ────────────────────────────────────────────────

def test_dropped_null_dob_wide_registry():
    """Missing date of birth → excluded."""
    df = pd.DataFrame({
        "JANTINA":      ["L", "P"],
        "TARIKH LAHIR": ["2019-01-01", None],
        "2022 Berat":   [16.0, 16.5],
        "2022 Tinggi":  [105.0, 106.0],
        "2022 Tarikh":  ["2022-06-01", "2022-06-01"],
    })
    cleaned, stats = cleaning.clean_data(df, "wide_registry")
    assert stats["dropped_null_dob"] == 1
    flagged = cleaned[cleaned["exclude_reason"].str.contains("dropped_null_dob", na=False)]
    assert len(flagged) == 1


# ── 5. dropped_duplicate_mykid — wide_registry ─────────────────────────────────────────

def test_dropped_duplicate_mykid_wide_registry():
    """Same MyKID + same DOB with two measurement dates → keep most recent, drop older."""
    # Pre-shaped long format (no year-prefix cols) so wide_registry skips wide-to-long reshape.
    df = pd.DataFrame({
        "No. MyKID":         ["KID001",     "KID001",     "KID002"],
        "JANTINA":           ["L",          "L",          "P"],
        "TARIKH LAHIR":      ["2019-01-01", "2019-01-01", "2019-01-01"],
        "Berat_kg":          [16.0,         16.5,         16.0],
        "Tinggi_cm":         [105.0,        106.0,        105.0],
        "Tarikh_Pengukuran": ["2022-01-01", "2023-06-01", "2023-06-01"],
    })
    cleaned, stats = cleaning.clean_data(df, "wide_registry")
    assert stats["dropped_duplicate_mykid"] == 1
    dup_rows = cleaned[cleaned["exclude_reason"].str.contains("dropped_duplicate_mykid", na=False)]
    assert len(dup_rows) == 1
    # The OLDER measurement (2022-01-01) is the one dropped; the 2023 row is kept.
    assert dup_rows.iloc[0]["Tarikh_Pengukuran"] == pd.Timestamp("2022-01-01")


# ── 6. dropped_ragu_gender — school_age ──────────────────────────────────────────────

def test_dropped_ragu_gender_school_age():
    """JANTINA = 'RAGU' → excluded."""
    df = pd.DataFrame({
        "ID_MURID":          ["A1",         "A2"],
        "JANTINA":           ["L",          "RAGU"],
        "TARIKH LAHIR":      ["2015-01-01", "2015-01-01"],
        "TARIKH PENGUKURAN": ["2023-06-01", "2023-06-01"],
        "BERAT":             [30.0,         30.0],
        "TINGGI":            [130.0,        130.0],
    })
    cleaned, stats = cleaning.clean_data(df, "school_age")
    assert stats["dropped_ragu_gender"] == 1
    # Anchor row ("L") is still analyzable.
    assert cleaned.iloc[0]["analyzable"]
    # RAGU row excluded with the right code.
    assert not cleaned.iloc[1]["analyzable"]
    assert "dropped_ragu_gender" in _codes(str(cleaned.iloc[1]["exclude_reason"]))
