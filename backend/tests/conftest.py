"""Pytest fixtures for backend P2 tests — shared SQLite harness.

Mirrors the proven tests/backend/conftest.py setup so the P2 endpoint tests
exercise the *real* app on an in-memory SQLite DB, with no live PostgreSQL and
no DATABASE_URL:

  * JSONB→JSON is patched BEFORE models import so SQLite can build the schema.
  * StaticPool + check_same_thread=False → one shared in-memory DB across the
    test session and the endpoint's get_db override.
  * PRAGMA foreign_keys=ON so ON DELETE CASCADE works (cascade test).
  * The TestClient is built *bare* (no `with`), so the app lifespan — which
    calls init_db() and hard-requires DATABASE_URL — is never triggered. The
    P2 routes use Depends(get_db), which we override to the test session.
"""

# JSONB→JSON MUST be patched before backend.db.models is imported anywhere.
import sqlalchemy.dialects.postgresql as _pg
from sqlalchemy.types import JSON as _JSON

_pg.JSONB = _JSON

from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def _engine():
    """Fresh in-memory SQLite per test, schema built from the ORM models."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    from backend.db.models import Base

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(_engine):
    """A session on the test engine. Also patches the app-global SessionLocal
    so code paths that use `with SessionLocal()` (e.g. /clean/run's persist
    hook) hit the test DB too."""
    TestSessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    with patch("backend.db.init_db.SessionLocal", TestSessionLocal):
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()


@pytest.fixture()
def client_with_db(db_session, monkeypatch, tmp_path):
    """Bare TestClient (no lifespan) with get_db overridden to the SAME session
    the seeding fixtures use, so endpoints see seeded data."""
    from fastapi.testclient import TestClient
    from backend import main
    from backend.db.init_db import get_db

    monkeypatch.setattr(main, "_CACHE_DIR", tmp_path)

    def _override_get_db():
        yield db_session

    main.app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(main.app)  # bare → lifespan/init_db never runs
    try:
        yield client
    finally:
        main.app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def test_dataset(db_session):
    from backend.db.models import Dataset

    ds = Dataset(
        id="test-ds-1",
        name="Test Dataset",
        filename="test.csv",
        source_type="myvass",
        row_count=10,
        created_at=datetime.utcnow(),
    )
    db_session.add(ds)
    db_session.commit()
    return ds


@pytest.fixture()
def test_cache_with_data(db_session, monkeypatch, tmp_path):
    """Seed a hot-cache DataFrame + a matching Dataset row so the sync and
    link-all endpoints have something to persist/read."""
    from backend import main
    from backend.db.models import Dataset

    df = pd.DataFrame(
        {
            "IC_NO_PASSPORT": ["900101010001", "900101010002", "910202020005"],
            "NAMA": ["ALI", "AHMAD", "SITI"],
            "TARIKH_LAHIR": ["2020-01-15", "2020-02-20", "2021-03-10"],
            "JANTINA": ["M", "M", "F"],
            "NEGERI": ["Selangor", "Johor", "KL"],
            "DAERAH": ["Petaling", "JB", "KL"],
            "BERAT_KG": [12.5, 14.0, 11.0],
            "TINGGI_CM": [85.0, 90.0, 80.0],
        }
    )

    # Cache keys must be valid UUIDs (_is_valid_cache_key rejects anything else).
    cache_id = "11111111-1111-1111-1111-111111111111"
    monkeypatch.setattr(main, "_CACHE_DIR", tmp_path)
    main._cleaned_cache[cache_id] = {
        "df": df,
        "stats": {"filename": "test.csv", "source_type": "myvass"},
    }

    ds = Dataset(
        id=cache_id,
        name="Test",
        filename="test.csv",
        source_type="myvass",
        row_count=3,
        created_at=datetime.utcnow(),
    )
    db_session.add(ds)
    db_session.commit()

    try:
        yield cache_id, cache_id
    finally:
        main._cleaned_cache.pop(cache_id, None)


@pytest.fixture()
def multiple_datasets_in_db(db_session):
    """Seed several datasets + child_records directly in the durable store
    (no hot cache) — exercises the P2-3 'sees evicted data' path."""
    from backend.db.models import Dataset, ChildRecord

    ds_ids = []
    for i in range(3):
        ds_id = f"test-ds-{i}"
        ds_ids.append(ds_id)
        db_session.add(
            Dataset(
                id=ds_id,
                name=f"Test {i}",
                filename=f"test{i}.csv",
                source_type="myvass",
                row_count=2,
                created_at=datetime.utcnow(),
            )
        )
        db_session.flush()  # parent Dataset before child rows (FK ordering)
        for j in range(2):
            db_session.add(
                ChildRecord(
                    dataset_id=ds_id,
                    source_type="myvass",
                    ic_norm=f"90010101000{i}{j}",
                    name=f"Child {i}-{j}",
                    dob=f"2020-0{i + 1}-15",
                    gender="M" if j == 0 else "F",
                )
            )
    db_session.commit()
    return ds_ids
