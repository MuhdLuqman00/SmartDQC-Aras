import pandas as pd
from backend.ml.corrections import (
    flag_anomalies,
    _detect_decimal_shift,
    _detect_transposition,
    _detect_column_swap,
    _classify_error_type,
)


def test_detect_decimal_shift_x10():
    # 320 / 32 = 10.0 -> decimal_shift_x10
    assert _detect_decimal_shift(320.0, 32.0) == "decimal_shift_x10"


def test_detect_decimal_shift_div10():
    # 3.2 / 32.0 = 0.1 -> decimal_shift_div10
    assert _detect_decimal_shift(3.2, 32.0) == "decimal_shift_div10"


def test_detect_decimal_shift_none_for_normal_value():
    # 35 / 32 ~= 1.09 -> no shift
    assert _detect_decimal_shift(35.0, 32.0) is None


def test_detect_transposition_swapped_adjacent_digits():
    # "139": swap positions 0+1 -> "319" which equals median 319 -> True
    assert _detect_transposition(139.0, 319.0) is True


def test_detect_transposition_no_match():
    # No adjacent swap of "100" produces 999
    assert _detect_transposition(100.0, 999.0) is False


def test_detect_column_swap_matches_other_column():
    col_stats = {
        "waz":       {"median": -1.5,  "q1": -2.0,  "q3": -1.0},
        "weight_kg": {"median": 25.5,  "q1": 23.0,  "q3": 28.0},
    }
    # val=25.0 for waz falls within weight_kg median(25.5) +/- iqr(5.0)
    assert _detect_column_swap(25.0, "waz", col_stats) == "column_swap:weight_kg"


def test_classify_error_type_decimal_shift_is_entry_error():
    assert _classify_error_type("decimal_shift_x10")   == "entry_error"
    assert _classify_error_type("decimal_shift_div10")  == "entry_error"
    assert _classify_error_type("digit_transposition")  == "entry_error"


def test_flag_anomalies_suggestion_includes_pattern_and_error_type():
    # 20 normal rows + 1 row with 10x value -> clear decimal shift
    data = {"weight": [25.0] * 20 + [250.0]}
    df = pd.DataFrame(data)
    result = flag_anomalies(df)
    flagged = result["flagged_rows"]
    assert len(flagged) >= 1
    sugg = flagged[0]["suggestions"]
    assert len(sugg) >= 1
    assert "pattern"    in sugg[0]
    assert "error_type" in sugg[0]
    assert sugg[0]["pattern"]    == "decimal_shift_x10"
    assert sugg[0]["error_type"] == "entry_error"
