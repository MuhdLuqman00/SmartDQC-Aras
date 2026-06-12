import pytest
from backend.ai.schema_mapper import ai_suggest_mapping, _needs_ai_assist


def test_needs_ai_assist_fires_when_core_field_missing():
    auto_map = {
        "jantina": "Gender", "berat_kg": None,
        "tinggi_cm": "Height", "tarikh_lahir": "DOB", "tarikh_ukur": "Msr_Date",
    }
    assert _needs_ai_assist(auto_map) is True


def test_needs_ai_assist_skips_when_all_core_mapped():
    # Optional fields unmapped (negeri, daerah) must NOT trigger the LLM.
    auto_map = {
        "jantina": "Gender", "berat_kg": "Weight",
        "tinggi_cm": "Height", "tarikh_lahir": "DOB", "tarikh_ukur": "Msr_Date",
        "negeri": None, "daerah": None,
    }
    assert _needs_ai_assist(auto_map) is False


def test_ai_suggest_mapping_returns_dict_with_standard_keys():
    from backend.config import STANDARD_SCHEMA
    columns = ["Child_ID", "Birth_Date", "Weight_KG", "Height_CM",
               "State_Name", "District", "Measurement_Date"]
    sample = {c: ["val1", "val2"] for c in columns}
    result = ai_suggest_mapping(columns, sample, source_type="unknown")
    for k, v in result.items():
        assert k in STANDARD_SCHEMA
        assert v is None or v in columns


def test_ai_suggest_mapping_drift_scenario(monkeypatch):
    from backend.config import STANDARD_SCHEMA
    import json
    columns = ["No. MyKid", "Berat2025", "Tinggi2025", "Negeri_Code", "Daerah_Name"]
    sample = {"No. MyKid": ["123456789012"], "Berat2025": ["12.5"],
              "Tinggi2025": ["95.0"], "Negeri_Code": ["SEL"], "Daerah_Name": ["Petaling"]}
    fake_response = {k: None for k in STANDARD_SCHEMA}
    fake_response["id"]       = "No. MyKid"
    fake_response["berat_kg"] = "Berat2025"
    fake_response["tinggi_cm"] = "Tinggi2025"
    import backend.ai.schema_mapper as sm
    monkeypatch.setattr(sm, "generate", lambda *a, **kw: json.dumps(fake_response))
    result = ai_suggest_mapping(columns, sample, source_type="myvass")
    assert result.get("id") == "No. MyKid"
