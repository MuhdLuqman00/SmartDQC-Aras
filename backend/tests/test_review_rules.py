"""Phase A — review-channel infrastructure (INF-1..3).

Pins that the infra exists and behaves correctly. Detection logic (rule fires)
comes in Phases B-D; these tests cover only the scaffolding.
"""
import pandas as pd
import pytest

from backend.eda.cleaning import (
    _flag,
    clean_wide_multiyear,
    clean_wide_registry,
    REVIEW_RULE_REGISTRY,
    REVIEW_EVALUATED_RULES,
    review_rules_for_source,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _wide_multiyear_df() -> pd.DataFrame:
    return pd.DataFrame({
        "JANTINA":           ["LELAKI", "PEREMPUAN"],
        "TARIKH LAHIR":      ["2020-01-01", "2020-01-01"],
        "TARIKH PENGUKURAN": ["2023-01-01", "2023-01-01"],
        "BERAT (KG)":        [12.0, 12.0],
        "TINGGI (CM)":       [85.0, 85.0],
    })


def _wide_registry_df() -> pd.DataFrame:
    return pd.DataFrame({
        "JANTINA":      ["L", "P"],
        "TARIKH LAHIR": ["2019-01-01", "2019-01-01"],
        "2023 Berat":   [18.0, 18.0],
        "2023 Tinggi":  [110.0, 110.0],
        "2023 Tarikh":  ["2023-06-01", "2023-06-01"],
    })


# ── INF-1: _flag() helper ─────────────────────────────────────────────────────

def test_flag_sets_review_reason_on_matched_rows():
    df = pd.DataFrame({"analyzable": [True, True], "review_reason": ["", ""]})
    _flag(df, pd.Series([True, False]), "test_code")
    assert df.loc[0, "review_reason"] == "test_code"
    assert df.loc[1, "review_reason"] == ""


def test_flag_leaves_analyzable_untouched():
    df = pd.DataFrame({"analyzable": [True, True], "review_reason": ["", ""]})
    _flag(df, pd.Series([True, True]), "any_code")
    assert df["analyzable"].all()


def test_flag_appends_semicolon_for_multi_fault_row():
    df = pd.DataFrame({"analyzable": [True], "review_reason": ["first_code"]})
    _flag(df, pd.Series([True]), "second_code")
    assert df.loc[0, "review_reason"] == "first_code; second_code"


def test_flag_noop_when_mask_all_false():
    df = pd.DataFrame({"analyzable": [True], "review_reason": [""]})
    _flag(df, pd.Series([False]), "test_code")
    assert df.loc[0, "review_reason"] == ""


# ── INF-1: review_reason column in cleaners ───────────────────────────────────

def test_clean_wide_multiyear_outputs_review_reason_column():
    df, _ = clean_wide_multiyear(_wide_multiyear_df())
    assert "review_reason" in df.columns


def test_clean_wide_multiyear_review_reason_is_string_dtype():
    import pandas as pd
    df, _ = clean_wide_multiyear(_wide_multiyear_df())
    assert pd.api.types.is_string_dtype(df["review_reason"])


def test_clean_wide_registry_outputs_review_reason_column():
    df, _ = clean_wide_registry(_wide_registry_df())
    assert "review_reason" in df.columns


def test_clean_wide_multiyear_stats_has_review_count():
    _, stats = clean_wide_multiyear(_wide_multiyear_df())
    assert "review_count" in stats
    assert isinstance(stats["review_count"], int)


def test_clean_wide_registry_stats_has_review_count():
    _, stats = clean_wide_registry(_wide_registry_df())
    assert "review_count" in stats
    assert isinstance(stats["review_count"], int)


def test_clean_wide_multiyear_review_count_zero_for_clean_data():
    _, stats = clean_wide_multiyear(_wide_multiyear_df())
    # No review rules fire yet (detection comes in Phase B-D); count must be 0
    assert stats["review_count"] == 0


# ── INF-2: REVIEW_RULE_REGISTRY ───────────────────────────────────────────────

def test_review_rule_registry_is_nonempty():
    assert len(REVIEW_RULE_REGISTRY) > 0


def test_review_rule_registry_all_entries_have_en_bm():
    for code, entry in REVIEW_RULE_REGISTRY.items():
        assert "en" in entry, f"{code} missing 'en'"
        assert "bm" in entry, f"{code} missing 'bm'"


def test_review_evaluated_rules_has_wide_multiyear_wide_registry_general():
    assert "wide_multiyear" in REVIEW_EVALUATED_RULES
    assert "wide_registry" in REVIEW_EVALUATED_RULES
    assert "general" in REVIEW_EVALUATED_RULES


def test_review_evaluated_rules_all_codes_exist_in_registry():
    for source, codes in REVIEW_EVALUATED_RULES.items():
        for code in codes:
            assert code in REVIEW_RULE_REGISTRY, (
                f"REVIEW_EVALUATED_RULES[{source!r}] references unknown code {code!r}"
            )


def test_review_rules_for_source_returns_list_of_dicts():
    result = review_rules_for_source("wide_multiyear")
    assert isinstance(result, list)
    assert len(result) > 0
    for entry in result:
        assert "code" in entry
        assert "en" in entry
        assert "bm" in entry


def test_review_rules_for_source_unknown_returns_general():
    result = review_rules_for_source("unknown_schema")
    assert isinstance(result, list)


# ── INF-3: _compute_row_flags reads review_reason ────────────────────────────

def test_compute_row_flags_true_for_nonempty_review_reason():
    import backend.main as main
    df = pd.DataFrame({
        "review_reason": ["review_future_measure_date", "", "review_daerah_null"],
    })
    result = main._compute_row_flags(df)
    assert bool(result.iloc[0]) is True
    assert bool(result.iloc[1]) is False
    assert bool(result.iloc[2]) is True


def test_compute_row_flags_false_when_review_reason_all_empty():
    import backend.main as main
    df = pd.DataFrame({"review_reason": ["", ""]})
    result = main._compute_row_flags(df)
    assert not result.any()
