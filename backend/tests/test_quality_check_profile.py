"""B2.1: /clean/quality-check surfaces a per-column profile (top_values) and
PII-free actionable business-rule findings (future dates, impossible weights, …)."""
import uuid
import pandas as pd
from fastapi.testclient import TestClient
import backend.main as main

client = TestClient(main.app)


def _seed(df: pd.DataFrame) -> str:
    cid = str(uuid.uuid4())
    main._cleaned_cache[cid] = {"df": df, "stats": {}}
    return cid


def _kkm_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Jantina":            ["L", "P", "L", "XYZ"],          # XYZ → BR-05 unknown gender
        "Tarikh Pengukuran":  ["2024-01-01", "2024-02-01",
                               "2030-05-01", "2024-03-01"],     # 2030 → BR-09 future date
        "Berat (kg)":         [20.0, 22.0, 200.0, 18.0],        # 200 → BR-02 impossible weight
    })


# ── Per-column profile ──────────────────────────────────────────────────────────

def test_columns_profile_present():
    cid = _seed(_kkm_df())
    body = client.post(f"/clean/quality-check?cache_id={cid}").json()
    assert "columns" in body
    by_name = {c["name"]: c for c in body["columns"]}
    # numeric column carries min/max/mean
    berat = by_name["Berat (kg)"]
    assert berat["is_numeric"] is True
    assert berat["min"] == 18.0 and berat["max"] == 200.0
    # categorical column carries top_values with value/count/pct
    jantina = by_name["Jantina"]
    assert jantina["is_numeric"] is False
    assert jantina["top_values"], "expected top_values for categorical column"
    top = jantina["top_values"][0]
    assert set(top) == {"value", "count", "pct"}
    assert top["value"] == "L" and top["count"] == 2


# ── Actionable findings ─────────────────────────────────────────────────────────

def test_actionable_findings_detect_future_dates():
    cid = _seed(_kkm_df())
    body = client.post(f"/clean/quality-check?cache_id={cid}").json()
    findings = body.get("actionable_findings")
    assert isinstance(findings, list) and findings
    codes = {f["code"] for f in findings}
    assert "suspicious_dates" in codes  # BR-09 future date


def test_findings_are_pii_free():
    """Findings must carry only aggregate fields — never the checker's raw rows."""
    cid = _seed(_kkm_df())
    body = client.post(f"/clean/quality-check?cache_id={cid}").json()
    allowed = {"code", "rule_id", "field", "title", "description", "fix", "severity", "count", "pct"}
    for f in body["actionable_findings"]:
        assert set(f).issubset(allowed), f"unexpected key in finding: {set(f) - allowed}"
        assert f["severity"] in {"critical", "warning", "info"}


def test_findings_empty_when_clean():
    """A benign frame with no KKM-recognisable columns yields no findings (no crash)."""
    cid = _seed(pd.DataFrame({"foo": [1, 2, 3], "bar": ["a", "b", "c"]}))
    body = client.post(f"/clean/quality-check?cache_id={cid}").json()
    assert body["actionable_findings"] == []
