"""add enterprise field for workflows and task assignment persistence support

Revision ID: 20260507_0009
Revises: 20260415_0008
Create Date: 2026-05-07 11:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260507_0009"
down_revision: Union[str, None] = "20260415_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("workflows") as batch_op:
        batch_op.add_column(sa.Column("enterprise_id", sa.String(length=120), nullable=True))
    op.create_index("ix_workflows_enterprise_id", "workflows", ["enterprise_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_workflows_enterprise_id", table_name="workflows")
    with op.batch_alter_table("workflows") as batch_op:
        batch_op.drop_column("enterprise_id")
