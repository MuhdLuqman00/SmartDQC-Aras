"""Phase G: unknown / near-known schemas must be mapped + cleaned honestly.

Covers: union-hints for unknown, generic cleaner never wipes rows,
unknown routing to the generic cleaner, and kpi.py surfacing unavailable
indicators.
"""
import numpy as np
import pandas as pd

from backend.config import auto_suggest_mapping
from backend.eda.cleaning import clean_data, clean_generic
from backend.eda.kpi import compute_kpi_dashboard


def test_unknown_uses_union_of_supported_hints():
    # Previously AUTO_MAPPING_HINTS.get("unknown") == {} → all None.
    cols = ["jantina", "tarikh lahir", "negeri", "weird_extra_col"]
    m = auto_suggest_mapping(cols, "unknown")
    assert m["jantina"] == "jantina"
    assert m["tarikh_lahir"] == "tarikh lahir"
    assert m["negeri"] == "negeri"


def test_union_hints_never_double_assign_one_column():
    m = auto_suggest_mapping(["jantina", "tarikh lahir"], "unknown")
    assigned = [v for v in m.values() if v is not None]
    assert len(assigned) == len(set(assigned))  # no raw column reused


def test_collision_guard_three_candidates_one_field_no_cross_assign():
    # "jantina"/"gender"/"sex" all alias the SAME canonical field. Exactly
    # one must win for `jantina`; the guard must not silently park the
    # leftovers under some other canonical field.
    m = auto_suggest_mapping(["jantina", "gender", "sex"], "unknown")
    assert m["jantina"] in ("jantina", "gender", "sex")
    assigned = [v for v in m.values() if v is not None]
    assert len(assigned) == len(set(assigned))   # invariant: no col reused
    # the two non-winning gender columns are NOT mapped onto unrelated fields
    non_gender = {k: v for k, v in m.items() if k != "jantina" and v is not None}
    assert not (set(non_gender.values()) & {"jantina", "gender", "sex"})


def test_clean_generic_does_not_wipe_rows_when_fields_missing():
    # No usable measurement/age/sex columns at all — must NOT drop every row.
    df = pd.DataFrame({"foo": [1, 2, 3], "bar": ["a", "b", "c"]})
    out, stats = clean_generic(df)
    assert len(out) == 3
    assert stats["data_type"] == "generic"
    assert "coverage" in stats and "indicators_unavailable" in stats


def test_clean_generic_marks_indicators_unavailable_not_fabricated():
    df = pd.DataFrame({"foo": [1, 2], "bar": ["x", "y"]})
    out, stats = clean_generic(df)
    # No Ind_* fabricated when inputs are absent.
    assert not [c for c in out.columns if c.startswith("Ind_")]
    assert set(stats["indicators_unavailable"]) >= {
        "stunting", "wasting", "underweight", "overweight"
    }


def test_clean_generic_preserves_rows_with_underscore_named_columns():
    # The drop-all bug: underscore date column + slightly-off names.
    df = pd.DataFrame({
        "Jantina": ["L", "P", "L"],
        "Tarikh_Lahir": ["2021-01-01", "2021-06-01", "2022-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01", "2023-01-01"],
        "Berat_Kg": [12.0, 11.0, 9.0],
        "Tinggi_Cm": [85.0, 80.0, 75.0],
    })
    out, stats = clean_generic(df)
    assert len(out) == 3  # not wiped to 0
    assert stats["coverage"]["jantina"] and stats["coverage"]["tarikh_lahir"]


def test_clean_data_routes_unknown_to_generic():
    df = pd.DataFrame({"a": [1], "b": [2]})
    for st in ("unknown", "something_new", "legacy_type"):
        out, stats = clean_data(df, st)  # must NOT raise ValueError
        assert stats["data_type"] == "generic"
        assert len(out) == 1


def test_kpi_surfaces_unavailable_indicators_without_crashing():
    df = pd.DataFrame({"Gender": ["Male", "Female"], "x": [1, 2]})
    out = compute_kpi_dashboard(df)
    assert "unavailable_indicators" in out
    assert len(out["unavailable_indicators"]) >= 1
    assert out["indicators"] == []  # nothing fabricated
