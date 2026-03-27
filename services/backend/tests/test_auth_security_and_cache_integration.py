"""Security and cache integration tests for auth workflows."""

from __future__ import annotations

import sys
import time
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth_api import router as auth_router
from app.api.devices_api import router as devices_router
from app.auth import CacheUnavailableError, get_auth_service, reset_auth_service
from app.auth.cache import AuthCacheManager
from app.auth.rate_limiter import RateRule
from app.config import settings
from app.security_middleware import security_guard_middleware


@pytest.fixture()
def auth_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", "security-suite-secret")
    reset_auth_service()
    app = FastAPI()
    app.middleware("http")(security_guard_middleware)
    app.include_router(auth_router, prefix="/api")
    app.include_router(devices_router, prefix="/api")
    with TestClient(app) as client:
        yield client
    reset_auth_service()


def _register_user(client: TestClient, email: str, password: str = "StrongPass123") -> None:
    service = get_auth_service()
    product_key = service.product_keys.generate_key(f"seed-{email}").product_key
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "product_key": product_key},
    )
    assert response.status_code == 200


def test_login_rejects_sql_injection_payload(auth_client: TestClient):
    _register_user(auth_client, "sql-guard@example.com")

    response = auth_client.post(
        "/api/auth/login",
        json={
            "email": "' OR 1=1 --@example.com",
            "password": "StrongPass123",
            "device_info": {"device_id": "sql-attack-device"},
        },
    )

    assert response.status_code == 401
    assert "非法字符" in response.text


def test_register_rejects_sql_injection_product_key(auth_client: TestClient):
    response = auth_client.post(
        "/api/auth/register",
        json={
            "email": "inject-register@example.com",
            "password": "StrongPass123",
            "product_key": "ABC-1234-5678-9XYZ; DROP TABLE users --",
        },
    )

    assert response.status_code == 400
    assert "非法字符" in response.text


def test_login_payload_xss_is_sanitized_and_not_reflected(auth_client: TestClient):
    _register_user(auth_client, "xss-guard@example.com")

    response = auth_client.post(
        "/api/auth/login",
        json={
            "email": "<script>alert(1)</script>xss-guard@example.com",
            "password": "WrongPass123",
            "device_info": {"device_id": "xss-device"},
        },
    )

    assert response.status_code == 401
    assert "<script>" not in response.text


def test_csrf_protects_delete_device_when_cookie_present(auth_client: TestClient):
    _register_user(auth_client, "csrf-delete@example.com")

    first_login = auth_client.post(
        "/api/auth/login",
        json={
            "email": "csrf-delete@example.com",
            "password": "StrongPass123",
            "device_info": {"device_id": "csrf-device-a"},
        },
    )
    assert first_login.status_code == 200

    second_login = auth_client.post(
        "/api/auth/login",
        json={
            "email": "csrf-delete@example.com",
            "password": "StrongPass123",
            "device_info": {"device_id": "csrf-device-b"},
        },
    )
    assert second_login.status_code == 200
    access_token = second_login.json()["data"]["access_token"]

    csrf_resp = auth_client.get("/api/auth/csrf-token")
    assert csrf_resp.status_code == 200
    csrf_token = csrf_resp.json()["data"]["csrf_token"]
    cookie_name = settings.AUTH_CSRF_COOKIE_NAME

    blocked = auth_client.delete(
        "/api/devices/csrf-device-a",
        headers={"Authorization": f"Bearer {access_token}"},
        cookies={cookie_name: csrf_token},
    )
    assert blocked.status_code == 403


def test_bruteforce_attempts_lock_account(auth_client: TestClient):
    _register_user(auth_client, "lock-api@example.com")
    service = get_auth_service()
    service.rate_limiter.rules["login"] = RateRule(hourly=20, daily=100)
    service.rate_limiter.rules["login_email"] = RateRule(hourly=20, daily=100)

    for _ in range(5):
        failed = auth_client.post(
            "/api/auth/login",
            json={
                "email": "lock-api@example.com",
                "password": "WrongPass123",
                "device_info": {"device_id": "lock-api-device"},
            },
        )
        assert failed.status_code == 401

    blocked = auth_client.post(
        "/api/auth/login",
        json={
            "email": "lock-api@example.com",
            "password": "StrongPass123",
            "device_info": {"device_id": "lock-api-device-2"},
        },
    )

    assert blocked.status_code == 401
    assert "账号已锁定" in blocked.text


def test_cache_manager_uses_fake_redis_pool(monkeypatch: pytest.MonkeyPatch):
    pool_calls = {}

    class FakeConnectionPool:
        @classmethod
        def from_url(cls, url: str, **kwargs):
            pool_calls["url"] = url
            pool_calls["kwargs"] = kwargs
            return {"url": url, **kwargs}

    class FakeRedis:
        def __init__(self, connection_pool):
            self.connection_pool = connection_pool
            self._store = {}
            self._exp = {}

        def ping(self):
            return True

        def set(self, key, value, ex=None):
            self._store[key] = value
            if ex is not None:
                self._exp[key] = time.time() + ex
            else:
                self._exp.pop(key, None)
            return True

        def get(self, key):
            expires_at = self._exp.get(key)
            if expires_at is not None and expires_at <= time.time():
                self._store.pop(key, None)
                self._exp.pop(key, None)
                return None
            return self._store.get(key)

        def exists(self, key):
            return 1 if self.get(key) is not None else 0

        def delete(self, key):
            existed = key in self._store
            self._store.pop(key, None)
            self._exp.pop(key, None)
            return 1 if existed else 0

        def ttl(self, key):
            if key not in self._store:
                return -2
            expires_at = self._exp.get(key)
            if expires_at is None:
                return -1
            return max(0, int(expires_at - time.time()))

    fake_redis_module = types.SimpleNamespace(ConnectionPool=FakeConnectionPool, Redis=FakeRedis)
    monkeypatch.setitem(sys.modules, "redis", fake_redis_module)

    cache = AuthCacheManager(redis_url="redis://localhost:6379/0", pool_size=6)
    assert cache.is_memory_backend is False
    assert cache.ping() is True

    assert cache.set("hello", {"value": 1}, ttl=2)
    assert cache.get("hello") == {"value": 1}
    assert cache.ttl("hello") >= 0

    assert pool_calls["url"] == "redis://localhost:6379/0"
    assert pool_calls["kwargs"]["max_connections"] == 6
    assert pool_calls["kwargs"]["decode_responses"] is True


def test_cache_manager_strict_mode_raises_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch):
    class BrokenConnectionPool:
        @classmethod
        def from_url(cls, url: str, **kwargs):
            return object()

    class BrokenRedis:
        def __init__(self, connection_pool):
            self.connection_pool = connection_pool

        def ping(self):
            raise RuntimeError("redis down")

    broken_module = types.SimpleNamespace(ConnectionPool=BrokenConnectionPool, Redis=BrokenRedis)
    monkeypatch.setitem(sys.modules, "redis", broken_module)

    with pytest.raises(CacheUnavailableError):
        AuthCacheManager(redis_url="redis://localhost:6379/1", strict_redis=True)
