"""Company admin role split, key expiry, and reminder helpers."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from ..auth_db.models import ProductKey, User

logger = logging.getLogger(__name__)

COMPANY_ADMIN_TYPE_TRIAL = "trial"
COMPANY_ADMIN_TYPE_STANDARD = "standard"
COMPANY_ADMIN_LIMITS: Dict[str, int] = {
    COMPANY_ADMIN_TYPE_TRIAL: 500,
    COMPANY_ADMIN_TYPE_STANDARD: 1000,
}
COMPANY_ADMIN_ALLOWED_KEY_TYPES: Dict[str, set[str]] = {
    COMPANY_ADMIN_TYPE_TRIAL: {"enterprise_trial"},
    COMPANY_ADMIN_TYPE_STANDARD: {"enterprise_trial", "enterprise_standard"},
}
ENTERPRISE_KEY_VALID_DAYS: Dict[str, int] = {
    "enterprise_trial": 365,
    "enterprise_standard": 1095,
}
_REMINDER_LEAD_DAYS = 30


@dataclass(frozen=True)
class CompanyAdminQuotaPolicy:
    admin_type: str
    total_limit: int
    allowed_key_types: set[str]
    total_keys_created: int

    @property
    def remaining(self) -> int:
        return max(0, self.total_limit - self.total_keys_created)


def utcnow() -> datetime:
    # auth_db 在 SQLite/部分驱动下常返回 naive datetime，这里统一使用 naive UTC
    return datetime.utcnow()


def is_datetime_expired(expires_at: Optional[datetime], *, now: Optional[datetime] = None) -> bool:
    if not expires_at:
        return False
    current = now or utcnow()
    if expires_at.tzinfo is None and current.tzinfo is not None:
        current = current.replace(tzinfo=None)
    elif expires_at.tzinfo is not None and current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return expires_at <= current


def normalize_company_admin_type(raw: Optional[str]) -> Optional[str]:
    text = str(raw or "").strip().lower()
    if text in {COMPANY_ADMIN_TYPE_TRIAL, COMPANY_ADMIN_TYPE_STANDARD}:
        return text
    return None


def resolve_company_admin_type_from_key_type(key_type: str) -> Optional[str]:
    normalized = str(key_type or "").strip().lower()
    if normalized == "enterprise_trial":
        return COMPANY_ADMIN_TYPE_TRIAL
    if normalized == "enterprise_standard":
        return COMPANY_ADMIN_TYPE_STANDARD
    return None


def compute_key_expires_at(key_type: str, base_time: Optional[datetime] = None) -> Optional[datetime]:
    days = ENTERPRISE_KEY_VALID_DAYS.get(str(key_type or "").strip().lower())
    if days is None:
        return None
    now = base_time or utcnow()
    return now + timedelta(days=days)


def resolve_company_admin_policy(user: User) -> CompanyAdminQuotaPolicy:
    admin_type = normalize_company_admin_type(getattr(user, "company_admin_type", None)) or COMPANY_ADMIN_TYPE_STANDARD
    total_keys_created = max(0, int(getattr(user, "total_keys_created", 0) or 0))
    return CompanyAdminQuotaPolicy(
        admin_type=admin_type,
        total_limit=COMPANY_ADMIN_LIMITS[admin_type],
        allowed_key_types=set(COMPANY_ADMIN_ALLOWED_KEY_TYPES[admin_type]),
        total_keys_created=total_keys_created,
    )


def sync_company_admin_role_by_key(user: User, key: ProductKey) -> None:
    next_type = resolve_company_admin_type_from_key_type(str(getattr(key, "key_type", "")))
    if not next_type:
        return
    current_type = normalize_company_admin_type(getattr(user, "company_admin_type", None))
    if current_type != next_type:
        user.company_admin_type = next_type
    if not getattr(user, "company_admin_key_id", None):
        user.company_admin_key_id = key.id


def mark_expired_product_keys(db: Session, *, now: Optional[datetime] = None) -> Dict[str, int]:
    current = now or utcnow()
    rows: Sequence[ProductKey] = (
        db.query(ProductKey)
        .filter(
            ProductKey.expires_at.isnot(None),
            ProductKey.expires_at <= current,
            ProductKey.status != "expired",
        )
        .all()
    )
    if not rows:
        return {"expired_keys": 0, "expired_related_keys": 0}

    expired_ids = {row.id for row in rows}
    expired_related = 0
    for row in rows:
        row.status = "expired"
        # 企业主密钥过期时，失效其显式关联的子密钥（通过 key_metadata.parent_key_id / root_key_id）。
        if str(row.key_type).startswith("enterprise_") and row.company_id:
            related = (
                db.query(ProductKey)
                .filter(
                    ProductKey.company_id == row.company_id,
                    ProductKey.id != row.id,
                    ProductKey.status != "expired",
                )
                .all()
            )
            for item in related:
                try:
                    metadata = json.loads(item.key_metadata or "{}")
                except Exception:
                    metadata = {}
                parent_id = metadata.get("parent_key_id") or metadata.get("root_key_id")
                try:
                    matched = int(parent_id) == int(row.id)
                except Exception:
                    matched = False
                if not matched:
                    continue
                item.status = "expired"
                if item.id not in expired_ids:
                    expired_related += 1
                    expired_ids.add(item.id)
    return {"expired_keys": len(rows), "expired_related_keys": expired_related}


def _iter_super_admin_emails() -> Iterable[str]:
    raw = os.getenv("AUTH_SUPER_ADMIN_EMAILS", "")
    for item in raw.split(","):
        email = item.strip().lower()
        if email and "@" in email:
            yield email


def send_expiry_reminders(
    db: Session,
    *,
    auth_service: Any,
    now: Optional[datetime] = None,
) -> Dict[str, int]:
    current = now or utcnow()
    threshold = current + timedelta(days=_REMINDER_LEAD_DAYS)
    rows: Sequence[ProductKey] = (
        db.query(ProductKey)
        .filter(
            ProductKey.key_type.in_(tuple(ENTERPRISE_KEY_VALID_DAYS.keys())),
            ProductKey.expires_at.isnot(None),
            ProductKey.expires_at > current,
            ProductKey.expires_at <= threshold,
            ProductKey.status != "expired",
        )
        .all()
    )
    if not rows:
        return {"candidates": 0, "sent": 0, "skipped": 0, "failed": 0}

    sent = 0
    skipped = 0
    failed = 0
    day_flag = current.strftime("%Y%m%d")

    for key in rows:
        dedup_key = f"company_key_expiry_reminder:{key.id}:{day_flag}"
        if auth_service.cache.get(dedup_key):
            skipped += 1
            continue

        admin_emails = [
            item.email
            for item in (
                db.query(User.email)
                .filter(
                    User.role == "company_admin",
                    User.status == "active",
                    User.company_id == key.company_id,
                )
                .all()
            )
            if item.email
        ]
        recipients = list(dict.fromkeys([*admin_emails, *_iter_super_admin_emails()]))
        if not recipients:
            skipped += 1
            auth_service.cache.set(dedup_key, {"status": "no_recipient"}, ttl=36 * 60 * 60)
            continue

        exp = key.expires_at
        if exp and exp.tzinfo is not None:
            expires_text = exp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            expires_text = (exp or current).strftime("%Y-%m-%d %H:%M:%S UTC")
        subject = "密钥即将到期提醒"
        html = (
            "<h3>密钥即将到期提醒</h3>"
            f"<p>密钥ID：{key.id}</p>"
            f"<p>密钥类型：{key.key_type}</p>"
            f"<p>过期时间：{expires_text}</p>"
            "<p>影响范围：该企业密钥及其下所有企业内密钥可能被自动失效。</p>"
            "<p>建议：请提前联系系统管理员完成续期或更换密钥。</p>"
        )

        had_error = False
        for recipient in recipients:
            try:
                auth_service.email_service.send_email(
                    to_email=recipient,
                    subject=subject,
                    html_content=html,
                    async_send=True,
                )
                sent += 1
            except Exception as exc:  # pragma: no cover - external SMTP errors
                had_error = True
                failed += 1
                logger.warning("发送密钥过期提醒失败 key_id=%s to=%s err=%s", key.id, recipient, exc)

        auth_service.cache.set(
            dedup_key,
            {"status": "partial_failed" if had_error else "ok", "recipients": len(recipients)},
            ttl=36 * 60 * 60,
        )
    return {"candidates": len(rows), "sent": sent, "skipped": skipped, "failed": failed}
