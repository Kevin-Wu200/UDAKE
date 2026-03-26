"""Authentication APIs for register/login/refresh/logout."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..auth import (
    JWTValidationError,
    ProductKeyValidationError,
    VerificationCodeError,
    get_auth_service,
)

router = APIRouter(prefix="/auth")


def _ok(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"success": True, "message": message, "data": data or {}}


def _fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"success": False, "message": message, "data": {}})


class RegisterRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., description="Raw password")
    product_key: str = Field(..., description="Product key")


class LoginRequest(BaseModel):
    email: str
    password: str
    device_info: Dict[str, Any] = Field(default_factory=dict)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    access_token: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


@router.post("/register")
def register(payload: RegisterRequest):
    service = get_auth_service()
    try:
        result = service.register(
            email=payload.email,
            password=payload.password,
            product_key=payload.product_key,
        )
        return _ok("注册成功，验证码已发送", result)
    except ProductKeyValidationError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, f"产品密钥校验失败: {exc}") from exc
    except ValueError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    service = get_auth_service()
    try:
        result = service.login(
            email=payload.email,
            password=payload.password,
            device_info=payload.device_info,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return _ok("登录成功", result)
    except ValueError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@router.post("/refresh")
def refresh(payload: RefreshRequest):
    service = get_auth_service()
    try:
        access_token = service.refresh_access_token(payload.refresh_token)
        return _ok("Token刷新成功", {"access_token": access_token})
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@router.post("/logout")
def logout(payload: LogoutRequest):
    service = get_auth_service()
    try:
        service.logout(payload.access_token)
        return _ok("登出成功")
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@router.post("/verify-email-code")
def verify_email_code(payload: VerifyCodeRequest):
    service = get_auth_service()
    try:
        service.verify_email_code(payload.email, payload.code)
        return _ok("验证码验证成功")
    except VerificationCodeError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
