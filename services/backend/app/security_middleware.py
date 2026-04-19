"""HTTP-level security middleware (IP policy, CSRF, XSS guard, headers)."""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from .auth import get_auth_service
from .auth.csrf import CSRFManager, CSRFValidationError
from .auth.input_sanitizer import sanitize_payload
from .config import settings
from .services.数据安全服务 import get_data_security_service

logger = logging.getLogger(__name__)
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


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


async def security_guard_middleware(request: Request, call_next):
    service = get_auth_service()
    security_service = get_data_security_service()
    ip_address = _extract_client_ip(request)
    transport_scheme = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").split(",", 1)[0].strip()
    transport_host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").strip()
    transport_tls = request.headers.get("x-tls-version")
    transport_result = security_service.validate_transport_security(
        scheme=transport_scheme,
        host=transport_host,
        tls_version=transport_tls,
    )
    if settings.is_production and not transport_result.get("compliant", False):
        logger.warning(
            "blocked request due to insecure transport path=%s scheme=%s tls=%s",
            request.url.path,
            transport_scheme,
            transport_tls,
        )
        return JSONResponse(
            status_code=426,
            content={
                "success": False,
                "message": "传输安全要求不满足：生产环境仅允许 TLS1.3 HTTPS 请求",
                "data": transport_result,
            },
        )

    ip_check = service.ip_controller.check(ip_address)
    if not ip_check.allowed:
        logger.warning("blocked request from blacklisted ip=%s path=%s", ip_address, request.url.path)
        return JSONResponse(
            status_code=403,
            content={"success": False, "message": "当前IP已被封禁，请稍后再试", "data": {}},
        )

    if request.method.upper() in _MUTATING_METHODS:
        # Basic XSS guard: sanitize JSON body before entering route handlers.
        content_type = (request.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            body = await request.body()
            if body:
                rewritten_body = body
                try:
                    payload = json.loads(body)
                except Exception:
                    payload = None
                if payload is not None:
                    sanitized = sanitize_payload(payload, max_len=settings.AUTH_XSS_MAX_INPUT_LEN)
                    if sanitized != payload:
                        rewritten_body = json.dumps(sanitized, ensure_ascii=False).encode("utf-8")

                async def _receive() -> dict:
                    return {"type": "http.request", "body": rewritten_body, "more_body": False}

                request._body = rewritten_body  # type: ignore[attr-defined]
                request._receive = _receive  # type: ignore[attr-defined]

        # CSRF double-submit validation.
        if settings.AUTH_CSRF_ENABLED and request.url.path.startswith("/api") and not (settings.is_development or settings.is_testing):
            csrf_manager = CSRFManager(
                service.cache,
                cookie_name=settings.AUTH_CSRF_COOKIE_NAME,
                header_name=settings.AUTH_CSRF_HEADER_NAME,
            )
            cookie_token = request.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
            header_token = request.headers.get(settings.AUTH_CSRF_HEADER_NAME)
            authorization = request.headers.get("authorization", "")
            require_csrf = settings.AUTH_CSRF_PROTECT_ALL or bool(cookie_token)
            if authorization.lower().startswith("bearer ") and not settings.AUTH_CSRF_PROTECT_ALL and not cookie_token:
                require_csrf = False
            if require_csrf:
                try:
                    csrf_manager.verify_token(
                        subject=csrf_manager.build_subject(request),
                        cookie_token=cookie_token,
                        header_token=header_token,
                    )
                except CSRFValidationError as exc:
                    return JSONResponse(
                        status_code=403,
                        content={"success": False, "message": str(exc), "data": {}},
                    )

    response = await call_next(request)
    if settings.AUTH_SECURITY_HEADERS_ENABLED:
        response.headers["Content-Security-Policy"] = settings.AUTH_CSP_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
