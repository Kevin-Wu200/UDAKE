"""Tests for 密钥申请工单系统 API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict

import pytest
from app.api.tickets_api import router as tickets_router
from app.auth import get_auth_service, reset_auth_service
from app.auth_db.models import AuditLog, Base, Company, ProductKey, Ticket, User
from app.auth_db.session import get_auth_db_session
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def tickets_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "tickets-api-secret")
    reset_auth_service()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        company = Company(
            id=1,
            name="某某测绘集团有限公司",
            status="active",
        )
        super_admin = User(
            id=1,
            username="root",
            email="root@example.com",
            password_hash="hash",
            role="super_admin",
            status="active",
        )
        admin = User(
            id=2,
            username="admin",
            email="admin@example.com",
            password_hash="hash",
            role="admin",
            status="active",
            company_id=1,
        )
        user = User(
            id=3,
            username="member",
            email="member@example.com",
            password_hash="hash",
            role="user",
            status="active",
        )
        existing_key = ProductKey(
            id=100,
            user_id=3,
            product_key="ABC-DEFG-HIJK-LMNO",
            key_type="personal_standard",
            key_sub_type="standard",
            status="active",
            total_quota=100,
            used_count=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=10),
        )
        pending_ticket = Ticket(
            id=200,
            ticket_id="TKT-TEST0001",
            ticket_type="key_request",
            status="pending",
            email="owner@example.com",
            phone="13800138000",
            industry="地理测绘",
            organization="某某测绘集团有限公司",
            usage_purpose="这是一个用于空间插值与不确定性分析平台测试的用途说明，确保超过十五个汉字。",
            key_type="personal_trial",
            company_id=1,
        )
        db.add_all([company, super_admin, admin, user, existing_key, pending_ticket])
        db.commit()

    app = FastAPI()
    app.include_router(tickets_router, prefix="/api")

    def override_get_auth_db_session():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_auth_db_session] = override_get_auth_db_session

    service = get_auth_service()
    tokens: Dict[str, str] = {
        "super_admin": service.jwt.generate_access_token(user_id=1, role="super_admin", permissions=["*"]),
        "admin": service.jwt.generate_access_token(user_id=2, role="admin", permissions=["*"]),
        "user": service.jwt.generate_access_token(user_id=3, role="user", permissions=["read"]),
    }

    with TestClient(app) as client:
        yield client, SessionLocal, tokens

    reset_auth_service()


def _auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_create_and_public_get_ticket(tickets_client):
    client, session_factory, _ = tickets_client

    create_resp = client.post(
        "/api/tickets",
        json={
            "ticket_type": "key_request",
            "email": "Applicant@Example.com",
            "phone": "13800138000",
            "industry": "环境",
            "organization": "某某环境检测技术服务有限公司",
            "usage_purpose": "这是一个用于空间插值与不确定性分析平台测试的用途说明，确保超过十五个汉字。",
            "key_type": "enterprise_trial",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    body = create_resp.json()
    assert body["success"] is True
    ticket_id = body["data"]["ticket_id"]
    assert body["data"]["ticket"]["status"] == "pending"
    assert body["data"]["ticket"]["email"] == "applicant@example.com"

    detail_resp = client.get(f"/api/tickets/{ticket_id}?email=applicant@example.com")
    assert detail_resp.status_code == 200, detail_resp.text
    ticket = detail_resp.json()["data"]["ticket"]
    assert ticket["ticket_id"] == ticket_id
    assert "processed_by" not in ticket

    with session_factory() as db:
        stored = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).one()
        assert stored.email == "applicant@example.com"
        assert stored.status == "pending"
        assert db.query(AuditLog).filter(AuditLog.target_id == str(stored.id)).count() >= 2


def test_create_ticket_validates_existing_key_requirement(tickets_client):
    client, _, _ = tickets_client

    resp = client.post(
        "/api/tickets",
        json={
            "ticket_type": "key_extension",
            "email": "bad@example.com",
            "phone": "13800138000",
            "industry": "地理测绘",
            "organization": "某某测绘集团",
            "usage_purpose": "这是一个用于空间插值与不确定性分析平台测试的用途说明，确保超过十五个汉字。",
            "key_type": "personal_standard",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["message"] == "key_extension 工单必须提供 existing_key"


def test_list_tickets_requires_super_admin_and_supports_filters(tickets_client):
    client, _, tokens = tickets_client

    forbidden_resp = client.get("/api/tickets", headers=_auth_header(tokens["user"]))
    assert forbidden_resp.status_code == 403

    ok_resp = client.get(
        "/api/tickets?status=pending&ticket_type=key_request&page=1&page_size=10",
        headers=_auth_header(tokens["super_admin"]),
    )
    assert ok_resp.status_code == 200, ok_resp.text
    data = ok_resp.json()["data"]
    assert data["total"] >= 1
    assert data["pagination"]["page"] == 1
    assert all(item["status"] == "pending" for item in data["tickets"])


def test_approve_key_request_generates_product_key_and_completes_ticket(tickets_client):
    client, session_factory, tokens = tickets_client

    resp = client.put(
        "/api/tickets/200/approve",
        json={"notes": "审批通过"},
        headers=_auth_header(tokens["admin"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["ticket"]["status"] == "completed"
    assert data["ticket"]["processed_by"] == "admin"
    assert data["assigned_key"]

    with session_factory() as db:
        ticket = db.query(Ticket).filter(Ticket.id == 200).one()
        assert ticket.status == "completed"
        assert ticket.assigned_key == data["assigned_key"]
        product_key = db.query(ProductKey).filter(ProductKey.product_key == data["assigned_key"]).one()
        assert product_key.user_id is not None
        assert product_key.total_quota == 10


def test_approve_key_extension_extends_expiry(tickets_client):
    client, session_factory, tokens = tickets_client

    with session_factory() as db:
        ticket = Ticket(
            id=201,
            ticket_id="TKT-TEST0002",
            ticket_type="key_extension",
            status="pending",
            email="member@example.com",
            phone="13800138000",
            industry="地理测绘",
            organization="某某测绘院",
            usage_purpose="这是一个用于空间插值与不确定性分析平台测试的用途说明，确保超过十五个汉字。",
            key_type="personal_standard",
            existing_key="ABC-DEFG-HIJK-LMNO",
        )
        db.add(ticket)
        before_expiry = db.query(ProductKey).filter(ProductKey.id == 100).one().expires_at
        db.commit()

    resp = client.put(
        "/api/tickets/201/approve",
        json={"notes": "同意延期"},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["assigned_key"] == "ABC-DEFG-HIJK-LMNO"

    with session_factory() as db:
        updated_key = db.query(ProductKey).filter(ProductKey.id == 100).one()
        assert updated_key.expires_at is not None
        assert updated_key.expires_at >= before_expiry + timedelta(days=89, hours=23)


def test_reject_ticket_requires_reason_and_updates_status(tickets_client):
    client, session_factory, tokens = tickets_client

    with session_factory() as db:
        ticket = Ticket(
            id=202,
            ticket_id="TKT-TEST0003",
            ticket_type="key_request",
            status="pending",
            email="reject@example.com",
            phone="13800138000",
            industry="教育",
            organization="某某大学",
            usage_purpose="这是一个用于空间插值与不确定性分析平台测试的用途说明，确保超过十五个汉字。",
            key_type="personal_standard",
        )
        db.add(ticket)
        db.commit()

    empty_reason_resp = client.put(
        "/api/tickets/202/reject",
        json={"reason": ""},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert empty_reason_resp.status_code == 400

    reject_resp = client.put(
        "/api/tickets/202/reject",
        json={"reason": "资料不完整"},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert reject_resp.status_code == 200, reject_resp.text
    assert reject_resp.json()["data"]["ticket"]["status"] == "rejected"

    with session_factory() as db:
        ticket = db.query(Ticket).filter(Ticket.id == 202).one()
        assert ticket.approval_notes == "资料不完整"
        assert ticket.response_message == "工单已被拒绝：资料不完整"
