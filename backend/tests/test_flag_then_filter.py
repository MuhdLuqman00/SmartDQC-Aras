"""Phase 6: flag-then-filter invariants + download/Explorer view contracts.

The cleaners now FLAG bad rows (analyzable=False + exclude_reason) instead of
physically dropping them. These tests pin the invariants that make that safe:

  * the full frame is returned (no silent row loss)
  * analyzable is a real bool and final_count counts it
  * per-rule drop counts are non-overlapping (they sum to total_dropped)
  * analytics (KPI) and downloads project to analyzable-only by default
  * view=full exposes every row + the flag columns for auditing
  * the Explorer keeps every row (row-edit ids are positional) but hides the
    internal analyzable bool while surfacing exclude_reason
"""
import io
import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.eda.cleaning import clean_data
from backend.eda.kpi import compute_kpi_dashboard

client = TestClient(main.app)


# ── Fixtures: each has exactly one row that fails a quality rule ──────────────
def _school_age() -> pd.DataFrame:
    # Two identical rows → the duplicate-id rule excludes the second.
    return pd.DataFrame({
        "ID_MURID":          ["A1", "A1"],
        "JANTINA":           ["L", "L"],
        "TARIKH LAHIR":      ["2018-01-01", "2018-01-01"],
        "TARIKH PENGUKURAN": ["2024-06-01", "2024-06-01"],
        "BERAT":             [20.0, 20.0],
        "TINGGI":            [115.0, 115.0],
    })


def _wide_multiyear() -> pd.DataFrame:
    # Second row's gender is unmappable → invalid-gender rule excludes it.
    return pd.DataFrame({
        "JANTINA":           ["LELAKI", "ZZZ"],
        "TARIKH LAHIR":      ["2020-01-01", "2020-01-01"],
        "TARIKH PENGUKURAN": ["2023-01-01", "2023-01-01"],
        "BERAT (KG)":        [12.0, 12.0],
        "TINGGI (CM)":       [85.0, 85.0],
    })


def _wide_registry() -> pd.DataFrame:
    # Wide format: one measurement year → reshaped to long, two clean rows.
    return pd.DataFrame({
        "JANTINA":      ["L", "P"],
        "TARIKH LAHIR": ["2019-01-01", "2019-01-01"],
        "2023 Berat":   [18.0, 18.0],
        "2023 Tinggi":  [110.0, 110.0],
        "2023 Tarikh":  ["2023-06-01", "2023-06-01"],
    })


def _general() -> pd.DataFrame:
    return pd.DataFrame({"name": ["A", "B"], "value": [1, 2]})


# ── Cleaner-level invariants (all four cleaners) ─────────────────────────────
@pytest.mark.parametrize("source,frame_fn", [
    ("school_age", _school_age), ("wide_multiyear", _wide_multiyear), ("wide_registry", _wide_registry), ("general", _general),
])
def test_cleaner_flags_instead_of_dropping(source, frame_fn):
    cleaned, stats = clean_data(frame_fn(), source)

    # Full frame returned — len matches raw_count (post-reshape for wide_registry).
    assert len(cleaned) == stats["raw_count"]

    # Bookkeeping columns present and correctly typed.
    assert "analyzable" in cleaned.columns
    assert "exclude_reason" in cleaned.columns
    assert cleaned["analyzable"].dtype == bool

    # final_count is the analyzable-row count, not the frame length.
    assert stats["final_count"] == int(cleaned["analyzable"].sum())

    # Non-overlapping attribution: per-rule counts sum to total_dropped.
    per_rule = sum(v for k, v in stats.items() if k.startswith("dropped_"))
    assert per_rule == stats["total_dropped"]
    assert stats["total_dropped"] == stats["raw_count"] - stats["final_count"]


def test_per_rule_counts_do_not_double_count_a_multi_fault_row():
    """A single row that violates TWO rules is attributed to the first rule
    only, so per-rule counts stay non-overlapping (sum == total_dropped == 1,
    not 2). This is the invariant a single-fault fixture can't exercise."""
    df = pd.DataFrame({
        "JANTINA":           ["ZZZ"],          # invalid gender (earlier rule)
        "TARIKH LAHIR":      ["2020-01-01"],
        "TARIKH PENGUKURAN": ["2019-01-01"],   # measured before birth (later rule)
        "BERAT (KG)":        [12.0],
        "TINGGI (CM)":       [85.0],
    })
    _, stats = clean_data(df, "wide_multiyear")
    assert stats["final_count"] == 0
    assert stats["total_dropped"] == 1
    per_rule = sum(v for k, v in stats.items() if k.startswith("dropped_"))
    assert per_rule == 1                              # counted once, not twice
    assert stats.get("dropped_invalid_gender") == 1  # attributed to the first rule
    assert stats.get("dropped_date_before_dob", 0) == 0


def test_analysis_view_reproduces_drop_based_output():
    """view=analysis must equal what the old (physically-dropping) cleaners
    produced: analyzable rows only, neither flag column present."""
    cleaned, stats = clean_data(_school_age(), "school_age")
    av = main._analysis_view(cleaned)
    assert len(av) == stats["final_count"]
    assert "analyzable" not in av.columns
    assert "exclude_reason" not in av.columns


# ── KPI denominator ──────────────────────────────────────────────────────────
def test_kpi_denominator_uses_only_analyzable_rows():
    df = pd.DataFrame({
        "NEGERI":     ["Johor"] * 4,
        "stunting":   [1, 1, 0, 0],
        "analyzable": [True, True, False, False],
    })
    out = compute_kpi_dashboard(df)
    # 2 analyzable rows, both stunted → 100%, not 4 rows / 50%.
    assert out["total_children"] == 2
    ind = {i["key"]: i for i in out["indicators"]}
    assert ind["stunting"]["actual"] == 100.0


# ── Download view contract ───────────────────────────────────────────────────
def _seed(df: pd.DataFrame) -> str:
    cid = str(uuid.uuid4())
    main._cleaned_cache[cid] = {"df": df, "stats": {}}
    return cid


def _flagged_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "Name":           ["A", "B", "C"],
        "analyzable":     [True, False, True],
        "exclude_reason": ["", "dropped_bad_date", ""],
    })


def test_download_analysis_excludes_flagged_rows_and_flag_columns():
    cid = _seed(_flagged_frame())
    resp = client.get(f"/clean/download-cached/{cid}?fmt=csv&view=analysis")
    assert resp.status_code == 200
    df = pd.read_csv(io.BytesIO(resp.content))
    assert len(df) == 2                       # B (non-analyzable) dropped
    assert "analyzable" not in df.columns
    assert "exclude_reason" not in df.columns


def test_download_default_view_is_analysis():
    cid = _seed(_flagged_frame())
    resp = client.get(f"/clean/download-cached/{cid}?fmt=csv")
    df = pd.read_csv(io.BytesIO(resp.content))
    assert len(df) == 2
    assert "analyzable" not in df.columns


def test_download_full_includes_all_rows_and_flag_columns():
    cid = _seed(_flagged_frame())
    resp = client.get(f"/clean/download-cached/{cid}?fmt=csv&view=full")
    df = pd.read_csv(io.BytesIO(resp.content))
    assert len(df) == 3
    assert "analyzable" in df.columns
    assert "exclude_reason" in df.columns


def test_download_xlsx_view_full_keeps_flag_columns():
    cid = _seed(_flagged_frame())
    resp = client.get(f"/clean/download-xlsx/{cid}?view=full")
    wb = pd.read_excel(io.BytesIO(resp.content))
    assert len(wb) == 3
    assert "exclude_reason" in wb.columns


def test_download_xlsx_default_view_excludes_flagged():
    cid = _seed(_flagged_frame())
    resp = client.get(f"/clean/download-xlsx/{cid}")
    wb = pd.read_excel(io.BytesIO(resp.content))
    assert len(wb) == 2
    assert "analyzable" not in wb.columns


# ── Explorer projection ──────────────────────────────────────────────────────
def test_explorer_preview_hides_analyzable_but_keeps_all_rows():
    cid = _seed(_flagged_frame())
    resp = client.get(f"/clean/preview-cached/{cid}")
    body = resp.json()
    assert body["row_count"] == 3                  # every row kept
    assert "analyzable" not in body["columns"]      # internal bool hidden
    assert "exclude_reason" in body["columns"]      # the per-row "why" surfaced
