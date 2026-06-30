"""Regression test for POST /datasets/compare.

Guards the bug where the endpoint queried a non-existent
AnalysisResult.dataset_id column (HTTP 500) and read a result_json shape
that is never written, so the Compare modal always came back empty.

Runs without a live DB or cache: the DB session is overridden with a fake
that returns synthetic Dataset rows, and the cache / target / KPI helpers are
monkeypatched. This exercises the real endpoint glue — quality from
Dataset.quality_score, indicators recomputed per dataset as fractions,
chronological sort, and graceful degradation when a dataset's cache is gone.
"""
import uuid
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

import backend.main as m
from backend.main import app, get_db


def _ds(name, quality, created):
    return SimpleNamespace(
        id=str(uuid.uuid4()), name=name, source_type="wide_multiyear",
        quality_score=quality, created_at=created,
    )


def test_datasets_compare_full_quality_and_indicators(monkeypatch):
    # Earliest and latest are cached (so their indicators populate); the
    # middle one has no cache (indicators must degrade to empty, not 500).
    earliest = _ds("old.csv",     70.0, datetime(2026, 1, 1))   # stunting 24%
    middle   = _ds("nocache.csv", 60.0, datetime(2026, 2, 1))   # cache evicted
    latest   = _ds("new.csv",     85.0, datetime(2026, 3, 1))   # stunting 20%
    store = {d.id: d for d in (earliest, middle, latest)}

    # df carries the stunting % for the dataset so the fake KPI can vary it.
    stunting_pct = {earliest.id: 24.0, latest.id: 20.0}

    class FakeDB:
        def get(self, _model, ds_id):
            return store.get(ds_id)

    def fake_cache_get(cid):
        return None if cid == middle.id else {"df": stunting_pct[cid]}

    def fake_kpi(df, npan, who):
        return {"indicators": [{"key": "stunting", "actual": df}]}

    app.dependency_overrides[get_db] = lambda: FakeDB()
    monkeypatch.setattr(m, "_load_kpi_targets", lambda db: {"npan": {}, "who": {}})
    monkeypatch.setattr(m, "_cache_get", fake_cache_get)
    monkeypatch.setattr(m, "compute_kpi_dashboard", fake_kpi)

    try:
        client = TestClient(app)
        # Send out of chronological order — endpoint must sort oldest→latest.
        r = client.post("/datasets/compare",
                        json={"dataset_ids": [latest.id, earliest.id, middle.id]})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200, r.text
    body = r.json()

    # Chronological order regardless of request order.
    names = [d["name"] for d in body["datasets"]]
    assert names == ["old.csv", "nocache.csv", "new.csv"]

    by_name = {d["name"]: d for d in body["datasets"]}
    # Quality comes straight from the Dataset row.
    assert by_name["old.csv"]["quality_score"] == 70.0
    assert by_name["new.csv"]["quality_score"] == 85.0
    # Indicators recomputed as fractions for cached datasets.
    assert by_name["old.csv"]["indicators"]["stunting_rate"] == 0.24
    assert by_name["new.csv"]["indicators"]["stunting_rate"] == 0.20
    # Evicted cache degrades to empty indicators — not a 500.
    assert by_name["nocache.csv"]["indicators"] == {}

    # Deltas/trend are computed latest-vs-earliest.
    assert body["deltas"]["quality_score"] == 15.0            # 85 - 70
    assert body["deltas"]["stunting_rate"] == -4.0            # (0.20 - 0.24) * 100
    assert body["trend"]["stunting_rate"] == "improving"      # lower is better


def test_datasets_compare_requires_two(monkeypatch):
    app.dependency_overrides[get_db] = lambda: object()
    try:
        client = TestClient(app)
        r = client.post("/datasets/compare", json={"dataset_ids": ["only-one"]})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 400
