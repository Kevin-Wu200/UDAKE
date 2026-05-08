"""Authentication and role-based authorization dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth import JWTValidationError, get_auth_service
from ..auth_db.models import User


def _fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"success": False, "message": message, "data": {}})


@dataclass(frozen=True)
class AuthUserContext:
    user_id: int
    role: str
    company_id: Optional[int]


def get_current_user_context(request: Request, db: Session) -> AuthUserContext:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")

    service = get_auth_service()
    try:
        payload = service.jwt.verify_token(token, expected_type="access", check_blacklist=True)
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user_id = payload.get("user_id")
    token_role = str(payload.get("role") or "")
    if not user_id:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "Token缺少用户标识")

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError) as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "Token用户标识无效") from exc

    user = db.query(User).filter(User.id == user_id_int).one_or_none()
    if not user:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "用户不存在或Token无效")
    if user.status in {"deleted", "disabled", "locked"}:
        raise _fail(status.HTTP_403_FORBIDDEN, "用户状态不可用")
    if token_role and token_role != user.role:
        raise _fail(status.HTTP_403_FORBIDDEN, "Token角色与数据库角色不一致")

    return AuthUserContext(user_id=user.id, role=user.role, company_id=user.company_id)


class RoleChecker:
    """Role-based guard for protected routes."""

    def __init__(self, allowed_roles: Iterable[str], *, require_company_scope: bool = False):
        self.allowed_roles = {str(role).strip() for role in allowed_roles if str(role).strip()}
        self.require_company_scope = require_company_scope

    def __call__(self, request: Request, db: Session) -> AuthUserContext:
        user = get_current_user_context(request, db)
        if user.role not in self.allowed_roles:
            raise _fail(status.HTTP_403_FORBIDDEN, "权限不足")
        if self.require_company_scope and not user.company_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "企业管理员必须绑定企业")
        return user


def ensure_same_company_scope(current_user: AuthUserContext, target_company_id: Optional[int]) -> None:
    if current_user.role == "company_admin" and target_company_id and current_user.company_id != target_company_id:
        raise _fail(status.HTTP_403_FORBIDDEN, "无权限访问其他企业数据")

