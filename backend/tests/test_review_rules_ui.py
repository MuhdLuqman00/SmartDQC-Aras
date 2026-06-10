"""Tests for review-rules UI integration (Phases 1 & 2).

Covers:
- All active review rules have desc_en / desc_bm
- Deferred rules never appear in /settings/rules or /clean/rules
- /settings/rules returns both drop (kind=drop) and review (kind=review) groups
- /clean/rules returns both groups per data_type
- /settings/rules/toggle accepts review codes
- D2 merge: persisted review disable suppresses flags in a clean run
- Edge case: all review rules disabled -> _review_rule_on constrains via sentinel

Note: /settings/rules and /settings/rules/toggle require a DB session and use
the client_with_db fixture from conftest.py (SQLite-backed). /clean/rules has a
best-effort fallback so the bare module-level client works.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.eda.cleaning import (
    REVIEW_RULE_REGISTRY,
    REVIEW_EVALUATED_RULES,
    _review_rule_on,
    _REVIEW_MANAGED_SENTINEL,
    clean_myvass,
)

# Bare client — no DB. OK for /clean/rules (try-except fallback) and unit tests.
client = TestClient(main.app)

# Deferred codes that must never surface in endpoints
_DEFERRED = {"review_daerah_not_in_negeri", "review_class_range_mismatch"}

# Active codes = union of all REVIEW_EVALUATED_RULES values
_ACTIVE_CODES = {c for codes in REVIEW_EVALUATED_RULES.values() for c in codes}


# ── Phase 1: Registry descriptions ───────────────────────────────────────────

def test_all_active_rules_have_desc_en():
    for code in _ACTIVE_CODES:
        assert "desc_en" in REVIEW_RULE_REGISTRY[code], f"{code} missing desc_en"
        assert REVIEW_RULE_REGISTRY[code]["desc_en"], f"{code} desc_en is empty"


def test_all_active_rules_have_desc_bm():
    for code in _ACTIVE_CODES:
        assert "desc_bm" in REVIEW_RULE_REGISTRY[code], f"{code} missing desc_bm"
        assert REVIEW_RULE_REGISTRY[code]["desc_bm"], f"{code} desc_bm is empty"


def test_deferred_rules_have_descriptions_too():
    """Deferred entries stay in registry for labelling; they just don't surface."""
    for code in _DEFERRED:
        assert "desc_en" in REVIEW_RULE_REGISTRY[code]
        assert "desc_bm" in REVIEW_RULE_REGISTRY[code]


# ── Phase 1: /settings/rules endpoint (requires DB via client_with_db) ───────

def test_settings_rules_returns_both_kinds(client_with_db):
    r = client_with_db.get("/settings/rules")
    assert r.status_code == 200
    rules = r.json()["rules"]
    kinds = {x["kind"] for x in rules}
    assert "drop" in kinds
    assert "review" in kinds


def test_settings_rules_no_deferred_codes(client_with_db):
    r = client_with_db.get("/settings/rules")
    assert r.status_code == 200
    codes = {x["code"] for x in r.json()["rules"]}
    for code in _DEFERRED:
        assert code not in codes, f"Deferred rule {code} must not appear in /settings/rules"


def test_settings_rules_review_have_descriptions(client_with_db):
    r = client_with_db.get("/settings/rules")
    assert r.status_code == 200
    for rule in r.json()["rules"]:
        if rule["kind"] == "review":
            assert rule.get("desc_en"), f"{rule['code']} missing desc_en"
            assert rule.get("desc_bm"), f"{rule['code']} missing desc_bm"


def test_settings_rules_review_have_source_types(client_with_db):
    r = client_with_db.get("/settings/rules")
    assert r.status_code == 200
    for rule in r.json()["rules"]:
        if rule["kind"] == "review":
            assert isinstance(rule["source_types"], list)
            assert len(rule["source_types"]) > 0, f"{rule['code']} has empty source_types"


def test_settings_rules_review_not_locked(client_with_db):
    r = client_with_db.get("/settings/rules")
    assert r.status_code == 200
    for rule in r.json()["rules"]:
        if rule["kind"] == "review":
            assert rule.get("locked") is False, f"{rule['code']} should not be locked"


# ── Phase 1: /clean/rules endpoint (bare client, try-except fallback) ─────────

def test_clean_rules_myvass_returns_both_kinds():
    r = client.get("/clean/rules?data_type=myvass")
    assert r.status_code == 200
    rules = r.json()["rules"]
    kinds = {x["kind"] for x in rules}
    assert "drop" in kinds
    assert "review" in kinds


def test_clean_rules_ncdc_has_review_rules():
    r = client.get("/clean/rules?data_type=ncdc")
    assert r.status_code == 200
    review = [x for x in r.json()["rules"] if x["kind"] == "review"]
    assert len(review) > 0


def test_clean_rules_general_has_no_review_rules():
    """general schema has empty REVIEW_EVALUATED_RULES so no review rules appear."""
    r = client.get("/clean/rules?data_type=general")
    assert r.status_code == 200
    review = [x for x in r.json()["rules"] if x["kind"] == "review"]
    assert len(review) == 0


def test_clean_rules_no_deferred():
    for dt in ("myvass", "ncdc", "general"):
        r = client.get(f"/clean/rules?data_type={dt}")
        codes = {x["code"] for x in r.json()["rules"]}
        for code in _DEFERRED:
            assert code not in codes, (
                f"Deferred {code} appeared in /clean/rules?data_type={dt}"
            )


# ── Phase 2: toggle accepts review codes (requires DB) ───────────────────────

def test_toggle_review_rule_accepted(client_with_db):
    r = client_with_db.post(
        "/settings/rules/toggle",
        json={"rule": "review_daerah_null", "enabled": False},
    )
    assert r.status_code == 200
    rules = r.json()["rules"]
    toggled = next((x for x in rules if x["code"] == "review_daerah_null"), None)
    assert toggled is not None
    assert toggled["enabled"] is False
    # Restore
    client_with_db.post("/settings/rules/toggle", json={"rule": "review_daerah_null", "enabled": True})


def test_toggle_deferred_review_rule_rejected(client_with_db):
    r = client_with_db.post(
        "/settings/rules/toggle",
        json={"rule": "review_daerah_not_in_negeri", "enabled": False},
    )
    assert r.status_code == 404


def test_toggle_unknown_code_rejected(client_with_db):
    r = client_with_db.post(
        "/settings/rules/toggle",
        json={"rule": "review_nonexistent_rule", "enabled": False},
    )
    assert r.status_code == 404


# ── Phase 2: _review_rule_on sentinel behaviour ───────────────────────────────

def test_sentinel_suppresses_all_review_rules_when_all_disabled():
    """With sentinel + no review codes, _review_rule_on returns False (all off)."""
    drop_only_with_sentinel = {"dropped_no_dob", _REVIEW_MANAGED_SENTINEL}
    assert _review_rule_on("review_ic_malformed", drop_only_with_sentinel) is False


def test_drop_only_set_without_sentinel_leaves_review_rules_on():
    """A drop-only set without sentinel still leaves all review rules ON (back-compat)."""
    drop_only = {"dropped_no_dob"}
    assert _review_rule_on("review_ic_malformed", drop_only) is True


def test_none_enabled_rules_all_review_on():
    assert _review_rule_on("review_ic_malformed", None) is True


def test_review_code_in_set_is_on():
    enabled = {"review_ic_malformed", "dropped_no_dob"}
    assert _review_rule_on("review_ic_malformed", enabled) is True
    assert _review_rule_on("review_daerah_null", enabled) is False


# ── Phase 2: sentinel suppresses flag in cleaner ─────────────────────────────

def _future_date_df():
    """Row 0: future measurement date triggers review_future_measure_date.
    Row 1: clean row."""
    future = (pd.Timestamp.today() + pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    return pd.DataFrame({
        "IC_NO_PASSPORT": ["200101010101", "200101010102"],
        "jantina": ["LELAKI", "PEREMPUAN"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": [future, "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })


def test_review_rule_fires_when_enabled():
    df = _future_date_df()
    cleaned, _ = clean_myvass(df, enabled_rules=None)
    assert "review_future_measure_date" in str(cleaned.loc[0, "review_reason"])


def test_review_rule_suppressed_when_disabled_via_sentinel():
    """Sentinel + code absent = rule is off; flag must not appear."""
    df = _future_date_df()
    rules = {_REVIEW_MANAGED_SENTINEL, "dropped_no_dob"}
    cleaned, _ = clean_myvass(df, enabled_rules=rules)
    assert "review_future_measure_date" not in str(cleaned.loc[0, "review_reason"])
