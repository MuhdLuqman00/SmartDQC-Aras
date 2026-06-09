"""B3 endpoints: /clean/rules (registry view) and /clean/preview-impact
(true, side-effect-free row-impact for a proposed enabled_rules set)."""
import uuid
import pandas as pd
from fastapi.testclient import TestClient
import backend.main as main
from backend.eda.cleaning import rules_for_source

client = TestClient(main.app)


def _seed(df: pd.DataFrame) -> str:
    cid = str(uuid.uuid4())
    main._cleaned_cache[cid] = {"df": df, "stats": {}}
    return cid


def _kpm_dups() -> pd.DataFrame:
    return pd.DataFrame({
        "ID_MURID":          ["A1", "A1"],
        "JANTINA":           ["L", "L"],
        "TARIKH LAHIR":      ["2018-01-01", "2018-01-01"],
        "TARIKH PENGUKURAN": ["2024-06-01", "2024-06-01"],
        "BERAT":             [20.0, 20.0],
        "TINGGI":            [115.0, 115.0],
    })


def test_clean_rules_lists_registry():
    body = client.get("/clean/rules?data_type=kpm").json()
    codes = [x["code"] for x in body["rules"]]
    assert "dropped_duplicate_id" in codes
    nobmi = next(x for x in body["rules"] if x["code"] == "dropped_no_bmi")
    assert nobmi["locked"] is True
    assert {"en", "bm", "desc_en", "desc_bm"} <= set(nobmi)


def test_preview_impact_all_rules():
    cid = _seed(_kpm_dups())
    body = client.post(f"/clean/preview-impact?cache_id={cid}&data_type=kpm", json={}).json()
    assert body["rows_before"] == 2
    assert body["rows_after"] == 1
    dup = next(x for x in body["per_rule"] if x["code"] == "dropped_duplicate_id")
    assert dup["count"] == 1 and dup["fired"] is True and dup["enabled"] is True


def test_preview_impact_disable_dedup():
    cid = _seed(_kpm_dups())
    enabled = [r["code"] for r in rules_for_source("kpm") if r["code"] != "dropped_duplicate_id"]
    body = client.post(
        f"/clean/preview-impact?cache_id={cid}&data_type=kpm",
        json={"enabled_rules": enabled},
    ).json()
    assert body["rows_after"] == 2  # dedup off → both rows kept
    dup = next(x for x in body["per_rule"] if x["code"] == "dropped_duplicate_id")
    assert dup["count"] == 0 and dup["enabled"] is False
    # locked rule remains enabled even though omitted from enabled_rules
    nobmi = next(x for x in body["per_rule"] if x["code"] == "dropped_no_bmi")
    assert nobmi["locked"] is True and nobmi["enabled"] is True
