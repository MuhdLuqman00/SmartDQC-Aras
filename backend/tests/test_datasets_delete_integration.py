import os
import uuid
from datetime import datetime

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="requires a live PostgreSQL DATABASE_URL",
)


def test_delete_datasets_removes_rows_cache_and_unlinks_entity(tmp_path, monkeypatch):
    from backend.db.init_db import init_db
    import backend.db.init_db as initdb
    init_db()
    from backend.db.models import (
        Dataset, Session as _Session, AnalysisResult, EntityLinkage,
    )
    import backend.main as m

    monkeypatch.setattr(m, "_CACHE_DIR", tmp_path)

    ds_id = str(uuid.uuid4())
    sess_id = str(uuid.uuid4())
    ar_id = str(uuid.uuid4())
    now = datetime.utcnow()

    with initdb.SessionLocal() as db:
        db.add(Dataset(id=ds_id, name="t", filename="t.csv",
                        source_type="myvass", row_count=1,
                        quality_score=50.0, created_at=now))
        db.add(_Session(id=sess_id, dataset_id=ds_id,
                         created_at=now, updated_at=now))
        db.add(AnalysisResult(id=ar_id, session_id=sess_id,
                              result_type="clean", result_json={"a": 1},
                              created_at=now))
        db.add(EntityLinkage(ic_no="IC123", source_type="myvass",
                             dataset_id=ds_id, created_at=now))
        db.commit()
        linkage_id = db.query(EntityLinkage).filter(
            EntityLinkage.dataset_id == ds_id).one().id

    pkl = tmp_path / f"{ds_id}.pkl"
    pkl.write_bytes(b"x")

    with initdb.SessionLocal() as db:
        result = m._delete_datasets(db, [ds_id, "does-not-exist"])

    assert result["deleted"] == [ds_id]
    assert result["not_found"] == ["does-not-exist"]
    assert not pkl.exists()
    with initdb.SessionLocal() as db:
        assert db.get(Dataset, ds_id) is None
        assert db.get(_Session, sess_id) is None
        assert db.get(AnalysisResult, ar_id) is None
        link = db.get(EntityLinkage, linkage_id)
        assert link is not None and link.dataset_id is None
