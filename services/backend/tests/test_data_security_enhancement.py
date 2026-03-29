"""Tests for data security enhancement module."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.数据安全接口 import router as security_router
from app.config import settings
from app.security_middleware import security_guard_middleware
from app.services.数据安全服务 import get_data_security_service, reset_data_security_service


@pytest.fixture()
def security_client():
    reset_data_security_service()
    app = FastAPI()
    app.middleware("http")(security_guard_middleware)
    app.include_router(security_router, prefix="/api")

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    with TestClient(app) as client:
        yield client
    reset_data_security_service()


def test_security_middleware_blocks_insecure_transport_in_production(
    security_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)

    insecure = security_client.get("/api/ping")
    assert insecure.status_code == 426
    payload = insecure.json()
    assert payload["success"] is False
    assert payload["data"]["required_tls"] == "TLSv1.3"

    secure = security_client.get(
        "/api/ping",
        headers={
            "X-Forwarded-Proto": "https",
            "X-TLS-Version": "TLSv1.3",
            "Host": "api.example.com",
        },
    )
    assert secure.status_code == 200
    assert secure.json()["ok"] is True


def test_data_security_service_core_workflow():
    service = get_data_security_service()

    encrypted = service.encrypt_field("18888888888")
    assert encrypted.startswith("kmsf:v1:")
    assert service.decrypt_field(encrypted) == "18888888888"

    file_ciphertext = service.encrypt_file_content("top-secret".encode("utf-8"))
    assert service.decrypt_file_content(file_ciphertext) == b"top-secret"

    protected = service.protect_memory(b"in-memory-secret")
    assert service.recover_memory(protected) == b"in-memory-secret"

    service.register_user("u-analyst", "analyst", {"clearance": "high", "department": "risk"})
    service.grant_permission("analyst", "data:read_sensitive")
    service.add_abac_rule(
        rule_id="risk_internal_allow",
        action="data:read_sensitive",
        effect="allow",
        conditions={"user.attributes.department": "risk", "resource.classification": "internal"},
    )

    allowed = service.check_access(
        user_id="u-analyst",
        action="data:read_sensitive",
        resource_attributes={"classification": "internal"},
    )
    assert allowed["allowed"] is True

    denied = service.check_access(
        user_id="u-analyst",
        action="data:read_sensitive",
        resource_attributes={"classification": "external"},
    )
    assert denied["allowed"] is False

    revoked = service.revoke_user_access("u-analyst")
    assert revoked["revoked"] is True
    denied_after_revoke = service.check_access(
        user_id="u-analyst",
        action="data:read_sensitive",
        resource_attributes={"classification": "internal"},
    )
    assert denied_after_revoke["allowed"] is False
    assert denied_after_revoke["reason"] == "access_revoked"

    masked = service.dynamic_mask_data(
        {"email": "alice@example.com", "phone": "13812345678"},
        viewer_role="guest",
    )
    assert "***" in masked["email"]
    assert "****" in masked["phone"]

    anon = service.anonymize_data(
        {"user_id": "u-1", "x": 120.12345, "y": 30.98765, "value": 19.2, "email": "a@b.com"}
    )
    assert anon["user_id"] == "anonymous"
    assert anon["email"] == "anonymous"
    assert anon["value"].startswith("[")

    dp = service.differential_privacy([10, 20, 30], epsilon=0.7, sensitivity=1.0, seed=7)
    assert dp["count"] == 3
    assert "noisy_mean" in dp

    backup = service.create_backup(payload={"dataset": "security", "count": 2}, mode="full", user_id="admin-1")
    verified = service.verify_backup(backup["backup_id"])
    restored = service.restore_backup(backup["backup_id"], user_id="admin-1")
    assert verified["verified"] is True
    assert restored["snapshot"]["dataset"] == "security"

    incremental = service.create_backup(
        payload={"dataset": "security", "count": 3, "new_field": "yes"},
        mode="incremental",
        user_id="admin-1",
    )
    restored_inc = service.restore_backup(incremental["backup_id"], user_id="admin-1")
    assert restored_inc["snapshot"]["count"] == 3
    assert restored_inc["snapshot"]["new_field"] == "yes"

    compliance = service.compliance_check()
    assert compliance["passed"] is True
    assert compliance["pass_rate"] == 100.0

    scan = service.vulnerability_scan()
    assert "passed" in scan


def test_data_security_api_end_to_end(security_client: TestClient):
    register = security_client.post(
        "/api/security/access/users",
        json={"user_id": "api_user", "role": "analyst", "attributes": {"clearance": "high", "department": "risk"}},
    )
    assert register.status_code == 200

    grant = security_client.post(
        "/api/security/access/permissions/grant",
        json={"role": "analyst", "permission": "data:read_sensitive"},
    )
    assert grant.status_code == 200

    abac = security_client.post(
        "/api/security/access/abac/rules",
        json={
            "rule_id": "api_rule_1",
            "action": "data:read_sensitive",
            "effect": "allow",
            "conditions": {"user.attributes.department": "risk", "resource.classification": "internal"},
        },
    )
    assert abac.status_code == 200

    access = security_client.post(
        "/api/security/access/check",
        json={
            "user_id": "api_user",
            "action": "data:read_sensitive",
            "resource_attributes": {"classification": "internal"},
        },
    )
    assert access.status_code == 200
    assert access.json()["data"]["allowed"] is True

    encrypted = security_client.post("/api/security/encrypt/field", json={"plaintext": "secret-token-001"})
    assert encrypted.status_code == 200
    ciphertext = encrypted.json()["data"]["ciphertext"]
    assert ciphertext.startswith("kmsf:v1:")

    decrypted = security_client.post("/api/security/decrypt/field", json={"ciphertext": ciphertext})
    assert decrypted.status_code == 200
    assert decrypted.json()["data"]["plaintext"] == "secret-token-001"

    backup = security_client.post(
        "/api/security/backup",
        json={"payload": {"a": 1, "b": "safe"}, "mode": "full", "user_id": "api_user", "regions": ["cn-hz", "cn-bj"]},
    )
    assert backup.status_code == 200
    backup_id = backup.json()["data"]["backup_id"]

    verify = security_client.get(f"/api/security/backup/{backup_id}/verify")
    assert verify.status_code == 200
    assert verify.json()["data"]["verified"] is True

    restore = security_client.post(f"/api/security/backup/{backup_id}/restore")
    assert restore.status_code == 200
    assert restore.json()["data"]["snapshot"]["b"] == "safe"

    compliance = security_client.get("/api/security/compliance/check")
    assert compliance.status_code == 200
    assert compliance.json()["data"]["passed"] is True

    report = security_client.get("/api/security/audit/report")
    assert report.status_code == 200
    assert report.json()["data"]["total_audit_events"] >= 1

