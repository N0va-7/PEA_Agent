"""add llm content review column

Revision ID: 0005_llm_content_review
Revises: 0004_payload_analysis
Create Date: 2026-03-09 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_llm_content_review"
down_revision = "0004_payload_analysis"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "email_analyses" in existing_tables and not _has_column(inspector, "email_analyses", "llm_content_review"):
        op.add_column("email_analyses", sa.Column("llm_content_review", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "email_analyses" in existing_tables and _has_column(inspector, "email_analyses", "llm_content_review"):
        op.drop_column("email_analyses", "llm_content_review")
