"""Admin backend APIs for product keys, users, audit logs, and dashboard stats."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import logging
import os
import secrets
import string
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from ..auth import JWTValidationError, ProductKeyRegistry, SensitiveDataCipher, get_auth_service, hash_password
from ..auth.input_sanitizer import sanitize_payload
from ..auth_db.models import (
    AuditLog,
    Company,
    PasswordHistory,
    ProductKey,
    ProductKeyStatus,
    ProductKeyType,
    User,
    UserDevice,
)
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

router = APIRouter(prefix="/admin")

PRODUCT_KEY_TYPE_TO_DB = {
    "personal_trial": "personal_trial",
    "personal_standard": "personal_standard",
    "enterprise_trial": "enterprise_trial",
    "enterprise_standard": "enterprise_standard",
}
PRODUCT_KEY_TYPE_FROM_DB = {
    "personal_trial": "personal_trial",
    "personal_standard": "personal_standard",
    "enterprise_trial": "enterprise_trial",
    "enterprise_standard": "enterprise_standard",
}
PRODUCT_KEY_QUOTA_MAP = {
    "personal_trial": 10,
    "personal_standard": 100,
    "enterprise_trial": 500,
    "enterprise_standard": 1000,
}
PRODUCT_KEY_TYPES = set(PRODUCT_KEY_TYPE_TO_DB)
ENTERPRISE_PRODUCT_KEY_TYPES = {
    ProductKeyType.ENTERPRISE_TRIAL.value,
    ProductKeyType.ENTERPRISE_STANDARD.value,
}
VALID_PRODUCT_KEY_STATUS = {item.value for item in ProductKeyStatus}
VALID_USER_STATUS = {"active", "disabled"}
AUDIT_EXPORT_LIMIT = 10_000
STATS_CACHE_TTL_SECONDS = 3600
_STATS_CACHE_KEY = "admin:stats:v1"

_DIGEST_INFO_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")

# 固定开发用 RSA 私钥参数（1024 位），用于企业密钥签名。
# 仅用于后台批量生成签名，生产环境建议改为 KMS/HSM 托管密钥。
_ADMIN_RSA_N = int(
    "108644163298684185968680396944903067290814949464415306645182857358122199241528367130765515403781105"
    "840621355983429113603291852850772994045538138201257980155979391128332602462982542089549509329182486"
    "796575296132483742090345217235385860308345414163449413268470181601975565027549148699671851236458081"
    "808436073289"
)
_ADMIN_RSA_D = int(
    "979897842834615901339502611259780018548311894478170922653883866890245692840188257182896625649251745"
    "767906427236598395576633263959166833701841608416064086815198881921867733431557954013478383195130854"
    "444536529318902547281630975310580646401209487762487120996819065058041336924603321362037892551086296"
    "64759349273"
)

_key_registry = ProductKeyRegistry()
_product_key_cipher = SensitiveDataCipher(settings.AUTH_ENCRYPTION_KEY or os.getenv("AUTH_JWT_SECRET") or "udake-key")


class ProductKeyCreateRequest(BaseModel):
    type: Literal["personal_trial", "personal_standard", "enterprise_trial", "enterprise_standard"] = Field(
        ...,
        description="密钥类型",
    )
    user_id: Optional[int] = Field(default=None, description="分配给用户ID")
    company_id: Optional[int] = Field(default=None, description="企业ID（企业密钥必填）")
    count: int = Field(1, ge=1, le=1000, description="生成数量")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="密钥元数据")


class ProductKeyUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None)
    company_name: Optional[str] = Field(default=None, max_length=128)
    extend_days: Optional[int] = Field(default=None, ge=0, le=3650, description="延长天数，0表示取消过期限制")


class ProductKeyBatchImportRequest(BaseModel):
    keys: List[str] = Field(..., min_length=1, max_length=5000)
    type: Literal["personal_trial", "personal_standard", "enterprise_trial", "enterprise_standard"] = Field(...)
    duplicate_action: Literal["skip", "overwrite"] = Field(default="skip")
    company_name: Optional[str] = Field(default=None, max_length=128)


class UserToggleStatusRequest(BaseModel):
    status: Literal["active", "disabled"]


class ProductKeyResponse(BaseModel):
    id: int
    product_key: str
    key_type: str
    key_sub_type: str
    status: str
    total_quota: int
    used_count: int
    user_id: Optional[int]
    company_id: Optional[int]
    assigned_at: Optional[datetime]
    expires_at: Optional[datetime]
    metadata: Optional[Dict[str, Any]]


class ProductKeyAssignRequest(BaseModel):
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


def _mask_ip(ip_address: Optional[str]) -> str:
    if not ip_address:
        return "-"
    if ":" in ip_address:
        segments = [segment for segment in ip_address.split(":") if segment]
        if len(segments) >= 2:
            return f"{segments[0]}:{segments[1]}:*:*"
        return "*:*"
    parts = ip_address.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.*"
    return ip_address


def _verify_access_token(request: Request) -> Dict[str, Any]:
    token = _extract_bearer_token(request)
    service = get_auth_service()
    try:
        payload = service.jwt.verify_token(token, expected_type="access", check_blacklist=True)
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return payload


def _get_authenticated_user(request: Request, db: Session) -> User:
    payload = _verify_access_token(request)
    token_role = str(payload.get("role") or "")
    user_id = payload.get("user_id")
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
    return user


def _require_super_admin_user(request: Request, db: Session) -> User:
    user = _get_authenticated_user(request, db)
    if user.role not in {"admin", "super_admin"}:
        raise _fail(status.HTTP_403_FORBIDDEN, "权限不足，仅超级管理员可访问")
    return user


def require_role(allowed_roles: List[str]):
    """角色权限验证装饰器。"""

    def decorator(handler):
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

            current_user = _get_authenticated_user(request, db)
            if current_user.role not in set(allowed_roles):
                raise _fail(status.HTTP_403_FORBIDDEN, "权限不足")
            request.state.current_user = current_user
            return handler(*args, **kwargs)

        return wrapper

    return decorator


def company_admin_required(handler):
    """企业管理员权限验证装饰器。"""

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

        current_user = _get_authenticated_user(request, db)
        if current_user.role != "company_admin":
            raise _fail(status.HTTP_403_FORBIDDEN, "需要企业管理员权限")
        if not current_user.company_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "企业管理员必须绑定企业")
        request.state.current_user = current_user
        return handler(*args, **kwargs)

    return wrapper


def _normalize_datetime(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_time_filter(raw_value: Optional[str], *, field_name: str) -> Optional[datetime]:
    if raw_value is None or not raw_value.strip():
        return None
    value = raw_value.strip()
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise _fail(status.HTTP_400_BAD_REQUEST, f"{field_name} 不是合法的ISO时间") from exc
    return _normalize_datetime(parsed)


def _to_iso(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _parse_key_metadata(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _serialize_product_key(item: ProductKey, company_name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": item.id,
        "product_key": item.product_key,
        "type": PRODUCT_KEY_TYPE_FROM_DB.get(item.key_type, item.key_type),
        "sub_type": item.key_sub_type,
        "key_type": PRODUCT_KEY_TYPE_FROM_DB.get(item.key_type, item.key_type),
        "key_sub_type": item.key_sub_type,
        "status": item.status,
        "user_id": item.user_id,
        "company_id": item.company_id,
        "company_name": company_name,
        "total_quota": int(item.total_quota or 0),
        "used_count": int(item.used_count or 0),
        "signature": item.signature,
        "encrypted": bool(item.product_key_ciphertext),
        "issued_at": _to_iso(item.issued_at),
        "assigned_at": _to_iso(item.assigned_at),
        "last_used_at": _to_iso(item.last_used_at),
        "expires_at": _to_iso(item.expires_at),
        "metadata": _parse_key_metadata(item.key_metadata),
        "created_at": _to_iso(item.created_at),
        "updated_at": _to_iso(item.updated_at),
    }


def _serialize_user(item: User, company_name: Optional[str] = None) -> Dict[str, Any]:
    company_admin_type = getattr(item, "company_admin_type", None)
    total_keys_created = int(getattr(item, "total_keys_created", 0) or 0)
    return {
        "id": item.id,
        "username": item.username,
        "email": item.email,
        "role": item.role,
        "status": item.status,
        "company_id": item.company_id,
        "company_name": company_name,
        "company_admin_type": company_admin_type,
        "company_admin_key_id": getattr(item, "company_admin_key_id", None),
        "total_keys_created": total_keys_created,
        "last_login_at": _to_iso(item.last_login_at),
        "created_at": _to_iso(item.created_at),
        "updated_at": _to_iso(item.updated_at),
    }


def _serialize_audit_log(item: AuditLog) -> Dict[str, Any]:
    return {
        "id": item.id,
        "user_id": item.user_id,
        "actor_username": item.actor_username,
        "event_type": item.operation_type,
        "target_table": item.target_table,
        "target_id": item.target_id,
        "ip_address": item.ip_address,
        "ip_address_masked": item.ip_address_masked,
        "user_agent": item.user_agent,
        "request_id": item.request_id,
        "success": item.success,
        "failure_reason": item.failure_reason,
        "details": item.details or {},
        "operated_at": _to_iso(item.operated_at),
    }


def _resolve_or_create_company(db: Session, company_name: Optional[str]) -> Optional[Company]:
    name = (company_name or "").strip()
    if not name:
        return None
    company = db.query(Company).filter(Company.name == name).one_or_none()
    if company:
        return company
    company = Company(id=_next_model_id(db, Company), name=name, status="active")
    db.add(company)
    db.flush()
    return company


def _resolve_company_by_id(db: Session, company_id: Optional[int]) -> Optional[Company]:
    if company_id is None:
        return None
    return db.query(Company).filter(Company.id == company_id).one_or_none()


def _normalize_product_key(raw: str) -> str:
    return raw.strip().upper()


def _make_seed(index: int, operator_id: int) -> str:
    return f"admin:{operator_id}:{index}:{time.time_ns()}:{uuid.uuid4().hex}"


def _resolve_key_sub_type(key_type: str) -> str:
    return "trial" if key_type.endswith("_trial") else "standard"


def _rsa_sign_pkcs1_v15_sha256(message: bytes) -> str:
    key_size = (_ADMIN_RSA_N.bit_length() + 7) // 8
    digest = hashlib.sha256(message).digest()
    digest_info = _DIGEST_INFO_SHA256_PREFIX + digest
    ps_length = key_size - len(digest_info) - 3
    if ps_length < 8:
        raise RuntimeError("RSA key size too short for PKCS#1 v1.5 SHA-256")
    em = b"\x00\x01" + (b"\xff" * ps_length) + b"\x00" + digest_info
    signature_int = pow(int.from_bytes(em, "big"), _ADMIN_RSA_D, _ADMIN_RSA_N)
    signature = signature_int.to_bytes(key_size, "big")
    return base64.b64encode(signature).decode("ascii")


def _generate_temp_password(length: int = 12) -> str:
    if length < 12:
        length = 12
    lowers = string.ascii_lowercase
    uppers = string.ascii_uppercase
    digits = string.digits
    specials = "!@#$%^&*()-_=+"
    all_chars = lowers + uppers + digits + specials

    while True:
        candidate = "".join(secrets.choice(all_chars) for _ in range(length))
        if (
            any(ch in lowers for ch in candidate)
            and any(ch in uppers for ch in candidate)
            and any(ch in digits for ch in candidate)
            and any(ch in specials for ch in candidate)
        ):
            return candidate


def _record_audit_log(
    db: Session,
    *,
    actor: User,
    request: Request,
    operation_type: Literal[
        "create",
        "read",
        "update",
        "delete",
        "login",
        "logout",
        "password_change",
        "email_change",
        "api_call",
        "delete_user",
        "other",
    ],
    target_table: Optional[str],
    target_id: Optional[str],
    details: Optional[Dict[str, Any]] = None,
) -> None:
    success = True
    failure_reason = None
    if details and str(details.get("result", "")).lower() == "failed":
        success = False
        failure_reason = str(details.get("reason", "") or "unknown")
    ip_address = _extract_client_ip(request)
    db.add(
        AuditLog(
            id=_next_model_id(db, AuditLog),
            user_id=actor.id,
            actor_username=actor.username,
            operation_type=operation_type,
            target_table=target_table,
            target_id=target_id,
            ip_address=ip_address,
            ip_address_masked=_mask_ip(ip_address),
            user_agent=request.headers.get("user-agent"),
            success=success,
            failure_reason=failure_reason,
            details=details or {},
        )
    )


def _invalidate_user_tokens(user_id: int) -> None:
    service = get_auth_service()
    service.jwt.blacklist_all_user_tokens(user_id=user_id)


def _insert_password_history(db: Session, user_id: int, password_hash_value: str) -> None:
    history_rows = (
        db.query(PasswordHistory)
        .filter(PasswordHistory.user_id == user_id)
        .order_by(PasswordHistory.history_order.desc())
        .all()
    )

    # 先整体偏移，避免唯一约束(user_id, history_order)冲突。
    for row in history_rows:
        row.history_order = int(row.history_order) + 10
    db.flush()

    for row in history_rows:
        row.history_order = int(row.history_order) - 9

    db.query(PasswordHistory).filter(
        PasswordHistory.user_id == user_id,
        PasswordHistory.history_order > 5,
    ).delete(synchronize_session=False)

    db.add(
        PasswordHistory(
            id=_next_model_id(db, PasswordHistory),
            user_id=user_id,
            password_hash=password_hash_value,
            history_order=1,
        )
    )


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
    except Exception as exc:  # pragma: no cover - maintenance failure should not block API
        logger.warning("企业密钥维护任务执行失败: %s", exc)


@router.post("/product-keys")
@require_role(["super_admin", "company_admin"])
def create_product_keys(
    payload: ProductKeyCreateRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user: User = request.state.current_user
    _run_company_key_maintenance(db)
    db_type = PRODUCT_KEY_TYPE_TO_DB[payload.type]
    sanitized_metadata = sanitize_payload(payload.metadata) if payload.metadata is not None else None

    if current_user.role == "super_admin" and payload.count > 1:
        raise _fail(status.HTTP_403_FORBIDDEN, "超级管理员不支持批量生成密钥")
    if current_user.role == "company_admin":
        if db_type not in ENTERPRISE_PRODUCT_KEY_TYPES:
            raise _fail(status.HTTP_403_FORBIDDEN, "企业管理员只能生成企业密钥")
        if not current_user.company_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "企业管理员必须绑定企业")
        if payload.company_id is not None and payload.company_id != current_user.company_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "只能为所属企业生成密钥")
        policy = resolve_company_admin_policy(current_user)
        if db_type not in policy.allowed_key_types:
            raise _fail(
                status.HTTP_403_FORBIDDEN,
                f"当前企业管理员类型为{policy.admin_type}，不允许创建 {db_type}",
            )
        if policy.total_keys_created + payload.count > policy.total_limit:
            raise _fail(
                status.HTTP_403_FORBIDDEN,
                f"创建数量超限：已创建 {policy.total_keys_created}，本次 {payload.count}，上限 {policy.total_limit}",
            )

    company: Optional[Company] = None
    resolved_company_id = payload.company_id
    if current_user.role == "company_admin":
        resolved_company_id = current_user.company_id

    if resolved_company_id is not None:
        company = _resolve_company_by_id(db, resolved_company_id)
        if not company:
            raise _fail(status.HTTP_404_NOT_FOUND, "企业不存在")

    if db_type in ENTERPRISE_PRODUCT_KEY_TYPES:
        if company is None:
            raise _fail(status.HTTP_400_BAD_REQUEST, "企业密钥必须提供 company_id")
    elif current_user.role == "company_admin":
        raise _fail(status.HTTP_403_FORBIDDEN, "企业管理员只能生成企业密钥")

    target_user: Optional[User] = None
    target_user_id = payload.user_id or current_user.id
    if payload.user_id is not None:
        target_user = db.query(User).filter(User.id == payload.user_id).one_or_none()
        if not target_user or target_user.status == "deleted":
            raise _fail(status.HTTP_404_NOT_FOUND, "目标用户不存在")
        if current_user.role == "company_admin" and target_user.company_id != current_user.company_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "只能为所属企业用户分配密钥")
        target_user_id = target_user.id

    created_items: List[ProductKey] = []
    next_key_id = _next_model_id(db, ProductKey)
    max_attempts = payload.count * 10
    attempt = 0
    while len(created_items) < payload.count and attempt < max_attempts:
        attempt += 1
        seed = _make_seed(index=attempt, operator_id=current_user.id)
        generated = _key_registry.generate_key(seed, key_type=db_type)
        normalized_key = _normalize_product_key(generated.product_key)

        exists = db.query(ProductKey.id).filter(ProductKey.product_key == normalized_key).first()
        if exists:
            continue

        signature = None
        if db_type in ENTERPRISE_PRODUCT_KEY_TYPES:
            signature = _rsa_sign_pkcs1_v15_sha256(normalized_key.encode("ascii"))

        item = ProductKey(
            id=next_key_id,
            user_id=target_user_id,
            product_key=normalized_key,
            product_key_ciphertext=_product_key_cipher.encrypt(normalized_key),
            key_type=db_type,
            key_sub_type=_resolve_key_sub_type(db_type),
            generation_seed=seed,
            key_metadata=json.dumps(sanitized_metadata, ensure_ascii=False) if sanitized_metadata is not None else None,
            status="unused",
            company_id=company.id if company else None,
            total_quota=PRODUCT_KEY_QUOTA_MAP.get(db_type, ProductKey.get_default_quota(db_type)),
            used_count=0,
            signature=signature,
            assigned_at=datetime.now(timezone.utc) if payload.user_id else None,
            expires_at=compute_key_expires_at(db_type),
        )
        db.add(item)
        created_items.append(item)
        next_key_id += 1

    if len(created_items) != payload.count:
        db.rollback()
        raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, "生成密钥失败，请重试")

    _record_audit_log(
        db,
        actor=current_user,
        request=request,
        operation_type="create",
        target_table="product_keys",
        target_id=None,
        details={
            "action": "create_product_keys",
            "count": payload.count,
            "type": PRODUCT_KEY_TYPE_FROM_DB.get(db_type, db_type),
            "company_id": company.id if company else None,
            "target_user_id": payload.user_id,
        },
    )
    if current_user.role == "company_admin":
        current_user.total_keys_created = int(getattr(current_user, "total_keys_created", 0) or 0) + payload.count
    db.commit()

    company_name_map: Dict[int, str] = {}
    if company:
        company_name_map[company.id] = company.name
    else:
        company_ids = {item.company_id for item in created_items if item.company_id}
        if company_ids:
            rows = db.query(Company.id, Company.name).filter(Company.id.in_(company_ids)).all()
            company_name_map = {row.id: row.name for row in rows}
    return _ok(
        "产品密钥创建成功",
        {
            "keys": [
                _serialize_product_key(item, company_name=company_name_map.get(item.company_id or -1))
                for item in created_items
            ],
            "count": len(created_items),
        },
    )


@router.get("/product-keys")
@require_role(["super_admin", "company_admin"])
def list_product_keys(
    request: Request,
    db: Session = Depends(get_auth_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    key_type: Optional[str] = Query(default=None, alias="type"),
    status_value: Optional[str] = Query(default=None, alias="status"),
    company_id: Optional[int] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    current_user: User = request.state.current_user
    _run_company_key_maintenance(db)

    query = db.query(ProductKey, Company.name.label("company_name")).outerjoin(Company, Company.id == ProductKey.company_id)

    if key_type:
        normalized_type = key_type.strip().lower()
        if normalized_type not in PRODUCT_KEY_TYPES:
            raise _fail(
                status.HTTP_400_BAD_REQUEST,
                "type 仅支持 personal_trial/personal_standard/enterprise_trial/enterprise_standard",
            )
        query = query.filter(ProductKey.key_type == PRODUCT_KEY_TYPE_TO_DB[normalized_type])

    if status_value:
        normalized_status = status_value.strip().lower()
        if normalized_status not in VALID_PRODUCT_KEY_STATUS:
            raise _fail(status.HTTP_400_BAD_REQUEST, "status 参数无效")
        query = query.filter(ProductKey.status == normalized_status)

    effective_company_id = company_id
    if current_user.role == "company_admin":
        if not current_user.company_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "企业管理员必须绑定企业")
        effective_company_id = current_user.company_id
    if effective_company_id is not None:
        query = query.filter(ProductKey.company_id == effective_company_id)

    if user_id is not None:
        query = query.filter(ProductKey.user_id == user_id)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(ProductKey.product_key.ilike(pattern), Company.name.ilike(pattern)))

    total = query.count()
    rows = (
        query.order_by(ProductKey.created_at.desc(), ProductKey.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return _ok(
        "产品密钥列表获取成功",
        {
            "keys": [_serialize_product_key(item, company_name=company_name) for item, company_name in rows],
            "pagination": {"page": page, "page_size": page_size, "total": total},
            "total": total,
        },
    )


@router.post("/product-keys/assign")
@require_role(["super_admin", "company_admin"])
def assign_product_key_to_user(
    payload: ProductKeyAssignRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user: User = request.state.current_user
    _run_company_key_maintenance(db)
    target_user = db.query(User).filter(User.id == payload.user_id).one_or_none()
    if not target_user or target_user.status == "deleted":
        raise _fail(status.HTTP_404_NOT_FOUND, "目标用户不存在")

    target_key = db.query(ProductKey).filter(ProductKey.id == payload.key_id).one_or_none()
    if not target_key:
        raise _fail(status.HTTP_404_NOT_FOUND, "产品密钥不存在")

    if current_user.role == "company_admin":
        if target_user.company_id != current_user.company_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "只能为所属企业用户分配密钥")
        if target_key.company_id != current_user.company_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "只能分配所属企业密钥")

    if target_key.status in {"disabled", "expired"}:
        raise _fail(status.HTTP_400_BAD_REQUEST, "密钥状态不可分配")
    if is_datetime_expired(target_key.expires_at):
        target_key.status = "expired"
        db.commit()
        raise _fail(status.HTTP_400_BAD_REQUEST, "密钥已过期，无法分配")

    target_key.user_id = target_user.id
    target_key.assigned_at = datetime.now(timezone.utc)
    if target_key.status == "unused":
        target_key.status = "active"
        target_key.used_count = min(int(target_key.total_quota or 0), int(target_key.used_count or 0) + 1)
        target_key.activated_at = target_key.activated_at or datetime.now(timezone.utc)
        if target_key.expires_at is None:
            target_key.expires_at = compute_key_expires_at(target_key.key_type, base_time=target_key.activated_at)
    target_user.product_key_id = target_key.id
    if current_user.role == "company_admin":
        sync_company_admin_role_by_key(current_user, target_key)

    _record_audit_log(
        db,
        actor=current_user,
        request=request,
        operation_type="update",
        target_table="product_keys",
        target_id=str(target_key.id),
        details={"action": "assign_product_key", "user_id": target_user.id},
    )
    db.commit()

    company_name = db.query(Company.name).filter(Company.id == target_key.company_id).scalar() if target_key.company_id else None
    return _ok("密钥分配成功", {"key": _serialize_product_key(target_key, company_name=company_name)})


@router.get("/product-keys/stats")
@require_role(["super_admin", "company_admin"])
def get_product_key_stats(
    request: Request,
    db: Session = Depends(get_auth_db_session),
    company_id: Optional[int] = Query(default=None),
):
    current_user: User = request.state.current_user
    _run_company_key_maintenance(db)
    effective_company_id = company_id
    if current_user.role == "company_admin":
        effective_company_id = current_user.company_id

    query = db.query(ProductKey)
    if effective_company_id is not None:
        query = query.filter(ProductKey.company_id == effective_company_id)

    status_rows = query.with_entities(ProductKey.status, func.count(ProductKey.id)).group_by(ProductKey.status).all()
    type_rows = query.with_entities(ProductKey.key_type, func.count(ProductKey.id)).group_by(ProductKey.key_type).all()

    return _ok(
        "密钥统计获取成功",
        {
            "by_status": {status_name: int(count or 0) for status_name, count in status_rows},
            "by_type": {
                PRODUCT_KEY_TYPE_FROM_DB.get(type_name, type_name): int(count or 0)
                for type_name, count in type_rows
            },
            "company_id": effective_company_id,
        },
    )


@router.put("/product-keys/{key_id}")
def update_product_key(
    key_id: int,
    payload: ProductKeyUpdateRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user = _require_super_admin_user(request, db)
    target = db.query(ProductKey).filter(ProductKey.id == key_id).one_or_none()
    if not target:
        raise _fail(status.HTTP_404_NOT_FOUND, "产品密钥不存在")

    changed_fields: Dict[str, Any] = {}

    if payload.status is not None:
        next_status = payload.status.strip().lower()
        if next_status not in VALID_PRODUCT_KEY_STATUS:
            raise _fail(status.HTTP_400_BAD_REQUEST, "status 参数无效")
        if target.status != next_status:
            changed_fields["status"] = {"from": target.status, "to": next_status}
            target.status = next_status

    if payload.extend_days is not None:
        current_expiry = target.expires_at
        if payload.extend_days == 0:
            target.expires_at = None
            changed_fields["expires_at"] = {
                "from": current_expiry.isoformat() if current_expiry else None,
                "to": None,
                "extend_days": payload.extend_days,
            }
        else:
            base_time = current_expiry or datetime.now(timezone.utc).replace(tzinfo=None)
            target.expires_at = base_time + timedelta(days=payload.extend_days)
            changed_fields["expires_at"] = {
                "from": current_expiry.isoformat() if current_expiry else None,
                "to": target.expires_at.isoformat(),
                "extend_days": payload.extend_days,
            }

    if payload.company_name is not None:
        next_company = _resolve_or_create_company(db, payload.company_name)
        next_company_id = next_company.id if next_company else None
        if target.company_id != next_company_id:
            changed_fields["company_id"] = {"from": target.company_id, "to": next_company_id}
            target.company_id = next_company_id

    _record_audit_log(
        db,
        actor=current_user,
        request=request,
        operation_type="update",
        target_table="product_keys",
        target_id=str(target.id),
        details={"action": "update_product_key", "changes": changed_fields},
    )
    db.commit()

    company_name = db.query(Company.name).filter(Company.id == target.company_id).scalar() if target.company_id else None
    return _ok("产品密钥更新成功", {"key": _serialize_product_key(target, company_name=company_name)})


@router.delete("/product-keys/{key_id}")
def delete_product_key(
    key_id: int,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user = _require_super_admin_user(request, db)
    target = db.query(ProductKey).filter(ProductKey.id == key_id).one_or_none()
    if not target:
        raise _fail(status.HTTP_404_NOT_FOUND, "产品密钥不存在")
    if target.status != "unused" or int(target.used_count or 0) > 0:
        raise _fail(status.HTTP_400_BAD_REQUEST, "仅未使用密钥允许删除")

    target_id = str(target.id)
    product_key_value = target.product_key
    db.delete(target)
    _record_audit_log(
        db,
        actor=current_user,
        request=request,
        operation_type="delete",
        target_table="product_keys",
        target_id=target_id,
        details={"action": "delete_product_key", "product_key": product_key_value},
    )
    db.commit()
    return _ok("产品密钥删除成功", {"id": key_id})


@router.post("/product-keys/batch")
def batch_import_product_keys(
    payload: ProductKeyBatchImportRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user = _require_super_admin_user(request, db)
    db_type = payload.type

    company: Optional[Company] = None
    if db_type in ENTERPRISE_PRODUCT_KEY_TYPES:
        if not payload.company_name or not payload.company_name.strip():
            raise _fail(status.HTTP_400_BAD_REQUEST, "企业密钥导入必须提供 company_name")
        company = _resolve_or_create_company(db, payload.company_name)

    success_count = 0
    failed_count = 0
    overwrite_count = 0
    failed_items: List[Dict[str, str]] = []
    next_key_id = _next_model_id(db, ProductKey)
    normalized_candidates = {_normalize_product_key(item) for item in payload.keys}
    existing_records = (
        db.query(ProductKey)
        .filter(ProductKey.product_key.in_(normalized_candidates))
        .all()
        if normalized_candidates
        else []
    )
    existing_by_key = {item.product_key: item for item in existing_records}
    inserted_in_batch: set[str] = set()

    for raw_key in payload.keys:
        normalized_key = _normalize_product_key(raw_key)
        try:
            _key_registry.validate_key_format(normalized_key)
            _key_registry.validate_checksum(normalized_key)
        except Exception as exc:  # pylint: disable=broad-except
            failed_count += 1
            failed_items.append({"key": normalized_key, "reason": f"密钥格式或校验失败: {exc}"})
            continue

        if normalized_key in inserted_in_batch:
            if payload.duplicate_action == "skip":
                failed_count += 1
                failed_items.append({"key": normalized_key, "reason": "同一批次重复密钥，已跳过"})
                continue
            overwrite_count += 1
            success_count += 1
            continue

        existing = existing_by_key.get(normalized_key)
        if existing is not None:
            if payload.duplicate_action == "skip":
                failed_count += 1
                failed_items.append({"key": normalized_key, "reason": "重复密钥，已跳过"})
                continue

            existing.key_type = db_type
            existing.key_sub_type = _resolve_key_sub_type(db_type)
            existing.company_id = company.id if company else None
            existing.product_key_ciphertext = _product_key_cipher.encrypt(normalized_key)
            existing.total_quota = ProductKey.get_default_quota(db_type)
            if db_type in ENTERPRISE_PRODUCT_KEY_TYPES:
                existing.signature = _rsa_sign_pkcs1_v15_sha256(normalized_key.encode("ascii"))
            else:
                existing.signature = None
            overwrite_count += 1
            success_count += 1
            continue

        item = ProductKey(
            id=next_key_id,
            user_id=current_user.id,
            product_key=normalized_key,
            product_key_ciphertext=_product_key_cipher.encrypt(normalized_key),
            key_type=db_type,
            key_sub_type=_resolve_key_sub_type(db_type),
            status="unused",
            company_id=company.id if company else None,
            total_quota=ProductKey.get_default_quota(db_type),
            used_count=0,
            signature=(
                _rsa_sign_pkcs1_v15_sha256(normalized_key.encode("ascii"))
                if db_type in ENTERPRISE_PRODUCT_KEY_TYPES
                else None
            ),
        )
        db.add(item)
        inserted_in_batch.add(normalized_key)
        existing_by_key[normalized_key] = item
        success_count += 1
        next_key_id += 1

    _record_audit_log(
        db,
        actor=current_user,
        request=request,
        operation_type="create",
        target_table="product_keys",
        target_id=None,
        details={
            "action": "batch_import_product_keys",
            "type": payload.type,
            "total": len(payload.keys),
            "success": success_count,
            "failed": failed_count,
            "overwrite": overwrite_count,
            "duplicate_action": payload.duplicate_action,
        },
    )
    db.commit()

    return _ok(
        "批量导入完成",
        {
            "total": len(payload.keys),
            "success_count": success_count,
            "failed_count": failed_count,
            "overwrite_count": overwrite_count,
            "failed_items": failed_items,
        },
    )


@router.get("/users")
def list_admin_users(
    request: Request,
    db: Session = Depends(get_auth_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    role: Optional[str] = Query(default=None),
    status_value: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
):
    _require_super_admin_user(request, db)

    query = db.query(User, Company.name.label("company_name")).outerjoin(Company, Company.id == User.company_id)

    if role:
        query = query.filter(User.role == role.strip())

    if status_value:
        query = query.filter(User.status == status_value.strip().lower())

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(User.username.ilike(pattern), User.email.ilike(pattern)))

    total = query.count()
    rows = (
        query.order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return _ok(
        "用户列表获取成功",
        {
            "users": [_serialize_user(user, company_name=company_name) for user, company_name in rows],
            "pagination": {"page": page, "page_size": page_size, "total": total},
            "total": total,
        },
    )


@router.get("/users/{user_id}")
def get_admin_user_detail(
    user_id: int,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    _require_super_admin_user(request, db)

    user = db.query(User).filter(User.id == user_id).one_or_none()
    if not user:
        raise _fail(status.HTTP_404_NOT_FOUND, "用户不存在")

    company = db.query(Company).filter(Company.id == user.company_id).one_or_none() if user.company_id else None
    devices = (
        db.query(UserDevice)
        .filter(UserDevice.user_id == user.id)
        .order_by(func.coalesce(UserDevice.last_seen_at, UserDevice.created_at).desc(), UserDevice.id.desc())
        .all()
    )
    login_logs = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user.id, AuditLog.operation_type == "login")
        .order_by(AuditLog.operated_at.desc(), AuditLog.id.desc())
        .limit(50)
        .all()
    )

    return _ok(
        "用户详情获取成功",
        {
            "user": _serialize_user(user, company_name=company.name if company else None),
            "company": (
                {"id": company.id, "name": company.name, "status": company.status} if company else None
            ),
            "devices": [
                {
                    "id": item.id,
                    "device_id": item.device_id,
                    "device_name": item.device_name,
                    "platform": item.platform,
                    "is_trusted": bool(item.is_trusted),
                    "last_seen_at": _to_iso(item.last_seen_at),
                    "created_at": _to_iso(item.created_at),
                }
                for item in devices
            ],
            "login_logs": [_serialize_audit_log(item) for item in login_logs],
        },
    )


@router.post("/users/{user_id}/toggle-status")
def toggle_admin_user_status(
    user_id: int,
    payload: UserToggleStatusRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user = _require_super_admin_user(request, db)
    if payload.status not in VALID_USER_STATUS:
        raise _fail(status.HTTP_400_BAD_REQUEST, "status 仅支持 active/disabled")

    user = db.query(User).filter(User.id == user_id).one_or_none()
    if not user or user.status == "deleted":
        raise _fail(status.HTTP_404_NOT_FOUND, "用户不存在")
    if user.id == current_user.id and payload.status == "disabled":
        raise _fail(status.HTTP_400_BAD_REQUEST, "不能禁用当前登录管理员")

    previous_status = user.status
    user.status = payload.status

    blacklisted = False
    if payload.status == "disabled":
        _invalidate_user_tokens(user.id)
        blacklisted = True

    _record_audit_log(
        db,
        actor=current_user,
        request=request,
        operation_type="update",
        target_table="users",
        target_id=str(user.id),
        details={
            "action": "toggle_user_status",
            "from": previous_status,
            "to": payload.status,
            "token_revoked": blacklisted,
        },
    )
    db.commit()

    return _ok("用户状态更新成功", {"user_id": user.id, "status": user.status})


@router.post("/users/{user_id}/reset-password")
def admin_reset_user_password(
    user_id: int,
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    current_user = _require_super_admin_user(request, db)
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if not user or user.status == "deleted":
        raise _fail(status.HTTP_404_NOT_FOUND, "用户不存在")

    temp_password = _generate_temp_password(12)
    new_password_hash = hash_password(temp_password)

    user.password_hash = new_password_hash
    _insert_password_history(db, user_id=user.id, password_hash_value=new_password_hash)
    _invalidate_user_tokens(user.id)

    service = get_auth_service()
    email_result = service.email_service.send_email(
        to_email=user.email,
        subject="UDAKE 管理员已重置你的密码",
        html_content=(
            "<h3>你的账号密码已被管理员重置</h3>"
            f"<p>临时密码：<b>{temp_password}</b></p>"
            "<p>请尽快登录并修改密码。</p>"
        ),
        plain_text=f"你的临时密码为: {temp_password}，请尽快修改。",
        async_send=False,
    )

    _record_audit_log(
        db,
        actor=current_user,
        request=request,
        operation_type="password_change",
        target_table="users",
        target_id=str(user.id),
        details={
            "action": "admin_reset_password",
            "email": user.email,
            "email_delivery_status": email_result.get("status") if isinstance(email_result, dict) else "unknown",
        },
    )
    db.commit()

    return _ok("密码重置成功，已通知用户")


def _build_audit_logs_query(
    db: Session,
    *,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    event_type: Optional[str],
    user_id: Optional[int],
    search: Optional[str],
):
    query = db.query(AuditLog)
    if start_time:
        query = query.filter(AuditLog.operated_at >= start_time)
    if end_time:
        query = query.filter(AuditLog.operated_at <= end_time)
    if event_type:
        query = query.filter(AuditLog.operation_type == event_type)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                AuditLog.actor_username.ilike(pattern),
                AuditLog.target_table.ilike(pattern),
                AuditLog.target_id.ilike(pattern),
                cast(AuditLog.details, String).ilike(pattern),
            )
        )
    return query


@router.get("/audit-logs")
def list_audit_logs(
    request: Request,
    db: Session = Depends(get_auth_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None),
):
    _require_super_admin_user(request, db)

    parsed_start = _parse_time_filter(start_time, field_name="start_time")
    parsed_end = _parse_time_filter(end_time, field_name="end_time")

    query = _build_audit_logs_query(
        db,
        start_time=parsed_start,
        end_time=parsed_end,
        event_type=event_type,
        user_id=user_id,
        search=search,
    )
    total = query.count()
    rows = (
        query.order_by(AuditLog.operated_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return _ok(
        "审计日志查询成功",
        {
            "logs": [_serialize_audit_log(item) for item in rows],
            "pagination": {"page": page, "page_size": page_size, "total": total},
            "total": total,
        },
    )


@router.get("/audit-logs/export")
def export_audit_logs(
    request: Request,
    db: Session = Depends(get_auth_db_session),
    format: Literal["csv", "json"] = Query(...),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
):
    _require_super_admin_user(request, db)

    parsed_start = _parse_time_filter(start_time, field_name="start_time")
    parsed_end = _parse_time_filter(end_time, field_name="end_time")

    rows = (
        _build_audit_logs_query(
            db,
            start_time=parsed_start,
            end_time=parsed_end,
            event_type=event_type,
            user_id=None,
            search=None,
        )
        .order_by(AuditLog.operated_at.desc(), AuditLog.id.desc())
        .limit(AUDIT_EXPORT_LIMIT)
        .all()
    )

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    if format == "json":
        payload = {
            "success": True,
            "message": "审计日志导出成功",
            "data": [_serialize_audit_log(item) for item in rows],
        }
        import json

        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        filename = f"audit_logs_{timestamp}.json"
        return StreamingResponse(
            io.BytesIO(raw),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(
        [
            "id",
            "user_id",
            "actor_username",
            "event_type",
            "target_table",
            "target_id",
            "ip_address",
            "user_agent",
            "operated_at",
            "details",
        ]
    )

    import json

    for row in rows:
        writer.writerow(
            [
                row.id,
                row.user_id,
                row.actor_username,
                row.operation_type,
                row.target_table,
                row.target_id,
                row.ip_address,
                row.user_agent,
                _to_iso(row.operated_at),
                json.dumps(row.details or {}, ensure_ascii=False),
            ]
        )

    raw = csv_buffer.getvalue().encode("utf-8-sig")
    filename = f"audit_logs_{timestamp}.csv"
    return StreamingResponse(
        io.BytesIO(raw),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_user_growth_trend(db: Session, now: datetime) -> List[Dict[str, Any]]:
    start_day = datetime(now.year, now.month, now.day) - timedelta(days=29)
    rows = (
        db.query(func.date(User.created_at).label("day"), func.count(User.id).label("count"))
        .filter(User.created_at >= start_day)
        .group_by(func.date(User.created_at))
        .all()
    )
    day_to_count = {str(day): int(count or 0) for day, count in rows}

    trend: List[Dict[str, Any]] = []
    for i in range(30):
        day = start_day + timedelta(days=i)
        day_text = day.date().isoformat()
        trend.append({"date": day_text, "count": day_to_count.get(day_text, 0)})
    return trend


def _build_stats_payload(db: Session) -> Dict[str, Any]:
    now = datetime.utcnow()
    start_of_today = datetime(now.year, now.month, now.day)

    user_growth_trend = _build_user_growth_trend(db, now)

    total_keys = int(db.query(func.count(ProductKey.id)).scalar() or 0)
    used_keys = int(
        db.query(func.count(ProductKey.id))
        .filter(or_(ProductKey.status.in_(["active", "disabled", "expired"]), ProductKey.used_count > 0))
        .scalar()
        or 0
    )
    unused_keys = max(0, total_keys - used_keys)

    active_users_7d = int(
        db.query(func.count(User.id))
        .filter(
            User.status == "active",
            User.last_login_at.isnot(None),
            User.last_login_at >= (now - timedelta(days=7)),
        )
        .scalar()
        or 0
    )

    total_companies = int(db.query(func.count(Company.id)).scalar() or 0)
    active_companies = int(
        db.query(func.count(Company.id)).filter(Company.status == "active").scalar() or 0
    )

    total_devices = int(db.query(func.count(UserDevice.id)).scalar() or 0)
    online_devices = int(
        db.query(func.count(UserDevice.id))
        .filter(
            UserDevice.last_seen_at.isnot(None),
            UserDevice.last_seen_at >= (now - timedelta(minutes=15)),
        )
        .scalar()
        or 0
    )

    today_registrations = int(
        db.query(func.count(User.id)).filter(User.created_at >= start_of_today).scalar() or 0
    )
    today_logins = int(
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.operation_type == "login", AuditLog.operated_at >= start_of_today)
        .scalar()
        or 0
    )

    return {
        "generated_at": now.isoformat(),
        "user_growth_trend": user_growth_trend,
        "key_usage": {
            "total": total_keys,
            "used": used_keys,
            "unused": unused_keys,
            "usage_rate": round((used_keys / total_keys) * 100, 2) if total_keys else 0,
        },
        "active_users_7d": active_users_7d,
        "company_stats": {
            "total": total_companies,
            "active": active_companies,
        },
        "device_stats": {
            "total": total_devices,
            "online": online_devices,
        },
        "today_registrations": today_registrations,
        "today_logins": today_logins,
    }


@router.get("/stats")
def get_admin_stats(
    request: Request,
    db: Session = Depends(get_auth_db_session),
):
    _require_super_admin_user(request, db)
    cache = get_auth_service().cache

    cached = None
    try:
        cached = cache.get(_STATS_CACHE_KEY)
    except Exception as exc:  # pragma: no cover
        logger.warning("读取统计缓存失败: %s", exc)

    if isinstance(cached, dict) and cached:
        return _ok("统计数据获取成功", {**cached, "cached": True})

    stats_payload = _build_stats_payload(db)
    try:
        cache.set(_STATS_CACHE_KEY, stats_payload, ttl=STATS_CACHE_TTL_SECONDS)
    except Exception as exc:  # pragma: no cover
        logger.warning("写入统计缓存失败: %s", exc)

    return _ok("统计数据获取成功", {**stats_payload, "cached": False})
