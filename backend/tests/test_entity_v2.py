"""Unit tests for backend/ml/entity.py::link_records_v2 v2.1 features.

Covers the 10 cases listed in plans/peppy-toasting-turing.md:
  1. Name fuzzy match: 'Ali bin Ahmad' ↔ 'Ali Ahmad' (BIN stripping)
  2. Name fuzzy miss: completely different names below 0.6
  3. DOB ±1 day tolerance hit
  4. DOB ±2 day with dob_tolerance_days=1 miss
  5. Location boost: same IC + same negeri raises confidence
  6. Contradiction hard: same IC, jantina mismatch
  7. Contradiction soft: same IC, name fuzzy but not exact
  8. Timeline ordering: 3 sources with measurement dates → ascending
  9. Canonical tie-break: newest Dataset.created_at wins
 10. NaN survives as None — no 'nan' false-conflict for missing daerah

Tests call link_records_v2 directly with synthetic record dicts so we
don't need a cached DataFrame or DB. Pure-function level tests.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from backend.ml.entity import (
    _dob_equal,
    _name_similarity,
    _parse_dob,
    link_records_v2,
)


# ─── Helpers ────────────────────────────────────────────────────────────────

def _rec(**kw) -> dict:
    """Build a record with sensible defaults so tests stay short."""
    base = {
        "ic": "",
        "source_type": "MyVASS",
        "dataset_id": "ds-test",
        "name": None,
        "dob": None,
        "gender": None,
        "state": None,
        "district": None,
        "measure_date": None,
        "weight_kg": None,
        "height_cm": None,
        "bmi": None,
        "waz": None,
        "haz": None,
        "baz": None,
    }
    base.update(kw)
    return base


def _find_group(groups, ic):
    return next((g for g in groups if g["ic"] == ic), None)


# ─── 1. Name fuzzy match — BIN stripping ────────────────────────────────────

def test_name_fuzzy_handles_bin_particle():
    """'Ali bin Ahmad' and 'Ali Ahmad' should match >= 0.85 once particles
    are stripped — without the strip they'd only score ~0.66 on
    sorted-token ratio."""
    sim = _name_similarity("Ali bin Ahmad", "Ali Ahmad")
    assert sim >= 0.85, f"expected ≥0.85, got {sim:.3f}"


def test_name_fuzzy_groups_records_via_pass4():
    """Two IC-less records with fuzzy-name and same DOB should link."""
    records = [
        _rec(name="Ali bin Ahmad", dob="2020-05-12", source_type="MyVASS"),
        _rec(name="Ali Ahmad",     dob="2020-05-12", source_type="KKM",   dataset_id="ds-kkm"),
    ]
    groups = link_records_v2(records, min_confidence=0.0)
    matched = [g for g in groups if len(g["sources"]) > 1]
    assert len(matched) == 1
    reasons = matched[0]["match_reasons"]
    assert any(r.startswith("name_fuzzy") for r in reasons), reasons


# ─── 2. Name fuzzy miss — different names ───────────────────────────────────

def test_name_fuzzy_does_not_match_unrelated_names():
    sim = _name_similarity("Aiman Iskandar", "Pankaj Subramaniam")
    assert sim < 0.6, f"expected <0.6, got {sim:.3f}"

    records = [
        _rec(name="Aiman Iskandar",     dob="2021-01-15", source_type="MyVASS"),
        _rec(name="Pankaj Subramaniam", dob="2021-01-15", source_type="KKM", dataset_id="ds-kkm"),
    ]
    groups = link_records_v2(records, min_confidence=0.0)
    # Different children → two single-source groups, not one merged group.
    assert all(len(g["sources"]) == 1 for g in groups)


# ─── 3 & 4. DOB tolerance ──────────────────────────────────────────────────

def test_dob_equal_tolerance_one_day():
    assert _dob_equal("2020-05-12", "2020-05-13", tol_days=1) is True
    assert _dob_equal("2020-05-12", "2020-05-14", tol_days=1) is False


def test_dob_tolerance_links_one_day_apart():
    """Same-name records 1 day apart on DOB should link with tol=1."""
    records = [
        _rec(name="Sofea Lim", dob="2020-05-12", source_type="MyVASS"),
        _rec(name="Sofea Lim", dob="2020-05-13", source_type="KKM", dataset_id="ds-kkm"),
    ]
    groups = link_records_v2(records, dob_tolerance_days=1, min_confidence=0.0)
    matched = [g for g in groups if len(g["sources"]) > 1]
    assert len(matched) == 1


def test_dob_tolerance_misses_two_days_apart_when_tol_is_one():
    records = [
        _rec(name="Sofea Lim", dob="2020-05-12", source_type="MyVASS"),
        _rec(name="Sofea Lim", dob="2020-05-14", source_type="KKM", dataset_id="ds-kkm"),
    ]
    groups = link_records_v2(records, dob_tolerance_days=1, min_confidence=0.0)
    assert all(len(g["sources"]) == 1 for g in groups)


# ─── 5. Location boost ─────────────────────────────────────────────────────

def test_location_boost_raises_confidence_when_states_agree():
    """Exact IC + same state → confidence > 1.0 base, capped at 1.0."""
    # Use fuzzy IC so the base confidence is 0.85, not 1.0 — that way the
    # +0.10 boost is observable (1.0 cap doesn't hide it).
    records = [
        _rec(ic="200512100001", name="A", state="Selangor", source_type="MyVASS"),
        _rec(ic="200512100002", name="A", state="Selangor", source_type="KKM",
             dataset_id="ds-kkm"),
    ]
    boosted = link_records_v2(
        records, fuzzy_ic=True, fuzzy_ic_max_distance=1,
        location_boost=True, min_confidence=0.0,
    )
    not_boosted = link_records_v2(
        records, fuzzy_ic=True, fuzzy_ic_max_distance=1,
        location_boost=False, min_confidence=0.0,
    )
    bg = next(g for g in boosted     if len(g["sources"]) > 1)
    ng = next(g for g in not_boosted if len(g["sources"]) > 1)
    assert bg["confidence"] > ng["confidence"]
    assert "same_state" in bg["match_reasons"]


# ─── 6. Contradiction: hard (gender mismatch) ──────────────────────────────

def test_contradiction_hard_gender_mismatch():
    """Same IC, opposite gender → conflicts list with severity=hard."""
    records = [
        _rec(ic="200512100001", name="Sofea", gender="L", source_type="MyVASS"),
        _rec(ic="200512100001", name="Sofea", gender="P", source_type="KKM",
             dataset_id="ds-kkm"),
    ]
    groups = link_records_v2(records, min_confidence=0.0)
    g = next(grp for grp in groups if grp["ic"] == "200512100001")
    gender_conflicts = [c for c in g["conflicts"] if c["field"] == "gender"]
    assert len(gender_conflicts) == 1
    assert gender_conflicts[0]["severity"] == "hard"


# ─── 7. Contradiction: soft (name fuzzy but not exact) ─────────────────────

def test_contradiction_soft_name_fuzzy_not_exact():
    """Same IC, names match fuzzy but differ in particles → soft."""
    records = [
        _rec(ic="200512100001", name="Ali bin Ahmad", source_type="MyVASS"),
        _rec(ic="200512100001", name="Ali Ahmad",     source_type="KKM",
             dataset_id="ds-kkm"),
    ]
    groups = link_records_v2(records, min_confidence=0.0)
    g = next(grp for grp in groups if grp["ic"] == "200512100001")
    name_conflicts = [c for c in g["conflicts"] if c["field"] == "name"]
    assert len(name_conflicts) == 1
    assert name_conflicts[0]["severity"] == "soft"


# ─── 8. Timeline ordering ──────────────────────────────────────────────────

def test_timeline_orders_measurements_ascending():
    records = [
        _rec(ic="200512100001", source_type="MyVASS", measure_date="2025-06-01",
             weight_kg=12.0),
        _rec(ic="200512100001", source_type="KKM",    measure_date="2024-12-15",
             weight_kg=10.5, dataset_id="ds-kkm"),
        _rec(ic="200512100001", source_type="NCDC",   measure_date="2026-01-20",
             weight_kg=14.1, dataset_id="ds-ncdc"),
    ]
    groups = link_records_v2(records, min_confidence=0.0)
    g = next(grp for grp in groups if grp["ic"] == "200512100001")
    timeline = g["profile"]["timeline"]
    assert [t["date"] for t in timeline] == ["2024-12-15", "2025-06-01", "2026-01-20"]
    assert [t["weight_kg"] for t in timeline] == [10.5, 12.0, 14.1]


# ─── 9. Canonical tie-break: newest Dataset.created_at wins ────────────────

def test_canonical_prefers_newest_dataset_when_tied_on_frequency():
    """When two sources disagree 1-1 on name, the one from the newer
    dataset becomes canonical."""
    records = [
        _rec(ic="200512100001", name="OLD NAME", source_type="MyVASS", dataset_id="ds-old"),
        _rec(ic="200512100001", name="NEW NAME", source_type="MyVASS", dataset_id="ds-new"),
    ]
    created_at = {
        "ds-old": datetime(2024, 1, 1),
        "ds-new": datetime(2026, 5, 20),
    }
    groups = link_records_v2(
        records, dataset_created_at_by_id=created_at, min_confidence=0.0,
    )
    g = next(grp for grp in groups if grp["ic"] == "200512100001")
    assert g["profile"]["canonical"]["name"] == "NEW NAME"


# ─── 10. NaN survives as None — no false 'nan' conflict ───────────────────

def test_nan_district_does_not_trigger_false_conflict():
    """If one source has district=None (real NaN) and another has a value,
    the contradiction scanner must NOT treat None as a competing value."""
    records = [
        _rec(ic="200512100001", state="Selangor", district="Shah Alam",
             source_type="MyVASS"),
        _rec(ic="200512100001", state="Selangor", district=None,
             source_type="KKM", dataset_id="ds-kkm"),
    ]
    groups = link_records_v2(records, min_confidence=0.0)
    g = next(grp for grp in groups if grp["ic"] == "200512100001")
    district_conflicts = [c for c in g["conflicts"] if c["field"] == "district"]
    assert len(district_conflicts) == 0


# ─── Bonus: _parse_dob handles common Malaysian formats ────────────────────

@pytest.mark.parametrize("raw,expected_iso", [
    ("2020-05-12",  "2020-05-12"),
    ("12/05/2020",  "2020-05-12"),
    ("12-05-2020",  "2020-05-12"),
    ("20200512",    "2020-05-12"),
])
def test_parse_dob_accepts_common_formats(raw, expected_iso):
    parsed = _parse_dob(raw)
    assert parsed is not None
    assert parsed.isoformat() == expected_iso


def test_parse_dob_returns_none_for_garbage():
    for raw in ("", None, "nan", "NaT", "not a date", "??-??-????"):
        assert _parse_dob(raw) is None
