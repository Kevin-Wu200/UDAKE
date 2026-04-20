"""SQLAlchemy models for authentication-related tables."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
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
    Text,
    UniqueConstraint,
    event,
    func,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, validates


class Base(DeclarativeBase):
    """Declarative base for auth database models."""


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    users = relationship("User", back_populates="company")
    product_keys = relationship("ProductKey", back_populates="company")

    __table_args__ = (
        UniqueConstraint("name", name="uq_companies_name"),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_companies_status_enum"),
        Index("ix_companies_name", "name"),
        Index("ix_companies_status", "status"),
    )


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
    lock_until: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    lock_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    product_key_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    company_admin_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    company_admin_key_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("product_keys.id", ondelete="SET NULL"), nullable=True
    )
    total_keys_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_login_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    company = relationship("Company", back_populates="users")
    product_keys = relationship(
        "ProductKey",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="ProductKey.user_id",
    )
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
    processed_tickets = relationship("Ticket", back_populates="processor", foreign_keys="Ticket.processed_by")

    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "role IN ('user', 'admin', 'enterprise', 'company_admin', 'super_admin')",
            name="ck_users_role_enum",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'disabled', 'locked', 'deleted')",
            name="ck_users_status_enum",
        ),
        CheckConstraint(
            "company_admin_type IS NULL OR company_admin_type IN ('trial', 'standard')",
            name="ck_users_company_admin_type_enum",
        ),
        Index("ix_users_username", "username"),
        Index("ix_users_email", "email"),
        Index("ix_users_status", "status"),
        Index("ix_users_company_id", "company_id"),
        Index("ix_users_company_admin_type", "company_admin_type"),
    )


class ProductKeyType(str, Enum):
    PERSONAL_TRIAL = "personal_trial"
    PERSONAL_STANDARD = "personal_standard"
    ENTERPRISE_TRIAL = "enterprise_trial"
    ENTERPRISE_STANDARD = "enterprise_standard"


class ProductKeyStatus(str, Enum):
    UNUSED = "unused"
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"


class TicketType(str, Enum):
    KEY_REQUEST = "key_request"
    KEY_EXTENSION = "key_extension"


class TicketStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class ProductKey(Base):
    __tablename__ = "product_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_key: Mapped[str] = mapped_column(String(128), nullable=False)
    product_key_ciphertext: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    key_type: Mapped[str] = mapped_column(String(20), nullable=False)
    key_sub_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'standard'"))
    generation_seed: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    key_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unused'"))
    company_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    total_quota: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    signature: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    issued_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    company = relationship("Company", back_populates="product_keys")
    user = relationship("User", back_populates="product_keys", foreign_keys=[user_id])

    @classmethod
    def get_default_quota(cls, key_type: str) -> int:
        quota_map = {
            ProductKeyType.PERSONAL_TRIAL.value: 10,
            ProductKeyType.PERSONAL_STANDARD.value: 100,
            ProductKeyType.ENTERPRISE_TRIAL.value: 500,
            ProductKeyType.ENTERPRISE_STANDARD.value: 1000,
        }
        return quota_map.get(key_type, 1)

    __table_args__ = (
        CheckConstraint(
            "key_type IN ('personal_trial', 'personal_standard', 'enterprise_trial', 'enterprise_standard')",
            name="ck_product_keys_type_enum",
        ),
        CheckConstraint(
            "key_sub_type IN ('trial', 'standard')",
            name="ck_product_keys_sub_type_enum",
        ),
        CheckConstraint(
            "status IN ('unused', 'active', 'disabled', 'expired')",
            name="ck_product_keys_status_enum",
        ),
        CheckConstraint("total_quota >= 0", name="ck_product_keys_total_quota_non_negative"),
        CheckConstraint("used_count >= 0", name="ck_product_keys_used_count_non_negative"),
        Index("ix_product_keys_user_id", "user_id"),
        Index("ix_product_keys_status", "status"),
        Index("ix_product_keys_product_key", "product_key"),
        Index("ix_product_keys_company_id", "company_id"),
        Index("ix_product_keys_ciphertext", "product_key_ciphertext"),
        Index("idx_product_keys_key_status", "product_key", "status"),
        Index("idx_product_keys_type_status", "key_type", "status"),
        Index("idx_product_keys_company_status", "company_id", "status"),
        Index("idx_product_keys_user_status", "user_id", "status"),
        Index("ix_product_keys_activated_at", "activated_at"),
        Index("ix_product_keys_expires_at", "expires_at"),
        Index("uq_product_keys_key", "product_key", unique=True),
    )


class Ticket(Base):
    __tablename__ = "tickets"

    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    PHONE_PATTERN = re.compile(r"^(1[3-9]\d{9}|\+[1-9]\d{6,19})$")
    ALLOWED_TRANSITIONS = {
        TicketStatus.PENDING.value: {TicketStatus.APPROVED.value, TicketStatus.REJECTED.value},
        TicketStatus.APPROVED.value: {TicketStatus.COMPLETED.value},
        TicketStatus.REJECTED.value: set(),
        TicketStatus.COMPLETED.value: set(),
    }

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    organization: Mapped[str] = mapped_column(String(128), nullable=False)
    usage_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    key_type: Mapped[str] = mapped_column(String(50), nullable=False)
    existing_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    processed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    processed_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    response_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    processor = relationship("User", back_populates="processed_tickets", foreign_keys=[processed_by])

    __table_args__ = (
        CheckConstraint(
            "ticket_type IN ('key_request', 'key_extension')",
            name="ck_tickets_ticket_type_enum",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'completed')",
            name="ck_tickets_status_enum",
        ),
        CheckConstraint(
            "key_type IN ('personal_trial', 'personal_standard', 'enterprise_trial', 'enterprise_standard')",
            name="ck_tickets_key_type_enum",
        ),
        CheckConstraint(
            "("
            "(ticket_type = 'key_extension' AND existing_key IS NOT NULL AND length(trim(existing_key)) > 0)"
            " OR "
            "(ticket_type = 'key_request' AND existing_key IS NULL)"
            ")",
            name="ck_tickets_existing_key_required",
        ),
        CheckConstraint(
            "("
            "(status = 'pending' AND processed_by IS NULL AND processed_at IS NULL)"
            " OR "
            "(status IN ('approved', 'rejected', 'completed') AND processed_by IS NOT NULL AND processed_at IS NOT NULL)"
            ")",
            name="ck_tickets_processed_fields_consistency",
        ),
        CheckConstraint(
            "status <> 'completed' OR assigned_key IS NOT NULL",
            name="ck_tickets_completed_requires_assigned_key",
        ),
        Index("ix_tickets_email", "email"),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_created_at", "created_at"),
        Index("ix_tickets_ticket_type", "ticket_type"),
        Index("ix_tickets_processed_by", "processed_by"),
    )

    @validates("email")
    def _validate_email(self, _key: str, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("email 不能为空")
        if not self.EMAIL_PATTERN.match(normalized):
            raise ValueError("email 格式不合法")
        return normalized

    @validates("phone")
    def _validate_phone(self, _key: str, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("phone 不能为空")
        if not self.PHONE_PATTERN.match(normalized):
            raise ValueError("phone 格式不合法")
        return normalized

    @validates("industry", "organization", "usage_purpose", "key_type")
    def _validate_required_text(self, key: str, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError(f"{key} 不能为空")
        return normalized

    @validates("ticket_type")
    def _validate_ticket_type(self, _key: str, value: str) -> str:
        normalized = (value or "").strip()
        if normalized not in {member.value for member in TicketType}:
            raise ValueError("ticket_type 不合法")
        if normalized == TicketType.KEY_REQUEST.value:
            self.existing_key = None
        return normalized

    @validates("existing_key")
    def _validate_existing_key(self, _key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @validates("status")
    def _validate_status_enum(self, _key: str, value: str) -> str:
        normalized = (value or "").strip()
        if normalized not in {member.value for member in TicketStatus}:
            raise ValueError("status 不合法")
        return normalized

    def validate_business_rules(self) -> None:
        if self.ticket_type == TicketType.KEY_EXTENSION.value and not self.existing_key:
            raise ValueError("key_extension 工单必须提供 existing_key")
        if self.ticket_type == TicketType.KEY_REQUEST.value and self.existing_key:
            raise ValueError("key_request 工单不允许提供 existing_key")


@event.listens_for(Ticket, "before_insert")
def _ticket_before_insert(_mapper: Any, _connection: Any, target: Ticket) -> None:
    target.validate_business_rules()


@event.listens_for(Ticket, "before_update")
def _ticket_before_update(_mapper: Any, _connection: Any, target: Ticket) -> None:
    target.validate_business_rules()
    state = inspect(target)
    status_history = state.attrs.status.history
    previous_status = status_history.deleted[0] if status_history.deleted else None
    current_status = target.status

    if previous_status is None and current_status == TicketStatus.COMPLETED.value:
        raise ValueError("已完成工单不允许修改")

    if previous_status:
        if previous_status == TicketStatus.COMPLETED.value:
            raise ValueError("已完成工单不允许修改")

        if previous_status != current_status:
            allowed = Ticket.ALLOWED_TRANSITIONS.get(previous_status, set())
            if current_status not in allowed:
                raise ValueError(f"不允许的工单状态流转: {previous_status} -> {current_status}")

    processed_by_history = state.attrs.processed_by.history
    processed_at_history = state.attrs.processed_at.history
    if processed_by_history.deleted and processed_by_history.deleted[0] is not None:
        if processed_by_history.added and processed_by_history.added[0] != processed_by_history.deleted[0]:
            raise ValueError("processed_by 一旦写入后不可修改")
    if processed_at_history.deleted and processed_at_history.deleted[0] is not None:
        if processed_at_history.added and processed_at_history.added[0] != processed_at_history.deleted[0]:
            raise ValueError("processed_at 一旦写入后不可修改")


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
    ip_address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ip_address_masked: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    operated_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        CheckConstraint(
            "operation_type IN ('create', 'read', 'update', 'delete', "
            "'register', 'login', 'logout', 'reset_password', 'change_password', 'change_email', "
            "'verify_email', 'register_device', 'kick_device', 'password_change', 'email_change', "
            "'delete_user', 'api_call', 'other', 'device_risk_event', 'reset_password_send_code', "
            "'change_email_send_code')",
            name="ck_audit_logs_operation_type_enum",
        ),
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_operation_type", "operation_type"),
        Index("ix_audit_logs_operated_at", "operated_at"),
        Index("ix_audit_logs_target", "target_table", "target_id"),
        Index("ix_audit_logs_operation_time", "operation_type", "operated_at"),
        Index("ix_audit_logs_user_time", "user_id", "operated_at"),
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


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    definition: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        Index("ix_workflows_owner_id", "owner_id"),
        Index("ix_workflows_is_public", "is_public"),
        Index("ix_workflows_created_at", "created_at"),
    )


class WorkflowVersion(Base):
    __tablename__ = "workflow_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_workflow_version"),
        Index("ix_workflow_versions_workflow_id", "workflow_id"),
        Index("ix_workflow_versions_version_number", "version_number"),
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (Index("ix_teams_owner_id", "owner_id"),)


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'member'"))
    joined_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
        CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name="ck_team_members_role_enum"),
        Index("ix_team_members_team_id", "team_id"),
        Index("ix_team_members_user_id", "user_id"),
    )


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True
    )
    workflow_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=True
    )
    invited_by_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    invitee_email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("token", name="uq_invitations_token"),
        CheckConstraint("(team_id IS NOT NULL) OR (workflow_id IS NOT NULL)", name="ck_invitations_target_not_null"),
        CheckConstraint("status IN ('pending', 'accepted', 'declined', 'expired')", name="ck_invitations_status_enum"),
        Index("ix_invitations_team_id", "team_id"),
        Index("ix_invitations_workflow_id", "workflow_id"),
        Index("ix_invitations_token", "token"),
        Index("ix_invitations_status", "status"),
    )


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    delegator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    delegate_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permissions: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    granted_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("delegator_id <> delegate_id", name="ck_delegations_no_self_delegate"),
        Index("ix_delegations_workflow_id", "workflow_id"),
        Index("ix_delegations_delegator_id", "delegator_id"),
        Index("ix_delegations_delegate_id", "delegate_id"),
    )


class ShareLink(Base):
    __tablename__ = "share_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    created_by_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(128), nullable=False)
    access_mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'read'"))
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("token", name="uq_share_links_token"),
        CheckConstraint("access_mode IN ('read', 'comment', 'edit')", name="ck_share_links_access_mode_enum"),
        CheckConstraint("access_count >= 0", name="ck_share_links_access_count_non_negative"),
        Index("ix_share_links_workflow_id", "workflow_id"),
        Index("ix_share_links_token", "token"),
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("comments.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(String(4000), nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("length(content) > 0", name="ck_comments_content_not_empty"),
        Index("ix_comments_workflow_id", "workflow_id"),
        Index("ix_comments_parent_id", "parent_id"),
        Index("ix_comments_user_id", "user_id"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type: Mapped[str] = mapped_column("type", String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(String(4000), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reference_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_is_read", "is_read"),
        Index("ix_notifications_type", "type"),
    )


class CollaborationOperation(Base):
    __tablename__ = "collaboration_operations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_collaboration_operations_workflow_id", "workflow_id"),
        Index("ix_collaboration_operations_user_id", "user_id"),
        Index("ix_collaboration_operations_created_at", "created_at"),
    )


class CollaborationCursor(Base):
    __tablename__ = "collaboration_cursors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cursor_position: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False)
    last_updated: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("workflow_id", "user_id", name="uq_collaboration_cursors_workflow_user"),
        Index("ix_collaboration_cursors_workflow_id", "workflow_id"),
        Index("ix_collaboration_cursors_user_id", "user_id"),
    )


class CollaborationConflict(Base):
    __tablename__ = "collaboration_conflicts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(64), nullable=False)
    conflict_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_collaboration_conflicts_workflow_id", "workflow_id"),
        Index("ix_collaboration_conflicts_user_id", "user_id"),
        Index("ix_collaboration_conflicts_resolved", "resolved"),
    )
