"""add quality_score to datasets

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("datasets", sa.Column("quality_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("datasets", "quality_score")
