"""Tests for reconciliation summary + worklist (P2-5)."""


def test_reconciliation_summary_in_link_all(client_with_db, test_cache_with_data):
    """Test /entity/link/all includes reconciliation block."""
    cache_id, dataset_id = test_cache_with_data

    # Sync to persist
    client_with_db.post(
        "/entity/records/sync",
        json={"dataset_ids": [dataset_id]},
    )

    # Link all should include reconciliation
    response = client_with_db.post(
        "/entity/link/all",
        json={"dataset_ids": [dataset_id], "min_confidence": 0.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert "reconciliation" in body
    rec = body["reconciliation"]
    assert "total_records" in rec
    assert "unique_children" in rec
    assert "duplicate_records" in rec
    assert "duplication_rate" in rec
    assert "multi_source_children" in rec
    assert "source_overlap" in rec
    assert "conflicts_by_severity" in rec


def test_worklist_conflicts_csv(client_with_db, test_cache_with_data):
    """Test /entity/link/all/worklist?type=conflicts returns CSV."""
    cache_id, dataset_id = test_cache_with_data

    client_with_db.post(
        "/entity/records/sync",
        json={"dataset_ids": [dataset_id]},
    )

    response = client_with_db.get("/entity/link/all/worklist?type=conflicts")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    content = response.content.decode()
    assert "group_index" in content or content == ""  # May be empty if no conflicts


def test_worklist_duplicates_csv(client_with_db, test_cache_with_data):
    """Test /entity/link/all/worklist?type=duplicates returns CSV."""
    cache_id, dataset_id = test_cache_with_data

    client_with_db.post(
        "/entity/records/sync",
        json={"dataset_ids": [dataset_id]},
    )

    response = client_with_db.get("/entity/link/all/worklist?type=duplicates")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    content = response.content.decode()
    assert "group_index" in content or content == ""  # May be empty if no conflicts


def test_worklist_duplicates_csv(client_with_db, test_cache_with_data):
    """Test /entity/link/all/worklist?type=duplicates returns CSV."""
    cache_id, dataset_id = test_cache_with_data

    client_with_db.post(
        "/entity/records/sync",
        json={"dataset_ids": [dataset_id]},
    )

    response = client_with_db.get("/entity/link/all/worklist?type=duplicates")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
