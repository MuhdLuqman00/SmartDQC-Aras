"""Phase 0 safety net for the unified cohort-aware cleaning engine refactor.

These are BEHAVIOR-PRESERVATION golden snapshots, not correctness oracles. They
pin the *current* output of the three named cleaners (wide_multiyear / wide_registry / school_age) on
fixtures that deliberately exercise the paths the refactor touches: exclusion
masks, cohort bounds, NCDC wide->long reshape, WHO z-scores, and school-age BMI
categories. Phases 1-2 (extract CohortProfile, unify the rule battery) must
reproduce these snapshots exactly; any drift means the named-cleaner behavior
changed and the "presets are config, not code" guarantee broke.

Notes
-----
* Fixtures use historical dates (2014-2023 births/measurements). Ages are derived
  from the two date columns (clock-independent) and no measurement date is in the
  future relative to any plausible run year, so these snapshots do NOT rot with
  the wall clock (unlike the BR-09/2030 review-rule test).
* Integer stats / flag vectors are asserted exactly. Float columns (z-scores,
  BMI, age) use a tolerance so a pure operation-reorder in the refactor that
  shifts a float by a ULP does not cry wolf.
"""
import os
import pathlib

import pandas as pd
import pytest

# WHO LMS tables load at import time; point the loader at the repo copy BEFORE
# importing cleaning so z-scores are real (mirrors test_clean_wide_multiyear_columns.py).
_ZDIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "zscore"
os.environ.setdefault("WHO_ZSCORE_DIR", str(_ZDIR))

from backend.eda import cleaning  # noqa: E402

_FTOL = 1e-3  # float tolerance for z-score / BMI / age columns


# ── Fixtures (raw column names; cleaners self-map via find_col) ───────────────
def _wide_multiyear() -> pd.DataFrame:
    # Infant cohort: clean, invalid gender, measure<dob, impossible height,
    # implausible weight.
    return pd.DataFrame({
        "JANTINA":           ["LELAKI", "ZZZ", "PEREMPUAN", "LELAKI", "PEREMPUAN", "LELAKI"],
        "TARIKH LAHIR":      ["2021-01-01"] * 6,
        "TARIKH PENGUKURAN": ["2023-01-01", "2023-01-01", "2022-01-01", "2023-01-01", "2023-01-01", "2023-01-01"],
        "BERAT (KG)":        [12.0, 12.0, 12.5, 13.0, 500.0, 11.5],
        "TINGGI (CM)":       [85.0, 85.0, 86.0, 300.0, 84.0, 83.0],
    })


def _wide_registry() -> pd.DataFrame:
    # Wide format, two measurement years -> reshaped to long (8 rows).
    return pd.DataFrame({
        "JANTINA":      ["L", "P", "L", "ZZZ"],
        "TARIKH LAHIR": ["2019-01-01"] * 4,
        "2022 Berat":   [16.0, 16.5, 999.0, 16.0],
        "2022 Tinggi":  [105.0, 106.0, 104.0, 105.0],
        "2022 Tarikh":  ["2022-06-01"] * 4,
        "2023 Berat":   [18.0, 18.5, 18.0, 18.0],
        "2023 Tinggi":  [110.0, 111.0, 109.0, 110.0],
        "2023 Tarikh":  ["2023-06-01"] * 4,
    })


def _school_age() -> pd.DataFrame:
    # School-age cohort: clean, duplicate id, invalid gender, implausible
    # weight, measure<dob.
    return pd.DataFrame({
        "ID_MURID":          ["A1", "A1", "A2", "A3", "A4"],
        "JANTINA":           ["L", "L", "ZZZ", "P", "L"],
        "TARIKH LAHIR":      ["2015-01-01"] * 5,
        "TARIKH PENGUKURAN": ["2023-06-01", "2023-06-01", "2023-06-01", "2023-06-01", "2014-06-01"],
        "BERAT":             [30.0, 30.0, 31.0, 500.0, 29.0],
        "TINGGI":            [130.0, 130.0, 131.0, 132.0, 128.0],
    })


# ── Expected snapshots (captured from current code 2026-06-11) ────────────────
GOLDEN = {
    "wide_multiyear": {
        "frame": _wide_multiyear,
        "len": 6,
        "stats": {
            "raw_count": 6, "data_type": "wide_multiyear", "dropped_invalid_gender": 1,
            "dropped_date_before_dob": 0, "dropped_age_over5": 0,
            "dropped_measurement_outlier": 2, "dropped_no_measurement": 0,
            "dropped_bmi_outlier": 0, "dropped_null_zscore": 0,
            "ind_kurang_berat": 0, "ind_bantut": 0, "ind_susut": 0,
            "ind_berlebihan_bb": 0, "ind_obes": 0, "ind_normal": 3,
            "final_count": 3, "total_dropped": 3, "review_count": 0,
            "gender_male": 2, "gender_female": 1,
        },
        "analyzable": [True, False, True, False, False, True],
        "exclude_reason": [
            "", "dropped_invalid_gender; dropped_null_zscore", "",
            "dropped_measurement_outlier; dropped_null_zscore",
            "dropped_measurement_outlier; dropped_bmi_outlier; dropped_null_zscore", "",
        ],
        "floats": {
            "WAZ": [-0.11, None, 2.64, None, None, -0.48],
            "HAZ": [-0.92, None, 4.66, None, None, -1.57],
            "BAZ": [0.68, None, 0.37, None, None, 0.74],
            "BMI": [16.61, 16.61, 16.9, 1.44, 708.62, 16.69],
            "Age_Days": [730.0, 730.0, 365.0, 730.0, 730.0, 730.0],
        },
    },
    "wide_registry": {
        "frame": _wide_registry,
        "len": 8,
        "stats": {
            "raw_count": 8, "data_type": "wide_registry", "years_found": [2022, 2023],
            "dropped_invalid_gender": 2, "dropped_pendapatan_x": 0,
            "dropped_null_dob": 0, "dropped_date_before_dob": 0,
            "dropped_age_invalid": 0, "dropped_measurement_outlier": 1,
            "dropped_no_measurement": 0, "dropped_bmi_outlier": 0,
            "dropped_duplicate_mykid": 0, "dropped_null_zscore": 0,
            "ind_kurang_berat": 0, "ind_bantut": 0, "ind_susut": 0,
            "ind_berlebihan_bb": 0, "ind_obes": 0, "ind_normal": 5,
            "final_count": 5, "total_dropped": 3, "review_count": 0,
            "gender_male": 3, "gender_female": 2,
            "year_counts": {2023: 3, 2022: 2},
        },
        "analyzable": [True, True, True, True, False, True, False, False],
        "exclude_reason": [
            "", "", "", "",
            "dropped_measurement_outlier; dropped_bmi_outlier; dropped_null_zscore", "",
            "dropped_invalid_gender; dropped_null_zscore",
            "dropped_invalid_gender; dropped_null_zscore",
        ],
        "floats": {
            "WAZ": [0.43, 0.36, 0.81, 0.6, None, 0.36, None, None],
            "HAZ": [1.47, 0.89, 1.89, 1.2, None, 0.66, None, None],
            "BAZ": [-0.8, -0.3, -0.5, -0.16, None, -0.09, None, None],
            "BMI": [14.51, 14.88, 14.68, 15.02, 923.63, 15.15, 14.51, 14.88],
            "Age_Days": [1247.0, 1612.0, 1247.0, 1612.0, 1247.0, 1612.0, 1247.0, 1612.0],
        },
    },
    "school_age": {
        "frame": _school_age,
        "len": 5,
        "stats": {
            "raw_count": 5, "data_type": "school_age", "dropped_ragu_gender": 0,
            "dropped_invalid_gender": 1, "dropped_duplicate_id": 1,
            "dropped_invalid_date": 1, "dropped_age_invalid": 0,
            "dropped_measurement_outlier": 1, "dropped_no_bmi": 0,
            "final_count": 1, "total_dropped": 4, "ind_kurus": 0,
            "ind_normal": 0, "ind_berlebihan": 1, "ind_obes": 0,
            "gender_male": 1, "gender_female": 0,
        },
        "analyzable": [True, False, False, False, False],
        "exclude_reason": [
            "", "dropped_duplicate_id", "dropped_invalid_gender",
            "dropped_measurement_outlier", "dropped_invalid_date; dropped_age_invalid",
        ],
        "floats": {
            "BMI": [17.75, 17.75, 18.06, 286.96, 17.7],
            "Age_Days": [3073.0, 3073.0, 3073.0, 3073.0, -214.0],
        },
    },
}


def _assert_floats(actual: pd.Series, expected: list, label: str):
    assert len(actual) == len(expected), f"{label}: length {len(actual)} != {len(expected)}"
    for i, exp in enumerate(expected):
        got = actual.iloc[i]
        if exp is None:
            assert pd.isna(got), f"{label}[{i}]: expected NaN, got {got}"
        else:
            assert not pd.isna(got), f"{label}[{i}]: expected {exp}, got NaN"
            assert got == pytest.approx(exp, abs=_FTOL), f"{label}[{i}]: {got} != {exp}"


@pytest.mark.parametrize("source", ["wide_multiyear", "wide_registry", "school_age"])
def test_named_cleaner_golden_snapshot(source):
    g = GOLDEN[source]
    cleaned, stats = cleaning.clean_data(g["frame"](), source)

    assert len(cleaned) == g["len"]

    # Every captured stat reproduced exactly (ints, lists, dicts).
    for key, exp in g["stats"].items():
        assert stats.get(key) == exp, f"stats[{key}]: {stats.get(key)} != {exp}"

    # No new dropped_* / ind_* keys silently appeared or changed.
    for key, val in stats.items():
        if key.startswith(("dropped_", "ind_")):
            assert key in g["stats"], f"unexpected new stat key: {key}={val}"

    # Flag vectors exact.
    assert [bool(x) for x in cleaned["analyzable"]] == g["analyzable"]
    assert [str(x) for x in cleaned["exclude_reason"]] == g["exclude_reason"]

    # Float columns within tolerance.
    for col, exp in g["floats"].items():
        assert col in cleaned.columns, f"missing float column {col}"
        _assert_floats(cleaned[col], exp, f"{source}.{col}")
