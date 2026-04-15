"""Product key activation APIs for frontend login flow."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..auth import JWTValidationError, ProductKeyValidationError, get_auth_service
from ..auth.input_sanitizer import ensure_safe_text

router = APIRouter(prefix="/product-keys")

MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 30 * 60
VALIDATE_IP_LIMIT = 10
VALIDATE_IP_WINDOW_SECONDS = 60
VALIDATE_KEY_LIMIT = 20
VALIDATE_KEY_WINDOW_SECONDS = 60 * 60
VALIDATE_FAILED_COUNT_TTL_SECONDS = 60 * 60


def _ok(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"success": True, "message": message, "data": data or {}}


def _fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"success": False, "message": message, "data": {}})


class ActivateRequest(BaseModel):
    product_key: str = Field(..., min_length=15, max_length=128)
    user_id: Optional[int] = Field(default=None)


class ValidateRequest(BaseModel):
    product_key: str = Field(..., min_length=1, max_length=128)


class ValidateResponse(BaseModel):
    valid: bool
    key_type: Optional[str] = None
    message: str


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")
    return token


def _extract_client_ip(request: Request) -> Optional[str]:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        first_ip = x_forwarded_for.split(",", 1)[0].strip()
        if first_ip:
            return first_ip
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()
    return request.client.host if request.client else None


def _attempts_key(user_id: int) -> str:
    return f"product_key_activation_attempts:{user_id}"


def _lock_key(user_id: int) -> str:
    return f"product_key_activation_locked_until:{user_id}"


def _validate_ip_rate_key(ip_address: str) -> str:
    return f"product_key_validate:ip:{ip_address}"


def _validate_target_rate_key(product_key: str) -> str:
    digest = hashlib.sha256(product_key.encode("utf-8")).hexdigest()
    return f"product_key_validate:key:{digest}"


def _validate_failed_ip_key(ip_address: str) -> str:
    return f"product_key_validate:fail:ip:{ip_address}"


def _validate_failed_target_key(product_key: str) -> str:
    digest = hashlib.sha256(product_key.encode("utf-8")).hexdigest()
    return f"product_key_validate:fail:key:{digest}"


def _serialize_key(record: Any) -> Dict[str, Any]:
    return {
        "product_key": getattr(record, "product_key", ""),
        "key_type": getattr(record, "key_type", "personal_standard"),
        "status": getattr(record, "status", "unused"),
        "total_quota": getattr(record, "total_quota", 0),
        "used_count": getattr(record, "used_count", 0),
        "expires_at": None,
    }


def _enforce_sliding_window_limit(
    service: Any,
    *,
    cache_key: str,
    window_seconds: int,
    max_attempts: int,
    now: int,
    exceed_message: str,
) -> None:
    rows = service.cache.get(cache_key)
    logs = [int(item) for item in rows] if isinstance(rows, list) else []
    logs = [item for item in logs if now - item < window_seconds]
    if len(logs) >= max_attempts:
        retry_after = max(1, window_seconds - (now - logs[0]))
        service.cache.set(cache_key, logs, ttl=window_seconds)
        raise _fail(status.HTTP_429_TOO_MANY_REQUESTS, f"{exceed_message}，请在 {retry_after} 秒后重试")
    logs.append(now)
    service.cache.set(cache_key, logs, ttl=window_seconds)


def _record_validate_failed_count(service: Any, *, ip_address: str, product_key: str) -> None:
    failed_ip_key = _validate_failed_ip_key(ip_address)
    failed_target_key = _validate_failed_target_key(product_key)

    ip_failed_count = int(service.cache.get(failed_ip_key) or 0) + 1
    key_failed_count = int(service.cache.get(failed_target_key) or 0) + 1
    service.cache.set(failed_ip_key, ip_failed_count, ttl=VALIDATE_FAILED_COUNT_TTL_SECONDS)
    service.cache.set(failed_target_key, key_failed_count, ttl=VALIDATE_FAILED_COUNT_TTL_SECONDS)


def _mask_product_key(product_key: str) -> str:
    text = product_key.strip().upper()
    if len(text) < 8:
        return "***"
    return f"{text[:3]}****{text[-4:]}"


def _audit_validate(
    service: Any,
    *,
    ip_address: str,
    user_agent: Optional[str],
    product_key: str,
    valid: bool,
    message: str,
    key_type: Optional[str],
) -> None:
    details = {
        "result": "success" if valid else "failed",
        "reason": "" if valid else message,
        "target_type": "product_key",
        "target_id": _mask_product_key(product_key),
        "key_type": key_type,
        "message": message,
    }
    audit_fn = getattr(service, "_audit", None)
    if callable(audit_fn):
        audit_fn(
            operation="product_key_validate",
            user_id=None,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return

    logs = getattr(service, "audit_logs", None)
    if isinstance(logs, list):
        logs.append(
            {
                "operation": "product_key_validate",
                "details": details,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "timestamp": int(time.time()),
            }
        )


def _friendly_validate_error_message(exc: ProductKeyValidationError) -> str:
    text = str(exc).lower()
    if "format" in text:
        return "密钥格式无效"
    if "checksum" in text or "hash tail" in text:
        return "密钥校验失败"
    if "length" in text:
        return "密钥长度无效"
    return "密钥无效"


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


@router.post("/validate")
def validate_product_key(payload: ValidateRequest, request: Request):
    service = get_auth_service()
    ip_address = _extract_client_ip(request) or "unknown"
    user_agent = request.headers.get("user-agent")
    now = int(time.time())

    try:
        normalized_key = ensure_safe_text(payload.product_key, max_len=128, reject_sql=True).strip().upper()
    except ValueError:
        response = ValidateResponse(valid=False, key_type=None, message="密钥输入包含非法字符")
        _record_validate_failed_count(service, ip_address=ip_address, product_key=str(payload.product_key))
        _audit_validate(
            service,
            ip_address=ip_address,
            user_agent=user_agent,
            product_key=str(payload.product_key),
            valid=False,
            message=response.message,
            key_type=None,
        )
        return _ok("密钥校验完成", response.model_dump())

    if not normalized_key:
        response = ValidateResponse(valid=False, key_type=None, message="请输入产品密钥")
        _record_validate_failed_count(service, ip_address=ip_address, product_key=normalized_key)
        _audit_validate(
            service,
            ip_address=ip_address,
            user_agent=user_agent,
            product_key=normalized_key,
            valid=False,
            message=response.message,
            key_type=None,
        )
        return _ok("密钥校验完成", response.model_dump())

    _enforce_sliding_window_limit(
        service,
        cache_key=_validate_ip_rate_key(ip_address),
        window_seconds=VALIDATE_IP_WINDOW_SECONDS,
        max_attempts=VALIDATE_IP_LIMIT,
        now=now,
        exceed_message="请求过于频繁",
    )
    _enforce_sliding_window_limit(
        service,
        cache_key=_validate_target_rate_key(normalized_key),
        window_seconds=VALIDATE_KEY_WINDOW_SECONDS,
        max_attempts=VALIDATE_KEY_LIMIT,
        now=now,
        exceed_message="该密钥验证次数过多",
    )

    registry = service.product_keys
    response = ValidateResponse(valid=False, key_type=None, message="密钥无效")
    try:
        registry.validate_key_format(normalized_key)
        registry.validate_checksum(normalized_key)
        record = registry.get_record(normalized_key)
        if not record:
            response = ValidateResponse(valid=False, key_type=None, message="密钥不存在")
        else:
            record_status = str(getattr(record, "status", "")).lower().strip()
            record_type = getattr(record, "key_type", None)
            if record_status == "unused":
                response = ValidateResponse(valid=True, key_type=record_type, message="密钥有效，可用于注册")
            elif record_status == "active":
                response = ValidateResponse(valid=False, key_type=record_type, message="密钥已被使用")
            elif record_status == "revoked":
                response = ValidateResponse(valid=False, key_type=record_type, message="密钥已被撤销")
            elif record_status == "expired":
                response = ValidateResponse(valid=False, key_type=record_type, message="密钥已过期")
            else:
                response = ValidateResponse(valid=False, key_type=record_type, message="密钥状态异常，无法使用")
    except ProductKeyValidationError as exc:
        response = ValidateResponse(valid=False, key_type=None, message=_friendly_validate_error_message(exc))
    except HTTPException:
        raise
    except Exception:
        _audit_validate(
            service,
            ip_address=ip_address,
            user_agent=user_agent,
            product_key=normalized_key,
            valid=False,
            message="密钥验证服务异常",
            key_type=None,
        )
        raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, "密钥验证服务异常，请稍后重试")

    if not response.valid:
        _record_validate_failed_count(service, ip_address=ip_address, product_key=normalized_key)

    _audit_validate(
        service,
        ip_address=ip_address,
        user_agent=user_agent,
        product_key=normalized_key,
        valid=response.valid,
        message=response.message,
        key_type=response.key_type,
    )
    return _ok("密钥校验完成", response.model_dump())


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
