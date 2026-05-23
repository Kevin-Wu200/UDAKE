"""security hardening for auth tables

Revision ID: 20260327_0004
Revises: 20260327_0003
Create Date: 2026-03-27 16:50:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260327_0004"
down_revision: Union[str, None] = "20260327_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product_keys", sa.Column("product_key_ciphertext", sa.String(length=512), nullable=True))
    op.create_index("ix_product_keys_ciphertext", "product_keys", ["product_key_ciphertext"], unique=False)

    op.add_column("users", sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("lock_reason", sa.String(length=255), nullable=True))

    op.alter_column("audit_logs", "ip_address", type_=sa.String(length=512), existing_type=sa.String(length=45))
    op.add_column("audit_logs", sa.Column("ip_address_masked", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("success", sa.Boolean(), nullable=True))
    op.add_column("audit_logs", sa.Column("failure_reason", sa.String(length=255), nullable=True))

    op.drop_constraint("ck_audit_logs_operation_type_enum", "audit_logs", type_="check")
    op.create_check_constraint(
        "ck_audit_logs_operation_type_enum",
        "audit_logs",
        "operation_type IN ('create', 'read', 'update', 'delete', "
        "'register', 'login', 'logout', 'reset_password', 'change_password', 'change_email', "
        "'verify_email', 'register_device', 'kick_device', 'password_change', 'email_change', "
        "'delete_user', 'api_call', 'other', 'device_risk_event', "
        "'reset_password_send_code', 'change_email_send_code')",
    )

    op.create_index("ix_audit_logs_operation_time", "audit_logs", ["operation_type", "operated_at"], unique=False)
    op.create_index("ix_audit_logs_user_time", "audit_logs", ["user_id", "operated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_keys_ciphertext", table_name="product_keys")
    op.drop_column("product_keys", "product_key_ciphertext")

    op.drop_index("ix_audit_logs_user_time", table_name="audit_logs")
    op.drop_index("ix_audit_logs_operation_time", table_name="audit_logs")

    op.drop_constraint("ck_audit_logs_operation_type_enum", "audit_logs", type_="check")
    op.create_check_constraint(
        "ck_audit_logs_operation_type_enum",
        "audit_logs",
        "operation_type IN ('create', 'read', 'update', 'delete', "
        "'login', 'logout', 'password_change', 'email_change', 'api_call', 'delete_user', 'other')",
    )

    op.drop_column("audit_logs", "failure_reason")
    op.drop_column("audit_logs", "success")
    op.drop_column("audit_logs", "ip_address_masked")
    op.alter_column("audit_logs", "ip_address", type_=sa.String(length=45), existing_type=sa.String(length=512))

    op.drop_column("users", "lock_reason")
    op.drop_column("users", "lock_until")
