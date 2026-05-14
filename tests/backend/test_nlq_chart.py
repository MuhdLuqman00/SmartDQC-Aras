import pytest
from backend.ai.nlq import _result_to_chart


def test_chart_returns_none_for_scalar():
    assert _result_to_chart(42) is None


def test_chart_returns_none_for_string():
    assert _result_to_chart("some text") is None


def test_chart_returns_none_for_empty_list():
    assert _result_to_chart([]) is None


def test_chart_returns_base64_for_dict_of_numerics():
    data = {"Petaling": 12.5, "Klang": 8.3, "Gombak": 15.1}
    result = _result_to_chart(data)
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 100


def test_chart_returns_base64_for_list_of_records():
    data = [
        {"district": "Petaling", "stunting_rate": 12.5},
        {"district": "Klang",    "stunting_rate": 8.3},
    ]
    result = _result_to_chart(data)
    assert result is not None
    assert isinstance(result, str)


def test_chart_returns_none_for_non_numeric_records():
    data = [{"district": "Petaling", "status": "Good"},
            {"district": "Klang",    "status": "Bad"}]
    assert _result_to_chart(data) is None
