"""Tests for authentication core module."""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth_api import router as auth_router
from app.auth import (
    AuthCacheManager,
    JWTManager,
    JWTValidationError,
    ProductKeyRegistry,
    ProductKeyValidationError,
    TokenFileFormatError,
    decrypt_tokens_blob,
    encrypt_tokens_blob,
    get_auth_service,
    hash_password,
    hash_passwords_parallel,
    parse_tokens_blob_header,
    reset_auth_service,
    verify_password,
)
from app.auth.product_key_service import verify_rsa_signature_sha256
from app.auth.rate_limiter import AuthRateLimiter, RateLimitExceededError, RateRule
from app.auth.verification import EmailVerificationService, VerificationCodeError


def test_tokens_enc_encrypt_and_decrypt_roundtrip():
    payload = {"access": "token", "refresh": "token2"}
    blob = encrypt_tokens_blob(payload, "P@ssw0rd")

    header = parse_tokens_blob_header(blob)
    assert header.magic == b"TKNS"
    assert header.version == 1
    assert header.memory_cost == 65536

    parsed = decrypt_tokens_blob(blob, "P@ssw0rd", decode_json=True)
    assert parsed == payload

    broken = b"XXXX" + blob[4:]
    with pytest.raises(TokenFileFormatError):
        parse_tokens_blob_header(broken)

    with pytest.raises(TokenFileFormatError):
        decrypt_tokens_blob(blob, "wrong-password", decode_json=True)


def test_password_hash_and_verify_and_parallel_hashing():
    encoded = hash_password("StrongPass123")
    assert verify_password("StrongPass123", encoded)
    assert not verify_password("bad-pass", encoded)

    results = hash_passwords_parallel(["Aa111111", "Bb222222", "Cc333333"], max_workers=2)
    assert len(results) == 3
    assert all(item.startswith("argon2id$") for item in results)


def test_jwt_access_refresh_and_blacklist():
    cache = AuthCacheManager(redis_url=None)
    jwt = JWTManager(secret_key="test-secret", cache_manager=cache)

    access = jwt.generate_access_token(user_id=1, role="user", permissions=["read"])
    payload = jwt.verify_token(access, expected_type="access")
    assert payload["user_id"] == "1"
    assert payload["role"] == "user"

    refresh = jwt.generate_refresh_token(user_id=1, device_id="dev-1")
    refresh_payload = jwt.verify_token(refresh, expected_type="refresh")
    assert refresh_payload["device_id"] == "dev-1"

    jwt.blacklist_token(access)
    with pytest.raises(JWTValidationError):
        jwt.verify_token(access, expected_type="access")


def test_product_key_validation_and_rsa_signature():
    registry = ProductKeyRegistry()
    record = registry.generate_key("seed-001")
    validated = registry.validate_key(record.product_key)
    assert validated.product_key == record.product_key

    bad_key = record.product_key[:-1] + ("0" if record.product_key[-1] != "0" else "1")
    with pytest.raises(ProductKeyValidationError):
        registry.validate_key(bad_key)

    # Pre-generated RSA sample (1024-bit, PKCS#1 v1.5 SHA-256).
    message = b"ABC-DEFG-HIJK-LMNO"
    public_pem = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDCyyDL5hrvmHeGFcxmdAdSDEs6
pwWVB/V9Ood2yzGKt7csTYGddMTkwiKyvYQCFRVb74jsocFDR637atOSf/s/NBny
uJy8ZqTdKDsTJyxZXEOuPZNLqVeezEl14TXffVEh2pjXFa7tZK5nC9+jXy9YPyDu
qZBjvhx2MwVWlSgyUwIDAQAB
-----END PUBLIC KEY-----"""
    signature_b64 = (
        "vKIDZ4D0LbHqlNYYOL7l4XV8rFy3U8D8hRHzaaZGkbvaPpM4CC7QUyJXk6STFlD3"
        "ktmhiP0udRnrwm9uIHMC+nfPjBQxTO48SZooD68tVuwP1LhuSipyqutLgZmP8cqO"
        "YqF1UPZTxIX5Cd0tZ102VBrkHwZu63CT3v52Ho2AS2w="
    )
    assert verify_rsa_signature_sha256(message, signature_b64, public_pem)


def test_verification_code_issue_and_attempt_limit():
    cache = AuthCacheManager(redis_url=None)
    verifier = EmailVerificationService(cache, code_ttl_seconds=30, max_attempts=3)

    code = verifier.issue_code("test@example.com")
    assert len(code) == 6

    with pytest.raises(VerificationCodeError):
        verifier.verify_code("test@example.com", "AAAAAA")
    with pytest.raises(VerificationCodeError):
        verifier.verify_code("test@example.com", "BBBBBB")
    with pytest.raises(VerificationCodeError):
        verifier.verify_code("test@example.com", "CCCCCC")

    code2 = verifier.issue_code("ok@example.com")
    result = verifier.verify_code("ok@example.com", code2)
    assert result.success is True


@pytest.fixture()
def auth_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "integration-secret")
    reset_auth_service()
    app = FastAPI()
    app.include_router(auth_router, prefix="/api")
    with TestClient(app) as client:
        yield client
    reset_auth_service()


def test_auth_api_register_login_refresh_logout(auth_client: TestClient):
    service = get_auth_service()
    key = service.product_keys.generate_key("api-integration-seed").product_key

    register_resp = auth_client.post(
        "/api/auth/register",
        json={"email": "foo@example.com", "password": "StrongPass123", "product_key": key},
    )
    assert register_resp.status_code == 200
    assert register_resp.json()["success"] is True

    login_resp = auth_client.post(
        "/api/auth/login",
        json={
            "email": "foo@example.com",
            "password": "StrongPass123",
            "device_info": {"device_id": "device-01", "platform": "web"},
        },
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()["data"]
    assert "access_token" in login_data
    assert "refresh_token" in login_data

    refresh_resp = auth_client.post("/api/auth/refresh", json={"refresh_token": login_data["refresh_token"]})
    assert refresh_resp.status_code == 200
    assert refresh_resp.json()["data"]["access_token"]

    logout_resp = auth_client.post("/api/auth/logout", json={"access_token": login_data["access_token"]})
    assert logout_resp.status_code == 200


def test_cache_ttl_management():
    cache = AuthCacheManager(redis_url=None)
    cache.set("foo", {"x": 1}, ttl=1)
    assert cache.exists("foo")
    ttl = cache.ttl("foo")
    assert ttl >= 0
    time.sleep(1.05)
    assert cache.get("foo") is None


def test_rate_limiter_lock_behaviour():
    cache = AuthCacheManager(redis_url=None)
    limiter = AuthRateLimiter(
        cache,
        lock_seconds=2,
        rules={"login": RateRule(hourly=1, daily=2)},
    )
    first = limiter.check_and_consume(identity="u1", action="login")
    assert first["remaining_hourly"] == 0
    with pytest.raises(RateLimitExceededError):
        limiter.check_and_consume(identity="u1", action="login")
    assert cache.ttl("rate_limit_lock:u1:login") > 0


def test_auth_service_change_password_reset_password_and_history(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "history-secret")
    reset_auth_service()
    service = get_auth_service()

    register_key = service.product_keys.generate_key("change-password-seed").product_key
    reset_key = service.product_keys.generate_key("reset-password-seed").product_key
    service.register(email="history@example.com", password="StrongPass123", product_key=register_key)
    login_payload = service.login(
        email="history@example.com",
        password="StrongPass123",
        device_info={"device_id": "history-device"},
    )
    access_token = login_payload["access_token"]

    service.change_password(
        access_token=access_token,
        old_password="StrongPass123",
        new_password="NewStrongPass123",
        confirm_password="NewStrongPass123",
    )
    with pytest.raises(JWTValidationError):
        service.jwt.verify_token(access_token, expected_type="access")

    refreshed_login = service.login(
        email="history@example.com",
        password="NewStrongPass123",
        device_info={"device_id": "history-device-2"},
    )
    with pytest.raises(ValueError):
        service.change_password(
            access_token=refreshed_login["access_token"],
            old_password="NewStrongPass123",
            new_password="StrongPass123",
            confirm_password="StrongPass123",
        )

    service.send_reset_password_code(email="history@example.com", product_key=reset_key)
    reset_payload = service.cache.get("reset_code:history@example.com")
    assert reset_payload and reset_payload["code"]
    service.reset_password(
        email="history@example.com",
        code=reset_payload["code"],
        new_password="ResetStrongPass123",
        confirm_password="ResetStrongPass123",
    )
    final_login = service.login(
        email="history@example.com",
        password="ResetStrongPass123",
        device_info={"device_id": "history-device-3"},
    )
    assert "access_token" in final_login

    history = service.get_password_history(final_login["user_info"]["user_id"])
    assert len(history) <= 5
    reset_auth_service()


def test_auth_service_change_email_flow(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "email-change-secret")
    reset_auth_service()
    service = get_auth_service()

    register_key = service.product_keys.generate_key("change-email-seed").product_key
    service.register(email="old-email@example.com", password="StrongPass123", product_key=register_key)
    login_payload = service.login(
        email="old-email@example.com",
        password="StrongPass123",
        device_info={"device_id": "email-device"},
    )
    access_token = login_payload["access_token"]
    user_id = login_payload["user_info"]["user_id"]

    service.send_change_email_code(
        access_token=access_token,
        new_email="new-email@example.com",
        current_password="StrongPass123",
    )
    cached = service.cache.get(f"change_email:{user_id}")
    assert cached and cached["code"]

    verify_result = service.verify_change_email(access_token=access_token, code=cached["code"])
    assert verify_result["new_email"] == "new-email@example.com"

    relogin = service.login(
        email="new-email@example.com",
        password="StrongPass123",
        device_info={"device_id": "email-device-2"},
    )
    assert relogin["user_info"]["email"] == "new-email@example.com"
    with pytest.raises(ValueError):
        service.login(
            email="old-email@example.com",
            password="StrongPass123",
            device_info={"device_id": "email-device-3"},
        )
    reset_auth_service()


def test_auth_api_reset_password_and_change_email(auth_client: TestClient):
    service = get_auth_service()
    register_key = service.product_keys.generate_key("auth-api-03-register").product_key
    reset_key = service.product_keys.generate_key("auth-api-03-reset").product_key

    register_resp = auth_client.post(
        "/api/auth/register",
        json={"email": "flow@example.com", "password": "StrongPass123", "product_key": register_key},
    )
    assert register_resp.status_code == 200

    login_resp = auth_client.post(
        "/api/auth/login",
        json={"email": "flow@example.com", "password": "StrongPass123", "device_info": {"device_id": "flow-01"}},
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["data"]["access_token"]

    change_password_resp = auth_client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "old_password": "StrongPass123",
            "new_password": "StrongPass456",
            "confirm_password": "StrongPass456",
        },
    )
    assert change_password_resp.status_code == 200

    reset_send_resp = auth_client.post(
        "/api/auth/reset-password/send-code",
        json={"email": "flow@example.com", "product_key": reset_key},
    )
    assert reset_send_resp.status_code == 200
    reset_code = service.cache.get("reset_code:flow@example.com")["code"]

    reset_verify_resp = auth_client.post(
        "/api/auth/reset-password/verify",
        json={
            "email": "flow@example.com",
            "code": reset_code,
            "new_password": "StrongPass789",
            "confirm_password": "StrongPass789",
        },
    )
    assert reset_verify_resp.status_code == 200

    relogin_resp = auth_client.post(
        "/api/auth/login",
        json={"email": "flow@example.com", "password": "StrongPass789", "device_info": {"device_id": "flow-02"}},
    )
    assert relogin_resp.status_code == 200
    new_access_token = relogin_resp.json()["data"]["access_token"]

    send_change_email_resp = auth_client.post(
        "/api/auth/change-email/send-code",
        headers={"Authorization": f"Bearer {new_access_token}"},
        json={"new_email": "flow-new@example.com", "current_password": "StrongPass789"},
    )
    assert send_change_email_resp.status_code == 200

    user_id = relogin_resp.json()["data"]["user_info"]["user_id"]
    email_code = service.cache.get(f"change_email:{user_id}")["code"]
    verify_change_email_resp = auth_client.post(
        "/api/auth/change-email/verify",
        headers={"Authorization": f"Bearer {new_access_token}"},
        json={"code": email_code},
    )
    assert verify_change_email_resp.status_code == 200

    login_new_email_resp = auth_client.post(
        "/api/auth/login",
        json={
            "email": "flow-new@example.com",
            "password": "StrongPass789",
            "device_info": {"device_id": "flow-03"},
        },
    )
    assert login_new_email_resp.status_code == 200
