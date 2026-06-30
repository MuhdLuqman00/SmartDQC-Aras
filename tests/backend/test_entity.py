import pytest
from backend.ml.entity import _normalise_ic, _ic_match_confidence, link_records


def test_normalise_ic_strips_dashes():
    assert _normalise_ic("880101-14-5678") == "880101145678"


def test_normalise_ic_invalid_length_returns_empty():
    assert _normalise_ic("12345") == ""


def test_normalise_ic_valid_12_digit():
    assert _normalise_ic("880101145678") == "880101145678"


def test_ic_match_confidence_exact():
    assert _ic_match_confidence("880101145678", "880101145678") == 1.0


def test_ic_match_confidence_no_match():
    assert _ic_match_confidence("880101145678", "990202246789") == 0.0


def test_link_records_exact_ic_match():
    records = [
        {"ic": "880101145678", "source_type": "wide_multiyear",
         "dataset_id": "ds1", "name": "Ahmad", "dob": "1988-01-01"},
        {"ic": "880101145678", "source_type": "klinik",
         "dataset_id": "ds2", "name": "Ahmad Bin Ali", "dob": "1988-01-01"},
    ]
    groups = link_records(records)
    assert len(groups) == 1
    assert len(groups[0]["sources"]) == 2
    assert groups[0]["match_confidence"] == 1.0


def test_link_records_no_match_different_ic():
    records = [
        {"ic": "880101145678", "source_type": "wide_multiyear",
         "dataset_id": "ds1", "name": "Ahmad", "dob": "1988-01-01"},
        {"ic": "990202246789", "source_type": "klinik",
         "dataset_id": "ds2", "name": "Siti", "dob": "1999-02-02"},
    ]
    groups = link_records(records)
    assert len(groups) == 2


def test_link_records_unified_profile_has_source_types():
    records = [
        {"ic": "880101145678", "source_type": "wide_multiyear",
         "dataset_id": "ds1", "name": "Ahmad", "dob": "1988-01-01"},
        {"ic": "880101145678", "source_type": "wide_registry",
         "dataset_id": "ds3", "name": "Ahmad", "dob": "1988-01-01"},
    ]
    groups = link_records(records)
    assert groups[0]["ic"] == "880101145678"
    assert "wide_multiyear" in groups[0]["source_types"]
    assert "wide_registry" in groups[0]["source_types"]
