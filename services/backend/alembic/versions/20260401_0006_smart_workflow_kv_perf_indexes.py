"""add smart workflow kv perf indexes

Revision ID: 20260401_0006
Revises: 20260331_0005
Create Date: 2026-04-01 09:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260401_0006"
down_revision: Union[str, None] = "20260331_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("smart_workflow_kv"):
        return

    op.add_column("smart_workflow_kv", sa.Column("workflow_id", sa.String(length=128), nullable=True))
    op.add_column("smart_workflow_kv", sa.Column("user_id", sa.String(length=128), nullable=True))
    op.add_column("smart_workflow_kv", sa.Column("is_unread", sa.Boolean(), nullable=True))
    op.add_column("smart_workflow_kv", sa.Column("payload_created_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "ix_smart_workflow_kv_type_workflow_created",
        "smart_workflow_kv",
        ["entity_type", "workflow_id", "payload_created_at"],
        unique=False,
    )
    op.create_index(
        "ix_smart_workflow_kv_type_workflow_user_unread_created",
        "smart_workflow_kv",
        ["entity_type", "workflow_id", "user_id", "is_unread", "payload_created_at"],
        unique=False,
    )
    op.create_index(
        "ix_smart_workflow_kv_type_updated",
        "smart_workflow_kv",
        ["entity_type", "updated_at"],
        unique=False,
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_smart_workflow_kv_notification_unread_partial "
            "ON smart_workflow_kv (workflow_id, user_id, payload_created_at DESC) "
            "WHERE entity_type='notification' AND is_unread=true"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("smart_workflow_kv"):
        return
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_smart_workflow_kv_notification_unread_partial")

    op.drop_index("ix_smart_workflow_kv_type_updated", table_name="smart_workflow_kv")
    op.drop_index("ix_smart_workflow_kv_type_workflow_user_unread_created", table_name="smart_workflow_kv")
    op.drop_index("ix_smart_workflow_kv_type_workflow_created", table_name="smart_workflow_kv")

    op.drop_column("smart_workflow_kv", "payload_created_at")
    op.drop_column("smart_workflow_kv", "is_unread")
    op.drop_column("smart_workflow_kv", "user_id")
    op.drop_column("smart_workflow_kv", "workflow_id")
