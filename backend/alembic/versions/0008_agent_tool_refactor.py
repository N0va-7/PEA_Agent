"""refactor analyses for agent tools and VT URL cache

Revision ID: 0008_agent_tool_refactor
Revises: 0007_policy_event_log
Create Date: 2026-03-10 22:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_agent_tool_refactor"
down_revision = "0007_policy_event_log"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "email_analyses"):
        existing = _columns(inspector, "email_analyses")
        with op.batch_alter_table("email_analyses") as batch:
            if "parsed_email" not in existing:
                batch.add_column(sa.Column("parsed_email", sa.JSON(), nullable=True))
            if "url_extraction" not in existing:
                batch.add_column(sa.Column("url_extraction", sa.JSON(), nullable=True))
            if "url_reputation" not in existing:
                batch.add_column(sa.Column("url_reputation", sa.JSON(), nullable=True))
            if "content_review" not in existing:
                batch.add_column(sa.Column("content_review", sa.JSON(), nullable=True))
            if "decision" not in existing:
                batch.add_column(sa.Column("decision", sa.JSON(), nullable=True))
            if "report_markdown" not in existing:
                batch.add_column(sa.Column("report_markdown", sa.Text(), nullable=True))
            for legacy in ["body_analysis", "llm_content_review", "payload_analysis", "final_decision", "llm_report"]:
                if legacy in existing:
                    batch.drop_column(legacy)

    inspector = sa.inspect(bind)
    if not _has_table(inspector, "vt_url_cache"):
        op.create_table(
            "vt_url_cache",
            sa.Column("url_hash", sa.String(length=64), nullable=False),
            sa.Column("normalized_url", sa.Text(), nullable=False),
            sa.Column("vt_url_id", sa.String(length=512), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=True),
            sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("http_status", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("url_hash"),
        )
        op.create_index("idx_vt_url_cache_expires_at", "vt_url_cache", ["expires_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "vt_url_cache"):
        op.drop_index("idx_vt_url_cache_expires_at", table_name="vt_url_cache")
        op.drop_table("vt_url_cache")

    inspector = sa.inspect(bind)
    if _has_table(inspector, "email_analyses"):
        existing = _columns(inspector, "email_analyses")
        with op.batch_alter_table("email_analyses") as batch:
            for column in ["parsed_email", "url_extraction", "url_reputation", "content_review", "decision", "report_markdown"]:
                if column in existing:
                    batch.drop_column(column)
            if "body_analysis" not in existing:
                batch.add_column(sa.Column("body_analysis", sa.JSON(), nullable=True))
            if "llm_content_review" not in existing:
                batch.add_column(sa.Column("llm_content_review", sa.JSON(), nullable=True))
            if "payload_analysis" not in existing:
                batch.add_column(sa.Column("payload_analysis", sa.JSON(), nullable=True))
            if "final_decision" not in existing:
                batch.add_column(sa.Column("final_decision", sa.JSON(), nullable=True))
            if "llm_report" not in existing:
                batch.add_column(sa.Column("llm_report", sa.Text(), nullable=True))
