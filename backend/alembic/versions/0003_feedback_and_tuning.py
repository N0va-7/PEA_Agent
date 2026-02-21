"""add feedback and tuning tables

Revision ID: 0003_feedback_and_tuning
Revises: 0002_analysis_jobs_progress
Create Date: 2026-02-21 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


revision = "0003_feedback_and_tuning"
down_revision = "0002_analysis_jobs_progress"
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

    if "email_analyses" in existing_tables:
        if not _has_column(inspector, "email_analyses", "review_label"):
            op.add_column("email_analyses", sa.Column("review_label", sa.String(length=32), nullable=True))
        if not _has_column(inspector, "email_analyses", "review_note"):
            op.add_column("email_analyses", sa.Column("review_note", sa.Text(), nullable=True))
        if not _has_column(inspector, "email_analyses", "reviewed_by"):
            op.add_column("email_analyses", sa.Column("reviewed_by", sa.String(length=128), nullable=True))
        if not _has_column(inspector, "email_analyses", "reviewed_at"):
            op.add_column("email_analyses", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

        inspector = sa.inspect(bind)
        if not _has_index(inspector, "email_analyses", "idx_email_analyses_review_label"):
            op.create_index("idx_email_analyses_review_label", "email_analyses", ["review_label"], unique=False)
        if not _has_index(inspector, "email_analyses", "idx_email_analyses_reviewed_at"):
            op.create_index("idx_email_analyses_reviewed_at", "email_analyses", ["reviewed_at"], unique=False)

    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "analysis_feedback_events" not in existing_tables:
        op.create_table(
            "analysis_feedback_events",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("analysis_id", sa.String(length=64), nullable=False),
            sa.Column("old_review_label", sa.String(length=32), nullable=True),
            sa.Column("new_review_label", sa.String(length=32), nullable=True),
            sa.Column("old_review_note", sa.Text(), nullable=True),
            sa.Column("new_review_note", sa.Text(), nullable=True),
            sa.Column("changed_by", sa.String(length=128), nullable=False),
            sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_feedback_events_analysis_id", "analysis_feedback_events", ["analysis_id"], unique=False)
        op.create_index("idx_feedback_events_changed_at", "analysis_feedback_events", ["changed_at"], unique=False)

    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "fusion_tuning_runs" not in existing_tables:
        op.create_table(
            "fusion_tuning_runs",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("triggered_by", sa.String(length=128), nullable=False),
            sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("reviewed_from", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_to", sa.DateTime(timezone=True), nullable=True),
            sa.Column("fpr_target", sa.Float(), nullable=False, server_default="0.03"),
            sa.Column("w_step", sa.Float(), nullable=False, server_default="0.05"),
            sa.Column("th_min", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("th_max", sa.Float(), nullable=False, server_default="0.95"),
            sa.Column("th_step", sa.Float(), nullable=False, server_default="0.01"),
            sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("positive_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("negative_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("recent_feedback_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("precheck", sqlite.JSON(), nullable=True),
            sa.Column("dataset_csv_path", sa.Text(), nullable=True),
            sa.Column("result_json_path", sa.Text(), nullable=True),
            sa.Column("best_params", sqlite.JSON(), nullable=True),
            sa.Column("top_k", sqlite.JSON(), nullable=True),
            sa.Column("selection_reason", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_fusion_tuning_runs_status", "fusion_tuning_runs", ["status"], unique=False)
        op.create_index("idx_fusion_tuning_runs_triggered_at", "fusion_tuning_runs", ["triggered_at"], unique=False)
        op.create_index("idx_fusion_tuning_runs_is_active", "fusion_tuning_runs", ["is_active"], unique=False)

    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "system_config" not in existing_tables:
        op.create_table(
            "system_config",
            sa.Column("key", sa.String(length=128), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("key"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "system_config" in existing_tables:
        op.drop_table("system_config")

    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "fusion_tuning_runs" in existing_tables:
        op.drop_index("idx_fusion_tuning_runs_is_active", table_name="fusion_tuning_runs")
        op.drop_index("idx_fusion_tuning_runs_triggered_at", table_name="fusion_tuning_runs")
        op.drop_index("idx_fusion_tuning_runs_status", table_name="fusion_tuning_runs")
        op.drop_table("fusion_tuning_runs")

    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "analysis_feedback_events" in existing_tables:
        op.drop_index("idx_feedback_events_changed_at", table_name="analysis_feedback_events")
        op.drop_index("idx_feedback_events_analysis_id", table_name="analysis_feedback_events")
        op.drop_table("analysis_feedback_events")

    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "email_analyses" in existing_tables:
        if _has_index(inspector, "email_analyses", "idx_email_analyses_reviewed_at"):
            op.drop_index("idx_email_analyses_reviewed_at", table_name="email_analyses")
        if _has_index(inspector, "email_analyses", "idx_email_analyses_review_label"):
            op.drop_index("idx_email_analyses_review_label", table_name="email_analyses")

        inspector = sa.inspect(bind)
        if _has_column(inspector, "email_analyses", "reviewed_at"):
            op.drop_column("email_analyses", "reviewed_at")
        inspector = sa.inspect(bind)
        if _has_column(inspector, "email_analyses", "reviewed_by"):
            op.drop_column("email_analyses", "reviewed_by")
        inspector = sa.inspect(bind)
        if _has_column(inspector, "email_analyses", "review_note"):
            op.drop_column("email_analyses", "review_note")
        inspector = sa.inspect(bind)
        if _has_column(inspector, "email_analyses", "review_label"):
            op.drop_column("email_analyses", "review_label")
