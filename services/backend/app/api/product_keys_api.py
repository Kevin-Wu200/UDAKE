"""Product key activation APIs for frontend login flow."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..auth import JWTValidationError, ProductKeyValidationError, get_auth_service
from ..auth.input_sanitizer import ensure_safe_text

router = APIRouter(prefix="/product-keys")

MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 30 * 60


def _ok(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"success": True, "message": message, "data": data or {}}


def _fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"success": False, "message": message, "data": {}})


class ActivateRequest(BaseModel):
    product_key: str = Field(..., min_length=15, max_length=128)
    user_id: Optional[int] = Field(default=None)


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")
    return token


def _attempts_key(user_id: int) -> str:
    return f"product_key_activation_attempts:{user_id}"


def _lock_key(user_id: int) -> str:
    return f"product_key_activation_locked_until:{user_id}"


def _serialize_key(record: Any) -> Dict[str, Any]:
    return {
        "product_key": getattr(record, "product_key", ""),
        "key_type": getattr(record, "key_type", "personal_standard"),
        "status": getattr(record, "status", "unused"),
        "total_quota": getattr(record, "total_quota", 0),
        "used_count": getattr(record, "used_count", 0),
        "expires_at": None,
    }


def _get_active_key_for_user(service: Any, user_id: int) -> Optional[Any]:
    registry = getattr(service, "product_keys", None)
    records = getattr(registry, "_keys", {}) if registry else {}
    for record in records.values():
        if getattr(record, "user_id", None) == user_id and getattr(record, "status", None) == "active":
            return record
    return None


def _increase_failed_attempts(service: Any, user_id: int) -> Dict[str, int]:
    cache = service.cache
    now = int(time.time())
    attempts = int(cache.get(_attempts_key(user_id)) or 0) + 1
    cache.set(_attempts_key(user_id), attempts, ttl=LOCK_SECONDS)
    if attempts >= MAX_FAILED_ATTEMPTS:
        locked_until = now + LOCK_SECONDS
        cache.set(_lock_key(user_id), locked_until, ttl=LOCK_SECONDS)
        cache.set(_attempts_key(user_id), 0, ttl=LOCK_SECONDS)
        return {"attempts": MAX_FAILED_ATTEMPTS, "locked_until": locked_until}
    return {"attempts": attempts, "locked_until": 0}


def _clear_failed_attempts(service: Any, user_id: int) -> None:
    service.cache.delete(_attempts_key(user_id))
    service.cache.delete(_lock_key(user_id))


@router.post("/activate")
def activate_product_key(payload: ActivateRequest, request: Request):
    service = get_auth_service()
    token = _extract_bearer_token(request)

    try:
        jwt_payload = service.jwt.verify_token(token, expected_type="access", check_blacklist=True)
        token_user_id = int(jwt_payload["user_id"])
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    if payload.user_id is not None and int(payload.user_id) != token_user_id:
        raise _fail(status.HTTP_403_FORBIDDEN, "user_id 与当前登录用户不匹配")

    now = int(time.time())
    lock_until = int(service.cache.get(_lock_key(token_user_id)) or 0)
    if lock_until > now:
        remain = max(1, lock_until - now)
        raise _fail(status.HTTP_423_LOCKED, f"激活尝试次数过多，请在 {remain} 秒后重试")

    normalized_key = ensure_safe_text(payload.product_key, max_len=128, reject_sql=True).strip().upper()
    registry = service.product_keys
    record = registry.get_record(normalized_key)

    try:
        if record and getattr(record, "status", "") == "active" and getattr(record, "user_id", None) == token_user_id:
            _clear_failed_attempts(service, token_user_id)
            return _ok("密钥已激活", _serialize_key(record))

        if record and getattr(record, "status", "") != "unused":
            raise ProductKeyValidationError(f"product key status invalid: {getattr(record, 'status', 'unknown')}")

        checked = registry.validate_key(normalized_key, require_unused=True)
        checked.status = "active"
        checked.user_id = token_user_id
        _clear_failed_attempts(service, token_user_id)
        return _ok("密钥激活成功", _serialize_key(checked))
    except ProductKeyValidationError as exc:
        lock_info = _increase_failed_attempts(service, token_user_id)
        attempts = lock_info["attempts"]
        locked_until = lock_info["locked_until"]
        if locked_until > now:
            remain = max(1, locked_until - now)
            raise _fail(status.HTTP_423_LOCKED, f"激活失败次数达到上限，请在 {remain} 秒后重试") from exc
        remain_attempts = max(0, MAX_FAILED_ATTEMPTS - attempts)
        raise _fail(status.HTTP_400_BAD_REQUEST, f"密钥激活失败，剩余尝试次数 {remain_attempts}") from exc


@router.get("/status")
def get_product_key_status(request: Request):
    service = get_auth_service()
    token = _extract_bearer_token(request)

    try:
        jwt_payload = service.jwt.verify_token(token, expected_type="access", check_blacklist=True)
        user_id = int(jwt_payload["user_id"])
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    now = int(time.time())
    lock_until = int(service.cache.get(_lock_key(user_id)) or 0)
    active = _get_active_key_for_user(service, user_id)
    attempts = int(service.cache.get(_attempts_key(user_id)) or 0)

    return _ok(
        "密钥状态获取成功",
        {
            "key_info": _serialize_key(active) if active else None,
            "attempts": attempts,
            "remaining_attempts": max(0, MAX_FAILED_ATTEMPTS - attempts),
            "locked_until": lock_until if lock_until > now else None,
            "lock_remaining_seconds": max(0, lock_until - now),
        },
    )
