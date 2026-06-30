"""Phase C: narrative is persisted by cache_id and reused by reports.

Pins the roundtrip so reports stop receiving an empty {} narrative and
regeneration is latest-wins, without needing Ollama or a live server.
"""
import pandas as pd

from backend.main import (
    _cache_cleaned,
    _cache_get,
    _cache_set_narrative,
    _get_or_build_narrative,
)


def test_set_then_get_narrative_roundtrip():
    cid = _cache_cleaned(pd.DataFrame({"a": [1, 2]}), {"source_type": "wide_multiyear"})
    nar = {"executive_summary": {"en": "hello", "bm": "helo"}, "recommendations": []}
    _cache_set_narrative(cid, nar)
    assert _cache_get(cid)["narrative"] == nar


def test_regeneration_is_latest_wins():
    cid = _cache_cleaned(pd.DataFrame({"a": [1]}), {})
    _cache_set_narrative(cid, {"executive_summary": {"en": "v1", "bm": "v1"}})
    _cache_set_narrative(cid, {"executive_summary": {"en": "v2", "bm": "v2"}})
    assert _cache_get(cid)["narrative"]["executive_summary"]["en"] == "v2"


def test_get_or_build_returns_cached_without_regenerating():
    cid = _cache_cleaned(pd.DataFrame({"a": [1]}), {})
    sentinel = {"executive_summary": {"en": "cached", "bm": "cached"}}
    _cache_set_narrative(cid, sentinel)
    entry = _cache_get(cid)
    # Must return the cached one (no Ollama call) — proves report reuse path.
    assert _get_or_build_narrative(cid, entry) is sentinel
