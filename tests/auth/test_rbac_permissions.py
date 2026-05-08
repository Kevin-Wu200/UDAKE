from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.backend.app.auth.dependencies import RoleChecker, ensure_same_company_scope, get_current_user_context


class _FakeJWT:
    def __init__(self, payload):
        self.payload = payload

    def verify_token(self, token, expected_type="access", check_blacklist=True):
        assert token == "valid-token"
        return self.payload


class _FakeAuthService:
    def __init__(self, payload):
        self.jwt = _FakeJWT(payload)


class _FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *_args, **_kwargs):
        return self

    def one_or_none(self):
        return self.user


class _FakeDB:
    def __init__(self, user):
        self._user = user

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self._user)


class _FakeRequest:
    def __init__(self, token="valid-token"):
        self.headers = {"authorization": f"Bearer {token}"}


@pytest.fixture
def patch_auth(monkeypatch):
    def _apply(payload):
        monkeypatch.setattr(
            "services.backend.app.auth.dependencies.get_auth_service",
            lambda: _FakeAuthService(payload),
        )

    return _apply


def test_get_current_user_context_success(patch_auth):
    patch_auth({"user_id": 1, "role": "company_admin"})
    user = SimpleNamespace(id=1, role="company_admin", company_id=11, status="active")

    ctx = get_current_user_context(_FakeRequest(), _FakeDB(user))

    assert ctx.user_id == 1
    assert ctx.role == "company_admin"
    assert ctx.company_id == 11


def test_role_checker_blocks_overreach(patch_auth):
    patch_auth({"user_id": 1, "role": "user"})
    user = SimpleNamespace(id=1, role="user", company_id=None, status="active")

    checker = RoleChecker(["admin", "super_admin"])
    with pytest.raises(HTTPException) as exc:
        checker(_FakeRequest(), _FakeDB(user))

    assert exc.value.status_code == 403


def test_role_checker_company_scope_required(patch_auth):
    patch_auth({"user_id": 2, "role": "company_admin"})
    user = SimpleNamespace(id=2, role="company_admin", company_id=None, status="active")

    checker = RoleChecker(["company_admin"], require_company_scope=True)
    with pytest.raises(HTTPException) as exc:
        checker(_FakeRequest(), _FakeDB(user))

    assert exc.value.status_code == 403


def test_company_scope_isolation_violation():
    current = SimpleNamespace(role="company_admin", company_id=101)

    with pytest.raises(HTTPException) as exc:
        ensure_same_company_scope(current, 202)

    assert exc.value.status_code == 403


def test_company_scope_isolation_pass():
    current = SimpleNamespace(role="company_admin", company_id=101)
    ensure_same_company_scope(current, 101)
