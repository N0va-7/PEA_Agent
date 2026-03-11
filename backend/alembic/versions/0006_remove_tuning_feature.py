"""remove tuning feature tables and config

Revision ID: 0006_remove_tuning_feature
Revises: 0005_llm_content_review
Create Date: 2026-03-09 00:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_remove_tuning_feature"
down_revision = "0005_llm_content_review"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "system_config"):
        op.execute(sa.text("DELETE FROM system_config WHERE `key` = 'active_fusion_tuning_run_id'"))

    inspector = sa.inspect(bind)
    if _has_table(inspector, "fusion_tuning_runs"):
        if _has_index(inspector, "fusion_tuning_runs", "idx_fusion_tuning_runs_is_active"):
            op.drop_index("idx_fusion_tuning_runs_is_active", table_name="fusion_tuning_runs")
        inspector = sa.inspect(bind)
        if _has_index(inspector, "fusion_tuning_runs", "idx_fusion_tuning_runs_triggered_at"):
            op.drop_index("idx_fusion_tuning_runs_triggered_at", table_name="fusion_tuning_runs")
        inspector = sa.inspect(bind)
        if _has_index(inspector, "fusion_tuning_runs", "idx_fusion_tuning_runs_status"):
            op.drop_index("idx_fusion_tuning_runs_status", table_name="fusion_tuning_runs")
        op.drop_table("fusion_tuning_runs")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "fusion_tuning_runs"):
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
            sa.Column("precheck", sa.JSON(), nullable=True),
            sa.Column("dataset_csv_path", sa.Text(), nullable=True),
            sa.Column("result_json_path", sa.Text(), nullable=True),
            sa.Column("best_params", sa.JSON(), nullable=True),
            sa.Column("top_k", sa.JSON(), nullable=True),
            sa.Column("selection_reason", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_fusion_tuning_runs_status", "fusion_tuning_runs", ["status"], unique=False)
        op.create_index("idx_fusion_tuning_runs_triggered_at", "fusion_tuning_runs", ["triggered_at"], unique=False)
        op.create_index("idx_fusion_tuning_runs_is_active", "fusion_tuning_runs", ["is_active"], unique=False)
