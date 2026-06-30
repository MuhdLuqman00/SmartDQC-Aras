"""Tests for child_record table (P2-1)."""

from datetime import datetime


def test_child_record_create_and_query(db_session):
    """Test creating a child record and querying by dataset_id and ic_norm."""
    from backend.db.models import ChildRecord, Dataset

    now = datetime.utcnow()
    ds_id = "test-ds-1"

    # Create parent dataset
    ds = Dataset(
        id=ds_id,
        name="test",
        filename="test.csv",
        source_type="wide_multiyear",
        row_count=1,
        quality_score=50.0,
        created_at=now,
    )
    db_session.add(ds)
    db_session.flush()  # parent before child (FK ordering)

    # Create child record
    rec = ChildRecord(
        dataset_id=ds_id,
        source_type="wide_multiyear",
        ic_norm="900101010001",
        name="ALI BIN AHMAD",
        dob="2020-01-15",
        gender="M",
        state="Selangor",
        district="Petaling",
        measure_date="2020-03-01",
        weight_kg=12.5,
        height_cm=85.0,
        bmi=17.3,
        waz=0.5,
        haz=1.2,
        baz=0.8,
    )
    db_session.add(rec)
    db_session.commit()

    # Query by dataset_id
    results = (
        db_session.query(ChildRecord).filter(ChildRecord.dataset_id == ds_id).all()
    )
    assert len(results) == 1
    assert results[0].ic_norm == "900101010001"
    assert results[0].name == "ALI BIN AHMAD"


def test_child_record_query_by_ic_norm(db_session):
    """Test querying child records by ic_norm across datasets."""
    from backend.db.models import ChildRecord, Dataset

    now = datetime.utcnow()
    ds1_id = "test-ds-1"
    ds2_id = "test-ds-2"

    # Create parent datasets
    db_session.add(
        Dataset(
            id=ds1_id,
            name="test1",
            filename="test1.csv",
            source_type="wide_multiyear",
            row_count=1,
            created_at=now,
        )
    )
    db_session.add(
        Dataset(
            id=ds2_id,
            name="test2",
            filename="test2.csv",
            source_type="wide_registry",
            row_count=1,
            created_at=now,
        )
    )
    db_session.flush()  # parents before children (FK ordering)

    # Create child records with same IC
    db_session.add(
        ChildRecord(
            dataset_id=ds1_id, source_type="wide_multiyear", ic_norm="900101010001", name="ALI"
        )
    )
    db_session.add(
        ChildRecord(
            dataset_id=ds2_id,
            source_type="wide_registry",
            ic_norm="900101010001",
            name="ALI BIN AHMAD",
        )
    )
    db_session.commit()

    # Query by ic_norm
    results = (
        db_session.query(ChildRecord)
        .filter(ChildRecord.ic_norm == "900101010001")
        .all()
    )
    assert len(results) == 2
    assert {r.dataset_id for r in results} == {ds1_id, ds2_id}


def test_child_record_cascade_delete(db_session):
    """Test that deleting a dataset cascades to child_record."""
    from backend.db.models import ChildRecord, Dataset

    now = datetime.utcnow()
    ds_id = "test-ds-1"

    # Create dataset and child record
    db_session.add(
        Dataset(
            id=ds_id,
            name="test",
            filename="test.csv",
            source_type="wide_multiyear",
            row_count=1,
            created_at=now,
        )
    )
    db_session.flush()  # parent before child (FK ordering)
    db_session.add(
        ChildRecord(
            dataset_id=ds_id, source_type="wide_multiyear", ic_norm="900101010001", name="ALI"
        )
    )
    db_session.commit()

    # Verify record exists
    count = (
        db_session.query(ChildRecord).filter(ChildRecord.dataset_id == ds_id).count()
    )
    assert count == 1

    # Delete dataset
    db_session.query(Dataset).filter(Dataset.id == ds_id).delete()
    db_session.commit()

    # Verify child record is gone (cascade)
    count = (
        db_session.query(ChildRecord).filter(ChildRecord.dataset_id == ds_id).count()
    )
    assert count == 0
