"""Day 5 tables: zscore_archive, indicator_snapshots, entity_linkage

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zscore_archive",
        sa.Column("id",         sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("ic_no",      sa.String(),   nullable=False),
        sa.Column("period",     sa.String(),   nullable=False),
        sa.Column("district",   sa.String(),   nullable=False),
        sa.Column("state",      sa.String(),   nullable=True),
        sa.Column("waz",        sa.Float(),    nullable=True),
        sa.Column("haz",        sa.Float(),    nullable=True),
        sa.Column("baz",        sa.Float(),    nullable=True),
        sa.Column("age_months", sa.Integer(),  nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_zscore_ic_no",           "zscore_archive", ["ic_no"])
    op.create_index("ix_zscore_district_period",  "zscore_archive", ["district", "period"])

    op.create_table(
        "indicator_snapshots",
        sa.Column("id",               sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("period",           sa.String(),   nullable=False),
        sa.Column("district",         sa.String(),   nullable=False),
        sa.Column("state",            sa.String(),   nullable=True),
        sa.Column("stunting_rate",    sa.Float(),    nullable=True),
        sa.Column("wasting_rate",     sa.Float(),    nullable=True),
        sa.Column("underweight_rate", sa.Float(),    nullable=True),
        sa.Column("overweight_rate",  sa.Float(),    nullable=True),
        sa.Column("n_records",        sa.Integer(),  nullable=True),
        sa.Column("created_at",       sa.DateTime(), nullable=False),
    )
    op.create_index("ix_indicator_district_period", "indicator_snapshots", ["district", "period"])

    op.create_table(
        "entity_linkage",
        sa.Column("id",               sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("ic_no",            sa.String(),   nullable=False),
        sa.Column("source_type",      sa.String(),   nullable=False),
        sa.Column("dataset_id",       sa.String(),   sa.ForeignKey("datasets.id"), nullable=True),
        sa.Column("name",             sa.String(),   nullable=True),
        sa.Column("dob",              sa.String(),   nullable=True),
        sa.Column("match_confidence", sa.Float(),    nullable=True),
        sa.Column("created_at",       sa.DateTime(), nullable=False),
    )
    op.create_index("ix_entity_linkage_ic_no", "entity_linkage", ["ic_no"])


def downgrade() -> None:
    op.drop_index("ix_entity_linkage_ic_no",      "entity_linkage")
    op.drop_table("entity_linkage")
    op.drop_index("ix_indicator_district_period",  "indicator_snapshots")
    op.drop_table("indicator_snapshots")
    op.drop_index("ix_zscore_district_period",     "zscore_archive")
    op.drop_index("ix_zscore_ic_no",               "zscore_archive")
    op.drop_table("zscore_archive")
