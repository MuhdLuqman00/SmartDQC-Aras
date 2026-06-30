"""Phase 4: preview-cached endpoint must return per-row row_flags alongside rows."""
import uuid
import pandas as pd
from fastapi.testclient import TestClient
import backend.main as main

client = TestClient(main.app)


def _seed(df: pd.DataFrame) -> str:
    cid = str(uuid.uuid4())
    main._cleaned_cache[cid] = {"df": df, "stats": {}}
    return cid


def test_flags_via_data_quality_flag_column():
    """Provenance path: Data_Quality_Flag != 'Valid' rows are flagged."""
    df = pd.DataFrame({
        "Name": ["Alice", "Bob"],
        "Data_Quality_Flag": ["Valid", "Invalid Age"],
    })
    cid = _seed(df)
    resp = client.get(f"/clean/preview-cached/{cid}")
    assert resp.status_code == 200
    body = resp.json()
    assert "row_flags" in body
    assert body["row_flags"] == [False, True]


def test_flags_valid_quality_flag_not_flagged():
    """All 'Valid' rows — none flagged."""
    df = pd.DataFrame({
        "Name": ["Alice", "Bob"],
        "Data_Quality_Flag": ["Valid", "Valid"],
    })
    cid = _seed(df)
    body = client.get(f"/clean/preview-cached/{cid}").json()
    assert body["row_flags"] == [False, False]


def test_flags_fallback_berat_out_of_clinical_range():
    """Fallback: Berat_kg outside 12-50 kg is flagged."""
    df = pd.DataFrame({
        "Berat_kg": [25.0, 55.0],
        "Tinggi_cm": [120.0, 120.0],
    })
    cid = _seed(df)
    body = client.get(f"/clean/preview-cached/{cid}").json()
    assert "row_flags" in body
    assert body["row_flags"] == [False, True]


def test_flags_fallback_tinggi_out_of_clinical_range():
    """Fallback: Tinggi_cm outside 100-160 cm is flagged."""
    df = pd.DataFrame({
        "Berat_kg": [25.0, 25.0],
        "Tinggi_cm": [120.0, 90.0],
    })
    cid = _seed(df)
    body = client.get(f"/clean/preview-cached/{cid}").json()
    assert body["row_flags"] == [False, True]


def test_flags_fallback_missing_measurement():
    """Null in Berat_kg is treated as flagged."""
    df = pd.DataFrame({
        "Berat_kg": [25.0, None],
        "Tinggi_cm": [120.0, 120.0],
    })
    cid = _seed(df)
    body = client.get(f"/clean/preview-cached/{cid}").json()
    assert body["row_flags"][1] is True
    assert body["row_flags"][0] is False


def test_flags_no_clinical_columns_all_false():
    """No recognised clinical columns — all rows return False."""
    df = pd.DataFrame({"Name": ["Alice", "Bob"], "Score": [10, 20]})
    cid = _seed(df)
    body = client.get(f"/clean/preview-cached/{cid}").json()
    assert body["row_flags"] == [False, False]


def test_flags_length_matches_returned_rows():
    """row_flags length must equal returned (not row_count)."""
    df = pd.DataFrame({"Berat_kg": [25.0] * 10})
    cid = _seed(df)
    body = client.get(f"/clean/preview-cached/{cid}?limit=3").json()
    assert len(body["row_flags"]) == body["returned"] == 3
