"""统一 API 响应格式中间件（v2）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_success_response(*, data: Any, request: Request, status_code: int) -> dict[str, Any]:
    request_id = str(getattr(request.state, "request_id", "")) or uuid.uuid4().hex
    api_version = str(getattr(request.state, "api_version", "unknown"))
    return {
        "success": True,
        "code": "OK",
        "message": "请求成功",
        "data": data,
        "meta": {
            "timestamp": _utc_now_iso(),
            "request_id": request_id,
            "api_version": api_version,
            "status_code": status_code,
            "path": request.url.path,
        },
    }


def build_error_response(
    *,
    code: str,
    message: str,
    detail: Any,
    request: Request,
    status_code: int,
) -> dict[str, Any]:
    request_id = str(getattr(request.state, "request_id", "")) or uuid.uuid4().hex
    api_version = str(getattr(request.state, "api_version", "unknown"))
    return {
        "success": False,
        "code": code,
        "message": message,
        "error": detail,
        "meta": {
            "timestamp": _utc_now_iso(),
            "request_id": request_id,
            "api_version": api_version,
            "status_code": status_code,
            "path": request.url.path,
        },
    }


def _is_already_wrapped(payload: Any) -> bool:
    return isinstance(payload, dict) and {"success", "code", "meta"}.issubset(payload.keys())


def _guess_error_code(status_code: int, detail: Any) -> str:
    if status_code == 400:
        return "BAD_REQUEST"
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code == 422:
        return "VALIDATION_ERROR"
    if status_code == 429:
        return "RATE_LIMITED"
    if isinstance(detail, dict):
        code = detail.get("error")
        if isinstance(code, str) and code.strip():
            return code.strip().upper()
    return "INTERNAL_ERROR" if status_code >= 500 else "REQUEST_ERROR"


async def unified_api_response_middleware(request: Request, call_next):
    if not getattr(request.state, "request_id", None):
        request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex

    response = await call_next(request)
    path = request.url.path
    api_version = str(getattr(request.state, "api_version", ""))

    if not path.startswith("/api") or api_version != "2.0":
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    content_type = (response.headers.get("content-type") or "").lower()
    if "application/json" not in content_type:
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    body_chunks = [chunk async for chunk in response.body_iterator]
    body = b"".join(body_chunks)
    if not body:
        wrapped = build_success_response(data=None, request=request, status_code=response.status_code)
        wrapped_response = JSONResponse(status_code=response.status_code, content=wrapped)
        wrapped_response.headers["X-Request-ID"] = str(request.state.request_id)
        return wrapped_response

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    if _is_already_wrapped(payload):
        wrapped_response = JSONResponse(status_code=response.status_code, content=payload)
        wrapped_response.headers["X-Request-ID"] = str(request.state.request_id)
        return wrapped_response

    if response.status_code < 400:
        wrapped = build_success_response(data=payload, request=request, status_code=response.status_code)
    else:
        detail = payload
        if isinstance(payload, dict) and "detail" in payload:
            detail = payload.get("detail")
        message = "请求失败"
        if isinstance(detail, str) and detail.strip():
            message = detail.strip()
        elif isinstance(payload, dict):
            maybe_msg = payload.get("message")
            if isinstance(maybe_msg, str) and maybe_msg.strip():
                message = maybe_msg.strip()
        wrapped = build_error_response(
            code=_guess_error_code(response.status_code, detail),
            message=message,
            detail=detail,
            request=request,
            status_code=response.status_code,
        )

    wrapped_response = JSONResponse(status_code=response.status_code, content=wrapped)
    wrapped_response.headers["X-Request-ID"] = str(request.state.request_id)
    return wrapped_response

