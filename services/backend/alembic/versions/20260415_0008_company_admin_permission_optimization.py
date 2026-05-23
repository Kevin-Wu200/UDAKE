"""optimize company admin permission system

Revision ID: 20260415_0008
Revises: 20260414_0007
Create Date: 2026-04-15 10:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260415_0008"
down_revision: Union[str, None] = "20260414_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("company_admin_type", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("company_admin_key_id", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("total_keys_created", sa.Integer(), nullable=False, server_default=sa.text("0")))

    op.create_foreign_key(
        "fk_users_company_admin_key_id_product_keys",
        "users",
        "product_keys",
        ["company_admin_key_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_users_company_admin_type_enum",
        "users",
        "company_admin_type IS NULL OR company_admin_type IN ('trial', 'standard')",
    )
    op.create_index("ix_users_company_admin_type", "users", ["company_admin_type"], unique=False)
    op.create_index("ix_product_keys_activated_at", "product_keys", ["activated_at"], unique=False)
    op.create_index("ix_product_keys_expires_at", "product_keys", ["expires_at"], unique=False)

    op.execute(
        """
        UPDATE users
        SET company_admin_type = 'standard'
        WHERE role = 'company_admin' AND company_admin_type IS NULL
        """
    )
    op.execute(
        """
        UPDATE users
        SET total_keys_created = 0
        WHERE total_keys_created IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_product_keys_expires_at", table_name="product_keys")
    op.drop_index("ix_product_keys_activated_at", table_name="product_keys")
    op.drop_index("ix_users_company_admin_type", table_name="users")
    op.drop_constraint("ck_users_company_admin_type_enum", "users", type_="check")
    op.drop_constraint("fk_users_company_admin_key_id_product_keys", "users", type_="foreignkey")
    op.drop_column("users", "total_keys_created")
    op.drop_column("users", "company_admin_key_id")
    op.drop_column("users", "company_admin_type")
