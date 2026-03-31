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
    last_login_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    company = relationship("Company", back_populates="users")
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
            "role IN ('user', 'admin', 'enterprise', 'company_admin', 'super_admin')",
            name="ck_users_role_enum",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'disabled', 'locked', 'deleted')",
            name="ck_users_status_enum",
        ),
        Index("ix_users_username", "username"),
        Index("ix_users_email", "email"),
        Index("ix_users_status", "status"),
        Index("ix_users_company_id", "company_id"),
    )


class ProductKey(Base):
    __tablename__ = "product_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_key: Mapped[str] = mapped_column(String(128), nullable=False)
    product_key_ciphertext: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    key_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'unused'"))
    company_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    total_quota: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    signature: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
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

    company = relationship("Company", back_populates="product_keys")
    user = relationship("User", back_populates="product_keys")

    __table_args__ = (
        UniqueConstraint("product_key", name="uq_product_keys_key"),
        CheckConstraint(
            "key_type IN ('personal', 'enterprise')",
            name="ck_product_keys_type_enum",
        ),
        CheckConstraint(
            "status IN ('unused', 'active', 'revoked', 'expired', 'available')",
            name="ck_product_keys_status_enum",
        ),
        CheckConstraint("total_quota >= 0", name="ck_product_keys_total_quota_non_negative"),
        CheckConstraint("used_count >= 0", name="ck_product_keys_used_count_non_negative"),
        Index("ix_product_keys_user_id", "user_id"),
        Index("ix_product_keys_status", "status"),
        Index("ix_product_keys_company_id", "company_id"),
        Index("ix_product_keys_ciphertext", "product_key_ciphertext"),
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
