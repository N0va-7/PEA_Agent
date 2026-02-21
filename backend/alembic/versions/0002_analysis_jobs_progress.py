"""add analysis job progress fields

Revision ID: 0002_analysis_jobs_progress
Revises: 0001_init
Create Date: 2026-02-21 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


revision = "0002_analysis_jobs_progress"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "analysis_jobs" not in existing_tables:
        return

    if not _has_column(inspector, "analysis_jobs", "current_stage"):
        op.add_column("analysis_jobs", sa.Column("current_stage", sa.String(length=64), nullable=True))
    if not _has_column(inspector, "analysis_jobs", "progress_events"):
        op.add_column("analysis_jobs", sa.Column("progress_events", sqlite.JSON(), nullable=True))
    if not _has_index(inspector, "analysis_jobs", "idx_analysis_jobs_status"):
        op.create_index("idx_analysis_jobs_status", "analysis_jobs", ["status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "analysis_jobs" not in existing_tables:
        return

    if _has_index(inspector, "analysis_jobs", "idx_analysis_jobs_status"):
        op.drop_index("idx_analysis_jobs_status", table_name="analysis_jobs")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "analysis_jobs", "progress_events"):
        op.drop_column("analysis_jobs", "progress_events")

    inspector = sa.inspect(bind)
    if _has_column(inspector, "analysis_jobs", "current_stage"):
        op.drop_column("analysis_jobs", "current_stage")
