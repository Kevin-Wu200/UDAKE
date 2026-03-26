"""Tests for authentication database schema and basic operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_db.database import build_engine_options, ping_database
from app.auth_db.models import (
    AuditLog,
    Base,
    EmailChangeRequest,
    EmailVerificationCode,
    PasswordHistory,
    ProductKey,
    RateLimit,
    User,
    UserDevice,
)
from app.config import settings


@pytest.fixture()
def sqlite_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_build_engine_options_match_required_pool_settings(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DB_POOL_SIZE", 10, raising=False)
    monkeypatch.setattr(settings, "AUTH_DB_MAX_OVERFLOW", 20, raising=False)
    monkeypatch.setattr(settings, "AUTH_DB_POOL_TIMEOUT", 30, raising=False)
    monkeypatch.setattr(settings, "AUTH_DB_POOL_RECYCLE", 1800, raising=False)
    monkeypatch.setattr(settings, "AUTH_DB_PRE_PING", True, raising=False)

    options = build_engine_options()

    assert options["pool_size"] == 10
    assert options["max_overflow"] == 20
    assert options["pool_timeout"] == 30
    assert options["pool_recycle"] == 1800
    assert options["pool_pre_ping"] is True


def test_crud_and_transaction_flow(sqlite_engine):
    now = datetime.now(timezone.utc)
    with Session(sqlite_engine) as session:
        user = User(
            id=1,
            username="alice",
            email="alice@example.com",
            password_hash="hashed_password_v1",
            role="user",
            status="active",
            is_email_verified=True,
        )
        session.add(user)
        session.flush()

        session.add_all(
            [
                ProductKey(
                    id=1,
                    user_id=user.id,
                    product_key="PK-ALICE-001",
                    key_type="personal",
                    status="active",
                    expires_at=now + timedelta(days=30),
                ),
                EmailVerificationCode(
                    id=1,
                    user_id=user.id,
                    email=user.email,
                    code="123456",
                    purpose="register",
                    expires_at=now + timedelta(minutes=10),
                ),
                PasswordHistory(
                    id=1,
                    user_id=user.id,
                    password_hash="hashed_password_v1",
                    history_order=1,
                ),
                UserDevice(
                    id=1,
                    user_id=user.id,
                    device_id="device-001",
                    platform="android",
                    refresh_token_hash="refresh-token-hash",
                ),
                EmailChangeRequest(
                    id=1,
                    user_id=user.id,
                    old_email="alice@example.com",
                    new_email="alice.new@example.com",
                    verify_code="654321",
                    status="pending",
                    expires_at=now + timedelta(minutes=20),
                ),
                RateLimit(
                    id=1,
                    scope="user",
                    identity=str(user.id),
                    endpoint="/api/auth/login",
                    window_seconds=60,
                    request_count=1,
                ),
                AuditLog(
                    id=1,
                    user_id=user.id,
                    operation_type="login",
                    target_table="users",
                    target_id=str(user.id),
                    details={"result": "success"},
                    operated_at=now,
                ),
            ]
        )
        session.commit()

    with Session(sqlite_engine) as session:
        stored_user = session.query(User).filter_by(username="alice").one()
        assert stored_user.email == "alice@example.com"

        stored_user.status = "disabled"
        session.commit()
        assert session.query(User).filter_by(status="disabled").count() == 1

    with Session(sqlite_engine) as session:
        session.add(
            User(
                id=2,
                username="alice",
                email="duplicate@example.com",
                password_hash="hashed_password_v2",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.query(User).filter_by(id=2).count() == 0

    with Session(sqlite_engine) as session:
        session.add(
            PasswordHistory(
                id=2,
                user_id=1,
                password_hash="hashed_password_v6",
                history_order=6,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_ping_database(sqlite_engine):
    assert ping_database(sqlite_engine) is True
