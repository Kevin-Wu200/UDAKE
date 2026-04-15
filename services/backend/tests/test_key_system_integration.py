"""Key system integration tests covering admin/company/auth workflows."""

from __future__ import annotations

from typing import Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.admin_api import router as admin_router
from app.api.auth_api import router as auth_router
from app.api.company_management_api import router as company_router
from app.auth import ProductKeyRegistry, get_auth_service, reset_auth_service
from app.auth_db.models import AuditLog, Base, Company, ProductKey, User
from app.auth_db.session import get_auth_db_session


@pytest.fixture()
def key_system_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "key-system-integration-secret")
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
        company_a = Company(id=1, name="测试企业A", status="active")
        company_b = Company(id=2, name="测试企业B", status="active")
        db.add_all([company_a, company_b])

        super_admin = User(
            id=1,
            username="root",
            email="root@example.com",
            password_hash="hash",
            role="super_admin",
            status="active",
        )
        company_admin = User(
            id=2,
            username="company_admin_a",
            email="company_admin_a@example.com",
            password_hash="hash",
            role="company_admin",
            status="active",
            company_id=1,
        )
        user_a = User(
            id=3,
            username="user_a",
            email="user_a@example.com",
            password_hash="hash",
            role="user",
            status="active",
            company_id=1,
        )
        user_b = User(
            id=4,
            username="user_b",
            email="user_b@example.com",
            password_hash="hash",
            role="user",
            status="active",
            company_id=2,
        )
        db.add_all([super_admin, company_admin, user_a, user_b])
        db.commit()

    app = FastAPI()
    app.include_router(admin_router, prefix="/api")
    app.include_router(company_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")

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
        "company_admin": service.jwt.generate_access_token(user_id=2, role="company_admin", permissions=["*"]),
        "user": service.jwt.generate_access_token(user_id=3, role="user", permissions=["read"]),
        "invalid": "not-a-valid-token",
    }

    with TestClient(app) as client:
        yield client, SessionLocal, tokens

    reset_auth_service()


@pytest.fixture()
def auth_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "key-system-auth-integration-secret")
    reset_auth_service()

    app = FastAPI()
    app.include_router(auth_router, prefix="/api")

    with TestClient(app) as client:
        yield client

    reset_auth_service()


def _auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_database_schema_and_api_integration(key_system_client):
    client, session_factory, tokens = key_system_client

    with session_factory() as db:
        inspector = inspect(db.bind)
        columns = {item["name"] for item in inspector.get_columns("product_keys")}
        assert {"key_sub_type", "generation_seed", "key_metadata", "activated_at", "expires_at"}.issubset(columns)
        user_columns = {item["name"] for item in inspector.get_columns("users")}
        assert {"company_admin_type", "company_admin_key_id", "total_keys_created"}.issubset(user_columns)

    create_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_standard", "count": 1, "company_id": 1, "metadata": {"source": "integration"}},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert create_resp.status_code == 200, create_resp.text
    key = create_resp.json()["data"]["keys"][0]

    with session_factory() as db:
        stored = db.query(ProductKey).filter(ProductKey.id == key["id"]).one()
        assert stored.product_key == key["product_key"]
        assert stored.company_id == 1
        assert stored.product_key_ciphertext is not None


def test_api_contract_error_and_auth_integration(key_system_client):
    client, _, tokens = key_system_client

    ok_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_trial", "count": 2, "company_id": 1, "metadata": {"notes": "前后端联调"}},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert ok_resp.status_code == 200, ok_resp.text
    body = ok_resp.json()["data"]
    assert body["count"] == 2
    assert all("id" in item and "product_key" in item and "metadata" in item for item in body["keys"])

    invalid_payload_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "bad_type", "count": -1},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert invalid_payload_resp.status_code == 422

    invalid_token_resp = client.get(
        "/api/admin/product-keys",
        headers=_auth_header(tokens["invalid"]),
    )
    assert invalid_token_resp.status_code == 401


def test_product_key_generation_service_and_database_integration(key_system_client):
    _, session_factory, _ = key_system_client
    registry = ProductKeyRegistry()

    generated = registry.generate_keys(
        key_type="enterprise_trial",
        count=20,
        company_id=1,
        company_name="测试企业A",
    )
    assert len(generated) == 20
    assert len({item.product_key for item in generated}) == 20

    with session_factory() as db:
        next_id = int((db.query(ProductKey.id).order_by(ProductKey.id.desc()).first() or (100,))[0]) + 1
        for index, item in enumerate(generated):
            db.add(
                ProductKey(
                    id=next_id + index,
                    user_id=2,
                    product_key=item.product_key,
                    key_type=item.key_type,
                    key_sub_type=item.key_sub_type,
                    status=item.status,
                    company_id=1,
                    total_quota=item.total_quota,
                    used_count=item.used_count,
                    generation_seed=item.generation_seed,
                )
            )
        db.commit()

        rows = db.query(ProductKey).filter(ProductKey.company_id == 1, ProductKey.key_type == "enterprise_trial").all()
        assert len(rows) >= 20


def test_permission_control_integration(key_system_client):
    client, _, tokens = key_system_client

    super_admin_resp = client.get("/api/admin/product-keys", headers=_auth_header(tokens["super_admin"]))
    assert super_admin_resp.status_code == 200

    company_admin_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_standard", "count": 1, "company_id": 1},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert company_admin_resp.status_code == 200

    forbidden_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_standard", "count": 1, "company_id": 1},
        headers=_auth_header(tokens["user"]),
    )
    assert forbidden_resp.status_code == 403


def test_user_auth_registration_login_integration(auth_client):
    service = get_auth_service()
    register_key = service.product_keys.generate_key("integration-register-seed").product_key

    register_resp = auth_client.post(
        "/api/auth/register",
        json={
            "email": "integration_user@example.com",
            "password": "StrongPass123",
            "product_key": register_key,
        },
    )
    assert register_resp.status_code == 200, register_resp.text

    code_payload = service.verifier.cache.get("verify_code:integration_user@example.com")
    assert isinstance(code_payload, dict)
    code = str(code_payload.get("code") or "")
    assert len(code) == 6

    verify_resp = auth_client.post(
        "/api/auth/verify-email-code",
        json={"email": "integration_user@example.com", "code": code},
    )
    assert verify_resp.status_code == 200, verify_resp.text

    login_resp = auth_client.post(
        "/api/auth/login",
        json={"email": "integration_user@example.com", "password": "StrongPass123", "device_info": {"device_id": "i-1"}},
    )
    assert login_resp.status_code == 200, login_resp.text
    login_data = login_resp.json()["data"]
    assert "access_token" in login_data and "refresh_token" in login_data


def test_register_can_use_database_created_admin_key(key_system_client, monkeypatch: pytest.MonkeyPatch):
    client, session_factory, tokens = key_system_client
    monkeypatch.setattr("app.auth_db.session.get_auth_session_factory", lambda: session_factory)

    create_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "personal_standard", "count": 1},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert create_resp.status_code == 200, create_resp.text
    created_key = str(create_resp.json()["data"]["keys"][0]["product_key"])

    register_resp = client.post(
        "/api/auth/register",
        json={
            "email": "db_key_user@example.com",
            "password": "StrongPass123",
            "product_key": created_key,
        },
    )
    assert register_resp.status_code == 200, register_resp.text

    with session_factory() as db:
        stored = db.query(ProductKey).filter(ProductKey.product_key == created_key).one()
        assert stored.status == "active"


def test_company_system_integration_batch_assign_and_stats(key_system_client):
    client, session_factory, tokens = key_system_client

    batch_resp = client.post(
        "/api/company/product-keys/batch",
        json={"key_type": "enterprise_standard", "count": 3, "metadata": {"ticket": "INT-9"}},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert batch_resp.status_code == 200, batch_resp.text
    batch_data = batch_resp.json()["data"]
    key_id = batch_data["keys"][0]["id"]

    assign_resp = client.post(
        "/api/company/product-keys/assign",
        json={"key_id": key_id, "user_id": 3},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert assign_resp.status_code == 200, assign_resp.text

    stats_resp = client.get("/api/company/product-keys/stats", headers=_auth_header(tokens["company_admin"]))
    assert stats_resp.status_code == 200, stats_resp.text
    assert stats_resp.json()["data"]["company_id"] == 1

    with session_factory() as db:
        user = db.query(User).filter(User.id == 3).one()
        assert user.product_key_id == key_id

    cross_company_resp = client.post(
        "/api/company/product-keys/assign",
        json={"key_id": key_id, "user_id": 4},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert cross_company_resp.status_code == 404


def test_audit_system_integration_for_key_operations(key_system_client):
    client, session_factory, tokens = key_system_client

    create_resp = client.post(
        "/api/admin/product-keys",
        json={"type": "enterprise_trial", "count": 1, "company_id": 1},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert create_resp.status_code == 200, create_resp.text

    with session_factory() as db:
        create_log = (
            db.query(AuditLog)
            .filter(AuditLog.target_table == "product_keys")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert create_log is not None
        assert create_log.operation_type == "create"
        assert isinstance(create_log.details, dict)
        assert create_log.details.get("action") == "create_product_keys"

    list_audit_resp = client.get(
        "/api/admin/audit-logs?page=1&page_size=10&operation_type=create",
        headers=_auth_header(tokens["super_admin"]),
    )
    assert list_audit_resp.status_code == 200, list_audit_resp.text
    assert list_audit_resp.json()["data"]["total"] >= 1


def test_end_to_end_key_lifecycle_integration(key_system_client):
    client, session_factory, tokens = key_system_client

    created = client.post(
        "/api/company/product-keys/batch",
        json={"key_type": "enterprise_trial", "count": 1, "metadata": {"flow": "e2e"}},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert created.status_code == 200, created.text
    key = created.json()["data"]["keys"][0]

    assigned = client.post(
        "/api/company/product-keys/assign",
        json={"key_id": key["id"], "user_id": 3},
        headers=_auth_header(tokens["company_admin"]),
    )
    assert assigned.status_code == 200, assigned.text

    with session_factory() as db:
        before = db.query(ProductKey).filter(ProductKey.id == key["id"]).one()
        assert before.status in {"unused", "active"}

    disable_resp = client.put(
        f"/api/admin/product-keys/{key['id']}",
        json={"status": "disabled"},
        headers=_auth_header(tokens["super_admin"]),
    )
    assert disable_resp.status_code == 200, disable_resp.text
    assert disable_resp.json()["data"]["key"]["status"] == "disabled"
