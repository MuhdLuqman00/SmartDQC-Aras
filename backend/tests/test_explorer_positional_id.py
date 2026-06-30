"""4e positional-id preservation: editing an excluded row via _row_id must land
on the correct cached record regardless of the "Analyzable only" display filter.

Root cause being guarded: /clean/query-cached assigns _row_id = iloc position
in the full df (all rows, flag-then-filter columns stripped). If the endpoint
silently resliced to analyzable rows only, _row_id would desync from entry["df"]
and every edit would corrupt the wrong record.

This test verifies:
1. query-cached returns ALL rows (no implicit analyzable filter).
2. Each row's _row_id equals its sequential 0-based position.
3. An edit sent with _row_id pointing at an excluded row updates the correct
   cell in entry["df"].
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client_and_cache(monkeypatch, tmp_path):
    """Minimal setup: bare TestClient + one seeded cache entry."""
    from backend import main

    monkeypatch.setattr(main, "_CACHE_DIR", tmp_path)

    df = pd.DataFrame(
        {
            "IC_NO_PASSPORT": ["010101010001", "020202020002", "030303030003",
                               "040404040004", "050505050005"],
            "Berat_kg":       [12.0, 9.5, 14.0, 11.5, 13.0],
            "Negeri":         ["Selangor"] * 5,
            "analyzable":     [True, False, True, False, True],
            "exclude_reason": [None, "dropped_invalid_gender", None,
                               "dropped_null_dob", None],
        }
    )

    cache_id = "aaaa0000-1111-2222-3333-444444444444"
    main._cleaned_cache[cache_id] = {
        "df": df,
        "stats": {"filename": "test.csv", "source_type": "wide_multiyear"},
    }

    client = TestClient(main.app)
    try:
        yield client, cache_id
    finally:
        main._cleaned_cache.pop(cache_id, None)


def test_query_cached_returns_all_rows(client_and_cache):
    """Explorer must return every row, not just the analyzable subset."""
    client, cache_id = client_and_cache
    r = client.post("/clean/query-cached", json={"cache_id": cache_id, "limit": 100})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5, f"Expected 5 rows (all), got {data['total']}"
    assert len(data["rows"]) == 5


def test_row_ids_are_sequential_positional(client_and_cache):
    """_row_id for each row must equal its 0-based position in entry['df']."""
    client, cache_id = client_and_cache
    r = client.post("/clean/query-cached", json={"cache_id": cache_id, "limit": 100})
    rows = r.json()["rows"]
    for expected_pos, row in enumerate(rows):
        assert row["_row_id"] == expected_pos, (
            f"Row at position {expected_pos} has _row_id={row['_row_id']}"
        )


def test_edit_excluded_row_via_row_id_lands_correctly(client_and_cache):
    """Editing an excluded row using its _row_id must update the right record."""
    from backend import main

    client, cache_id = client_and_cache

    # Row index 1 is excluded (analyzable=False). Edit its Berat_kg.
    excluded_row_id = 1
    new_weight = 99.9

    r = client.patch("/clean/cell", json={
        "cache_id": cache_id,
        "row_index": excluded_row_id,
        "column": "Berat_kg",
        "value": new_weight,
    })
    assert r.status_code == 200

    # The edit must land at iloc[1] in the original cached df.
    entry = main._cleaned_cache[cache_id]
    actual = entry["df"].iloc[excluded_row_id]["Berat_kg"]
    assert float(actual) == new_weight, (
        f"Edit landed at wrong row — expected Berat_kg={new_weight}, got {actual}"
    )


def test_excluded_row_id_unchanged_after_edit(client_and_cache):
    """After editing, re-querying the excluded row still returns _row_id=1."""
    client, cache_id = client_and_cache

    client.patch("/clean/cell", json={
        "cache_id": cache_id, "row_index": 1, "column": "Berat_kg", "value": 88.8,
    })

    r = client.post("/clean/query-cached", json={"cache_id": cache_id, "limit": 100})
    rows = r.json()["rows"]
    row1 = next(row for row in rows if row["_row_id"] == 1)
    assert float(row1["Berat_kg"]) == 88.8
