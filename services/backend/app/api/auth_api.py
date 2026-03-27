"""Authentication APIs for register/login/password/email management."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..auth import (
    JWTValidationError,
    ProductKeyValidationError,
    RateLimitExceededError,
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


class ResetPasswordSendCodeRequest(BaseModel):
    email: str
    product_key: str


class ResetPasswordVerifyRequest(BaseModel):
    email: str
    code: str
    new_password: str
    confirm_password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


class ChangeEmailSendCodeRequest(BaseModel):
    new_email: str
    current_password: str


class ChangeEmailVerifyRequest(BaseModel):
    code: str


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")
    return token


@router.post("/register")
def register(payload: RegisterRequest, request: Request):
    service = get_auth_service()
    try:
        result = service.register(
            email=payload.email,
            password=payload.password,
            product_key=payload.product_key,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return _ok("注册成功，验证码已发送", result)
    except ProductKeyValidationError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, f"产品密钥校验失败: {exc}") from exc
    except RateLimitExceededError as exc:
        raise _fail(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
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
    except RateLimitExceededError as exc:
        raise _fail(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc


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
    except RateLimitExceededError as exc:
        raise _fail(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc


@router.post("/reset-password/send-code")
def send_reset_password_code(payload: ResetPasswordSendCodeRequest, request: Request):
    service = get_auth_service()
    try:
        service.send_reset_password_code(
            email=payload.email,
            product_key=payload.product_key,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return _ok("验证码已发送")
    except ProductKeyValidationError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, f"产品密钥校验失败: {exc}") from exc
    except RateLimitExceededError as exc:
        raise _fail(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except ValueError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/reset-password/verify")
def verify_reset_password(payload: ResetPasswordVerifyRequest, request: Request):
    service = get_auth_service()
    try:
        service.reset_password(
            email=payload.email,
            code=payload.code,
            new_password=payload.new_password,
            confirm_password=payload.confirm_password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return _ok("密码重置成功")
    except VerificationCodeError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RateLimitExceededError as exc:
        raise _fail(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except ValueError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, request: Request):
    service = get_auth_service()
    token = _extract_bearer_token(request)
    try:
        service.change_password(
            access_token=token,
            old_password=payload.old_password,
            new_password=payload.new_password,
            confirm_password=payload.confirm_password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return _ok("密码修改成功")
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except ValueError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/change-email/send-code")
def send_change_email_code(payload: ChangeEmailSendCodeRequest, request: Request):
    service = get_auth_service()
    token = _extract_bearer_token(request)
    try:
        service.send_change_email_code(
            access_token=token,
            new_email=payload.new_email,
            current_password=payload.current_password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return _ok("验证码已发送")
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except ValueError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/change-email/verify")
def verify_change_email(payload: ChangeEmailVerifyRequest, request: Request):
    service = get_auth_service()
    token = _extract_bearer_token(request)
    try:
        service.verify_change_email(
            access_token=token,
            code=payload.code,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return _ok("邮箱修改成功")
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except VerificationCodeError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RateLimitExceededError as exc:
        raise _fail(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    except ValueError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
