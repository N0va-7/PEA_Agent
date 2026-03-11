"""add persistent standalone url analyses

Revision ID: 0009_url_analysis_console
Revises: 0008_agent_tool_refactor
Create Date: 2026-03-11 10:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_url_analysis_console"
down_revision = "0008_agent_tool_refactor"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "url_analyses"):
        return

    op.create_table(
        "url_analyses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("requested_url", sa.Text(), nullable=True),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("url_reputation", sa.JSON(), nullable=True),
        sa.Column("url_analysis", sa.JSON(), nullable=True),
        sa.Column("decision", sa.JSON(), nullable=True),
        sa.Column("execution_trace", sa.JSON(), nullable=True),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_hash"),
    )
    op.create_index("idx_url_analyses_updated_at", "url_analyses", ["updated_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "url_analyses"):
        return
    op.drop_index("idx_url_analyses_updated_at", table_name="url_analyses")
    op.drop_table("url_analyses")
