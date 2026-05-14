import pytest
from fastapi.testclient import TestClient
from backend.main import app, _log_audit


@pytest.fixture
def client(override_get_db):
    return TestClient(app)


def test_log_audit_does_not_raise():
    try:
        _log_audit(action="test.action", dataset_id=None, detail="unit test", user_id=None)
    except Exception as exc:
        pytest.fail(f"_log_audit raised: {exc}")


def test_audit_log_endpoint_returns_list(client):
    resp = client.get("/audit/log")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_audit_log_filter_by_dataset(client):
    resp = client.get("/audit/log?dataset_id=99999")
    assert resp.status_code == 200
    assert resp.json() == []
