"""indexes and jsonb

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_sessions_dataset_id", "sessions", ["dataset_id"])
    op.create_index("ix_analysis_results_session_id", "analysis_results", ["session_id"])
    op.create_index("ix_analysis_results_result_type", "analysis_results", ["result_type"])
    op.alter_column(
        "analysis_results",
        "result_json",
        type_=JSONB(),
        postgresql_using="result_json::jsonb",
    )


def downgrade() -> None:
    op.alter_column(
        "analysis_results",
        "result_json",
        type_=sa.Text(),
        postgresql_using="result_json::text",
    )
    op.drop_index("ix_analysis_results_result_type", "analysis_results")
    op.drop_index("ix_analysis_results_session_id", "analysis_results")
    op.drop_index("ix_sessions_dataset_id", "sessions")
