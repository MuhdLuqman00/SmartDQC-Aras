import pytest
from backend.eda.compare import compare_datasets, _rate_delta, _quality_delta


def test_rate_delta_positive():
    assert _rate_delta(0.15, 0.10) == pytest.approx(5.0)


def test_rate_delta_negative():
    assert _rate_delta(0.08, 0.12) == pytest.approx(-4.0)


def test_rate_delta_baseline_zero_returns_none():
    assert _rate_delta(0.05, 0.0) is None


def test_quality_delta():
    assert _quality_delta(85, 80) == pytest.approx(5.0)


def test_compare_datasets_returns_expected_keys():
    summaries = [
        {"dataset_id": "ds1", "source_type": "wide_multiyear", "quality_score": 85,
         "indicators": {"stunting_rate": 0.12, "wasting_rate": 0.05}},
        {"dataset_id": "ds2", "source_type": "wide_multiyear", "quality_score": 78,
         "indicators": {"stunting_rate": 0.15, "wasting_rate": 0.04}},
    ]
    result = compare_datasets(summaries)
    assert "datasets" in result
    assert "deltas" in result
    assert "trend" in result


def test_compare_datasets_computes_stunting_delta():
    summaries = [
        {"dataset_id": "ds1", "source_type": "wide_multiyear", "quality_score": 85,
         "indicators": {"stunting_rate": 0.10}},
        {"dataset_id": "ds2", "source_type": "wide_multiyear", "quality_score": 90,
         "indicators": {"stunting_rate": 0.14}},
    ]
    result = compare_datasets(summaries)
    assert result["deltas"]["stunting_rate"] == pytest.approx(4.0)


def test_compare_datasets_trend_improving():
    summaries = [
        {"dataset_id": "ds1", "source_type": "wide_multiyear", "quality_score": 70,
         "indicators": {"stunting_rate": 0.20}},
        {"dataset_id": "ds2", "source_type": "wide_multiyear", "quality_score": 75,
         "indicators": {"stunting_rate": 0.17}},
        {"dataset_id": "ds3", "source_type": "wide_multiyear", "quality_score": 80,
         "indicators": {"stunting_rate": 0.14}},
    ]
    result = compare_datasets(summaries)
    assert result["trend"]["stunting_rate"] == "improving"
