"""Device management APIs for auth module."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

from ..auth import JWTValidationError, get_auth_service

router = APIRouter(prefix="/devices")


def _ok(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"success": True, "message": message, "data": data or {}}


def _fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"success": False, "message": message, "data": {}})


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


def _extract_current_fingerprint(request: Request) -> Optional[str]:
    fingerprint = request.headers.get("x-device-fingerprint")
    if fingerprint:
        return fingerprint.strip() or None
    service = get_auth_service()
    screen_resolution = request.headers.get("x-screen-resolution")
    timezone = request.headers.get("x-timezone")
    language = request.headers.get("x-language")
    canvas_fingerprint = request.headers.get("x-canvas-fingerprint")
    info = {
        "screen_resolution": screen_resolution,
        "timezone": timezone,
        "language": language,
        "canvas_fingerprint": canvas_fingerprint,
    }
    generated = service.generate_device_fingerprint(device_info=info, user_agent=request.headers.get("user-agent"))
    return generated or None


@router.get("")
def list_devices(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    service = get_auth_service()
    token = _extract_bearer_token(request)
    try:
        data = service.list_user_devices(
            access_token=token,
            page=page,
            page_size=page_size,
            current_fingerprint=_extract_current_fingerprint(request),
        )
        return _ok("设备列表获取成功", data)
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@router.delete("/{device_id}")
def kick_device(device_id: str, request: Request):
    service = get_auth_service()
    token = _extract_bearer_token(request)
    try:
        data = service.kick_device(
            access_token=token,
            target_device_id=device_id,
            current_fingerprint=_extract_current_fingerprint(request),
            ip_address=_extract_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        return _ok("设备踢出成功", data)
    except PermissionError as exc:
        raise _fail(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except ValueError as exc:
        message = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "不存在" in message else status.HTTP_400_BAD_REQUEST
        raise _fail(status_code, message) from exc
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
