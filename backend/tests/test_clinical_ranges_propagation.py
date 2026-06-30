"""Propagation gate for the EDITABLE clinical-range keys.

The registry golden-pins (test_clinical_ranges_registry.py) only pin *defaults* —
they cannot catch a no-op where a saved override never reaches the cleaner. This
suite proves that each key marked editable in the Settings "Clinical Ranges" tab
*actually changes cleaning output* when overridden.

Pattern (per the plan): build a fully-valid row engineered to sit BETWEEN the
default bound and an overridden bound, then assert the targeted stat is unchanged
at default (no-override == known baseline) AND flips under the override. Asserting
both ends guards against false passes where the row silently died upstream.

If a key is in clinical_ranges.EDITABLE_KEYS it MUST be covered here.
"""

import pandas as pd

from backend.eda.cleaning import clean_wide_multiyear, clean_school_age, clean_data
from backend.eda.quality_rules import analyze_quality
import backend.clinical_ranges as CR


# ── fixtures ──────────────────────────────────────────────────────────────────

def _wide_multiyear_row(berat=12.0, tinggi=85.0, dob="2020-01-01", measure="2023-01-01"):
    """One fully-valid MyVASS row (~36mo, in-range weight/height, valid gender)."""
    return pd.DataFrame({
        "jantina": ["LELAKI"],
        "Tarikh_Lahir": [dob],
        "Tarikh_Pengukuran": [measure],
        "berat_kg": [berat],
        "tinggi_cm": [tinggi],
    })


def _school_age_row(berat=13.0, tinggi=120.0, dob="2016-01-01", measure="2023-01-01"):
    """One fully-valid KPM/school row (~7y, in-range weight/height, valid gender)."""
    return pd.DataFrame({
        "jantina": ["LELAKI"],
        "id_murid": ["S001"],
        "Tarikh_Lahir": [dob],
        "Tarikh_Pengukuran": [measure],
        "berat_kg": [berat],
        "tinggi_cm": [tinggi],
    })


def _br_rows(report, rule_id):
    return sum(i.get("row_count", 0) for i in report.get("issues", [])
               if i.get("rule_id") == rule_id)


# ── cohort weight/height (make_*_profile → _apply_measurement_outlier) ─────────

def test_school_weight_override_flags_measurement_outlier():
    # default school_weight = 12–50 kg; 13 kg is valid. Raise min to 20 → 13 trips.
    _, base = clean_school_age(_school_age_row(berat=13.0))
    assert base["dropped_measurement_outlier"] == 0
    _, ov = clean_school_age(_school_age_row(berat=13.0),
                      range_overrides={"school_weight": {"min": 20.0, "max": 50.0}})
    assert ov["dropped_measurement_outlier"] > base["dropped_measurement_outlier"]


def test_infant_height_override_flags_measurement_outlier():
    # default infant_height = 30–130 cm; 85 cm is valid. Raise min to 90 → 85 trips.
    _, base = clean_wide_multiyear(_wide_multiyear_row(tinggi=85.0))
    assert base["dropped_measurement_outlier"] == 0
    _, ov = clean_wide_multiyear(_wide_multiyear_row(tinggi=85.0),
                         range_overrides={"infant_height": {"min": 90.0, "max": 130.0}})
    assert ov["dropped_measurement_outlier"] > base["dropped_measurement_outlier"]


# ── bmi_max (_apply_bmi_outlier) ──────────────────────────────────────────────

def test_bmi_max_override_flags_bmi_outlier():
    # weight 30 / height 90 → BMI ≈ 37.0: under default 40 (ok), over an 18 override.
    _, base = clean_wide_multiyear(_wide_multiyear_row(berat=30.0, tinggi=90.0))
    assert base["dropped_bmi_outlier"] == 0
    _, ov = clean_wide_multiyear(_wide_multiyear_row(berat=30.0, tinggi=90.0),
                         range_overrides={"bmi_max": {"value": 18.0}})
    assert ov["dropped_bmi_outlier"] > base["dropped_bmi_outlier"]


# ── infant_age_cap (dropped_age_over5) — tested via infant cleaner, not general ─

def test_infant_age_cap_override_flags_age_invalid():
    # ~48mo row: under default cap 60 (kept). Lower cap to 36 → 48 ≥ 36 → flagged.
    _, base = clean_wide_multiyear(_wide_multiyear_row(dob="2019-01-01", measure="2023-01-01"))
    assert base["dropped_age_over5"] == 0
    _, ov = clean_wide_multiyear(_wide_multiyear_row(dob="2019-01-01", measure="2023-01-01"),
                         range_overrides={"infant_age_cap": {"value": 36.0}})
    assert ov["dropped_age_over5"] > base["dropped_age_over5"]


# ── br02 / br03 (QualityChecker ctor injection) ───────────────────────────────

def test_br02_override_flags_impossible_weight():
    df = pd.DataFrame({"Berat_kg": [11.0, 20.0]})  # both within default 10–125
    base = analyze_quality(df.copy())
    assert _br_rows(base, "BR-02") == 0
    ov = analyze_quality(df.copy(),
                             range_overrides={"br02_weight_impossible": {"min": 15.0, "max": 125.0}})
    assert _br_rows(ov, "BR-02") > _br_rows(base, "BR-02")


def test_br03_override_flags_impossible_height():
    df = pd.DataFrame({"Tinggi_cm": [55.0, 120.0]})  # both within default 50–200
    base = analyze_quality(df.copy())
    assert _br_rows(base, "BR-03") == 0
    ov = analyze_quality(df.copy(),
                             range_overrides={"br03_height_impossible": {"min": 60.0, "max": 200.0}})
    assert _br_rows(ov, "BR-03") > _br_rows(base, "BR-03")


# ── end-to-end: the DISPATCH layer the app actually uses (clean_run → clean_data) ─

def test_clean_data_forwards_overrides_to_dispatched_cleaner():
    """The running app never calls clean_wide_multiyear directly — it calls clean_data,
    which dispatches by type. Prove range_overrides survives the dispatch so the
    editable keys take effect on the real /clean/run path, not just in unit tests."""
    df = _wide_multiyear_row(berat=30.0, tinggi=90.0)  # BMI ≈ 37
    _, base = clean_data(df.copy(), "wide_multiyear", None, None)
    assert base["dropped_bmi_outlier"] == 0
    _, ov = clean_data(df.copy(), "wide_multiyear", None, {"bmi_max": {"value": 18.0}})
    assert ov["dropped_bmi_outlier"] > base["dropped_bmi_outlier"]


# ── meta-guard: every editable key has a propagation test above ───────────────

def test_every_editable_key_is_covered():
    """If a key is exposed as editable it must be proven here. Cohort weight/height
    share one mechanism — school_weight + infant_height exercise both profile sides,
    so the four cohort keys are covered by mechanism."""
    covered_directly = {
        "school_weight", "infant_height", "bmi_max", "infant_age_cap",
        "br02_weight_impossible", "br03_height_impossible",
    }
    covered_by_mechanism = {"infant_weight", "school_height"}  # same profile path
    assert CR.EDITABLE_KEYS <= (covered_directly | covered_by_mechanism)
