"""Regression: global clinical-range overrides (Settings) must reach the cleaner
on the non-cache endpoints too — not only the primary /clean/run path.

Before this fix, /clean/preview-impact, /clean/download, /clean/run-multi and
/clean/download-multi called clean_data() WITHOUT range_overrides, so a threshold
an operator changed in Settings was silently ignored on those paths. All five
sites now funnel through main._global_range_overrides(); this test pins that the
value actually arrives at clean_data().
"""
import uuid
import pandas as pd
from fastapi.testclient import TestClient
import backend.main as main

client = TestClient(main.app)

_OVERRIDE = {"bmi_max": {"value": 18.0}}


def _seed(df: pd.DataFrame) -> str:
    cid = str(uuid.uuid4())
    main._cleaned_cache[cid] = {"df": df, "stats": {}}
    return cid


def _kpm_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "ID_MURID":          ["A1", "A2"],
        "JANTINA":           ["L", "P"],
        "TARIKH LAHIR":      ["2018-01-01", "2018-01-01"],
        "TARIKH PENGUKURAN": ["2024-06-01", "2024-06-01"],
        "BERAT":             [20.0, 21.0],
        "TINGGI":            [115.0, 116.0],
    })


def test_preview_impact_forwards_global_overrides(monkeypatch):
    """The override returned by _global_range_overrides() must be passed verbatim
    into clean_data() as range_overrides."""
    monkeypatch.setattr(main, "_global_range_overrides", lambda: dict(_OVERRIDE))

    captured = {}
    real_clean_data = main.clean_data

    def _spy(df, data_type, enabled_rules=None, range_overrides=None):
        captured["range_overrides"] = range_overrides
        return real_clean_data(df, data_type, enabled_rules, range_overrides)

    monkeypatch.setattr(main, "clean_data", _spy)

    cid = _seed(_kpm_frame())
    resp = client.post(f"/clean/preview-impact?cache_id={cid}&data_type=kpm", json={})
    assert resp.status_code == 200
    assert captured["range_overrides"] == _OVERRIDE


def test_global_overrides_none_when_unset(monkeypatch):
    """Empty Settings → clean_data receives None (registry defaults apply),
    never an empty dict that could mask 'no override' from the cleaner."""
    monkeypatch.setattr(main, "_global_range_overrides", lambda: {})

    captured = {}
    real_clean_data = main.clean_data

    def _spy(df, data_type, enabled_rules=None, range_overrides=None):
        captured["range_overrides"] = range_overrides
        return real_clean_data(df, data_type, enabled_rules, range_overrides)

    monkeypatch.setattr(main, "clean_data", _spy)

    cid = _seed(_kpm_frame())
    resp = client.post(f"/clean/preview-impact?cache_id={cid}&data_type=kpm", json={})
    assert resp.status_code == 200
    assert captured["range_overrides"] is None
