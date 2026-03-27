"""Tests for enterprise/company management APIs."""

from __future__ import annotations

from typing import Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.company_management_api import router as company_router
from app.auth import get_auth_service, reset_auth_service
from app.auth_db.models import AuditLog, Base, Company, ProductKey, User
from app.auth_db.session import get_auth_db_session


@pytest.fixture()
def company_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "company-management-secret")
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
        company_a = Company(id=1, name="企业A", status="active")
        company_b = Company(id=2, name="企业B", status="active")
        db.add_all([company_a, company_b])
        db.flush()

        super_admin = User(
            id=1,
            username="root",
            email="root@example.com",
            password_hash="hash",
            role="super_admin",
            status="active",
        )
        company_admin = User(
            id=10,
            username="company_admin_a",
            email="company_admin_a@example.com",
            password_hash="hash",
            role="company_admin",
            status="active",
            company_id=company_a.id,
        )
        member_1 = User(
            id=11,
            username="member_a1",
            email="member_a1@example.com",
            password_hash="hash",
            role="user",
            status="active",
            company_id=company_a.id,
        )
        member_2 = User(
            id=12,
            username="member_a2",
            email="member_a2@example.com",
            password_hash="hash",
            role="user",
            status="active",
            company_id=company_a.id,
        )
        other_company_member = User(
            id=21,
            username="member_b1",
            email="member_b1@example.com",
            password_hash="hash",
            role="user",
            status="active",
            company_id=company_b.id,
        )
        db.add_all([super_admin, company_admin, member_1, member_2, other_company_member])
        db.flush()

        key_a = ProductKey(
            id=101,
            user_id=member_1.id,
            company_id=company_a.id,
            product_key="PK-ENT-A-001",
            key_type="enterprise",
            status="active",
            total_quota=10,
            used_count=1,
        )
        db.add(key_a)
        db.flush()
        member_1.product_key_id = key_a.id
        db.commit()

    app = FastAPI()
    app.include_router(company_router, prefix="/api")

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
        "company_admin": service.jwt.generate_access_token(user_id=10, role="company_admin", permissions=["*"]),
        "member_a2": service.jwt.generate_access_token(user_id=12, role="user", permissions=["read"]),
    }

    with TestClient(app) as client:
        yield client, SessionLocal, tokens

    reset_auth_service()


def _auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_list_company_users_with_scope_and_search(company_client):
    client, _, tokens = company_client

    resp = client.get("/api/company/users?page=1&page_size=20&search=member_a", headers=_auth_header(tokens["company_admin"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    users = body["data"]["users"]
    assert len(users) == 2
    assert {item["username"] for item in users} == {"member_a1", "member_a2"}
    assert all(item["company_name"] == "企业A" for item in users)

    forbidden_resp = client.get("/api/company/users", headers=_auth_header(tokens["member_a2"]))
    assert forbidden_resp.status_code == 403


def test_delete_company_user_soft_delete_release_quota_and_audit(company_client):
    client, session_factory, tokens = company_client

    resp = client.delete("/api/company/users/11", headers=_auth_header(tokens["company_admin"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    with session_factory() as db:
        user = db.query(User).filter(User.id == 11).one()
        assert user.status == "deleted"
        assert user.product_key_id is None

        product_key = db.query(ProductKey).filter(ProductKey.id == 101).one()
        assert product_key.used_count == 0
        assert product_key.status == "available"

        audit = (
            db.query(AuditLog)
            .filter(AuditLog.operation_type == "delete_user", AuditLog.target_id == "11")
            .one()
        )
        assert audit.user_id == 10


def test_delete_company_user_permission_boundaries(company_client):
    client, _, tokens = company_client

    self_delete = client.delete("/api/company/users/10", headers=_auth_header(tokens["company_admin"]))
    assert self_delete.status_code == 400

    cross_company = client.delete("/api/company/users/21", headers=_auth_header(tokens["company_admin"]))
    assert cross_company.status_code == 403


def test_company_profile_and_super_admin_views(company_client):
    client, _, tokens = company_client

    me_resp = client.get("/api/company/me", headers=_auth_header(tokens["member_a2"]))
    assert me_resp.status_code == 200, me_resp.text
    me_body = me_resp.json()["data"]["user"]
    assert me_body["company_name"] == "企业A"
    assert me_body["role"] == "user"

    admin_users_resp = client.get("/api/company/admin/users", headers=_auth_header(tokens["super_admin"]))
    assert admin_users_resp.status_code == 200, admin_users_resp.text
    all_users = admin_users_resp.json()["data"]["users"]
    assert len(all_users) >= 5
    assert any(item["company_name"] == "企业B" for item in all_users)

    stats_resp = client.get("/api/company/admin/company-stats", headers=_auth_header(tokens["super_admin"]))
    assert stats_resp.status_code == 200, stats_resp.text
    companies = stats_resp.json()["data"]["companies"]
    assert {item["company_name"] for item in companies} >= {"企业A", "企业B"}
