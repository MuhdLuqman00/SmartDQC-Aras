import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client(override_get_db):
    return TestClient(app)


def test_get_thresholds_returns_defaults(client):
    resp = client.get("/settings/thresholds")
    assert resp.status_code == 200
    data = resp.json()
    assert "missing_rate_warn" in data
    assert "missing_rate_fail" in data


def test_post_thresholds_persists(client):
    resp = client.post("/settings/thresholds", json={"missing_rate_warn": 0.07})
    assert resp.status_code == 200
    resp2 = client.get("/settings/thresholds")
    assert resp2.json()["missing_rate_warn"] == pytest.approx(0.07)


def test_get_rules_returns_registry(client):
    resp = client.get("/settings/rules")
    assert resp.status_code == 200
    rules = {r["code"]: r for r in resp.json()["rules"]}
    # real cleaner rule codes (B3), not the old inert rules.all keys
    assert "dropped_invalid_gender" in rules
    assert rules["dropped_null_zscore"]["locked"] is True
    assert {"en", "bm", "desc_en", "desc_bm", "enabled"} <= set(rules["dropped_invalid_gender"])
    # schema applicability (B3 schema filter): no-BMI is KPM-only; null-zscore is wide_multiyear/wide_registry
    assert "school_age" in rules["dropped_no_bmi"]["source_types"]
    assert "school_age" not in rules["dropped_null_zscore"]["source_types"]


def test_toggle_rule_disables(client):
    resp = client.post("/settings/rules/toggle", json={"rule": "dropped_invalid_gender", "enabled": False})
    assert resp.status_code == 200
    rules = {r["code"]: r for r in client.get("/settings/rules").json()["rules"]}
    assert rules["dropped_invalid_gender"]["enabled"] is False


def test_toggle_locked_rule_rejected(client):
    resp = client.post("/settings/rules/toggle", json={"rule": "dropped_null_zscore", "enabled": False})
    assert resp.status_code == 400


def test_toggle_unknown_rule_returns_404(client):
    resp = client.post("/settings/rules/toggle", json={"rule": "nonexistent_rule", "enabled": True})
    assert resp.status_code == 404
