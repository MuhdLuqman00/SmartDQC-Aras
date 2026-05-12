import os
from pathlib import Path

import duckdb

from .models import CREATE_STATEMENTS


def init_db() -> None:
    db_path = os.environ.get("SMARTDQC_DB_PATH", "/app/data/smartdqc.duckdb")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(db_path) as conn:
        for stmt in CREATE_STATEMENTS:
            conn.execute(stmt)
