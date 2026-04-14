"""Tests for admin backend APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.admin_api import router as admin_router
from app.auth import ProductKeyRegistry, get_auth_service, reset_auth_service
from app.auth_db.models import AuditLog, Base, Company, PasswordHistory, ProductKey, User, UserDevice
from app.auth_db.session import get_auth_db_session


@pytest.fixture()
def admin_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "admin-api-secret")
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
        company_b = Company(id=2, name="企业B", status="disabled")
        db.add_all([company_a, company_b])
        db.flush()

        super_admin = User(
            id=1,
            username="root",
            email="root@example.com",
            password_hash="old_hash",
            role="super_admin",
            status="active",
        )
        user_a = User(
            id=2,
            username="alice",
            email="alice@example.com",
            password_hash="old_hash_alice",
            role="user",
            status="active",
            company_id=1,
        )
        user_b = User(
            id=3,
            username="bob",
            email="bob@example.com",
            password_hash="old_hash_bob",
            role="user",
            status="disabled",
            company_id=2,
        )
        company_admin = User(
            id=4,
            username="company_admin_a",
            email="company_admin_a@example.com",
            password_hash="company_hash",
            role="company_admin",
            status="active",
            company_id=1,
        )
        user_c = User(
            id=5,
            username="charlie",
            email="charlie@example.com",
            password_hash="old_hash_charlie",
            role="user",
            status="active",
            company_id=1,
        )
        db.add_all([super_admin, user_a, user_b, company_admin, user_c])
        db.flush()

        key_unused = ProductKey(
            id=101,
            user_id=1,
            product_key="ABC-DEFG-HIJK-LMNO",
            key_type="personal_standard",
            key_sub_type="standard",
            status="unused",
            total_quota=100,
            used_count=0,
        )
        key_used = ProductKey(
            id=102,
            user_id=2,
            product_key="QWE-RTYU-IOPA-SDFG",
            key_type="enterprise_standard",
            key_sub_type="standard",
            status="active",
            company_id=1,
            total_quota=1000,
            used_count=1,
            signature="sig",
        )
        db.add_all([key_unused, key_used])

        device = UserDevice(
            id=201,
            user_id=2,
            device_id="alice-dev-1",
            device_name="Alice iPhone",
            platform="ios",
            is_trusted=True,
        )
        db.add(device)

        login_audit = AuditLog(
            id=301,
            user_id=2,
            actor_username="alice",
            operation_type="login",
            target_table="users",
            target_id="2",
            details={"result": "success"},
        )
        db.add(login_audit)
        db.commit()

    app = FastAPI()
    app.include_router(admin_router, prefix="/api")

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
        "company_admin": service.jwt.generate_access_token(user_id=4, role="company_admin", permissions=["*"]),
        "user": service.jwt.generate_access_token(user_id=2, role="user", permissions=["read"]),
    }

    with TestClient(app) as client:
        yield client, SessionLocal, tokens

    reset_auth_service()


def _auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_product_key_crud_and_batch(admin_client):
    client, _, tokens = admin_client

    super_batch_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_standard", "count": 2, "company_id": 1},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert super_batch_resp.status_code == 403, super_batch_resp.text

    create_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_standard", "count": 2, "company_id": 1, "metadata": {"source": "api-test"}},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert create_resp.status_code == 200, create_resp.text
    create_data = create_resp.json()["data"]
    assert create_data["count"] == 2
    assert all(item["type"] == "enterprise_standard" for item in create_data["keys"])
    assert all(item["metadata"] == {"source": "api-test"} for item in create_data["keys"])

    key_id_1 = create_data["keys"][0]["id"]
    key_id_2 = create_data["keys"][1]["id"]

    list_resp = client.get(
        "/api/admin/product-keys?page=1&page_size=50&type=enterprise_standard&company_id=2",
        headers=_auth_header(tokens["company_admin"]),
    )
    assert list_resp.status_code == 200, list_resp.text
    listed = list_resp.json()["data"]
    assert listed["total"] >= 2
    assert all(item["company_id"] == 1 for item in listed["keys"])

    assign_resp = client.post(
        "/api/admin/product-keys/assign",
        json={"key_id": key_id_1, "user_id": 2},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert assign_resp.status_code == 200, assign_resp.text
    assert assign_resp.json()["data"]["key"]["user_id"] == 2

    stats_resp = client.get("/api/admin/product-keys/stats", headers=_auth_header(tokens["company_admin"]))
    assert stats_resp.status_code == 200, stats_resp.text
    assert stats_resp.json()["data"]["company_id"] == 1

    update_resp = client.put(
        f"/api/admin/product-keys/{key_id_1}",
        json={"status": "disabled"},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["data"]["key"]["status"] == "disabled"

    delete_resp = client.delete(
        f"/api/admin/product-keys/{key_id_2}",
        headers=_auth_header(tokens["super_admin"]),
    )
    assert delete_resp.status_code == 200, delete_resp.text

    registry = ProductKeyRegistry()
    valid_key = registry.generate_key("batch-import-1").product_key
    batch_resp = client.post(
        "/api/admin/product-keys/batch",
        json={"keys": [valid_key, valid_key, "BAD-KEY"], "type": "personal_standard", "duplicate_action": "skip"},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    batch_data = batch_resp.json()["data"]
    assert batch_data["success_count"] == 1
    assert batch_data["failed_count"] == 2


def test_regular_user_product_key_permission_denied(admin_client):
    client, _, tokens = admin_client

    create_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "personal_standard", "count": 1},
        headers=_auth_header(tokens["user"]),
    )
    assert create_resp.status_code == 403, create_resp.text

    list_resp = client.get("/api/admin/product-keys", headers=_auth_header(tokens["user"]))
    assert list_resp.status_code == 403, list_resp.text

    batch_resp = client.post(
        "/api/admin/product-keys/batch",
        json={"keys": ["ABC1-DEF2-GHI3-JKL4"], "type": "personal_standard", "duplicate_action": "skip"},
        headers=_auth_header(tokens["user"]),
    )
    assert batch_resp.status_code == 403, batch_resp.text


def test_assign_product_key_cross_company_restriction_and_reassignment(admin_client):
    client, _, tokens = admin_client

    own_key_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_standard", "count": 1, "company_id": 1},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert own_key_resp.status_code == 200, own_key_resp.text
    own_key = own_key_resp.json()["data"]["keys"][0]

    assign_first = client.post(
        "/api/admin/product-keys/assign",
        json={"key_id": own_key["id"], "user_id": 2},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert assign_first.status_code == 200, assign_first.text
    first_payload = assign_first.json()["data"]["key"]
    first_assigned_at = datetime.fromisoformat(first_payload["assigned_at"])

    assign_second = client.post(
        "/api/admin/product-keys/assign",
        json={"key_id": own_key["id"], "user_id": 5},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert assign_second.status_code == 200, assign_second.text
    second_payload = assign_second.json()["data"]["key"]
    second_assigned_at = datetime.fromisoformat(second_payload["assigned_at"])
    assert second_payload["user_id"] == 5
    assert second_assigned_at >= first_assigned_at

    company_b_key_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_standard", "count": 1, "company_id": 2},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert company_b_key_resp.status_code == 200, company_b_key_resp.text
    company_b_key = company_b_key_resp.json()["data"]["keys"][0]

    cross_company_assign = client.post(
        "/api/admin/product-keys/assign",
        json={"key_id": company_b_key["id"], "user_id": 2},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert cross_company_assign.status_code == 403, cross_company_assign.text

    user_key_list = client.get(
        "/api/admin/product-keys?user_id=5",
        headers=_auth_header(tokens["company_admin"]),
    )
    assert user_key_list.status_code == 200, user_key_list.text
    listed_keys = user_key_list.json()["data"]["keys"]
    assert any(item["id"] == own_key["id"] and item["user_id"] == 5 for item in listed_keys)


def test_admin_user_management_and_reset_password(admin_client):
    client, session_factory, tokens = admin_client

    users_resp = client.get(
        "/api/admin/users?page=1&page_size=20&role=user&status=active&search=alice",
        headers=_auth_header(tokens["super_admin"]),
    )
    assert users_resp.status_code == 200, users_resp.text
    users = users_resp.json()["data"]["users"]
    assert len(users) == 1
    assert users[0]["username"] == "alice"

    detail_resp = client.get("/api/admin/users/2", headers=_auth_header(tokens["super_admin"]))
    assert detail_resp.status_code == 200, detail_resp.text
    detail_data = detail_resp.json()["data"]
    assert len(detail_data["devices"]) == 1
    assert len(detail_data["login_logs"]) >= 1

    disable_resp = client.post(
        "/api/admin/users/2/toggle-status",
        json={"status": "disabled"},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert disable_resp.status_code == 200, disable_resp.text

    with session_factory() as db:
        user = db.query(User).filter(User.id == 2).one()
        assert user.status == "disabled"

    service = get_auth_service()
    revoked = service.cache.get("jwt_user_revoked_after:2")
    assert revoked is not None

    enable_resp = client.post(
        "/api/admin/users/2/toggle-status",
        json={"status": "active"},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert enable_resp.status_code == 200, enable_resp.text

    reset_resp = client.post("/api/admin/users/2/reset-password", headers=_auth_header(tokens["super_admin"]))
    assert reset_resp.status_code == 200, reset_resp.text

    with session_factory() as db:
        user = db.query(User).filter(User.id == 2).one()
        assert user.password_hash != "old_hash_alice"

        histories = (
            db.query(PasswordHistory)
            .filter(PasswordHistory.user_id == 2)
            .order_by(PasswordHistory.history_order.asc())
            .all()
        )
        assert len(histories) >= 1
        assert histories[0].history_order == 1


def test_admin_audit_export_and_stats(admin_client):
    client, _, tokens = admin_client

    query_resp = client.get(
        "/api/admin/audit-logs?page=1&page_size=20&event_type=login",
        headers=_auth_header(tokens["super_admin"]),
    )
    assert query_resp.status_code == 200, query_resp.text
    assert query_resp.json()["data"]["total"] >= 1

    export_csv_resp = client.get(
        "/api/admin/audit-logs/export?format=csv",
        headers=_auth_header(tokens["super_admin"]),
    )
    assert export_csv_resp.status_code == 200, export_csv_resp.text
    assert export_csv_resp.headers["content-type"].startswith("application/octet-stream")
    assert "event_type" in export_csv_resp.content.decode("utf-8-sig")

    export_json_resp = client.get(
        "/api/admin/audit-logs/export?format=json",
        headers=_auth_header(tokens["super_admin"]),
    )
    assert export_json_resp.status_code == 200, export_json_resp.text
    assert b'"success": true' in export_json_resp.content

    stats_1 = client.get("/api/admin/stats", headers=_auth_header(tokens["super_admin"]))
    assert stats_1.status_code == 200, stats_1.text
    assert stats_1.json()["data"]["cached"] is False
    assert "user_growth_trend" in stats_1.json()["data"]

    stats_2 = client.get("/api/admin/stats", headers=_auth_header(tokens["super_admin"]))
    assert stats_2.status_code == 200, stats_2.text
    assert stats_2.json()["data"]["cached"] is True


def test_admin_endpoints_require_super_admin(admin_client):
    client, _, tokens = admin_client

    resp = client.get("/api/admin/users", headers=_auth_header(tokens["user"]))
    assert resp.status_code == 403
