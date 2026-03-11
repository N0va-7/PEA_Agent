"""add policy event log table

Revision ID: 0007_policy_event_log
Revises: 0006_remove_tuning_feature
Create Date: 2026-03-10 10:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_policy_event_log"
down_revision = "0006_remove_tuning_feature"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "policy_events"):
        op.create_table(
            "policy_events",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("event_type", sa.String(length=32), nullable=False),
            sa.Column("policy_key", sa.String(length=128), nullable=False),
            sa.Column("policy_value", sa.String(length=512), nullable=False),
            sa.Column("action", sa.String(length=32), nullable=False),
            sa.Column("actor", sa.String(length=128), nullable=True),
            sa.Column("analysis_id", sa.String(length=64), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("idx_policy_events_type", "policy_events", ["event_type"], unique=False)
        op.create_index(
            "idx_policy_events_key_value",
            "policy_events",
            ["policy_key", "policy_value"],
            unique=False,
        )
        op.create_index("idx_policy_events_created_at", "policy_events", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "policy_events"):
        if _has_index(inspector, "policy_events", "idx_policy_events_created_at"):
            op.drop_index("idx_policy_events_created_at", table_name="policy_events")
        inspector = sa.inspect(bind)
        if _has_index(inspector, "policy_events", "idx_policy_events_key_value"):
            op.drop_index("idx_policy_events_key_value", table_name="policy_events")
        inspector = sa.inspect(bind)
        if _has_index(inspector, "policy_events", "idx_policy_events_type"):
            op.drop_index("idx_policy_events_type", table_name="policy_events")
        op.drop_table("policy_events")
