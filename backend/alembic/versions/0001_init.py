"""init

Revision ID: 0001_init
Revises: 
Create Date: 2026-02-20 00:00:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None



def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "email_analyses" in existing_tables and "analysis_jobs" in existing_tables:
        return

    op.create_table(
        "email_analyses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.String(length=512), nullable=True),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("sender", sa.String(length=512), nullable=True),
        sa.Column("recipient", sa.String(length=512), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("url_analysis", sqlite.JSON(), nullable=True),
        sa.Column("body_analysis", sqlite.JSON(), nullable=True),
        sa.Column("attachment_analysis", sqlite.JSON(), nullable=True),
        sa.Column("final_decision", sqlite.JSON(), nullable=True),
        sa.Column("llm_report", sa.Text(), nullable=True),
        sa.Column("report_path", sa.Text(), nullable=False),
        sa.Column("execution_trace", sqlite.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
    )
    op.create_index("idx_email_analyses_created_at", "email_analyses", ["created_at"], unique=False)
    op.create_index("idx_email_analyses_message_id", "email_analyses", ["message_id"], unique=False)

    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=True),
        sa.Column("analysis_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("progress_events", sqlite.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_analysis_jobs_status", "analysis_jobs", ["status"], unique=False)



def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "analysis_jobs" in existing_tables:
        op.drop_index("idx_analysis_jobs_status", table_name="analysis_jobs")
        op.drop_table("analysis_jobs")
    if "email_analyses" in existing_tables:
        op.drop_index("idx_email_analyses_message_id", table_name="email_analyses")
        op.drop_index("idx_email_analyses_created_at", table_name="email_analyses")
        op.drop_table("email_analyses")
