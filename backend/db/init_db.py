import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

engine = None
SessionLocal = None


def init_db() -> None:
    global engine, SessionLocal

    url = os.environ["DATABASE_URL"]  # Hard fail — no silent fallback
    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        connect_args={"options": "-c statement_timeout=300000"},
    )
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Database connection verified.")

    # Idempotent additive migration — create_all only creates tables that
    # don't already exist, so this is safe to run on every boot. Lets the
    # chat_sessions / chat_messages tables come into existence without an
    # external migration step. Existing tables are untouched.
    try:
        from .models import Base
        Base.metadata.create_all(engine)
        logger.info("Database schema ensured (Base.metadata.create_all).")
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("create_all() failed: %s", exc)

    # create_all() only creates missing *tables*, never adds columns to an
    # existing one. The anonymous-identity `owner` column must be backfilled
    # onto an already-deployed `datasets` table. Postgres supports
    # ADD COLUMN IF NOT EXISTS, so this is idempotent and safe on every boot.
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE datasets ADD COLUMN IF NOT EXISTS owner VARCHAR")
            )
        logger.info("Migration ensured: datasets.owner column.")
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("datasets.owner migration failed: %s", exc)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
