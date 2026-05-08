"""Company user management APIs with enterprise-scope permission controls."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..auth import ProductKeyRegistry, SensitiveDataCipher, get_auth_service
from ..auth.dependencies import RoleChecker, ensure_same_company_scope, get_current_user_context
from ..auth_db.models import AuditLog, Company, ProductKey, User
from ..auth_db.session import get_auth_db_session
from ..config import settings
from ..services.company_admin_policy_service import (
    compute_key_expires_at,
    is_datetime_expired,
    mark_expired_product_keys,
    resolve_company_admin_policy,
    send_expiry_reminders,
    sync_company_admin_role_by_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/company")

ROLE_CACHE_TTL_SECONDS = 3600
COMPANY_CACHE_TTL_SECONDS = 3600
ENTERPRISE_PRODUCT_KEY_TYPES = {"enterprise_trial", "enterprise_standard"}
PRODUCT_KEY_QUOTA_MAP = {
    "personal_trial": 10,
    "personal_standard": 100,
    "enterprise_trial": 500,
    "enterprise_standard": 1000,
}

_key_registry = ProductKeyRegistry()
_product_key_cipher = SensitiveDataCipher(settings.AUTH_ENCRYPTION_KEY or os.getenv("AUTH_JWT_SECRET") or "udake-key")


class BatchCompanyKeyRequest(BaseModel):
    key_type: Literal["enterprise_trial", "enterprise_standard"]
    count: int = Field(1, ge=1, le=1000)
    metadata: Optional[Dict[str, Any]] = None


class AssignKeyRequest(BaseModel):
    key_id: int = Field(..., ge=1)
    user_id: int = Field(..., ge=1)


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


def _cache_user_role(user_id: int, role: str, company_id: Optional[int]) -> None:
    try:
        service = get_auth_service()
        service.cache.set(
            f"user_role:{user_id}",
            {"role": role, "company_id": company_id},
            ttl=ROLE_CACHE_TTL_SECONDS,
        )
    except Exception as exc:  # pragma: no cover - cache failures should not block request
        logger.warning("缓存用户角色失败 user_id=%s: %s", user_id, exc)


def _get_authenticated_user(request: Request, db: Session) -> User:
    ctx = get_current_user_context(request, db)
    user = db.query(User).filter(User.id == ctx.user_id).one_or_none()
    if not user:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "用户不存在或Token无效")
    _cache_user_role(user.id, user.role, user.company_id)
    return user


def _require_company_admin_user(request: Request, db: Session) -> User:
    ctx = RoleChecker(["company_admin"], require_company_scope=True)(request, db)
    user = db.query(User).filter(User.id == ctx.user_id).one_or_none()
    if not user:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "用户不存在或Token无效")
    return user


def _require_super_admin_user(request: Request, db: Session) -> User:
    ctx = RoleChecker(["admin", "super_admin"])(request, db)
    user = db.query(User).filter(User.id == ctx.user_id).one_or_none()
    if not user:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "用户不存在或Token无效")
    return user


def _get_company_name(db: Session, company_id: Optional[int]) -> Optional[str]:
    if not company_id:
        return None

    cache_key = f"company:{company_id}"
    service = get_auth_service()
    try:
        cached = service.cache.get(cache_key)
    except Exception as exc:  # pragma: no cover - cache failures should not block request
        logger.warning("读取企业缓存失败 company_id=%s: %s", company_id, exc)
        cached = None
    if isinstance(cached, dict):
        name = cached.get("name")
        if isinstance(name, str) and name:
            return name

    company = db.query(Company).filter(Company.id == company_id).one_or_none()
    if not company:
        return None
    try:
        service.cache.set(cache_key, {"name": company.name}, ttl=COMPANY_CACHE_TTL_SECONDS)
    except Exception as exc:  # pragma: no cover
        logger.warning("写入企业缓存失败 company_id=%s: %s", company_id, exc)
    return company.name


def _serialize_user(user: User, *, company_name: Optional[str] = None) -> Dict[str, Any]:
    policy = resolve_company_admin_policy(user) if user.role == "company_admin" else None
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "status": user.status,
        "company_name": company_name,
        "company_admin_type": getattr(user, "company_admin_type", None),
        "company_admin_key_id": getattr(user, "company_admin_key_id", None),
        "total_keys_created": int(getattr(user, "total_keys_created", 0) or 0),
        "remaining_keys_allowed": policy.remaining if policy else None,
    }


def _serialize_product_key(item: ProductKey, *, company_name: Optional[str] = None) -> Dict[str, Any]:
    metadata = None
    if item.key_metadata:
        try:
            parsed = json.loads(item.key_metadata)
            if isinstance(parsed, dict):
                metadata = parsed
        except (TypeError, ValueError):
            metadata = None
    return {
        "id": item.id,
        "product_key": item.product_key,
        "key_type": item.key_type,
        "key_sub_type": item.key_sub_type,
        "status": item.status,
        "user_id": item.user_id,
        "company_id": item.company_id,
        "company_name": company_name,
        "total_quota": int(item.total_quota or 0),
        "used_count": int(item.used_count or 0),
        "assigned_at": item.assigned_at.isoformat() if item.assigned_at else None,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "metadata": metadata,
    }


def _next_model_id(db: Session, model_cls: Any) -> int:
    return int((db.query(func.max(model_cls.id)).scalar() or 0) + 1)


def _run_company_key_maintenance(db: Session) -> None:
    try:
        auth_service = get_auth_service()
        expired_result = mark_expired_product_keys(db)
        if int(expired_result.get("expired_keys", 0) or 0) > 0 or int(
            expired_result.get("expired_related_keys", 0) or 0
        ) > 0:
            db.commit()
        send_expiry_reminders(db, auth_service=auth_service)
        db.flush()
    except Exception as exc:  # pragma: no cover
        logger.warning("企业密钥维护任务执行失败: %s", exc)


def _normalize_product_key(raw: str) -> str:
    return raw.strip().upper()


def _make_seed(index: int, operator_id: int) -> str:
    return f"company-admin:{operator_id}:{index}:{time.time_ns()}:{uuid.uuid4().hex}"


def _resolve_key_sub_type(key_type: str) -> str:
    return "trial" if key_type.endswith("_trial") else "standard"


def company_admin_required(handler):
    """Decorator that enforces company-admin role and enterprise scope."""

    @wraps(handler)
    def wrapper(*args, **kwargs):
        request = kwargs.get("request")
        db = kwargs.get("db")

        if request is None:
            request = next((arg for arg in args if isinstance(arg, Request)), None)
        if db is None:
            db = next((arg for arg in args if isinstance(arg, Session)), None)

        if request is None or db is None:
            raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, "权限装饰器参数解析失败")

        request.state.company_admin_user = _require_company_admin_user(request, db)
        return handler(*args, **kwargs)

    return wrapper


@router.get("/users")
@company_admin_required
def list_company_users(
    request: Request,
    db: Session = Depends(get_auth_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
):
    current_user: User = request.state.company_admin_user

    query = db.query(User).filter(
        User.company_id == current_user.company_id,
        User.status != "deleted",
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(User.username.ilike(pattern), User.email.ilike(pattern)))

    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    company_name = _get_company_name(db, current_user.company_id)
    return _ok(
        "企业用户列表获取成功",
        {
            "users": [_serialize_user(item, company_name=company_name) for item in users],
            "pagination": {"page": page, "page_size": page_size, "total": total},
            "total": total,
        },
    )


@router.post("/product-keys/batch")
@company_admin_required
def batch_generate_company_keys(
    payload: BatchCompanyKeyRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user: User = request.state.company_admin_user
    _run_company_key_maintenance(db)

    if payload.key_type not in ENTERPRISE_PRODUCT_KEY_TYPES:
        raise _fail(status.HTTP_400_BAD_REQUEST, "只支持企业试用和企业标准类型")
    policy = resolve_company_admin_policy(current_user)
    if payload.key_type not in policy.allowed_key_types:
        raise _fail(
            status.HTTP_403_FORBIDDEN,
            f"当前企业管理员类型为{policy.admin_type}，不允许创建 {payload.key_type}",
        )
    if policy.total_keys_created + payload.count > policy.total_limit:
        raise _fail(
            status.HTTP_403_FORBIDDEN,
            f"创建数量超限：已创建 {policy.total_keys_created}，本次 {payload.count}，上限 {policy.total_limit}",
        )

    created_items: List[ProductKey] = []
    next_key_id = _next_model_id(db, ProductKey)
    max_attempts = payload.count * 10
    attempt = 0
    while len(created_items) < payload.count and attempt < max_attempts:
        attempt += 1
        seed = _make_seed(index=attempt, operator_id=current_user.id)
        generated = _key_registry.generate_key(seed, key_type=payload.key_type)
        normalized_key = _normalize_product_key(generated.product_key)
        exists = db.query(ProductKey.id).filter(ProductKey.product_key == normalized_key).first()
        if exists:
            continue

        item = ProductKey(
            id=next_key_id,
            user_id=current_user.id,
            product_key=normalized_key,
            product_key_ciphertext=_product_key_cipher.encrypt(normalized_key),
            key_type=payload.key_type,
            key_sub_type=_resolve_key_sub_type(payload.key_type),
            generation_seed=seed,
            key_metadata=json.dumps(payload.metadata, ensure_ascii=False) if payload.metadata is not None else None,
            status="unused",
            company_id=current_user.company_id,
            total_quota=PRODUCT_KEY_QUOTA_MAP[payload.key_type],
            used_count=0,
            expires_at=compute_key_expires_at(payload.key_type),
        )
        db.add(item)
        created_items.append(item)
        next_key_id += 1

    if len(created_items) != payload.count:
        db.rollback()
        raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, "批量生成密钥失败，请重试")

    db.add(
        AuditLog(
            id=_next_model_id(db, AuditLog),
            user_id=current_user.id,
            actor_username=current_user.username,
            operation_type="create",
            target_table="product_keys",
            target_id=None,
            ip_address=_extract_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            details={
                "action": "batch_generate_company_keys",
                "company_id": current_user.company_id,
                "key_type": payload.key_type,
                "count": payload.count,
            },
        )
    )
    current_user.total_keys_created = int(getattr(current_user, "total_keys_created", 0) or 0) + payload.count
    db.commit()

    company_name = _get_company_name(db, current_user.company_id)
    return _ok(
        "企业密钥批量生成成功",
        {
            "keys": [_serialize_product_key(item, company_name=company_name) for item in created_items],
            "count": len(created_items),
        },
    )


@router.post("/product-keys/assign")
@company_admin_required
def assign_key_to_user(
    payload: AssignKeyRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user: User = request.state.company_admin_user
    _run_company_key_maintenance(db)

    user = db.query(User).filter(User.id == payload.user_id).one_or_none()
    if not user or user.status == "deleted" or user.company_id != current_user.company_id:
        raise _fail(status.HTTP_404_NOT_FOUND, "用户不存在或不属于本企业")

    key = db.query(ProductKey).filter(ProductKey.id == payload.key_id).one_or_none()
    if not key:
        raise _fail(status.HTTP_404_NOT_FOUND, "密钥不存在")
    if key.company_id != current_user.company_id:
        raise _fail(status.HTTP_403_FORBIDDEN, "只能分配本企业密钥")
    if key.key_type not in ENTERPRISE_PRODUCT_KEY_TYPES:
        raise _fail(status.HTTP_400_BAD_REQUEST, "只能分配企业类型密钥")
    if key.status in {"disabled", "expired"}:
        raise _fail(status.HTTP_400_BAD_REQUEST, "密钥状态不可分配")
    if is_datetime_expired(key.expires_at):
        key.status = "expired"
        db.commit()
        raise _fail(status.HTTP_400_BAD_REQUEST, "密钥已过期，无法分配")

    key.user_id = user.id
    key.assigned_at = datetime.now(timezone.utc)
    if key.status == "unused":
        key.status = "active"
        key.used_count = min(int(key.total_quota or 0), int(key.used_count or 0) + 1)
        key.activated_at = key.activated_at or datetime.now(timezone.utc)
        if key.expires_at is None:
            key.expires_at = compute_key_expires_at(key.key_type, base_time=key.activated_at)
    user.product_key_id = key.id
    sync_company_admin_role_by_key(current_user, key)

    db.add(
        AuditLog(
            id=_next_model_id(db, AuditLog),
            user_id=current_user.id,
            actor_username=current_user.username,
            operation_type="update",
            target_table="product_keys",
            target_id=str(key.id),
            ip_address=_extract_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            details={
                "action": "assign_company_key",
                "company_id": current_user.company_id,
                "user_id": user.id,
                "key_id": key.id,
            },
        )
    )
    db.commit()

    return _ok("企业密钥分配成功", {"key": _serialize_product_key(key, company_name=_get_company_name(db, key.company_id))})


@router.get("/product-keys/stats")
@company_admin_required
def get_company_key_stats(
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user: User = request.state.company_admin_user
    _run_company_key_maintenance(db)

    query = db.query(ProductKey).filter(ProductKey.company_id == current_user.company_id)
    total = int(query.count())
    by_type_rows = query.with_entities(ProductKey.key_type, func.count(ProductKey.id)).group_by(ProductKey.key_type).all()
    by_status_rows = query.with_entities(ProductKey.status, func.count(ProductKey.id)).group_by(ProductKey.status).all()

    return _ok(
        "企业密钥统计获取成功",
        {
            "company_id": current_user.company_id,
            "total": total,
            "by_type": {key_type: int(count or 0) for key_type, count in by_type_rows},
            "by_status": {status_name: int(count or 0) for status_name, count in by_status_rows},
        },
    )


@router.delete("/users/{user_id}")
@company_admin_required
def delete_company_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user: User = request.state.company_admin_user

    target_user = db.query(User).filter(User.id == user_id).one_or_none()
    if not target_user or target_user.status == "deleted":
        raise _fail(status.HTTP_404_NOT_FOUND, "目标用户不存在")
    ensure_same_company_scope(
        get_current_user_context(request, db),
        target_user.company_id,
    )
    if target_user.company_id != current_user.company_id:
        raise _fail(status.HTTP_403_FORBIDDEN, "无权限操作其他企业用户")
    if target_user.id == current_user.id:
        raise _fail(status.HTTP_400_BAD_REQUEST, "企业管理员不能删除自己")
    if target_user.role == "company_admin":
        raise _fail(status.HTTP_403_FORBIDDEN, "不能删除其他企业管理员")

    try:
        product_key: Optional[ProductKey] = None
        if target_user.product_key_id:
            product_key = db.query(ProductKey).filter(ProductKey.id == target_user.product_key_id).one_or_none()
        if product_key is None:
            product_key = (
                db.query(ProductKey)
                .filter(ProductKey.user_id == target_user.id)
                .order_by(ProductKey.created_at.desc())
                .first()
            )

        target_user.status = "deleted"
        released_quota = 0
        if product_key:
            current_used = max(0, int(product_key.used_count or 0))
            next_used = max(0, current_used - 1)
            released_quota = current_used - next_used
            product_key.used_count = next_used
            if next_used == 0:
                product_key.status = "unused"
            target_user.product_key_id = None

        next_audit_id = (db.query(func.max(AuditLog.id)).scalar() or 0) + 1
        audit = AuditLog(
            id=next_audit_id,
            user_id=current_user.id,
            actor_username=current_user.username,
            operation_type="delete_user",
            target_table="users",
            target_id=str(target_user.id),
            ip_address=_extract_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            details={
                "operator_role": current_user.role,
                "operator_company_id": current_user.company_id,
                "target_user_id": target_user.id,
                "target_username": target_user.username,
                "released_quota": released_quota,
                "product_key_id": getattr(product_key, "id", None),
            },
        )
        db.add(audit)
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:  # pylint: disable=broad-except
        db.rollback()
        logger.exception("删除企业用户失败 user_id=%s err=%s", user_id, exc)
        raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, "删除用户失败，事务已回滚") from exc

    return _ok("删除用户成功", {"user_id": user_id})


@router.get("/me")
def get_my_company_profile(
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user = _get_authenticated_user(request, db)
    _run_company_key_maintenance(db)
    policy = resolve_company_admin_policy(current_user) if current_user.role == "company_admin" else None
    return _ok(
        "用户企业信息获取成功",
        {
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "role": current_user.role,
                "joined_at": current_user.created_at,
                "company_name": _get_company_name(db, current_user.company_id),
                "company_admin_type": getattr(current_user, "company_admin_type", None),
                "company_admin_key_id": getattr(current_user, "company_admin_key_id", None),
                "total_keys_created": int(getattr(current_user, "total_keys_created", 0) or 0),
                "remaining_keys_allowed": policy.remaining if policy else None,
                "allowed_key_types": sorted(policy.allowed_key_types) if policy else [],
            }
        },
    )


@router.get("/admin/users")
def list_all_users_for_admin(
    request: Request,
    db: Session = Depends(get_auth_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
):
    _require_super_admin_user(request, db)

    query = db.query(User).filter(User.status != "deleted")
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(User.username.ilike(pattern), User.email.ilike(pattern)))

    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return _ok(
        "管理员用户列表获取成功",
        {
            "users": [_serialize_user(item, company_name=_get_company_name(db, item.company_id)) for item in users],
            "pagination": {"page": page, "page_size": page_size, "total": total},
            "total": total,
        },
    )


@router.get("/admin/users/{user_id}")
def get_user_detail_for_admin(
    user_id: int,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    _require_super_admin_user(request, db)
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if not user or user.status == "deleted":
        raise _fail(status.HTTP_404_NOT_FOUND, "目标用户不存在")

    company = db.query(Company).filter(Company.id == user.company_id).one_or_none() if user.company_id else None
    return _ok(
        "用户详情获取成功",
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "created_at": user.created_at,
                "last_login_at": user.last_login_at,
                "company": (
                    {"id": company.id, "name": company.name, "status": company.status}
                    if company
                    else None
                ),
            }
        },
    )


@router.get("/admin/company-stats")
def get_company_user_stats(
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    _require_super_admin_user(request, db)

    rows = (
        db.query(
            Company.id.label("company_id"),
            Company.name.label("company_name"),
            func.count(User.id).label("user_count"),
        )
        .outerjoin(User, (User.company_id == Company.id) & (User.status != "deleted"))
        .group_by(Company.id, Company.name)
        .order_by(Company.id.asc())
        .all()
    )

    return _ok(
        "企业统计获取成功",
        {
            "companies": [
                {
                    "company_id": row.company_id,
                    "company_name": row.company_name,
                    "user_count": int(row.user_count or 0),
                }
                for row in rows
            ]
        },
    )
