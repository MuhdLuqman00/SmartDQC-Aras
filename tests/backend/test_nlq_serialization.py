import json
import math

import numpy as np
import pandas as pd

from backend.ai.nlq import _to_json_native, _result_to_json_safe


def _assert_json_roundtrips(value):
    """A value is safe iff json.dumps accepts it without a default= hook —
    the same contract FastAPI's encoder and the JSONB column rely on."""
    json.dumps(value)


def test_numpy_int_scalar_becomes_native_int():
    out = _to_json_native(np.int64(7))
    assert out == 7
    assert isinstance(out, int) and not isinstance(out, np.generic)
    _assert_json_roundtrips(out)


def test_dict_of_numpy_counts_serialises():
    # df.groupby(...).size().to_dict() yields {str: np.int64} — the exact shape
    # that 500'd the /ai/nlq endpoint ("'numpy.int64' object is not iterable").
    result = {"Selangor": np.int64(5), "Johor": np.int64(3)}
    out = _to_json_native(result)
    assert out == {"Selangor": 5, "Johor": 3}
    assert all(isinstance(v, int) for v in out.values())
    _assert_json_roundtrips(out)


def test_nested_dataframe_serialises():
    # A DataFrame nested inside a dict is what broke the chat-append JSONB insert
    # ("Object of type DataFrame is not JSON serializable").
    df = pd.DataFrame({"negeri": ["Selangor", "Johor"], "n": [np.int64(5), np.int64(3)]})
    out = _to_json_native({"by_state": df})
    assert out == {"by_state": [{"negeri": "Selangor", "n": 5}, {"negeri": "Johor", "n": 3}]}
    _assert_json_roundtrips(out)


def test_series_becomes_dict():
    s = pd.Series({"a": np.int64(1), "b": np.int64(2)})
    out = _to_json_native(s)
    assert out == {"a": 1, "b": 2}
    _assert_json_roundtrips(out)


def test_nan_and_inf_become_null():
    out = _to_json_native({"x": float("nan"), "y": float("inf"), "z": 1.5})
    assert out["x"] is None and out["y"] is None and out["z"] == 1.5
    _assert_json_roundtrips(out)


def test_numpy_array_becomes_list():
    out = _to_json_native(np.array([1, 2, 3]))
    assert out == [1, 2, 3]
    _assert_json_roundtrips(out)


def test_dataframe_result_capped_at_20_rows():
    df = pd.DataFrame({"i": range(50)})
    out = _result_to_json_safe(df)
    assert isinstance(out, list) and len(out) == 20


def test_plain_values_pass_through():
    for v in (None, True, "hello", 42, 3.14):
        assert _to_json_native(v) == v
