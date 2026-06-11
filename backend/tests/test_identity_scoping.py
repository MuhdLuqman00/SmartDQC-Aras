"""Functional coverage for the anonymous named-identity scoping (Fix A).

The rest of the suite runs header-less, so it only exercises the `owner is
None` no-op branch — it proves no regression, not that scoping works. These
tests send the X-User header and assert the actual per-person filtering:

  * each person sees only their own datasets/sessions (+ legacy un-owned rows),
  * a different person's rows are hidden,
  * matching is case-insensitive (cross-device portability — "Alice" == "alice"),
  * no header → unscoped (no regression for un-headered callers),
  * persistence stamps the owner.
"""
from datetime import datetime

from backend import main
from backend.db.models import Dataset


def _seed(db, ds_id, owner):
    db.add(
        Dataset(
            id=ds_id,
            name=ds_id,
            filename=f"{ds_id}.csv",
            source_type="myvass",
            row_count=1,
            created_at=datetime.utcnow(),
            owner=owner,
        )
    )
    db.commit()


def test_datasets_scoped_by_identity(client_with_db, db_session):
    _seed(db_session, "ds-alice", "alice")
    _seed(db_session, "ds-bob", "bob")
    _seed(db_session, "ds-legacy", None)

    alice = {d["id"] for d in client_with_db.get("/datasets", headers={"X-User": "alice"}).json()}
    assert "ds-alice" in alice          # own dataset
    assert "ds-legacy" in alice         # legacy un-owned stays visible to all
    assert "ds-bob" not in alice        # other person's hidden

    bob = {d["id"] for d in client_with_db.get("/datasets", headers={"X-User": "bob"}).json()}
    assert "ds-bob" in bob
    assert "ds-alice" not in bob

    # Case-insensitive: a different-cased name on another device still resolves
    # to the same owner — the whole point of cross-device history.
    cased = {d["id"] for d in client_with_db.get("/datasets", headers={"X-User": "ALICE"}).json()}
    assert "ds-alice" in cased
    assert "ds-bob" not in cased

    # No identity header → unscoped, full library (no regression).
    unscoped = {d["id"] for d in client_with_db.get("/datasets").json()}
    assert {"ds-alice", "ds-bob", "ds-legacy"} <= unscoped


def test_sessions_scoped_by_identity(client_with_db, db_session):
    _seed(db_session, "sess-alice", "alice")
    _seed(db_session, "sess-bob", "bob")

    alice = {r["cache_id"] for r in client_with_db.get("/sessions", headers={"X-User": "alice"}).json()}
    assert "sess-alice" in alice
    assert "sess-bob" not in alice


def test_dashboard_summary_scoped_by_identity(client_with_db, db_session):
    # alice owns two, bob one, plus a legacy un-owned row visible to all.
    _seed(db_session, "dash-alice-1", "alice")
    _seed(db_session, "dash-alice-2", "alice")
    _seed(db_session, "dash-bob-1", "bob")
    _seed(db_session, "dash-legacy", None)

    alice = client_with_db.get("/dashboard/summary", headers={"X-User": "alice"}).json()
    assert alice["session_count"] == 3            # 2 own + 1 legacy
    assert "bob" not in alice["latest_session"]["cache_id"]

    bob = client_with_db.get("/dashboard/summary", headers={"X-User": "bob"}).json()
    assert bob["session_count"] == 2              # 1 own + 1 legacy
    assert bob["latest_session"]["cache_id"] in {"dash-bob-1", "dash-legacy"}

    # No identity header → unscoped (no regression): every row counts.
    unscoped = client_with_db.get("/dashboard/summary").json()
    assert unscoped["session_count"] == 4


def test_persist_session_stamps_owner(db_session):
    main._persist_session(
        cache_id="cid-owner-1",
        filename="f.csv",
        source_type="myvass",
        row_count=5,
        result={"quality_score": 90.0, "issues": []},
        db=db_session,
        owner="carol",
    )
    ds = db_session.query(Dataset).filter_by(id="cid-owner-1").first()
    assert ds is not None
    assert ds.owner == "carol"
