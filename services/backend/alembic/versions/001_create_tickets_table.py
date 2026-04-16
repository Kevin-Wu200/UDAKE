"""create tickets table for key request workflow

Revision ID: 20260416_0009
Revises: 20260415_0008
Create Date: 2026-04-16 11:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260416_0009"
down_revision: Union[str, None] = "20260415_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tickets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=False),
        sa.Column("usage_purpose", sa.Text(), nullable=False),
        sa.Column("key_type", sa.String(length=50), nullable=False),
        sa.Column("existing_key", sa.String(length=100), nullable=True),
        sa.Column("processed_by", sa.BigInteger(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_notes", sa.Text(), nullable=True),
        sa.Column("assigned_key", sa.String(length=100), nullable=True),
        sa.Column("response_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["processed_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "ticket_type IN ('key_request', 'key_extension')",
            name="ck_tickets_ticket_type_enum",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'completed')",
            name="ck_tickets_status_enum",
        ),
        sa.CheckConstraint(
            "key_type IN ('personal_trial', 'personal_standard', 'enterprise_trial', 'enterprise_standard')",
            name="ck_tickets_key_type_enum",
        ),
        sa.CheckConstraint(
            "((ticket_type = 'key_extension' AND existing_key IS NOT NULL AND length(trim(existing_key)) > 0) "
            "OR (ticket_type = 'key_request' AND existing_key IS NULL))",
            name="ck_tickets_existing_key_required",
        ),
        sa.CheckConstraint(
            "((status = 'pending' AND processed_by IS NULL AND processed_at IS NULL) "
            "OR (status IN ('approved', 'rejected', 'completed') AND processed_by IS NOT NULL AND processed_at IS NOT NULL))",
            name="ck_tickets_processed_fields_consistency",
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR assigned_key IS NOT NULL",
            name="ck_tickets_completed_requires_assigned_key",
        ),
    )

    op.create_index("ix_tickets_email", "tickets", ["email"], unique=False)
    op.create_index("ix_tickets_status", "tickets", ["status"], unique=False)
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"], unique=False)
    op.create_index("ix_tickets_ticket_type", "tickets", ["ticket_type"], unique=False)
    op.create_index("ix_tickets_processed_by", "tickets", ["processed_by"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tickets_processed_by", table_name="tickets")
    op.drop_index("ix_tickets_ticket_type", table_name="tickets")
    op.drop_index("ix_tickets_created_at", table_name="tickets")
    op.drop_index("ix_tickets_status", table_name="tickets")
    op.drop_index("ix_tickets_email", table_name="tickets")
    op.drop_table("tickets")
