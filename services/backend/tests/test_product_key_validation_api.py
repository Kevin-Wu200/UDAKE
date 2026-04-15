"""Tests for product key validation endpoint."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.product_keys_api import router as product_keys_router
from app.auth import ProductKeyValidationError, get_auth_service, reset_auth_service


@pytest.fixture()
def product_key_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "product-key-validate-api-secret")
    reset_auth_service()

    app = FastAPI()
    app.include_router(product_keys_router, prefix="/api")

    with TestClient(app) as client:
        yield client

    reset_auth_service()


def _validate(client: TestClient, product_key: str, ip: str = "10.0.0.1"):
    return client.post(
        "/api/product-keys/validate",
        json={"product_key": product_key},
        headers={"x-forwarded-for": ip},
    )


def test_validate_product_key_valid_key(product_key_client: TestClient):
    service = get_auth_service()
    record = service.product_keys.generate_key("validate-api-valid-seed")

    resp = _validate(product_key_client, record.product_key)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is True
    assert data["key_type"] == record.key_type
    assert "有效" in data["message"]


def test_validate_product_key_invalid_format(product_key_client: TestClient):
    resp = _validate(product_key_client, "INVALID-KEY")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is False
    assert data["key_type"] is None
    assert "格式" in data["message"]


def test_validate_product_key_checksum_mismatch(product_key_client: TestClient):
    service = get_auth_service()
    record = service.product_keys.generate_key("validate-api-checksum-seed")
    raw = record.product_key.replace("-", "")
    flipped = "0" if raw[-1] != "0" else "1"
    bad_raw = f"{raw[:-1]}{flipped}"
    bad_key = f"{bad_raw[:3]}-{bad_raw[3:7]}-{bad_raw[7:11]}-{bad_raw[11:15]}"

    resp = _validate(product_key_client, bad_key)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is False
    assert "校验" in data["message"]


def test_validate_product_key_not_found(product_key_client: TestClient):
    from app.auth.product_key_service import ProductKeyRegistry

    outsider_registry = ProductKeyRegistry()
    outsider_key = outsider_registry.generate_key("validate-api-not-found-seed").product_key

    resp = _validate(product_key_client, outsider_key)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is False
    assert data["message"] == "密钥不存在"


def test_validate_product_key_active_status(product_key_client: TestClient):
    service = get_auth_service()
    record = service.product_keys.generate_key("validate-api-active-seed")
    record.status = "active"

    resp = _validate(product_key_client, record.product_key)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is False
    assert data["key_type"] == record.key_type
    assert "已被使用" in data["message"]


def test_validate_product_key_rate_limit(product_key_client: TestClient):
    service = get_auth_service()
    record = service.product_keys.generate_key("validate-api-rate-limit-seed")

    for _ in range(10):
        resp = _validate(product_key_client, record.product_key, ip="10.0.0.9")
        assert resp.status_code == 200

    blocked = _validate(product_key_client, record.product_key, ip="10.0.0.9")
    assert blocked.status_code == 429
    assert "频繁" in blocked.json()["detail"]["message"]


def test_validate_product_key_exception_handling(product_key_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    service = get_auth_service()
    record = service.product_keys.generate_key("validate-api-exception-seed")

    def _boom(_: str) -> None:
        raise ProductKeyValidationError("product key format invalid")

    monkeypatch.setattr(service.product_keys, "validate_key_format", _boom)
    resp = _validate(product_key_client, record.product_key)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["valid"] is False
    assert data["message"] == "密钥格式无效"


def test_validate_product_key_audit_log_recorded(product_key_client: TestClient):
    service = get_auth_service()
    record = service.product_keys.generate_key("validate-api-audit-seed")

    resp = _validate(product_key_client, record.product_key, ip="10.0.0.88")
    assert resp.status_code == 200
    assert service.audit_logs
    latest = service.audit_logs[-1]
    assert latest["operation"] == "product_key_validate"
    assert latest["details"]["result"] == "success"
