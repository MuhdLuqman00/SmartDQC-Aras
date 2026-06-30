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


def test_general_school_uses_bmi_categories_not_infant_zscores():
    """Phase 4b: school-age children get BMI categories, not WHO
    infant z-scores. under/overweight become available via BMI categories;
    weight/height-for-age (stunting/wasting) stay unavailable; no infant
    z-score columns are fabricated."""
    out, stats = clean_general(_school_df())
    # BMI-category indicator columns emitted (same as clean_school_age).
    for col in ("BMI_Category", "Ind_Kurus", "Ind_Normal", "Ind_Berlebihan", "Ind_Obes"):
        assert col in out.columns
    # No infant z-score indicator columns fabricated.
    assert "Ind_Bantut" not in out.columns
    # z-score-only indicators remain unavailable with a clear reason.
    assert set(stats["indicators_unavailable"]) == {"stunting", "wasting"}
    for reason in stats["indicators_unavailable"].values():
        assert "school-age cohort" in reason
    # BMI-category-backed indicators are now reported available.
    assert set(stats["indicators_available"]) == {"underweight", "overweight"}


def test_general_school_bmi_category_values_match_classifier():
    out, stats = clean_general(_school_df())
    # 30kg/140cm -> BMI 15.3 -> Normal (school classifier: 13.5<=bmi<16.5).
    assert out.loc[0, "BMI_Category"] == "Normal"
    assert bool(out.loc[0, "Ind_Normal"]) is True


def test_general_infant_implausible_height_excluded_not_nulled():
    """Phase 4: general flags an implausible row out (analyzable=False) like the
    named cleaners instead of nulling the value — non-destructive, recoverable
    in the full download. The full frame is still returned."""
    df = _infant_df()
    df.loc[0, "Tinggi_Cm"] = 200.0  # impossible for an infant (> 130 cm cap)
    out, stats = clean_general(df)
    assert stats["cohort"] == "infant"
    assert bool(out.loc[0, "analyzable"]) is False
    assert "dropped_measurement_outlier" in out.loc[0, "exclude_reason"]
    assert out.loc[0, "Tinggi_cm"] == 200.0       # value retained, not nulled
    assert bool(out.loc[1, "analyzable"]) is True  # plausible row kept analyzable
    assert len(out) == 3                           # full frame returned
    assert stats["dropped_measurement_outlier"] == 1


def test_general_unknown_cohort_skips_cohort_bounds_and_retains_values():
    # No age signal at all -> cohort unknown -> cohort-DEPENDENT measurement
    # bounds skipped. 60kg is out of school weight bounds (max 50) but its BMI
    # (~20.8) is sane, so the universal bmi_outlier rule does NOT fire either ->
    # the row is retained, demonstrating the cohort-bounds skip in isolation.
    df = pd.DataFrame({
        "Jantina": ["L", "P"],
        "Berat_Kg": [60.0, 28.0],
        "Tinggi_Cm": [170.0, 135.0],
    })
    out, stats = clean_general(df)
    assert stats["cohort"] == "unknown"
    assert stats["dropped_measurement_outlier"] == 0
    assert bool(out.loc[0, "analyzable"]) is True   # not flagged — no cohort bounds
    assert out.loc[0, "Berat_kg"] == 60.0           # value retained
    assert any("cohort indeterminate" in a for a in stats["assumptions"])


def test_general_universal_bmi_outlier_fires_even_without_cohort():
    """bmi_outlier is a Class-A universal: a BMI > 40 from present measurements
    is garbage regardless of cohort, so it flags the row even when cohort is
    indeterminate (cohort-dependent bounds skipped)."""
    df = pd.DataFrame({
        "Jantina": ["L", "P"],
        "Berat_Kg": [500.0, 28.0],   # BMI ~255 at 140cm -> impossible
        "Tinggi_Cm": [140.0, 135.0],
    })
    out, stats = clean_general(df)
    assert stats["cohort"] == "unknown"
    assert stats["dropped_measurement_outlier"] == 0   # cohort bounds skipped
    assert stats["dropped_bmi_outlier"] == 1           # universal rule still fires
    assert bool(out.loc[0, "analyzable"]) is False
    assert out.loc[0, "Berat_kg"] == 500.0             # value retained (non-destructive)


def test_general_invalid_gender_flagged_out():
    """Class-A universal: a present-but-unmappable sex is flagged out; a missing
    gender column is an honest gap, never a flag."""
    df = _infant_df()
    df.loc[0, "Jantina"] = "ZZZ"
    out, stats = clean_general(df)
    assert stats["dropped_invalid_gender"] == 1
    assert bool(out.loc[0, "analyzable"]) is False
    assert "dropped_invalid_gender" in out.loc[0, "exclude_reason"]
    assert len(out) == 3


def test_general_default_path_does_not_drop_all_school_age():
    """Phase 5C regression guard: portable rules absent from general's baseline
    (dropped_age_over5 with the infant 5y cap, in particular) must NOT fire on the
    default enabled_rules=None path. The earlier len(out)/notna() assertions were
    blind to `analyzable`, so the drop-all (every school-age row excluded ->
    final_count 0) passed unnoticed. Assert on analyzable / final_count directly."""
    out, stats = clean_general(_school_df())          # enabled_rules=None (default)
    assert stats["cohort"] == "school"
    assert stats["dropped_age_over5"] == 0             # the regression: was 3
    assert int(out["analyzable"].sum()) == 3           # no row silently excluded
    assert stats["final_count"] == 3                   # the drop-all guard
    # The portable rules report a clean zero, never an exclusion, by default.
    for code in ("dropped_age_over5", "dropped_pendapatan_x", "dropped_null_dob",
                 "dropped_duplicate_mykid", "dropped_ragu_gender"):
        assert stats[code] == 0
    assert out["exclude_reason"].eq("").all()
