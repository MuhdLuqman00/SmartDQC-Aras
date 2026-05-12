CREATE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS datasets (
        id          VARCHAR PRIMARY KEY,
        name        VARCHAR NOT NULL,
        filename    VARCHAR NOT NULL,
        source_type VARCHAR,
        row_count   INTEGER,
        created_at  TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id          VARCHAR PRIMARY KEY,
        dataset_id  VARCHAR NOT NULL REFERENCES datasets(id),
        notes       VARCHAR,
        created_at  TIMESTAMP NOT NULL,
        updated_at  TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analysis_results (
        id          VARCHAR PRIMARY KEY,
        session_id  VARCHAR NOT NULL REFERENCES sessions(id),
        result_type VARCHAR NOT NULL,
        result_json VARCHAR NOT NULL,
        created_at  TIMESTAMP NOT NULL
    )
    """,
]
