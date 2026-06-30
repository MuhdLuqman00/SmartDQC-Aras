"""
Phase 1 gate: assert that every clinical_ranges.py default equals the
pre-existing module constant it replaces.  If a value drifts, this test
catches it before the behaviour-changing rewire in Phase 2.
"""

import pytest
import backend.clinical_ranges as CR


# ── §1  Cohort plausibility bounds ────────────────────────────────────────────

def test_infant_weight_matches_cleaning_constants():
    from backend.eda.cleaning import BERAT_MIN_INFANT, BERAT_MAX_INFANT
    lo, hi = CR.get_range("infant_weight")
    assert lo == BERAT_MIN_INFANT
    assert hi == BERAT_MAX_INFANT


def test_infant_height_matches_cleaning_constants():
    from backend.eda.cleaning import TINGGI_MIN_INFANT, TINGGI_MAX_INFANT
    lo, hi = CR.get_range("infant_height")
    assert lo == TINGGI_MIN_INFANT
    assert hi == TINGGI_MAX_INFANT


def test_school_weight_matches_cleaning_and_bounds():
    from backend.eda.cleaning import BERAT_MIN_SCHOOL, BERAT_MAX_SCHOOL
    from backend.cleaning.weight_height import BERAT_MIN, BERAT_MAX
    lo, hi = CR.get_range("school_weight")
    assert lo == BERAT_MIN_SCHOOL == BERAT_MIN
    assert hi == BERAT_MAX_SCHOOL == BERAT_MAX


def test_school_height_matches_cleaning_and_bounds():
    from backend.eda.cleaning import TINGGI_MIN_SCHOOL, TINGGI_MAX_SCHOOL
    from backend.cleaning.weight_height import TINGGI_MIN, TINGGI_MAX
    lo, hi = CR.get_range("school_height")
    assert lo == TINGGI_MIN_SCHOOL == TINGGI_MIN
    assert hi == TINGGI_MAX_SCHOOL == TINGGI_MAX


def test_bmi_max_matches_cleaning():
    from backend.eda.cleaning import BMI_MAX
    assert CR.get_val("bmi_max") == BMI_MAX


def test_infant_age_cap_matches_cleaning():
    from backend.eda.cleaning import AGE_MAX_MONTHS_INFANT
    assert CR.get_val("infant_age_cap") == AGE_MAX_MONTHS_INFANT


def test_bio_ranges_match_config():
    from backend.config import BIO_RANGES
    assert CR.get_range("bio_weight") == BIO_RANGES["berat_kg"]
    assert CR.get_range("bio_height") == BIO_RANGES["tinggi_cm"]
    assert CR.get_range("bio_bmi") == BIO_RANGES["bmi"]
    assert CR.get_range("bio_age_months") == BIO_RANGES["age_months_computed"]


# ── §2  WHO BIV z-score cutoffs ───────────────────────────────────────────────

def test_biv_matches_cleaning_BIV():
    from backend.eda.cleaning import BIV
    biv = CR.get_biv()
    assert biv["WAZ"] == BIV["WAZ"]
    assert biv["HAZ"] == BIV["HAZ"]
    assert biv["BAZ"] == BIV["BAZ"]


def test_biv_matches_who_zscore_BIV():
    from backend.eda.who_zscore import _BIV
    biv = CR.get_biv()
    assert biv["WAZ"] == _BIV["WAZ"]
    assert biv["HAZ"] == _BIV["HAZ"]
    assert biv["BAZ"] == _BIV["BAZ"]


def test_zscore_cap_default():
    assert CR.get_val("zscore_cap") == 6.0


# ── §3  BMI thresholds ────────────────────────────────────────────────────────

def test_bmi_categories_match_bounds():
    from backend.cleaning.weight_height import BMI_UNDERWEIGHT, BMI_OVERWEIGHT, BMI_OBESE
    assert CR.get_val("bmi_underweight") == BMI_UNDERWEIGHT
    assert CR.get_val("bmi_overweight") == BMI_OVERWEIGHT
    assert CR.get_val("bmi_obese") == BMI_OBESE


# ── §4  Stunting proxies ──────────────────────────────────────────────────────

def test_stunting_proxies_match_bounds():
    from backend.cleaning.weight_height import STUNTED_THRESHOLD, TALL_THRESHOLD
    assert CR.get_val("stunted_threshold") == STUNTED_THRESHOLD
    assert CR.get_val("tall_threshold") == TALL_THRESHOLD


# ── §5  Age windows ───────────────────────────────────────────────────────────

def test_school_age_matches_bounds():
    from backend.cleaning.weight_height import AGE_MIN_YEARS, AGE_MAX_YEARS
    assert CR.get_val("school_age_min") == AGE_MIN_YEARS
    assert CR.get_val("school_age_max") == AGE_MAX_YEARS


# ── §6  Quality-checker bounds ────────────────────────────────────────────────

def test_br02_weight_impossible_default():
    lo, hi = CR.get_range("br02_weight_impossible")
    assert lo == 10.0
    assert hi == 125.0


def test_br03_height_impossible_default():
    lo, hi = CR.get_range("br03_height_impossible")
    assert lo == 50.0
    assert hi == 200.0


def test_br06_year_level_default():
    lo, hi = CR.get_range("br06_year_level")
    assert lo == 1
    assert hi == 7


def test_br09_date_window_default():
    assert CR.get_val("br09_date_window_years") == 20


def test_height_unit_suspect_default():
    assert CR.get_val("height_unit_suspect") == 200.0


# ── §7  Geographic bounds ─────────────────────────────────────────────────────

def test_geo_bounds_defaults():
    assert CR.get_val("geo_lat_min") == 1.0
    assert CR.get_val("geo_lat_max") == 7.5
    assert CR.get_val("geo_lon_min") == 99.5
    assert CR.get_val("geo_lon_max") == 119.5


# ── §8  Birth-weight categories ───────────────────────────────────────────────

def test_birth_weight_categories_match_config():
    from backend.config import BIRTH_WEIGHT_CATEGORIES
    assert CR.get_val("birth_weight_elbw") == BIRTH_WEIGHT_CATEGORIES["extremely_low"][1]
    assert CR.get_val("birth_weight_vlbw") == BIRTH_WEIGHT_CATEGORIES["very_low"][1]
    assert CR.get_val("birth_weight_lbw") == BIRTH_WEIGHT_CATEGORIES["low"][1]
    assert CR.get_val("birth_weight_normal_max") == BIRTH_WEIGHT_CATEGORIES["normal"][1]


# ── Override mechanics ────────────────────────────────────────────────────────

def test_override_range_applies():
    overrides = {"school_weight": {"min": 15.0, "max": 60.0}}
    lo, hi = CR.get_range("school_weight", overrides)
    assert lo == 15.0
    assert hi == 60.0


def test_override_partial_range_keeps_other_default():
    overrides = {"school_weight": {"min": 15.0}}
    lo, hi = CR.get_range("school_weight", overrides)
    assert lo == 15.0
    assert hi == 50.0  # default max preserved


def test_override_value_applies():
    overrides = {"bmi_max": {"value": 45.0}}
    assert CR.get_val("bmi_max", overrides) == 45.0


def test_no_override_returns_default():
    assert CR.get_range("school_weight") == (12.0, 50.0)
    assert CR.get_val("bmi_max") == 40.0


def test_validate_overrides_ok():
    ok, errors = CR.validate_overrides({"school_weight": {"min": 10.0, "max": 60.0}})
    assert ok
    assert errors == []


def test_validate_overrides_min_gte_max():
    ok, errors = CR.validate_overrides({"school_weight": {"min": 60.0, "max": 10.0}})
    assert not ok
    assert any("min" in e for e in errors)


def test_validate_overrides_unknown_key():
    ok, errors = CR.validate_overrides({"nonexistent_key": {"min": 1, "max": 2}})
    assert not ok
    assert any("nonexistent_key" in e for e in errors)


def test_to_api_dict_structure():
    result = CR.to_api_dict()
    assert "school_weight" in result
    entry = result["school_weight"]
    assert entry["type"] == "range"
    assert entry["default_min"] == 12.0
    assert entry["effective_min"] == 12.0
    assert entry["overridden"] is False
    assert "why" in entry
    assert "recommended" in entry


def test_to_api_dict_with_override():
    overrides = {"school_weight": {"min": 15.0, "max": 55.0}}
    result = CR.to_api_dict(overrides)
    entry = result["school_weight"]
    assert entry["effective_min"] == 15.0
    assert entry["effective_max"] == 55.0
    assert entry["default_min"] == 12.0
    assert entry["overridden"] is True


def test_make_school_profile_defaults():
    p = CR.make_school_profile()
    assert p.berat_min == 12.0
    assert p.berat_max == 50.0
    assert p.tinggi_min == 100.0
    assert p.tinggi_max == 160.0


def test_make_school_profile_with_override():
    overrides = {"school_weight": {"min": 13.0, "max": 55.0}}
    p = CR.make_school_profile(overrides)
    assert p.berat_min == 13.0
    assert p.berat_max == 55.0
    assert p.tinggi_min == 100.0  # unchanged


def test_make_infant_profile_defaults():
    p = CR.make_infant_profile()
    assert p.berat_min == 0.5
    assert p.berat_max == 35.0
