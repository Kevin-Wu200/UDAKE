"""密钥申请工单系统 API。"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..auth import JWTValidationError, ProductKeyRegistry, get_auth_service, hash_password
from ..auth_db.models import AuditLog, Company, ProductKey, Ticket, TicketStatus, TicketType, User
from ..auth_db.session import get_auth_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets")

PRODUCT_KEY_TYPES = {
    "personal_trial",
    "personal_standard",
    "enterprise_trial",
    "enterprise_standard",
}

# 密钥类型的中文显示名称映射
KEY_TYPE_DISPLAY_NAMES = {
    "personal_trial": "个人试用版",
    "personal_standard": "个人标准版",
    "enterprise_trial": "企业试用版",
    "enterprise_standard": "企业标准版",
}
_DIGEST_INFO_SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
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
from ..utils.email_service import ticket_email_service as email_service
_key_registry = ProductKeyRegistry()


class TicketCreateRequest(BaseModel):
    ticket_type: str = Field(..., description="工单类型")
    email: str = Field(..., max_length=255, description="邮箱")
    phone: str = Field(..., max_length=20, description="电话号码")
    industry: str = Field(..., max_length=100, description="所处行业")
    organization: str = Field(..., max_length=128, description="所属单位")
    usage_purpose: str = Field(..., min_length=1, description="用途说明")
    key_type: str = Field(..., description="密钥类型")
    existing_key: Optional[str] = Field(default=None, max_length=100, description="需延期密钥")


class TicketResponse(BaseModel):
    id: int
    ticket_id: str
    ticket_type: str
    status: str
    email: str
    phone: str
    industry: str
    organization: str
    usage_purpose: str
    key_type: str
    existing_key: Optional[str] = None
    assigned_key: Optional[str] = None
    approval_notes: Optional[str] = None
    response_message: Optional[str] = None
    processed_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TicketUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None, description="工单状态")
    approval_notes: Optional[str] = Field(default=None, description="审批备注")


class TicketApprovalRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=2000, description="审批备注")
    reason: Optional[str] = Field(default=None, max_length=2000, description="拒绝原因")


def success_response(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"success": True, "message": message, "data": data or {}}


def error_response(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"success": False, "message": message, "data": data or {}}


def _fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=error_response(message))


def validate_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if not normalized:
        raise _fail(status.HTTP_400_BAD_REQUEST, "邮箱不能为空")
    if not Ticket.EMAIL_PATTERN.match(normalized):
        raise _fail(status.HTTP_400_BAD_REQUEST, "邮箱格式不正确")
    return normalized


def validate_phone(phone: str) -> str:
    normalized = (phone or "").strip()
    if not normalized:
        raise _fail(status.HTTP_400_BAD_REQUEST, "手机号不能为空")
    if not Ticket.PHONE_PATTERN.match(normalized):
        raise _fail(status.HTTP_400_BAD_REQUEST, "手机号格式不正确")
    return normalized


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
        parts = [segment for segment in ip_address.split(":") if segment]
        if len(parts) >= 2:
            return f"{parts[0]}:{parts[1]}:*:*"
        return "*:*"
    parts = ip_address.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.*"
    return ip_address


def _verify_access_token(request: Request) -> Dict[str, Any]:
    token = _extract_bearer_token(request)
    service = get_auth_service()
    try:
        return service.jwt.verify_token(token, expected_type="access", check_blacklist=True)
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


def _get_authenticated_user(request: Request, db: Session) -> User:
    payload = _verify_access_token(request)
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
    return user


def require_super_admin(handler):
    """超级管理员权限验证装饰器。"""

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
        if current_user.role not in {"super_admin", "admin"}:
            raise _fail(status.HTTP_403_FORBIDDEN, "权限不足，仅管理员可访问")
        request.state.current_user = current_user
        return handler(*args, **kwargs)

    return wrapper


def require_company_authorized(handler):
    """企业管理员权限验证装饰器。
    支持 super_admin (全量权限) 和 admin (所属企业权限)。
    """

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
        # 支持超级管理员和企业管理员
        if current_user.role not in {"super_admin", "admin"}:
            raise _fail(status.HTTP_403_FORBIDDEN, "权限不足，仅企业管理员或系统管理员可访问")

        # 如果是普通管理员，必须有关联的企业
        if current_user.role == "admin" and not current_user.company_id:
            raise _fail(status.HTTP_403_FORBIDDEN, "管理员账号未关联企业，请联系系统管理员")

        request.state.current_user = current_user
        return handler(*args, **kwargs)

    return wrapper


def _next_model_id(db: Session, model_cls: Any) -> int:
    return int((db.query(func.max(model_cls.id)).scalar() or 0) + 1)


def _normalize_datetime(value: Any) -> Optional[str]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.isoformat()
    return value.astimezone(timezone.utc).isoformat()


def generate_ticket_response(ticket: Ticket, *, hide_processor: bool = False) -> Dict[str, Any]:
    payload = TicketResponse(
        id=int(ticket.id),
        ticket_id=ticket.ticket_id,
        ticket_type=ticket.ticket_type,
        status=ticket.status,
        email=ticket.email,
        phone=ticket.phone,
        industry=ticket.industry,
        organization=ticket.organization,
        usage_purpose=ticket.usage_purpose,
        key_type=ticket.key_type,
        existing_key=ticket.existing_key,
        assigned_key=ticket.assigned_key,
        approval_notes=ticket.approval_notes,
        response_message=ticket.response_message,
        processed_at=_normalize_datetime(ticket.processed_at),
        created_at=_normalize_datetime(ticket.created_at),
        updated_at=_normalize_datetime(ticket.updated_at),
    ).model_dump()
    if not hide_processor:
        payload["processed_by"] = ticket.processed_by
    return payload


def validate_usage_purpose(purpose: str) -> bool:
    """校验用途说明：不低于15个中文字符 或 不低于50个英文字符 (均不包含标点符号)。"""
    import re
    # 匹配中文字符
    chinese_chars = re.findall(r'[\u4e00-\u9fa5]', purpose)
    # 匹配英文字符
    english_chars = re.findall(r'[a-zA-Z]', purpose)
    
    return len(chinese_chars) >= 15 or len(english_chars) >= 50


def validate_organization(industry: str, organization: str) -> bool:
    """校验所属单位：结合选择的"所处行业"校验合法性。"""
    org_lower = organization.lower()
    if industry == "教育":
        return any(k in org_lower for k in ["学院", "大学", "university", "college"])
    else:
        # 增加对英文单位关键字的支持：'group', 'company', 'institute' 等
        keywords = ["集团", "公司", "局", "中心", "院", "所", "group", "company", "institute", "corp", "inc"]
        return any(keyword in org_lower for keyword in keywords)


def _resolve_ticket(ticket_id_str: str, db: Session) -> Ticket:
    """根据传入的工单标识符查询工单。
    
    支持两种格式：
    - 以 TKT- 开头：按 ticket_id 字段查询（面向公众查询）
    - 纯数字：按 id 主键查询（面向管理后台）
    """
    if ticket_id_str.upper().startswith("TKT-"):
        ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id_str).one_or_none()
    else:
        try:
            numeric_id = int(ticket_id_str)
        except ValueError:
            raise _fail(status.HTTP_404_NOT_FOUND, "工单不存在（无效的工单ID格式）")
        ticket = db.query(Ticket).filter(Ticket.id == numeric_id).one_or_none()
    if not ticket:
        raise _fail(status.HTTP_404_NOT_FOUND, "工单不存在")
    return ticket


def verify_ticket_access(ticket_id_str: str, email: str, db: Session) -> Ticket:
    """公开查询：通过 ticket_id（TKT-XXXXXXXX 格式）和邮箱验证访问权限。"""
    ticket = _resolve_ticket(ticket_id_str, db)
    if ticket.email.lower() != validate_email(email):
        raise _fail(status.HTTP_403_FORBIDDEN, "邮箱验证失败，无权访问该工单")
    return ticket


def _resolve_key_sub_type(key_type: str) -> str:
    return "trial" if key_type.endswith("_trial") else "standard"


def _resolve_company_for_ticket(db: Session, organization: str) -> Company:
    company_name = organization.strip()
    company = db.query(Company).filter(Company.name == company_name).one_or_none()
    if company:
        return company
    company = Company(id=_next_model_id(db, Company), name=company_name, status="active")
    db.add(company)
    db.flush()
    return company


def _generate_temp_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(ch.islower() for ch in candidate)
            and any(ch.isupper() for ch in candidate)
            and any(ch.isdigit() for ch in candidate)
            and any(ch in "!@#$%^&*()-_=+" for ch in candidate)
        ):
            return candidate


def _resolve_or_create_ticket_user(db: Session, ticket: Ticket, company_id: Optional[int]) -> User:
    existing = db.query(User).filter(User.email == ticket.email).one_or_none()
    if existing:
        if company_id and not existing.company_id:
            existing.company_id = company_id
            db.flush()
        return existing

    base_name = ticket.email.split("@", 1)[0][:32] or "ticket_user"
    username = base_name
    suffix = 1
    while db.query(User).filter(User.username == username).one_or_none():
        suffix += 1
        username = f"{base_name[:28]}_{suffix}"

    user = User(
        id=_next_model_id(db, User),
        username=username,
        email=ticket.email,
        password_hash=hash_password(_generate_temp_password()),
        role="user",
        status="pending",
        company_id=company_id,
        is_email_verified=False,
    )
    db.add(user)
    db.flush()
    return user


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


def handle_key_request(ticket: Ticket, db: Session) -> str:
    company = None
    company_id = ticket.company_id
    company_name = None
    
    if ticket.key_type.startswith("enterprise_"):
        if company_id:
            company = db.query(Company).filter(Company.id == company_id).one_or_none()
        
        if not company:
            company = _resolve_company_for_ticket(db, ticket.organization)
            company_id = company.id
            ticket.company_id = company_id
            
        company_name = company.name

    user = _resolve_or_create_ticket_user(db, ticket, company_id)
    record = _key_registry.generate_key(
        key_type=ticket.key_type,
        user_id=user.id if not ticket.key_type.startswith("enterprise_") else None,
        company_id=company_id,
        company_name=company_name,
        metadata={"ticket_id": ticket.id, "ticket_type": ticket.ticket_type, "email": ticket.email},
    )
    normalized_key = record.product_key.strip().upper()
    product_key = ProductKey(
        id=_next_model_id(db, ProductKey),
        user_id=user.id,
        company_id=company_id,
        product_key=normalized_key,
        key_type=record.key_type,
        key_sub_type=_resolve_key_sub_type(record.key_type),
        status="unused",
        total_quota=record.total_quota,
        used_count=0,
        generation_seed=record.generation_seed,
        key_metadata=json.dumps(record.metadata or {}, ensure_ascii=False),
        signature=(
            _rsa_sign_pkcs1_v15_sha256(normalized_key.encode("ascii"))
            if record.key_type.startswith("enterprise_")
            else None
        ),
        expires_at=datetime.now(timezone.utc) + timedelta(days=90),
    )
    db.add(product_key)
    db.flush()
    ticket.assigned_key = normalized_key
    key_display = KEY_TYPE_DISPLAY_NAMES.get(ticket.key_type, ticket.key_type)
    ticket.response_message = f"工单已审批通过，已为您分配新的{key_display}密钥。"
    logger.info("工单审批生成新密钥 ticket_id=%s product_key_id=%s", ticket.id, product_key.id)
    return normalized_key


def handle_key_extension(ticket: Ticket, db: Session) -> str:
    existing_key = (ticket.existing_key or "").strip().upper()
    if not existing_key:
        raise _fail(status.HTTP_400_BAD_REQUEST, "延期工单必须提供 existing_key")

    product_key = db.query(ProductKey).filter(ProductKey.product_key == existing_key).one_or_none()
    if not product_key:
        raise _fail(status.HTTP_404_NOT_FOUND, "待延期密钥不存在")

    base_time = product_key.expires_at or datetime.now(timezone.utc)
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)
    product_key.expires_at = base_time + timedelta(days=90)
    ticket.assigned_key = product_key.product_key
    ticket.response_message = "工单已审批通过，原密钥有效期已延长90天。"
    logger.info("工单审批完成密钥延期 ticket_id=%s product_key_id=%s", ticket.id, product_key.id)
    return product_key.product_key


def _record_audit_log(
    db: Session,
    *,
    user: Optional[User],
    request: Request,
    operation_type: str,
    target_id: Optional[str],
    success: bool,
    details: Optional[Dict[str, Any]] = None,
    failure_reason: Optional[str] = None,
) -> None:
    try:
        audit = AuditLog(
            id=_next_model_id(db, AuditLog),
            user_id=user.id if user else None,
            actor_username=user.username if user else "anonymous",
            operation_type=operation_type,
            target_table="tickets",
            target_id=target_id,
            ip_address=_extract_client_ip(request),
            ip_address_masked=_mask_ip(_extract_client_ip(request)),
            user_agent=request.headers.get("user-agent"),
            request_id=request.headers.get("x-request-id") or uuid.uuid4().hex[:12],
            success=success,
            failure_reason=failure_reason,
            details=details or {},
        )
        db.add(audit)
        db.flush()
    except Exception as exc:  # pragma: no cover
        logger.warning("记录工单审计日志失败: %s", exc)


@router.post(
    "",
    summary="创建密钥申请工单",
    description="无需登录即可访问，使用邮箱作为身份标识，后续查询需提供相同邮箱完成身份验证。",
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
)
def create_ticket(
    payload: TicketCreateRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, Any]:
    """创建工单。无需登录即可访问，使用邮箱作为身份标识，后续查询需验证邮箱。"""
    ticket_type = (payload.ticket_type or "").strip()
    key_type = (payload.key_type or "").strip()
    if ticket_type not in {member.value for member in TicketType}:
        raise _fail(status.HTTP_400_BAD_REQUEST, "ticket_type 不合法")
    if key_type not in PRODUCT_KEY_TYPES:
        raise _fail(status.HTTP_400_BAD_REQUEST, "key_type 不合法")

    email = validate_email(payload.email)
    phone = validate_phone(payload.phone)
    industry = (payload.industry or "").strip()
    organization = (payload.organization or "").strip()
    usage_purpose = (payload.usage_purpose or "").strip()

    if not industry:
        raise _fail(status.HTTP_400_BAD_REQUEST, "industry 不能为空")
    if not organization:
        raise _fail(status.HTTP_400_BAD_REQUEST, "organization 不能为空")
    if not usage_purpose:
        raise _fail(status.HTTP_400_BAD_REQUEST, "usage_purpose 不能为空")

    # 业务校验
    if not validate_usage_purpose(usage_purpose):
        raise _fail(status.HTTP_400_BAD_REQUEST, "用途说明字数不符合要求（至少15个中文字符或50个英文字符，不含标点）")

    if not validate_organization(industry, organization):
        if industry == "教育":
            raise _fail(status.HTTP_400_BAD_REQUEST, "教育行业所属单位应包含'学院'或'大学'")
        else:
            raise _fail(status.HTTP_400_BAD_REQUEST, "所属单位名称不规范（应包含'集团'、'公司'、'单位'等关键词）")

    existing_key = (payload.existing_key or "").strip().upper() or None
    if ticket_type == TicketType.KEY_EXTENSION.value and not existing_key:
        raise _fail(status.HTTP_400_BAD_REQUEST, "key_extension 工单必须提供 existing_key")
    if ticket_type == TicketType.KEY_REQUEST.value and existing_key:
        raise _fail(status.HTTP_400_BAD_REQUEST, "key_request 工单不允许提供 existing_key")

    # 自动关联公司 ID
    company_id = None
    company = db.query(Company).filter(Company.name == organization).first()
    if company:
        company_id = company.id
    else:
        # 尝试通过邮箱域名匹配 (可选增强)
        email_domain = email.split("@")[-1]
        if email_domain not in {"gmail.com", "outlook.com", "qq.com", "163.com", "sina.com"}:
             # 简单匹配，实际项目中可能需要更复杂的域名归属表
             pass

    try:
        # 生成 TKT-XXXXXXXX 格式的 ID
        import secrets
        random_suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        ticket_id = f"TKT-{random_suffix}"
        
        ticket = Ticket(
            id=_next_model_id(db, Ticket),
            ticket_id=ticket_id,
            ticket_type=ticket_type,
            status=TicketStatus.PENDING.value,
            email=email,
            phone=phone,
            industry=industry,
            organization=organization,
            usage_purpose=usage_purpose,
            key_type=key_type,
            existing_key=existing_key,
            company_id=company_id,
        )
        db.add(ticket)
        db.flush()
        try:
            email_service.send_ticket_notification(ticket, "submitted")
        except Exception as e:
            logger.error("发送创建工单通知邮件失败: %s", e)
        _record_audit_log(
            db,
            user=None,
            request=request,
            operation_type="create",
            target_id=str(ticket.id),
            success=True,
            details={"ticket_id": ticket.ticket_id, "ticket_type": ticket_type, "email": email, "key_type": key_type},
        )
        db.commit()
        db.refresh(ticket)
        logger.info("创建工单成功 ticket_id=%s db_id=%s email=%s", ticket.ticket_id, ticket.id, email)
        return success_response(
            "工单创建成功",
            {
                "ticket_id": ticket.ticket_id,
                "ticket": generate_ticket_response(ticket, hide_processor=True),
                "created_at": _normalize_datetime(ticket.created_at),
            },
        )
    except Exception as exc:
        db.rollback()
        logger.error("创建工单过程中发生异常，详情: %s", str(exc), exc_info=True)
        raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, f"数据库错误: {exc}") from exc


@router.get(
    "",
    summary="查询工单列表",
    description="仅系统管理员或企业管理员可访问，系统管理员可查看全量，企业管理员仅可查看其所属企业工单。",
    responses={
        401: {"description": "未认证"},
        403: {"description": "权限不足"},
        500: {"description": "服务器内部错误"},
    },
)
@require_company_authorized
def list_tickets(
    request: Request,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    ticket_type: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, Any]:
    current_user = request.state.current_user
    try:
        query = db.query(Ticket)

        # 权限过滤：非超级管理员只能看到自己公司的工单
        if current_user.role != "super_admin":
            query = query.filter(Ticket.company_id == current_user.company_id)

        if status_filter:
            normalized_status = status_filter.strip()
            if normalized_status not in {item.value for item in TicketStatus}:
                raise _fail(status.HTTP_400_BAD_REQUEST, "status 不合法")
            query = query.filter(Ticket.status == normalized_status)
        if ticket_type:
            normalized_type = ticket_type.strip()
            if normalized_type not in {item.value for item in TicketType}:
                raise _fail(status.HTTP_400_BAD_REQUEST, "ticket_type 不合法")
            query = query.filter(Ticket.ticket_type == normalized_type)

        total = query.count()
        rows = (
            query.order_by(Ticket.created_at.desc(), Ticket.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        _record_audit_log(
            db,
            user=current_user,
            request=request,
            operation_type="read",
            target_id=None,
            success=True,
            details={"scope": "list", "page": page, "page_size": page_size, "total": total},
        )
        db.commit()
        logger.info("超级管理员查询工单列表 user_id=%s total=%s", current_user.id, total)
        return success_response(
            "工单列表查询成功",
            {
                "tickets": [generate_ticket_response(item) for item in rows],
                "pagination": {"page": page, "page_size": page_size, "total": total},
                "total": total,
            },
        )
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("查询工单列表失败: %s", exc)
        raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, f"数据库错误: {exc}") from exc


@router.get(
    "/{ticket_id}",
    summary="查询单个工单",
    description="支持两种认证方式：1) 管理员 Bearer Token 认证（无需邮箱）；2) 邮箱公开查询。",
    responses={
        400: {"description": "缺少邮箱参数且未提供管理员Token"},
        401: {"description": "Token无效"},
        403: {"description": "邮箱校验失败或无权限"},
        404: {"description": "工单不存在"},
        500: {"description": "服务器内部错误"},
    },
)
def get_ticket(
    ticket_id: str,
    request: Request,
    email: Optional[str] = Query(default=None, description="邮箱，用于公开查询的身份验证，管理员Token认证时可不填"),
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, Any]:
    try:
        # 尝试通过 Bearer Token 认证（管理员可直接查看工单）
        current_user = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                current_user = _get_authenticated_user(request, db)
                if current_user.role not in {"super_admin", "admin"}:
                    # 非管理员角色，降级为邮箱校验
                    current_user = None
            except HTTPException:
                # Token 无效，降级为邮箱校验
                current_user = None

        if current_user is not None:
            # 管理员 Token 认证：直接查询工单（支持 TKT-XXXXXXXX 格式或数字ID）
            ticket = _resolve_ticket(ticket_id, db)
            # 非超级管理员只能查看自己公司的工单
            if current_user.role != "super_admin" and ticket.company_id != current_user.company_id:
                raise _fail(status.HTTP_403_FORBIDDEN, "无权访问该工单")
            _record_audit_log(
                db,
                user=current_user,
                request=request,
                operation_type="read",
                target_id=str(ticket.id),
                success=True,
                details={"scope": "detail", "auth": "token", "user_id": current_user.id},
            )
            db.commit()
            logger.info("管理员查询工单详情 user_id=%s ticket_id=%s", current_user.id, ticket.id)
            return success_response("工单详情查询成功", {"ticket": generate_ticket_response(ticket, hide_processor=False)})
        else:
            # 邮箱公开查询
            if not email:
                raise _fail(status.HTTP_400_BAD_REQUEST, "请提供邮箱参数，或使用管理员Token认证")
            ticket = verify_ticket_access(ticket_id, email, db)
            _record_audit_log(
                db,
                user=None,
                request=request,
                operation_type="read",
                target_id=str(ticket.id),
                success=True,
                details={"scope": "detail", "email": validate_email(email)},
            )
            db.commit()
            logger.info("公开查询工单详情成功 ticket_id=%s", ticket.id)
            return success_response("工单详情查询成功", {"ticket": generate_ticket_response(ticket, hide_processor=True)})
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("查询工单详情失败: %s", exc)
        raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, f"数据库错误: {exc}") from exc


@router.put(
    "/{ticket_id}/approve",
    summary="审批通过工单",
    description="仅系统管理员或企业管理员可访问。审批通过后会根据工单类型自动生成新密钥或将现有密钥延期90天。",
    responses={
        400: {"description": "工单状态错误或审批参数错误"},
        401: {"description": "未认证"},
        403: {"description": "权限不足"},
        404: {"description": "工单或密钥不存在"},
        500: {"description": "审批处理失败"},
    },
)
@require_company_authorized
def approve_ticket(
    ticket_id: int,
    payload: TicketApprovalRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, Any]:
    current_user = request.state.current_user
    try:
        query = db.query(Ticket).filter(Ticket.id == ticket_id)
        if current_user.role != "super_admin":
            query = query.filter(Ticket.company_id == current_user.company_id)
        
        ticket = query.with_for_update().one_or_none()
        if not ticket:
            raise _fail(status.HTTP_404_NOT_FOUND, "工单不存在或无权访问")
        if ticket.status != TicketStatus.PENDING.value:
            raise _fail(status.HTTP_400_BAD_REQUEST, "仅 pending 状态工单允许审批")

        notes = (payload.notes or "").strip() or None
        ticket.status = TicketStatus.APPROVED.value
        ticket.processed_by = current_user.id
        ticket.processed_at = datetime.now(timezone.utc)
        ticket.approval_notes = notes
        db.flush()

        assigned_key = (
            handle_key_request(ticket, db)
            if ticket.ticket_type == TicketType.KEY_REQUEST.value
            else handle_key_extension(ticket, db)
        )
        ticket.status = TicketStatus.COMPLETED.value
        db.flush()
        _record_audit_log(
            db,
            user=current_user,
            request=request,
            operation_type="update",
            target_id=str(ticket.id),
            success=True,
            details={"action": "approve", "assigned_key": assigned_key, "ticket_type": ticket.ticket_type},
        )
        db.commit()
        db.refresh(ticket)
        try:
            email_service.send_ticket_notification(
                ticket, 
                "approved", 
                {"assigned_key": assigned_key, "approval_notes": notes}
            )
        except Exception as e:
            logger.error("发送审批通过通知邮件失败: %s", e)
        logger.info("审批通过工单成功 ticket_id=%s processor_id=%s", ticket.id, current_user.id)
        return success_response(
            "工单审批通过",
            {"ticket": generate_ticket_response(ticket), "assigned_key": assigned_key},
        )
    except HTTPException:
        db.rollback()
        raise
    except (ValueError, SQLAlchemyError) as exc:
        db.rollback()
        logger.exception("审批通过工单失败: %s", exc)
        raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, f"审批失败: {exc}") from exc


@router.put(
    "/{ticket_id}/reject",
    summary="拒绝工单",
    description="仅系统管理员或企业管理员可访问。拒绝时必须提供拒绝原因，系统会记录处理人与处理结果。",
    responses={
        400: {"description": "缺少拒绝原因或工单状态错误"},
        401: {"description": "未认证"},
        403: {"description": "权限不足"},
        404: {"description": "工单不存在"},
        500: {"description": "审批处理失败"},
    },
)
@require_company_authorized
def reject_ticket(
    ticket_id: int,
    payload: TicketApprovalRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, Any]:
    current_user = request.state.current_user
    reason = (payload.reason or "").strip()
    if not reason:
        raise _fail(status.HTTP_400_BAD_REQUEST, "拒绝原因不能为空")
    try:
        query = db.query(Ticket).filter(Ticket.id == ticket_id)
        if current_user.role != "super_admin":
            query = query.filter(Ticket.company_id == current_user.company_id)

        ticket = query.with_for_update().one_or_none()
        if not ticket:
            raise _fail(status.HTTP_404_NOT_FOUND, "工单不存在或无权访问")
        if ticket.status != TicketStatus.PENDING.value:
            raise _fail(status.HTTP_400_BAD_REQUEST, "仅 pending 状态工单允许拒绝")

        ticket.status = TicketStatus.REJECTED.value
        ticket.processed_by = current_user.id
        ticket.processed_at = datetime.now(timezone.utc)
        ticket.approval_notes = reason
        ticket.response_message = f"工单已被拒绝：{reason}"
        db.flush()
        _record_audit_log(
            db,
            user=current_user,
            request=request,
            operation_type="update",
            target_id=str(ticket.id),
            success=True,
            details={"action": "reject", "reason": reason},
        )
        db.commit()
        db.refresh(ticket)
        try:
            email_service.send_ticket_notification(
                ticket, 
                "rejected", 
                {"rejection_reason": reason}
            )
        except Exception as e:
            logger.error("发送审批拒绝通知邮件失败: %s", e)
        logger.info("拒绝工单成功 ticket_id=%s processor_id=%s", ticket.id, current_user.id)
        return success_response("工单已拒绝", {"ticket": generate_ticket_response(ticket)})
    except HTTPException:
        db.rollback()
        raise
    except (ValueError, SQLAlchemyError) as exc:
        db.rollback()
        logger.exception("拒绝工单失败: %s", exc)
        raise _fail(status.HTTP_500_INTERNAL_SERVER_ERROR, f"审批失败: {exc}") from exc
