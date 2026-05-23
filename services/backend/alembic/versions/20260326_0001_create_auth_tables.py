"""create auth database tables

Revision ID: 20260326_0001
Revises:
Create Date: 2026-03-26 18:40:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260326_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default=sa.text("'user'")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "is_email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("role IN ('user', 'admin', 'enterprise')", name="ck_users_role_enum"),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'disabled', 'locked')",
            name="ck_users_status_enum",
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_status", "users", ["status"], unique=False)

    op.create_table(
        "product_keys",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("product_key", sa.String(length=128), nullable=False),
        sa.Column("key_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'unused'")),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "key_type IN ('personal', 'enterprise')",
            name="ck_product_keys_type_enum",
        ),
        sa.CheckConstraint(
            "status IN ('unused', 'active', 'revoked', 'expired')",
            name="ck_product_keys_status_enum",
        ),
        sa.UniqueConstraint("product_key", name="uq_product_keys_key"),
    )
    op.create_index("ix_product_keys_user_id", "product_keys", ["user_id"], unique=False)
    op.create_index("ix_product_keys_status", "product_keys", ["status"], unique=False)

    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "purpose IN ('register', 'email_change', 'password_reset')",
            name="ck_email_verification_codes_purpose_enum",
        ),
    )
    op.create_index(
        "ix_email_verification_codes_user_id",
        "email_verification_codes",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_email_verification_codes_email",
        "email_verification_codes",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_email_verification_codes_code",
        "email_verification_codes",
        ["code"],
        unique=False,
    )
    op.create_index(
        "ix_email_verification_codes_expires_at",
        "email_verification_codes",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "password_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("history_order", sa.Integer(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "history_order BETWEEN 1 AND 5",
            name="ck_password_history_recent_five",
        ),
        sa.UniqueConstraint("user_id", "history_order", name="uq_password_history_user_order"),
    )
    op.create_index("ix_password_history_user_id", "password_history", ["user_id"], unique=False)
    op.create_index(
        "ix_password_history_changed_at",
        "password_history",
        ["changed_at"],
        unique=False,
    )

    op.create_table(
        "user_devices",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("device_name", sa.String(length=128), nullable=True),
        sa.Column(
            "platform",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'unknown'"),
        ),
        sa.Column("push_token", sa.String(length=255), nullable=True),
        sa.Column("refresh_token_hash", sa.String(length=255), nullable=True),
        sa.Column("is_trusted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "platform IN ('ios', 'android', 'web', 'desktop', 'unknown')",
            name="ck_user_devices_platform_enum",
        ),
        sa.UniqueConstraint("device_id", name="uq_user_devices_device_id"),
    )
    op.create_index("ix_user_devices_user_id", "user_devices", ["user_id"], unique=False)
    op.create_index(
        "ix_user_devices_last_seen_at",
        "user_devices",
        ["last_seen_at"],
        unique=False,
    )

    op.create_table(
        "email_change_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("old_email", sa.String(length=255), nullable=False),
        sa.Column("new_email", sa.String(length=255), nullable=False),
        sa.Column("verify_code", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('pending', 'verified', 'cancelled', 'expired')",
            name="ck_email_change_requests_status_enum",
        ),
    )
    op.create_index(
        "ix_email_change_requests_user_id",
        "email_change_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_email_change_requests_new_email",
        "email_change_requests",
        ["new_email"],
        unique=False,
    )
    op.create_index(
        "ix_email_change_requests_status",
        "email_change_requests",
        ["status"],
        unique=False,
    )

    op.create_table(
        "rate_limits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("identity", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=128), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_request_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "scope IN ('ip', 'user', 'api_key', 'device')",
            name="ck_rate_limits_scope_enum",
        ),
        sa.CheckConstraint("window_seconds > 0", name="ck_rate_limits_window_positive"),
        sa.CheckConstraint(
            "request_count >= 0",
            name="ck_rate_limits_request_count_non_negative",
        ),
        sa.UniqueConstraint(
            "scope",
            "identity",
            "endpoint",
            "window_seconds",
            name="uq_rate_limits_scope_identity_endpoint_window",
        ),
    )
    op.create_index("ix_rate_limits_identity", "rate_limits", ["identity"], unique=False)
    op.create_index("ix_rate_limits_scope", "rate_limits", ["scope"], unique=False)
    op.create_index("ix_rate_limits_endpoint", "rate_limits", ["endpoint"], unique=False)

    op.execute(
        """
        CREATE TABLE audit_logs (
            id BIGINT GENERATED BY DEFAULT AS IDENTITY,
            user_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL,
            actor_username VARCHAR(64),
            operation_type VARCHAR(32) NOT NULL,
            target_table VARCHAR(64),
            target_id VARCHAR(64),
            ip_address VARCHAR(45),
            user_agent VARCHAR(255),
            request_id VARCHAR(64),
            details JSONB,
            operated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_audit_logs_operation_type_enum CHECK (
                operation_type IN (
                    'create', 'read', 'update', 'delete',
                    'login', 'logout', 'password_change',
                    'email_change', 'api_call', 'other'
                )
            )
        ) PARTITION BY RANGE (operated_at);
        """
    )
    op.execute("CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id)")
    op.execute("CREATE INDEX ix_audit_logs_operation_type ON audit_logs (operation_type)")
    op.execute("CREATE INDEX ix_audit_logs_operated_at ON audit_logs (operated_at)")
    op.execute("CREATE INDEX ix_audit_logs_target ON audit_logs (target_table, target_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs_202603
        PARTITION OF audit_logs
        FOR VALUES FROM ('2026-03-01 00:00:00+00') TO ('2026-04-01 00:00:00+00');
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs_202604
        PARTITION OF audit_logs
        FOR VALUES FROM ('2026-04-01 00:00:00+00') TO ('2026-05-01 00:00:00+00');
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION ensure_audit_log_partitions(months_ahead INTEGER DEFAULT 2)
        RETURNS VOID
        LANGUAGE plpgsql
        AS $$
        DECLARE
            base_month DATE := date_trunc('month', NOW() AT TIME ZONE 'UTC')::date;
            idx INTEGER;
            part_start DATE;
            part_end DATE;
            part_name TEXT;
        BEGIN
            FOR idx IN 0..months_ahead LOOP
                part_start := (base_month + make_interval(months => idx))::date;
                part_end := (part_start + INTERVAL '1 month')::date;
                part_name := format('audit_logs_%s', to_char(part_start, 'YYYYMM'));
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)',
                    part_name,
                    part_start::timestamptz,
                    part_end::timestamptz
                );
            END LOOP;
        END;
        $$;
        """
    )
    op.execute("SELECT ensure_audit_log_partitions(3)")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS ensure_audit_log_partitions(INTEGER)")
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")

    op.drop_index("ix_rate_limits_endpoint", table_name="rate_limits")
    op.drop_index("ix_rate_limits_scope", table_name="rate_limits")
    op.drop_index("ix_rate_limits_identity", table_name="rate_limits")
    op.drop_table("rate_limits")

    op.drop_index("ix_email_change_requests_status", table_name="email_change_requests")
    op.drop_index("ix_email_change_requests_new_email", table_name="email_change_requests")
    op.drop_index("ix_email_change_requests_user_id", table_name="email_change_requests")
    op.drop_table("email_change_requests")

    op.drop_index("ix_user_devices_last_seen_at", table_name="user_devices")
    op.drop_index("ix_user_devices_user_id", table_name="user_devices")
    op.drop_table("user_devices")

    op.drop_index("ix_password_history_changed_at", table_name="password_history")
    op.drop_index("ix_password_history_user_id", table_name="password_history")
    op.drop_table("password_history")

    op.drop_index("ix_email_verification_codes_expires_at", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_code", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_email", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_user_id", table_name="email_verification_codes")
    op.drop_table("email_verification_codes")

    op.drop_index("ix_product_keys_status", table_name="product_keys")
    op.drop_index("ix_product_keys_user_id", table_name="product_keys")
    op.drop_table("product_keys")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
