"""Phase 3: clean_general infers its cohort from the data and selects
plausibility bounds accordingly, fixing the latent infant-bounds bug where
school-age measurements were nulled against 0-5y limits.

Cohort rule: median age < 60 months -> infant; >= 60 months -> school; no
determinable age -> unknown (cohort-dependent bounds skipped, values retained).
"""
import os
import pathlib

import numpy as np
import pandas as pd

_ZDIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "zscore"
os.environ.setdefault("WHO_ZSCORE_DIR", str(_ZDIR))

from backend.eda.cleaning import clean_general  # noqa: E402


def _infant_df() -> pd.DataFrame:
    # ~2-year-olds: infant-plausible weight/height.
    return pd.DataFrame({
        "Jantina": ["L", "P", "L"],
        "Tarikh_Lahir": ["2021-01-01", "2021-01-01", "2021-06-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01", "2023-06-01"],
        "Berat_Kg": [12.0, 11.5, 12.5],
        "Tinggi_Cm": [85.0, 84.0, 86.0],
    })


def _school_df() -> pd.DataFrame:
    # ~7-year-olds: school-plausible weight/height. Height 140cm exceeds the
    # INFANT max (130) — the old code nulled it; the school cohort must keep it.
    return pd.DataFrame({
        "Jantina": ["L", "P", "L"],
        "Tarikh_Lahir": ["2016-01-01", "2016-01-01", "2016-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01", "2023-01-01"],
        "Berat_Kg": [30.0, 28.0, 32.0],
        "Tinggi_Cm": [140.0, 135.0, 138.0],
    })


def test_general_detects_infant_cohort():
    out, stats = clean_general(_infant_df())
    assert stats["cohort"] == "infant"
    assert len(out) == 3
    # In-range infant measurements retained.
    assert out["Tinggi_cm"].notna().all()
    assert out["Berat_kg"].notna().all()


def test_general_detects_school_cohort():
    out, stats = clean_general(_school_df())
    assert stats["cohort"] == "school"
    assert len(out) == 3


def test_general_school_height_not_nulled_against_infant_bounds():
    """The bug fix: a 140cm 7-year-old is plausible school-age but exceeds the
    infant 130cm cap. Under the detected school cohort it must be retained."""
    out, stats = clean_general(_school_df())
    assert stats["cohort"] == "school"
    # Every school-plausible height kept (would be NaN under infant bounds).
    assert out["Tinggi_cm"].notna().all()
    assert (out["Tinggi_cm"] == pd.Series([140.0, 135.0, 138.0])).all()


def test_general_school_indicators_unavailable_not_fabricated():
    """WHO infant z-scores must not be computed for school-age children; the
    indicators are honestly reported unavailable instead of computed wrong."""
    out, stats = clean_general(_school_df())
    assert set(stats["indicators_unavailable"]) >= {
        "underweight", "stunting", "wasting", "overweight"
    }
    for name, reason in stats["indicators_unavailable"].items():
        assert "school-age cohort" in reason
    # No infant z-score indicator columns fabricated.
    assert "Ind_Bantut" not in out.columns


def test_general_infant_implausible_height_nulled():
    df = _infant_df()
    df.loc[0, "Tinggi_Cm"] = 200.0  # impossible for an infant (> 130 cm cap)
    out, stats = clean_general(df)
    assert stats["cohort"] == "infant"
    assert pd.isna(out.loc[0, "Tinggi_cm"])      # nulled against infant bounds
    assert out.loc[1, "Tinggi_cm"] == 84.0       # plausible row untouched
    assert len(out) == 3                          # row kept, only value nulled


def test_general_unknown_cohort_skips_bounds_and_retains_values():
    # No age signal at all -> cohort unknown -> measurement bounds skipped.
    df = pd.DataFrame({
        "Jantina": ["L", "P"],
        "Berat_Kg": [500.0, 28.0],   # 500kg implausible but retained (no cohort)
        "Tinggi_Cm": [140.0, 135.0],
    })
    out, stats = clean_general(df)
    assert stats["cohort"] == "unknown"
    assert out.loc[0, "Berat_kg"] == 500.0       # not nulled — no cohort bounds
    assert any("cohort indeterminate" in a for a in stats["assumptions"])
