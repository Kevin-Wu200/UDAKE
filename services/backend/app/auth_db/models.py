"""SQLAlchemy models for authentication-related tables."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for auth database models."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'user'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    is_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_login_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    product_keys = relationship("ProductKey", back_populates="user", cascade="all, delete-orphan")
    email_verification_codes = relationship(
        "EmailVerificationCode", back_populates="user", cascade="all, delete-orphan"
    )
    password_histories = relationship(
        "PasswordHistory", back_populates="user", cascade="all, delete-orphan"
    )
    devices = relationship("UserDevice", back_populates="user", cascade="all, delete-orphan")
    email_change_requests = relationship(
        "EmailChangeRequest", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "role IN ('user', 'admin', 'enterprise')",
            name="ck_users_role_enum",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'disabled', 'locked')",
            name="ck_users_status_enum",
        ),
        Index("ix_users_username", "username"),
        Index("ix_users_email", "email"),
        Index("ix_users_status", "status"),
    )


class ProductKey(Base):
    __tablename__ = "product_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_key: Mapped[str] = mapped_column(String(128), nullable=False)
    key_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unused'"))
    issued_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    activated_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="product_keys")

    __table_args__ = (
        UniqueConstraint("product_key", name="uq_product_keys_key"),
        CheckConstraint(
            "key_type IN ('personal', 'enterprise')",
            name="ck_product_keys_type_enum",
        ),
        CheckConstraint(
            "status IN ('unused', 'active', 'revoked', 'expired')",
            name="ck_product_keys_status_enum",
        ),
        Index("ix_product_keys_user_id", "user_id"),
        Index("ix_product_keys_status", "status"),
    )


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = relationship("User", back_populates="email_verification_codes")

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('register', 'email_change', 'password_reset')",
            name="ck_email_verification_codes_purpose_enum",
        ),
        Index("ix_email_verification_codes_user_id", "user_id"),
        Index("ix_email_verification_codes_email", "email"),
        Index("ix_email_verification_codes_code", "code"),
        Index("ix_email_verification_codes_expires_at", "expires_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_table: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    operated_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('create', 'read', 'update', 'delete', "
            "'login', 'logout', 'password_change', 'email_change', 'api_call', 'other')",
            name="ck_audit_logs_operation_type_enum",
        ),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_operation_type", "operation_type"),
        Index("ix_audit_logs_operated_at", "operated_at"),
        Index("ix_audit_logs_target", "target_table", "target_id"),
    )


class PasswordHistory(Base):
    __tablename__ = "password_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    history_order: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="password_histories")

    __table_args__ = (
        UniqueConstraint("user_id", "history_order", name="uq_password_history_user_order"),
        CheckConstraint("history_order BETWEEN 1 AND 5", name="ck_password_history_recent_five"),
        Index("ix_password_history_user_id", "user_id"),
        Index("ix_password_history_changed_at", "changed_at"),
    )


class UserDevice(Base):
    __tablename__ = "user_devices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    device_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unknown'"))
    push_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    last_seen_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="devices")

    __table_args__ = (
        UniqueConstraint("device_id", name="uq_user_devices_device_id"),
        CheckConstraint(
            "platform IN ('ios', 'android', 'web', 'desktop', 'unknown')",
            name="ck_user_devices_platform_enum",
        ),
        Index("ix_user_devices_user_id", "user_id"),
        Index("ix_user_devices_last_seen_at", "last_seen_at"),
    )


class EmailChangeRequest(Base):
    __tablename__ = "email_change_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    old_email: Mapped[str] = mapped_column(String(255), nullable=False)
    new_email: Mapped[str] = mapped_column(String(255), nullable=False)
    verify_code: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    requested_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="email_change_requests")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'verified', 'cancelled', 'expired')",
            name="ck_email_change_requests_status_enum",
        ),
        Index("ix_email_change_requests_user_id", "user_id"),
        Index("ix_email_change_requests_new_email", "new_email"),
        Index("ix_email_change_requests_status", "status"),
    )


class RateLimit(Base):
    __tablename__ = "rate_limits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    identity: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    blocked_until: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    last_request_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "scope",
            "identity",
            "endpoint",
            "window_seconds",
            name="uq_rate_limits_scope_identity_endpoint_window",
        ),
        CheckConstraint("scope IN ('ip', 'user', 'api_key', 'device')", name="ck_rate_limits_scope_enum"),
        CheckConstraint("window_seconds > 0", name="ck_rate_limits_window_positive"),
        CheckConstraint("request_count >= 0", name="ck_rate_limits_request_count_non_negative"),
        Index("ix_rate_limits_identity", "identity"),
        Index("ix_rate_limits_scope", "scope"),
        Index("ix_rate_limits_endpoint", "endpoint"),
    )
