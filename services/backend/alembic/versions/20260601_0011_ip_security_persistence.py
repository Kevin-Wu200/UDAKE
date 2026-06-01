"""add ip_rules and ip_reputations tables for IP security persistence

Revision ID: 20260601_0011
Revises: 20260521_0010
Create Date: 2026-06-01 12:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260601_0011"
down_revision: Union[str, None] = "20260521_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ip_rules 表：IP 黑白名单规则持久化
    op.create_table(
        "ip_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ip_or_cidr", sa.String(length=45), nullable=False),
        sa.Column(
            "rule_type",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
            "rule_type IN ('whitelist', 'blacklist')",
            name="ck_ip_rules_rule_type_enum",
        ),
        sa.Index("ix_ip_rules_ip_or_cidr", "ip_or_cidr"),
        sa.Index("ix_ip_rules_rule_type", "rule_type"),
        sa.Index("ix_ip_rules_is_active", "is_active"),
        sa.Index("ix_ip_rules_expires_at", "expires_at"),
        sa.Index("ix_ip_rules_active_expires", "is_active", "expires_at"),
    )

    # ip_reputations 表：IP 信誉度持久化
    op.create_table(
        "ip_reputations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column(
            "score",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column(
            "success_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "failed_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "rate_limited_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
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
        sa.UniqueConstraint("ip_address", name="uq_ip_reputations_ip_address"),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_ip_reputations_score_range",
        ),
        sa.CheckConstraint(
            "success_count >= 0",
            name="ck_ip_reputations_success_count_non_negative",
        ),
        sa.CheckConstraint(
            "failed_count >= 0",
            name="ck_ip_reputations_failed_count_non_negative",
        ),
        sa.CheckConstraint(
            "rate_limited_count >= 0",
            name="ck_ip_reputations_rate_limited_count_non_negative",
        ),
        sa.Index("ix_ip_reputations_ip_address", "ip_address", unique=True),
        sa.Index("ix_ip_reputations_score", "score"),
        sa.Index("ix_ip_reputations_updated_at", "updated_at"),
    )


def downgrade() -> None:
    op.drop_index("ix_ip_reputations_updated_at", table_name="ip_reputations")
    op.drop_index("ix_ip_reputations_score", table_name="ip_reputations")
    op.drop_index("ix_ip_reputations_ip_address", table_name="ip_reputations")
    op.drop_table("ip_reputations")

    op.drop_index("ix_ip_rules_active_expires", table_name="ip_rules")
    op.drop_index("ix_ip_rules_expires_at", table_name="ip_rules")
    op.drop_index("ix_ip_rules_is_active", table_name="ip_rules")
    op.drop_index("ix_ip_rules_rule_type", table_name="ip_rules")
    op.drop_index("ix_ip_rules_ip_or_cidr", table_name="ip_rules")
    op.drop_table("ip_rules")
