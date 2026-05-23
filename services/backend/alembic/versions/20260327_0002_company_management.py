"""add company management entities and columns

Revision ID: 20260327_0002
Revises: 20260326_0001
Create Date: 2026-03-27 11:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260327_0002"
down_revision: Union[str, None] = "20260326_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("name", name="uq_companies_name"),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_companies_status_enum"),
    )
    op.create_index("ix_companies_name", "companies", ["name"], unique=False)
    op.create_index("ix_companies_status", "companies", ["status"], unique=False)

    op.add_column("users", sa.Column("company_id", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("product_key_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("fk_users_company_id_companies", "users", "companies", ["company_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_users_company_id", "users", ["company_id"], unique=False)

    op.drop_constraint("ck_users_role_enum", "users", type_="check")
    op.drop_constraint("ck_users_status_enum", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role_enum",
        "users",
        "role IN ('user', 'admin', 'enterprise', 'company_admin', 'super_admin')",
    )
    op.create_check_constraint(
        "ck_users_status_enum",
        "users",
        "status IN ('pending', 'active', 'disabled', 'locked', 'deleted')",
    )

    op.add_column("product_keys", sa.Column("company_id", sa.BigInteger(), nullable=True))
    op.add_column("product_keys", sa.Column("total_quota", sa.Integer(), nullable=False, server_default=sa.text("1")))
    op.add_column("product_keys", sa.Column("used_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.create_foreign_key(
        "fk_product_keys_company_id_companies",
        "product_keys",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_product_keys_company_id", "product_keys", ["company_id"], unique=False)

    op.drop_constraint("ck_product_keys_status_enum", "product_keys", type_="check")
    op.create_check_constraint(
        "ck_product_keys_status_enum",
        "product_keys",
        "status IN ('unused', 'active', 'revoked', 'expired', 'available')",
    )
    op.create_check_constraint(
        "ck_product_keys_total_quota_non_negative",
        "product_keys",
        "total_quota >= 0",
    )
    op.create_check_constraint(
        "ck_product_keys_used_count_non_negative",
        "product_keys",
        "used_count >= 0",
    )

    op.drop_constraint("ck_audit_logs_operation_type_enum", "audit_logs", type_="check")
    op.create_check_constraint(
        "ck_audit_logs_operation_type_enum",
        "audit_logs",
        "operation_type IN ('create', 'read', 'update', 'delete', 'login', 'logout', "
        "'password_change', 'email_change', 'api_call', 'delete_user', 'other')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_audit_logs_operation_type_enum", "audit_logs", type_="check")
    op.create_check_constraint(
        "ck_audit_logs_operation_type_enum",
        "audit_logs",
        "operation_type IN ('create', 'read', 'update', 'delete', 'login', 'logout', "
        "'password_change', 'email_change', 'api_call', 'other')",
    )

    op.drop_constraint("ck_product_keys_used_count_non_negative", "product_keys", type_="check")
    op.drop_constraint("ck_product_keys_total_quota_non_negative", "product_keys", type_="check")
    op.drop_constraint("ck_product_keys_status_enum", "product_keys", type_="check")
    op.create_check_constraint(
        "ck_product_keys_status_enum",
        "product_keys",
        "status IN ('unused', 'active', 'revoked', 'expired')",
    )
    op.drop_index("ix_product_keys_company_id", table_name="product_keys")
    op.drop_constraint("fk_product_keys_company_id_companies", "product_keys", type_="foreignkey")
    op.drop_column("product_keys", "used_count")
    op.drop_column("product_keys", "total_quota")
    op.drop_column("product_keys", "company_id")

    op.drop_constraint("ck_users_status_enum", "users", type_="check")
    op.drop_constraint("ck_users_role_enum", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role_enum",
        "users",
        "role IN ('user', 'admin', 'enterprise')",
    )
    op.create_check_constraint(
        "ck_users_status_enum",
        "users",
        "status IN ('pending', 'active', 'disabled', 'locked')",
    )
    op.drop_index("ix_users_company_id", table_name="users")
    op.drop_constraint("fk_users_company_id_companies", "users", type_="foreignkey")
    op.drop_column("users", "product_key_id")
    op.drop_column("users", "company_id")

    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_table("companies")
