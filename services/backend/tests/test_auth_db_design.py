"""Tests for authentication database schema and basic operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_db.database import build_engine_options, create_auth_engine, ping_database
from app.auth_db.models import (
    AuditLog,
    Base,
    CollaborationConflict,
    CollaborationCursor,
    CollaborationOperation,
    Comment,
    Company,
    Delegation,
    EmailChangeRequest,
    EmailVerificationCode,
    Invitation,
    Notification,
    PasswordHistory,
    ProductKey,
    RateLimit,
    ShareLink,
    Team,
    TeamMember,
    Ticket,
    TicketStatus,
    TicketType,
    User,
    UserDevice,
    Workflow,
    WorkflowVersion,
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


def test_create_auth_engine_with_ssl_query(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_DB_REQUIRE_SSL", True, raising=False)
    monkeypatch.setattr(settings, "AUTH_DB_SSLMODE", "require", raising=False)
    engine = create_auth_engine("postgresql://user:pass@localhost:5432/demo_auth")
    try:
        assert "sslmode=require" in str(engine.url)
    finally:
        engine.dispose()


def test_crud_and_transaction_flow(sqlite_engine):
    now = datetime.now(timezone.utc)
    with Session(sqlite_engine) as session:
        company = Company(id=100, name="测试企业", status="active")
        session.add(company)
        session.flush()

        user = User(
            id=1,
            username="alice",
            email="alice@example.com",
            password_hash="hashed_password_v1",
            role="user",
            status="active",
            is_email_verified=True,
            company_id=company.id,
        )
        session.add(user)
        session.flush()

        session.add_all(
            [
                ProductKey(
                    id=1,
                    user_id=user.id,
                    product_key="PK-ALICE-001",
                    key_type="personal_standard",
                    key_sub_type="standard",
                    status="active",
                    company_id=company.id,
                    total_quota=ProductKey.get_default_quota("personal_standard"),
                    used_count=1,
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
        assert stored_user.company_id == 100

        stored_user.status = "disabled"
        session.commit()
        assert session.query(User).filter_by(status="disabled").count() == 1
        assert ProductKey.get_default_quota("personal_trial") == 10
        assert ProductKey.get_default_quota("personal_standard") == 100
        assert ProductKey.get_default_quota("enterprise_trial") == 500
        assert ProductKey.get_default_quota("enterprise_standard") == 1000

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


def test_company_model_and_audit_operation_type(sqlite_engine):
    now = datetime.now(timezone.utc)
    with Session(sqlite_engine) as session:
        company = Company(id=1, name="Enterprise A", status="active")
        session.add(company)
        session.add(
            User(
                id=1,
                username="admin_a",
                email="admin_a@example.com",
                password_hash="hash",
                role="company_admin",
                status="active",
                company_id=company.id,
            )
        )
        session.flush()
        session.add(
            AuditLog(
                id=2,
                user_id=1,
                operation_type="delete_user",
                target_table="users",
                target_id="2",
                operated_at=now,
            )
        )
        session.commit()

    with Session(sqlite_engine) as session:
        assert session.query(Company).count() == 1
        assert session.query(AuditLog).filter_by(operation_type="delete_user").count() == 1


def test_ping_database(sqlite_engine):
    assert ping_database(sqlite_engine) is True


def test_collaboration_and_sharing_tables(sqlite_engine):
    now = datetime.now(timezone.utc)
    with Session(sqlite_engine) as session:
        owner = User(
            id=10,
            username="owner",
            email="owner@example.com",
            password_hash="hash_owner",
            role="user",
            status="active",
        )
        editor = User(
            id=11,
            username="editor",
            email="editor@example.com",
            password_hash="hash_editor",
            role="user",
            status="active",
        )
        session.add_all([owner, editor])
        session.flush()

        workflow = Workflow(
            id=1,
            name="主流程",
            description="协作流程",
            definition={"nodes": [], "edges": []},
            owner_id=owner.id,
            is_public=False,
        )
        team = Team(
            id=1,
            name="研发团队",
            description="核心成员",
            owner_id=owner.id,
        )
        session.add_all([workflow, team])
        session.flush()

        session.add_all(
            [
                WorkflowVersion(
                    id=1,
                    workflow_id=workflow.id,
                    version_number=1,
                    definition={"nodes": [{"id": "n1"}], "edges": []},
                    created_by_id=owner.id,
                ),
                TeamMember(
                    id=1,
                    team_id=team.id,
                    user_id=editor.id,
                    role="member",
                ),
                Invitation(
                    id=1,
                    team_id=team.id,
                    workflow_id=workflow.id,
                    invited_by_id=owner.id,
                    invitee_email="newuser@example.com",
                    token="invite-token-001",
                    status="pending",
                    expires_at=now + timedelta(days=2),
                ),
                Delegation(
                    id=1,
                    workflow_id=workflow.id,
                    delegator_id=owner.id,
                    delegate_id=editor.id,
                    permissions={"can_edit": True, "can_share": True},
                    expires_at=now + timedelta(days=1),
                ),
                ShareLink(
                    id=1,
                    workflow_id=workflow.id,
                    created_by_id=owner.id,
                    token="share-token-001",
                    access_mode="edit",
                    password="secret",
                    expires_at=now + timedelta(hours=6),
                    access_count=0,
                ),
                Comment(
                    id=1,
                    workflow_id=workflow.id,
                    parent_id=None,
                    user_id=editor.id,
                    content="第一条评论",
                ),
                Notification(
                    id=1,
                    user_id=editor.id,
                    notification_type="workflow_shared",
                    title="收到新分享",
                    content="你被授予编辑权限",
                    is_read=False,
                    reference_id=workflow.id,
                ),
                CollaborationOperation(
                    id=1,
                    workflow_id=workflow.id,
                    user_id=editor.id,
                    operation_type="node_move",
                    operation_data={"node_id": "n1", "x": 120, "y": 80},
                ),
                CollaborationCursor(
                    id=1,
                    workflow_id=workflow.id,
                    user_id=editor.id,
                    cursor_position={"node_id": "n1"},
                    color="#00AA88",
                ),
                CollaborationConflict(
                    id=1,
                    workflow_id=workflow.id,
                    user_id=editor.id,
                    conflict_type="edit_collision",
                    conflict_data={"field": "name"},
                    resolved=False,
                ),
            ]
        )
        session.commit()

    with Session(sqlite_engine) as session:
        assert session.query(Workflow).count() == 1
        assert session.query(WorkflowVersion).count() == 1
        assert session.query(Team).count() == 1
        assert session.query(TeamMember).count() == 1
        assert session.query(Invitation).filter_by(status="pending").count() == 1
        assert session.query(Delegation).count() == 1
        assert session.query(ShareLink).filter_by(access_mode="edit").count() == 1
        assert session.query(Comment).count() == 1
        assert session.query(Notification).filter_by(notification_type="workflow_shared").count() == 1
        assert session.query(CollaborationOperation).count() == 1
        assert session.query(CollaborationCursor).count() == 1
        assert session.query(CollaborationConflict).filter_by(resolved=False).count() == 1


def test_collaboration_constraints(sqlite_engine):
    now = datetime.now(timezone.utc)
    with Session(sqlite_engine) as session:
        user = User(
            id=20,
            username="user20",
            email="user20@example.com",
            password_hash="hash20",
            role="user",
            status="active",
        )
        workflow = Workflow(
            id=20,
            name="约束测试流程",
            definition={"nodes": [], "edges": []},
            owner_id=20,
            is_public=False,
        )
        session.add(user)
        session.flush()
        session.add(workflow)
        session.flush()

        session.add(
            Delegation(
                id=20,
                workflow_id=workflow.id,
                delegator_id=user.id,
                delegate_id=user.id,
                permissions={"can_edit": True},
                expires_at=now + timedelta(hours=1),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Invitation(
                id=21,
                team_id=None,
                workflow_id=None,
                invited_by_id=user.id,
                invitee_email="x@example.com",
                token="invalid-invite-token",
                status="pending",
                expires_at=now + timedelta(days=1),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_ticket_crud_and_business_rules(sqlite_engine):
    now = datetime.now(timezone.utc)
    with Session(sqlite_engine) as session:
        operator = User(
            id=101,
            username="super_admin",
            email="super_admin@example.com",
            password_hash="hash",
            role="super_admin",
            status="active",
            is_email_verified=True,
        )
        session.add(operator)
        session.flush()

        ticket = Ticket(
            id=1,
            ticket_type=TicketType.KEY_REQUEST.value,
            status=TicketStatus.PENDING.value,
            email="requester@example.com",
            phone="13800138000",
            industry="能源",
            usage_purpose="用于空间分析试用",
            key_type="personal_trial",
        )
        session.add(ticket)
        session.commit()

    with Session(sqlite_engine) as session:
        ticket = session.query(Ticket).filter_by(id=1).one()
        ticket.status = TicketStatus.APPROVED.value
        ticket.processed_by = 101
        ticket.processed_at = now
        ticket.approval_notes = "审批通过"
        session.commit()

    with Session(sqlite_engine) as session:
        ticket = session.query(Ticket).filter_by(id=1).one()
        ticket.status = TicketStatus.COMPLETED.value
        ticket.assigned_key = "PK-TICKET-0001"
        ticket.response_message = "密钥已分配，请查收。"
        session.commit()

    with Session(sqlite_engine) as session:
        ticket = session.query(Ticket).filter_by(id=1).one()
        ticket.response_message = "尝试修改已完成工单"
        with pytest.raises(ValueError):
            session.commit()
        session.rollback()


def test_ticket_validation_and_constraints(sqlite_engine):
    with Session(sqlite_engine) as session:
        with pytest.raises(ValueError):
            Ticket(
                id=2,
                ticket_type=TicketType.KEY_REQUEST.value,
                status=TicketStatus.PENDING.value,
                email="invalid_email",
                phone="13800138000",
                industry="制造",
                usage_purpose="用途说明",
                key_type="personal_standard",
            )

        with pytest.raises(ValueError):
            Ticket(
                id=3,
                ticket_type=TicketType.KEY_REQUEST.value,
                status=TicketStatus.PENDING.value,
                email="valid@example.com",
                phone="12345",
                industry="制造",
                usage_purpose="用途说明",
                key_type="personal_standard",
            )

        session.add(
            Ticket(
                id=4,
                ticket_type=TicketType.KEY_EXTENSION.value,
                status=TicketStatus.PENDING.value,
                email="valid@example.com",
                phone="+8613800138000",
                industry="制造",
                usage_purpose="需要延期",
                key_type="enterprise_standard",
            )
        )
        with pytest.raises(ValueError):
            session.commit()
        session.rollback()


def test_ticket_status_transition_and_single_processing(sqlite_engine):
    now = datetime.now(timezone.utc)
    with Session(sqlite_engine) as session:
        operator = User(
            id=202,
            username="operator",
            email="operator@example.com",
            password_hash="hash",
            role="super_admin",
            status="active",
            is_email_verified=True,
        )
        rejected_ticket = Ticket(
            id=10,
            ticket_type=TicketType.KEY_EXTENSION.value,
            status=TicketStatus.REJECTED.value,
            email="rejected@example.com",
            phone="13900139000",
            industry="金融",
            usage_purpose="延期申请",
            key_type="enterprise_trial",
            existing_key="PK-OLD-0001",
            processed_by=202,
            processed_at=now,
            approval_notes="资料不足",
        )
        approved_ticket = Ticket(
            id=11,
            ticket_type=TicketType.KEY_EXTENSION.value,
            status=TicketStatus.APPROVED.value,
            email="approved@example.com",
            phone="13700137000",
            industry="医疗",
            usage_purpose="项目持续使用",
            key_type="enterprise_standard",
            existing_key="PK-OLD-0002",
            processed_by=202,
            processed_at=now,
            approval_notes="审批通过",
        )
        session.add_all([operator, rejected_ticket, approved_ticket])
        session.commit()

    with Session(sqlite_engine) as session:
        rejected_ticket = session.query(Ticket).filter_by(id=10).one()
        rejected_ticket.status = TicketStatus.APPROVED.value
        with pytest.raises(ValueError):
            session.commit()
        session.rollback()

    with Session(sqlite_engine) as session:
        approved_ticket = session.query(Ticket).filter_by(id=11).one()
        approved_ticket.processed_by = 999
        with pytest.raises(ValueError):
            session.commit()
        session.rollback()
