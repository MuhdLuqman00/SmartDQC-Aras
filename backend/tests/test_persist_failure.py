"""When DB persistence fails, /clean/run must still 200 but report it."""
import uuid
import logging

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import backend.main as main

client = TestClient(main.app)


@pytest.fixture
def _stub_clean(monkeypatch):
    """Isolate the persist branch: stub the cache, cleaner and EDA so the
    test exercises ONLY the _persist_session error handling."""
    # TestClient does not enter the FastAPI lifespan, so init_db() never runs
    # and SessionLocal is None. _persist_session is stubbed below, so the db
    # object is never actually used — override get_db with a harmless dummy.
    main.app.dependency_overrides[main.get_db] = lambda: iter([object()])
    df = pd.DataFrame({"NAMA": ["Ali", "Siti"], "BERAT_KG": [12.0, 14.0]})
    monkeypatch.setattr(main, "_resolve_cached_df", lambda cid: df.copy())
    monkeypatch.setattr(
        main, "_cache_get",
        lambda cid: {"stats": {"filename": "f.csv", "source_type": "unknown"}},
    )
    monkeypatch.setattr(main, "clean_data", lambda d, t: (d, {"source_type": t}))
    monkeypatch.setattr(
        main, "run_eda_auto",
        lambda d, t: {"data_quality_score": {"score": 80.0, "grade": "B"}},
    )
    monkeypatch.setattr(main, "_cache_cleaned", lambda d, s: str(uuid.uuid4()))
    monkeypatch.setattr(main, "_log_audit", lambda **k: None)
    yield str(uuid.uuid4())
    main.app.dependency_overrides.pop(main.get_db, None)


def test_persist_failure_returns_200_with_flag(_stub_clean, monkeypatch, caplog):
    def boom(**kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "_persist_session", boom)
    with caplog.at_level(logging.WARNING):
        r = client.post(f"/clean/run?cache_id={_stub_clean}&data_type=unknown", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is False
    assert body["persist_error"].startswith("RuntimeError")
    assert body["cache_id"]
    assert any("persistence failed" in m.lower() for m in caplog.messages)


def test_persist_success_sets_flag_true(_stub_clean, monkeypatch):
    monkeypatch.setattr(main, "_persist_session", lambda **kwargs: None)
    r = client.post(f"/clean/run?cache_id={_stub_clean}&data_type=unknown", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is True
    assert body["persist_error"] is None


@pytest.fixture
def _stub_eda(monkeypatch):
    """Isolate the /eda/run persist branch."""
    main.app.dependency_overrides[main.get_db] = lambda: iter([object()])
    df = pd.DataFrame({"NAMA": ["Ali"], "BERAT_KG": [12.0]})
    monkeypatch.setattr(main, "read_file", lambda c, f, s=None: (df.copy(), None))
    monkeypatch.setattr(
        main, "run_eda",
        lambda d, m, st, **k: {"_cleaned_data": [], "data_quality_score": {"score": 80.0}},
    )
    monkeypatch.setattr(main, "_cache_cleaned", lambda d, r: str(uuid.uuid4()))
    monkeypatch.setattr(main, "_log_audit", lambda **k: None)
    yield
    main.app.dependency_overrides.pop(main.get_db, None)


def _eda_post():
    return client.post(
        "/eda/run?source_type=unknown",
        files={"file": ("f.csv", b"NAMA,BERAT_KG\nAli,12", "text/csv")},
    )


def test_eda_persist_failure_logs_and_flags(_stub_eda, monkeypatch, caplog):
    def boom(**kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(main, "_persist_session", boom)
    with caplog.at_level(logging.WARNING):
        r = _eda_post()
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is False
    assert body["persist_error"].startswith("RuntimeError")
    assert any("persistence failed" in m.lower() for m in caplog.messages)


def test_eda_persist_success_sets_flag_true(_stub_eda, monkeypatch):
    monkeypatch.setattr(main, "_persist_session", lambda **kwargs: None)
    r = _eda_post()
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is True
    assert body["persist_error"] is None
