"""HTTP-level contract tests for GET /report/pptx and /report/pdf.

These endpoints are consumed by the frontend ReportsPage via
`api.get(/report/pptx?cache_id=...&include_kpi=...)` — i.e. a GET with
query params, reading the cached EDA result by cache_id (mirroring the
working GET /clean/download-report/{cache_id} Excel endpoint).
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import app, _cache_cleaned

SAMPLE_EDA = {
    "summary": {"total_rows": 2, "source_type": "wide_multiyear"},
    "quality": {"overall_score": 0.78, "missing_rate": 0.12, "overall_completeness": 88.5},
    "indicators": {"stunting_rate": 0.24, "wasting_rate": 0.11, "underweight_rate": 0.18},
    "outliers": {"total_flagged": 1},
}


@pytest.fixture
def client(override_get_db):
    return TestClient(app)


@pytest.fixture
def cache_id():
    df = pd.DataFrame({"STATE": ["Sabah", "Selangor"], "stunting_flag": [1, 0]})
    return _cache_cleaned(df, SAMPLE_EDA)


def test_report_pptx_get_returns_pptx(client, cache_id):
    resp = client.get(f"/report/pptx?cache_id={cache_id}&include_kpi=true")
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # PPTX is a ZIP


def test_report_pdf_get_returns_pdf(client, cache_id):
    resp = client.get(f"/report/pdf?cache_id={cache_id}&include_kpi=true")
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_pptx_get_without_kpi(client, cache_id):
    resp = client.get(f"/report/pptx?cache_id={cache_id}&include_kpi=false")
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"


def test_report_pptx_unknown_cache_id_returns_404(client):
    resp = client.get("/report/pptx?cache_id=00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
