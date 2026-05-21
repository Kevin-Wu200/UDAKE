"""add workflow_branches table for conflict branching support

Revision ID: 20260521_0010
Revises: ad11761e2338
Create Date: 2026-05-21 08:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260521_0010"
down_revision: Union[str, None] = "ad11761e2338"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_branches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "workflow_id",
            sa.BigInteger(),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_branch_id",
            sa.BigInteger(),
            sa.ForeignKey("workflow_branches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('open', 'merged', 'rejected')",
            name="ck_workflow_branches_status_enum",
        ),
        sa.Index("ix_workflow_branches_workflow_id", "workflow_id"),
        sa.Index("ix_workflow_branches_parent_branch_id", "parent_branch_id"),
        sa.Index("ix_workflow_branches_created_by", "created_by"),
        sa.Index("ix_workflow_branches_status", "status"),
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_branches_status", table_name="workflow_branches")
    op.drop_index("ix_workflow_branches_created_by", table_name="workflow_branches")
    op.drop_index("ix_workflow_branches_parent_branch_id", table_name="workflow_branches")
    op.drop_index("ix_workflow_branches_workflow_id", table_name="workflow_branches")
    op.drop_table("workflow_branches")
