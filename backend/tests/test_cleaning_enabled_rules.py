"""B3: clean_data honours an enabled_rules selection — a disabled rule records a
0 count and retains its rows; locked rules always run; None == all-enabled."""
import pandas as pd
from backend.eda.cleaning import clean_data, rules_for_source, LOCKED_RULES


def _kpm_dups() -> pd.DataFrame:
    # Two identical KPM rows (same student ID) that both clean successfully.
    return pd.DataFrame({
        "ID_MURID":          ["A1", "A1"],
        "JANTINA":           ["L", "L"],
        "TARIKH LAHIR":      ["2018-01-01", "2018-01-01"],
        "TARIKH PENGUKURAN": ["2024-06-01", "2024-06-01"],
        "BERAT":             [20.0, 20.0],
        "TINGGI":            [115.0, 115.0],
    })


def test_disable_rule_retains_rows():
    df = _kpm_dups()
    _, s_on = clean_data(df, "kpm")                       # all rules (None)
    assert s_on["dropped_duplicate_id"] == 1
    assert s_on["final_count"] == 1

    enabled = {r["code"] for r in rules_for_source("kpm")} - {"dropped_duplicate_id"}
    _, s_off = clean_data(df, "kpm", enabled)             # dedup disabled
    assert s_off["dropped_duplicate_id"] == 0
    assert s_off["final_count"] == 2                       # both rows kept


def test_none_equals_all_enabled():
    df = _kpm_dups()
    _, s_none = clean_data(df, "kpm")
    all_codes = {r["code"] for r in rules_for_source("kpm")}
    _, s_all = clean_data(df, "kpm", all_codes)
    assert s_none["final_count"] == s_all["final_count"]
    assert s_none["dropped_duplicate_id"] == s_all["dropped_duplicate_id"]


def test_locked_rule_always_runs():
    """dropped_no_bmi is locked: it runs even with an empty enabled set."""
    assert "dropped_no_bmi" in LOCKED_RULES
    df = pd.DataFrame({
        "ID_MURID":          ["B1"],
        "JANTINA":           ["P"],
        "TARIKH LAHIR":      ["2018-01-01"],
        "TARIKH PENGUKURAN": ["2024-06-01"],
        "BERAT":             [None],          # no weight → no BMI → locked drop
        "TINGGI":            [115.0],
    })
    _, s = clean_data(df, "kpm", enabled_rules=set())     # nothing user-enabled
    assert s["final_count"] == 0                           # locked gate still removed it
