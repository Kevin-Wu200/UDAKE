"""refactor product key model for multi-type key system

Revision ID: 20260414_0007
Revises: 20260401_0006
Create Date: 2026-04-14 18:45:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260414_0007"
down_revision: Union[str, None] = "20260401_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_keys",
        sa.Column("key_sub_type", sa.String(length=30), nullable=False, server_default=sa.text("'standard'")),
    )
    op.add_column("product_keys", sa.Column("generation_seed", sa.String(length=512), nullable=True))
    op.add_column("product_keys", sa.Column("key_metadata", sa.Text(), nullable=True))
    op.add_column("product_keys", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("product_keys", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        UPDATE product_keys
        SET key_type = CASE
            WHEN key_type = 'personal' THEN 'personal_standard'
            WHEN key_type = 'enterprise' THEN 'enterprise_standard'
            ELSE key_type
        END
        """
    )
    op.execute(
        """
        UPDATE product_keys
        SET status = CASE
            WHEN status = 'available' THEN 'unused'
            WHEN status = 'revoked' THEN 'disabled'
            ELSE status
        END
        """
    )

    op.drop_constraint("ck_product_keys_type_enum", "product_keys", type_="check")
    op.drop_constraint("ck_product_keys_status_enum", "product_keys", type_="check")
    op.drop_constraint("uq_product_keys_key", "product_keys", type_="unique")

    op.create_check_constraint(
        "ck_product_keys_type_enum",
        "product_keys",
        "key_type IN ('personal_trial', 'personal_standard', 'enterprise_trial', 'enterprise_standard')",
    )
    op.create_check_constraint(
        "ck_product_keys_sub_type_enum",
        "product_keys",
        "key_sub_type IN ('trial', 'standard')",
    )
    op.create_check_constraint(
        "ck_product_keys_status_enum",
        "product_keys",
        "status IN ('unused', 'active', 'disabled', 'expired')",
    )

    op.create_index("idx_product_keys_type_status", "product_keys", ["key_type", "status"], unique=False)
    op.create_index("idx_product_keys_company_status", "product_keys", ["company_id", "status"], unique=False)
    op.create_index("idx_product_keys_user_status", "product_keys", ["user_id", "status"], unique=False)
    op.create_index("uq_product_keys_key", "product_keys", ["product_key"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_product_keys_type_status", table_name="product_keys")
    op.drop_index("idx_product_keys_company_status", table_name="product_keys")
    op.drop_index("idx_product_keys_user_status", table_name="product_keys")
    op.drop_index("uq_product_keys_key", table_name="product_keys")

    op.drop_constraint("ck_product_keys_sub_type_enum", "product_keys", type_="check")
    op.drop_constraint("ck_product_keys_type_enum", "product_keys", type_="check")
    op.drop_constraint("ck_product_keys_status_enum", "product_keys", type_="check")

    op.create_check_constraint(
        "ck_product_keys_type_enum",
        "product_keys",
        "key_type IN ('personal', 'enterprise')",
    )
    op.create_check_constraint(
        "ck_product_keys_status_enum",
        "product_keys",
        "status IN ('unused', 'active', 'revoked', 'expired', 'available')",
    )
    op.create_unique_constraint("uq_product_keys_key", "product_keys", ["product_key"])

    op.execute(
        """
        UPDATE product_keys
        SET key_type = CASE
            WHEN key_type LIKE 'personal_%' THEN 'personal'
            WHEN key_type LIKE 'enterprise_%' THEN 'enterprise'
            ELSE key_type
        END
        """
    )
    op.execute(
        """
        UPDATE product_keys
        SET status = CASE
            WHEN status = 'disabled' THEN 'revoked'
            ELSE status
        END
        """
    )

    op.drop_column("product_keys", "last_used_at")
    op.drop_column("product_keys", "assigned_at")
    op.drop_column("product_keys", "key_metadata")
    op.drop_column("product_keys", "generation_seed")
    op.drop_column("product_keys", "key_sub_type")
