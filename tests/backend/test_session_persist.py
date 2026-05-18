import pytest
import uuid
import numpy as np
from datetime import datetime
from backend.main import _persist_session
from backend.db.models import Dataset, Session as DBSession, AnalysisResult


def test_persist_session_creates_dataset(db_session):
    cache_id = str(uuid.uuid4())
    _persist_session(
        cache_id=cache_id,
        filename="test.csv",
        source_type="myvass",
        row_count=500,
        result={"quality_score": 88, "issues": []},
        db=db_session,
    )
    ds = db_session.query(Dataset).filter_by(id=cache_id).first()
    assert ds is not None
    assert ds.filename == "test.csv"
    assert ds.source_type == "myvass"
    assert ds.row_count == 500


def test_persist_session_creates_session_record(db_session):
    cache_id = str(uuid.uuid4())
    _persist_session(
        cache_id=cache_id,
        filename="f.csv",
        source_type="klinik",
        row_count=100,
        result={"quality_score": 75},
        db=db_session,
    )
    sess = db_session.query(DBSession).filter_by(dataset_id=cache_id).first()
    assert sess is not None


def test_persist_session_stores_quality_in_analysis_result(db_session):
    cache_id = str(uuid.uuid4())
    _persist_session(
        cache_id=cache_id,
        filename="g.csv",
        source_type="myvass",
        row_count=200,
        result={"quality_score": 92, "issues": ["missing_ic"]},
        db=db_session,
    )
    sess = db_session.query(DBSession).filter_by(dataset_id=cache_id).first()
    ar = db_session.query(AnalysisResult).filter_by(session_id=sess.id).first()
    assert ar is not None
    assert ar.result_type == "quality"
    assert ar.result_json["quality_score"] == 92


def test_persist_session_accepts_numpy_scalars(db_session):
    # Regression: pandas/EDA hands back numpy scalars. NumPy 2.x reprs
    # np.float64(79.0) as the literal "np.float64(79.0)", which psycopg2
    # emitted into SQL -> Postgres "schema np does not exist". The np.int64
    # inside issues also breaks the JSON column's json.dumps on any backend.
    cache_id = str(uuid.uuid4())
    _persist_session(
        cache_id=cache_id,
        filename="Contoh data.xlsx",
        source_type="myvass",
        row_count=13,
        result={
            "quality_score": np.float64(79.0),
            "issues": [{"rule": "missing_ic", "count": np.int64(3)}],
        },
        db=db_session,
    )
    ds = db_session.query(Dataset).filter_by(id=cache_id).first()
    assert ds is not None
    assert ds.quality_score == 79.0
    sess = db_session.query(DBSession).filter_by(dataset_id=cache_id).first()
    ar = db_session.query(AnalysisResult).filter_by(session_id=sess.id).first()
    assert ar.result_json["quality_score"] == 79.0
    assert ar.result_json["issues"][0]["count"] == 3
