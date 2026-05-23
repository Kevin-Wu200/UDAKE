"""Product key activation APIs for frontend login flow."""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..audit.audit_logger import ProductKeyAuditLogger
from ..auth import JWTValidationError, ProductKeyValidationError, get_auth_service
from ..auth.input_sanitizer import ensure_safe_text
from ..cache.validation_cache import ValidationCacheManager
from ..config import settings
from ..monitoring.alerting import ValidationAlerting
from ..monitoring.dashboard import ValidationDashboard
from ..monitoring.metrics import ValidationMetrics
from ..security.ip_reputation import IPReputationService
from ..services.product_key_validation_queue import ProductKeyValidationQueue
from ..services.websocket_service import websocket_service
from ..validation_config import load_validation_runtime_config

router = APIRouter(prefix="/product-keys")

MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 30 * 60
VALIDATE_IP_LIMIT = 10
VALIDATE_IP_WINDOW_SECONDS = 60
VALIDATE_KEY_LIMIT = 20
VALIDATE_KEY_WINDOW_SECONDS = 60 * 60
VALIDATE_USER_LIMIT = 30
VALIDATE_USER_WINDOW_SECONDS = 60 * 60
VALIDATE_FAILED_COUNT_TTL_SECONDS = 60 * 60
_VALIDATION_METRICS = ValidationMetrics()
_VALIDATION_RUNTIME_CONFIG = load_validation_runtime_config()
_VALIDATION_RUNTIME_CONFIG = _VALIDATION_RUNTIME_CONFIG.__class__(
    ip_limit_per_minute=int(getattr(settings, "PRODUCT_KEY_VALIDATE_IP_LIMIT_PER_MINUTE", _VALIDATION_RUNTIME_CONFIG.ip_limit_per_minute)),
    key_limit_per_hour=int(getattr(settings, "PRODUCT_KEY_VALIDATE_KEY_LIMIT_PER_HOUR", _VALIDATION_RUNTIME_CONFIG.key_limit_per_hour)),
    user_limit_per_hour=int(getattr(settings, "PRODUCT_KEY_VALIDATE_USER_LIMIT_PER_HOUR", _VALIDATION_RUNTIME_CONFIG.user_limit_per_hour)),
    cache_enabled=bool(getattr(settings, "PRODUCT_KEY_VALIDATE_CACHE_ENABLED", _VALIDATION_RUNTIME_CONFIG.cache_enabled)),
    cache_ttl_seconds=int(getattr(settings, "PRODUCT_KEY_VALIDATE_CACHE_TTL_SECONDS", _VALIDATION_RUNTIME_CONFIG.cache_ttl_seconds)),
    enable_ip_reputation=bool(
        getattr(
            settings,
            "PRODUCT_KEY_VALIDATE_ENABLE_IP_REPUTATION",
            _VALIDATION_RUNTIME_CONFIG.enable_ip_reputation,
        )
    ),
    enable_audit_log=bool(
        getattr(
            settings,
            "PRODUCT_KEY_VALIDATE_ENABLE_AUDIT_LOG",
            _VALIDATION_RUNTIME_CONFIG.enable_audit_log,
        )
    ),
    enable_data_masking=bool(_VALIDATION_RUNTIME_CONFIG.enable_data_masking),
)
_VALIDATION_CACHE: Optional[ValidationCacheManager] = None
_IP_REPUTATION_SERVICE: Optional[IPReputationService] = None
_VALIDATION_AUDIT_LOGGER: Optional[ProductKeyAuditLogger] = None
_VALIDATION_ALERTING: Optional[ValidationAlerting] = None
_VALIDATION_DASHBOARD: Optional[ValidationDashboard] = None
_ASYNC_VALIDATION_QUEUE: Optional[ProductKeyValidationQueue] = None


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
    error_code: str = "OK"
    suggestion: str = ""


class ValidateAsyncResponse(BaseModel):
    task_id: str
    status: str


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


def _validate_user_rate_key(user_id: str) -> str:
    return f"product_key_validate:user:{user_id}"


def _serialize_key(record: Any) -> Dict[str, Any]:
    return {
        "product_key": getattr(record, "product_key", ""),
        "key_type": getattr(record, "key_type", "personal_standard"),
        "status": getattr(record, "status", "unused"),
        "total_quota": getattr(record, "total_quota", 0),
        "used_count": getattr(record, "used_count", 0),
        "expires_at": None,
    }


def _find_product_key_record(service: Any, normalized_key: str) -> Any:
    registry = getattr(service, "product_keys", None)
    record = registry.get_record(normalized_key) if registry else None
    if record is not None:
        return record

    db_query_func = getattr(service, "_query_product_key_from_db", None)
    if callable(db_query_func):
        try:
            return db_query_func(normalized_key)
        except Exception:
            return None
    return None


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


def _error_code_and_suggestion(message: str, valid: bool) -> tuple[str, str]:
    if valid:
        return "OK", "可继续进行注册或激活"
    if "格式" in message:
        return "KEY_FORMAT_INVALID", "请输入15位密钥，格式为XXX-XXXX-XXXX-XXXX"
    if "校验" in message:
        return "KEY_CHECKSUM_MISMATCH", "请确认密钥无输入错误后重试"
    if "不存在" in message:
        return "KEY_NOT_FOUND", "请确认密钥来源是否正确"
    if "已被使用" in message:
        return "KEY_ALREADY_USED", "请使用未激活的新密钥"
    if "撤销" in message:
        return "KEY_REVOKED", "请联系管理员获取可用密钥"
    if "过期" in message:
        return "KEY_EXPIRED", "请联系管理员续期或申请新密钥"
    if "频繁" in message:
        return "RATE_LIMITED", "请稍后再试"
    return "KEY_INVALID", "请检查密钥后重试"


def _get_validation_cache(service: Any) -> ValidationCacheManager:
    global _VALIDATION_CACHE
    if _VALIDATION_CACHE is None:
        _VALIDATION_CACHE = ValidationCacheManager(
            service.cache,
            ttl_seconds=int(max(1, _VALIDATION_RUNTIME_CONFIG.cache_ttl_seconds)),
        )
    return _VALIDATION_CACHE


def _get_ip_reputation_service(service: Any) -> IPReputationService:
    global _IP_REPUTATION_SERVICE
    if _IP_REPUTATION_SERVICE is None:
        _IP_REPUTATION_SERVICE = IPReputationService(service.cache)
    return _IP_REPUTATION_SERVICE


def _get_validation_audit_logger(service: Any) -> ProductKeyAuditLogger:
    global _VALIDATION_AUDIT_LOGGER
    if _VALIDATION_AUDIT_LOGGER is None:
        _VALIDATION_AUDIT_LOGGER = ProductKeyAuditLogger(service.cache)
    return _VALIDATION_AUDIT_LOGGER


def _get_validation_dashboard(service: Any) -> ValidationDashboard:
    global _VALIDATION_ALERTING, _VALIDATION_DASHBOARD
    if _VALIDATION_ALERTING is None:
        _VALIDATION_ALERTING = ValidationAlerting(service.cache)
    if _VALIDATION_DASHBOARD is None:
        _VALIDATION_DASHBOARD = ValidationDashboard(
            _VALIDATION_METRICS,
            _get_validation_cache(service),
            _VALIDATION_ALERTING,
        )
    return _VALIDATION_DASHBOARD


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
    # 优先从 users 表的内存对象读取 product_key 和 key_status
    user = service._users_by_id.get(user_id)  # noqa: SLF001
    if user is not None and user.product_key and user.key_status == "active":
        # 构造一个兼容 ProductKeyRecord 接口的对象
        class _UserKeyInfo:
            def __init__(self):
                self.product_key = user.product_key
                self.key_type = getattr(user, "role", "personal_standard")
                self.status = user.key_status
                self.total_quota = 0
                self.used_count = 0
                self.expires_at = None
        return _UserKeyInfo()

    # 回退：从 ProductKey 注册表中查找（向后兼容旧数据）
    registry = getattr(service, "product_keys", None)
    records = getattr(registry, "_keys", {}) if registry else {}
    for record in records.values():
        if getattr(record, "user_id", None) == user_id and getattr(record, "status", None) == "active":
            return record
    return None


class _MockClient:
    def __init__(self, host: str) -> None:
        self.host = host


class _MockRequest:
    def __init__(self, *, ip_address: str, user_agent: str, user_id: str) -> None:
        self.client = _MockClient(ip_address)
        self.headers = {
            "x-forwarded-for": ip_address,
            "user-agent": user_agent,
            "x-user-id": user_id,
        }


def _build_validation_payload_response(http_error: HTTPException) -> Dict[str, Any]:
    detail = http_error.detail if isinstance(http_error.detail, dict) else {"message": str(http_error.detail)}
    return {
        "success": False,
        "status_code": int(http_error.status_code),
        "detail": detail,
    }


def _async_validation_processor(payload: Dict[str, Any]) -> Dict[str, Any]:
    product_key = str(payload.get("product_key") or "")
    ip_address = str(payload.get("ip_address") or "unknown")
    user_agent = str(payload.get("user_agent") or "async-worker")
    user_id = str(payload.get("user_id") or "anonymous")
    mock_request = _MockRequest(ip_address=ip_address, user_agent=user_agent, user_id=user_id)
    try:
        result = validate_product_key(ValidateRequest(product_key=product_key), mock_request)  # type: ignore[arg-type]
        _notify_async_validation_result(user_id=user_id, task_id=str(payload.get("task_id") or ""), result=result)
        return {"response": result}
    except HTTPException as exc:
        response = _build_validation_payload_response(exc)
        _notify_async_validation_result(user_id=user_id, task_id=str(payload.get("task_id") or ""), result=response)
        return response


def _get_async_validation_queue() -> ProductKeyValidationQueue:
    global _ASYNC_VALIDATION_QUEUE
    if _ASYNC_VALIDATION_QUEUE is None:
        _ASYNC_VALIDATION_QUEUE = ProductKeyValidationQueue(processor=_async_validation_processor)
    return _ASYNC_VALIDATION_QUEUE


def _notify_async_validation_result(*, user_id: str, task_id: str, result: Dict[str, Any]) -> None:
    loop = getattr(websocket_service, "_loop", None)
    if loop is None or not user_id or user_id == "anonymous":
        return
    message = websocket_service.build_message(
        "product_key_validation_completed",
        data={"task_id": task_id, "result": result},
        user_id=str(user_id),
    )
    try:
        asyncio.run_coroutine_threadsafe(websocket_service.send_to_user(message, user_id=str(user_id)), loop)
    except Exception:
        return


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
    started = time.perf_counter()
    service = get_auth_service()
    ip_address = _extract_client_ip(request) or "unknown"
    user_agent = request.headers.get("user-agent")
    now = int(time.time())
    user_identity = request.headers.get("x-user-id", "anonymous").strip() or "anonymous"
    validation_cache = _get_validation_cache(service)
    ip_reputation = _get_ip_reputation_service(service)

    try:
        normalized_key = ensure_safe_text(payload.product_key, max_len=128, reject_sql=True).strip().upper()
    except ValueError:
        response = ValidateResponse(valid=False, key_type=None, message="密钥输入包含非法字符")
        response.error_code, response.suggestion = _error_code_and_suggestion(response.message, response.valid)
        _record_validate_failed_count(service, ip_address=ip_address, product_key=str(payload.product_key))
        ip_reputation.record_failed(ip_address)
        _audit_validate(
            service,
            ip_address=ip_address,
            user_agent=user_agent,
            product_key=str(payload.product_key),
            valid=False,
            message=response.message,
            key_type=None,
        )
        processing_ms = int((time.perf_counter() - started) * 1000)
        _VALIDATION_METRICS.record(valid=response.valid, processing_time_ms=processing_ms)
        if _VALIDATION_RUNTIME_CONFIG.enable_audit_log:
            _get_validation_audit_logger(service).append(
                ip_address=ip_address,
                user_agent=user_agent,
                product_key=str(payload.product_key),
                valid=response.valid,
                reason=response.message,
                key_type=response.key_type,
                processing_time_ms=processing_ms,
            )
        return _ok("密钥校验完成", response.model_dump())

    if not normalized_key:
        response = ValidateResponse(valid=False, key_type=None, message="请输入产品密钥")
        response.error_code, response.suggestion = _error_code_and_suggestion(response.message, response.valid)
        _record_validate_failed_count(service, ip_address=ip_address, product_key=normalized_key)
        ip_reputation.record_failed(ip_address)
        _audit_validate(
            service,
            ip_address=ip_address,
            user_agent=user_agent,
            product_key=normalized_key,
            valid=False,
            message=response.message,
            key_type=None,
        )
        processing_ms = int((time.perf_counter() - started) * 1000)
        _VALIDATION_METRICS.record(valid=response.valid, processing_time_ms=processing_ms)
        if _VALIDATION_RUNTIME_CONFIG.enable_audit_log:
            _get_validation_audit_logger(service).append(
                ip_address=ip_address,
                user_agent=user_agent,
                product_key=normalized_key,
                valid=response.valid,
                reason=response.message,
                key_type=response.key_type,
                processing_time_ms=processing_ms,
            )
        return _ok("密钥校验完成", response.model_dump())

    if _VALIDATION_RUNTIME_CONFIG.enable_ip_reputation:
        decision = ip_reputation.check(ip_address)
        if not decision.allowed:
            ip_reputation.record_rate_limited(ip_address)
            raise _fail(status.HTTP_429_TOO_MANY_REQUESTS, "请求过于频繁，请稍后重试")

    try:
        _enforce_sliding_window_limit(
            service,
            cache_key=_validate_ip_rate_key(ip_address),
            window_seconds=VALIDATE_IP_WINDOW_SECONDS,
            max_attempts=int(max(1, _VALIDATION_RUNTIME_CONFIG.ip_limit_per_minute or VALIDATE_IP_LIMIT)),
            now=now,
            exceed_message="请求过于频繁",
        )
        _enforce_sliding_window_limit(
            service,
            cache_key=_validate_target_rate_key(normalized_key),
            window_seconds=VALIDATE_KEY_WINDOW_SECONDS,
            max_attempts=int(max(1, _VALIDATION_RUNTIME_CONFIG.key_limit_per_hour or VALIDATE_KEY_LIMIT)),
            now=now,
            exceed_message="该密钥验证次数过多",
        )
        _enforce_sliding_window_limit(
            service,
            cache_key=_validate_user_rate_key(user_identity),
            window_seconds=VALIDATE_USER_WINDOW_SECONDS,
            max_attempts=int(max(1, _VALIDATION_RUNTIME_CONFIG.user_limit_per_hour or VALIDATE_USER_LIMIT)),
            now=now,
            exceed_message="当前用户验证次数过多",
        )
    except HTTPException:
        ip_reputation.record_rate_limited(ip_address)
        raise

    if _VALIDATION_RUNTIME_CONFIG.cache_enabled:
        cached = validation_cache.get(normalized_key)
        if isinstance(cached, dict):
            cached_response = ValidateResponse(
                valid=bool(cached.get("valid", False)),
                key_type=cached.get("key_type"),
                message=str(cached.get("message", "密钥验证完成")),
            )
            cached_response.error_code, cached_response.suggestion = _error_code_and_suggestion(
                cached_response.message,
                cached_response.valid,
            )
            processing_ms = int((time.perf_counter() - started) * 1000)
            _VALIDATION_METRICS.record(valid=cached_response.valid, processing_time_ms=processing_ms)
            return _ok("密钥校验完成", cached_response.model_dump())

    registry = service.product_keys
    response = ValidateResponse(valid=False, key_type=None, message="密钥无效")
    try:
        registry.validate_key_format(normalized_key)
        registry.validate_checksum(normalized_key)
        record = _find_product_key_record(service, normalized_key)
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
        processing_ms = int((time.perf_counter() - started) * 1000)
        _VALIDATION_METRICS.record(valid=False, processing_time_ms=processing_ms, is_error=True)
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
        ip_reputation.record_failed(ip_address)
    else:
        ip_reputation.record_success(ip_address)

    response.error_code, response.suggestion = _error_code_and_suggestion(response.message, response.valid)
    if _VALIDATION_RUNTIME_CONFIG.cache_enabled:
        validation_cache.set(normalized_key, response.model_dump())

    _audit_validate(
        service,
        ip_address=ip_address,
        user_agent=user_agent,
        product_key=normalized_key,
        valid=response.valid,
        message=response.message,
        key_type=response.key_type,
    )
    processing_ms = int((time.perf_counter() - started) * 1000)
    _VALIDATION_METRICS.record(valid=response.valid, processing_time_ms=processing_ms)
    if _VALIDATION_RUNTIME_CONFIG.enable_audit_log:
        _get_validation_audit_logger(service).append(
            ip_address=ip_address,
            user_agent=user_agent,
            product_key=normalized_key,
            valid=response.valid,
            reason=response.message,
            key_type=response.key_type,
            processing_time_ms=processing_ms,
        )
    _get_validation_dashboard(service).snapshot()
    return _ok("密钥校验完成", response.model_dump())


@router.get("/validate/metrics")
def validation_metrics_dashboard():
    service = get_auth_service()
    payload = _get_validation_dashboard(service).snapshot()
    return _ok("密钥验证监控指标获取成功", payload)


@router.post("/validate/async")
def validate_product_key_async(payload: ValidateRequest, request: Request):
    queue = _get_async_validation_queue()
    task_id = queue.submit(
        {
            "product_key": str(payload.product_key),
            "ip_address": _extract_client_ip(request) or "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "user_id": request.headers.get("x-user-id", "anonymous"),
        }
    )
    response = ValidateAsyncResponse(task_id=task_id, status="queued")
    return _ok(
        "异步密钥校验任务已提交",
        {
            **response.model_dump(),
            "poll_url": f"/api/product-keys/validate/async/{task_id}",
        },
    )


@router.get("/validate/async/{task_id}")
def get_async_validate_result(task_id: str):
    queue = _get_async_validation_queue()
    row = queue.get(task_id)
    if row is None:
        raise _fail(status.HTTP_404_NOT_FOUND, "任务不存在或已过期")
    return _ok("异步密钥校验任务状态获取成功", row)


@router.get("/validate/async-metrics")
def get_async_validate_metrics():
    queue = _get_async_validation_queue()
    return _ok("异步密钥校验队列指标获取成功", queue.metrics())


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
    _get_validation_cache(service).invalidate(normalized_key)
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

        # 同步更新内存中 users 表对应的 AuthUser 对象
        with service._lock:  # noqa: SLF001
            user = service._users_by_id.get(token_user_id)  # noqa: SLF001
            if user is not None:
                user.product_key = normalized_key
                user.key_status = "active"

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
