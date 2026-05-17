import uuid

import pandas as pd
from fastapi.testclient import TestClient
import backend.main as main

client = TestClient(main.app)


def _seed_cache() -> str:
    """Seed a cache entry under a valid uuid4 key.

    _cache_get rejects non-uuid keys via _is_valid_cache_key (path-traversal
    guard), so the seed key MUST be a real uuid4 or the endpoint 404s.
    """
    cache_id = str(uuid.uuid4())
    df = pd.DataFrame({"NAMA": ["Ali", "Siti"], "BERAT_KG": [12.0, 14.0]})
    main._cleaned_cache[cache_id] = {"df": df, "stats": {"source_type": "unknown"}}
    return cache_id


def test_patch_cell_updates_value_and_returns_row():
    cid = _seed_cache()
    resp = client.patch(
        "/clean/cell",
        json={"cache_id": cid, "row_index": 1, "column": "BERAT_KG", "value": "9.9"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["row"]["BERAT_KG"] in (9.9, "9.9")
    assert main._cleaned_cache[cid]["df"].iloc[1]["BERAT_KG"] in (9.9, "9.9")


def test_patch_cell_unknown_cache_id_404():
    resp = client.patch(
        "/clean/cell",
        json={"cache_id": str(uuid.uuid4()), "row_index": 0, "column": "X", "value": "1"},
    )
    assert resp.status_code == 404


def test_patch_cell_bad_column_400():
    cid = _seed_cache()
    resp = client.patch(
        "/clean/cell",
        json={"cache_id": cid, "row_index": 0, "column": "NOPE", "value": "1"},
    )
    assert resp.status_code == 400


def test_patch_cell_row_out_of_range_400():
    cid = _seed_cache()
    resp = client.patch(
        "/clean/cell",
        json={"cache_id": cid, "row_index": 999, "column": "NAMA", "value": "x"},
    )
    assert resp.status_code == 400
