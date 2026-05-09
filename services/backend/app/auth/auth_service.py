"""Application-level authentication service."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from sqlalchemy import func

from .cache import AuthCacheManager
from .input_sanitizer import ensure_safe_text
from .ip_control import IPAccessController
from .email_service import SMTPEmailService
from .email_templates import EmailTemplateManager
from .jwt_service import JWTManager, JWTValidationError
from .product_key_service import ProductKeyRecord, ProductKeyRegistry, ProductKeyValidationError
from .rate_limiter import AuthRateLimiter, RateLimitExceededError
from .security import SensitiveDataCipher, hash_password, verify_password
from .verification import EmailVerificationService, VerificationCodeError

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")
SUSPICIOUS_UA_KEYWORDS = ("bot", "spider", "crawler", "curl", "wget", "python-requests", "selenium", "scrapy")
UNKNOWN_LOCATION = "未知"
DEVICE_INACTIVE_AFTER_SECONDS = 30 * 24 * 60 * 60


@dataclass
class AuthUser:
    id: int
    email: str
    username: str = ""
    password_hash: str = ""
    role: str = "user"
    permissions: List[str] = field(default_factory=list)
    status: str = "active"
    created_at: int = field(default_factory=lambda: int(time.time()))
    last_login_at: Optional[int] = None
    is_email_verified: bool = False
    failed_login_attempts: int = 0
    lock_until: Optional[int] = None
    lock_reason: Optional[str] = None
    enterprise_id: Optional[int] = None


@dataclass
class UserDeviceSession:
    user_id: int
    device_id: str
    fingerprint: str
    refresh_token_hash: str
    device_name: Optional[str] = None
    device_type: str = "unknown"
    os_name: str = "Unknown"
    browser: str = "Unknown"
    ip_address: Optional[str] = None
    location: Optional[str] = None
    user_agent: Optional[str] = None
    status: str = "active"
    tokens: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time()))
    last_login_at: int = field(default_factory=lambda: int(time.time()))
    last_active_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))


@dataclass
class PasswordHistoryEntry:
    password_hash: str
    changed_at: int = field(default_factory=lambda: int(time.time()))


@dataclass
class EmailChangeRequestEntry:
    user_id: int
    old_email: str
    new_email: str
    status: str = "pending"
    requested_at: int = field(default_factory=lambda: int(time.time()))
    expires_at: int = field(default_factory=lambda: int(time.time()) + 600)
    processed_at: Optional[int] = None


class AuthService:
    """Core auth workflow including register/login/password/email operations."""

    def __init__(
        self,
        *,
        cache: AuthCacheManager,
        jwt_manager: JWTManager,
        product_keys: Optional[ProductKeyRegistry] = None,
        verifier: Optional[EmailVerificationService] = None,
        rate_limiter: Optional[AuthRateLimiter] = None,
        email_service: Optional[SMTPEmailService] = None,
        template_manager: Optional[EmailTemplateManager] = None,
    ) -> None:
        self.cache = cache
        self.jwt = jwt_manager
        self.product_keys = product_keys or ProductKeyRegistry()
        self.verifier = verifier or EmailVerificationService(cache)
        self.rate_limiter = rate_limiter or AuthRateLimiter(cache)
        self.email_service = email_service or SMTPEmailService.from_env()
        self.template_manager = template_manager or EmailTemplateManager()
        key_seed = settings.AUTH_ENCRYPTION_KEY or os.getenv("AUTH_JWT_SECRET") or os.urandom(32).hex()
        self.field_cipher = SensitiveDataCipher(key_seed)
        self.ip_controller = IPAccessController(
            cache,
            whitelist=settings.ip_whitelist_set,
            blacklist=settings.ip_blacklist_set,
            auto_ban_threshold=settings.AUTH_IP_AUTO_BAN_THRESHOLD,
            auto_ban_window_seconds=settings.AUTH_IP_AUTO_BAN_WINDOW_SECONDS,
            auto_ban_seconds=settings.AUTH_IP_AUTO_BAN_SECONDS,
        )

        self._lock = threading.Lock()
        self._next_user_id = 1
        self._users_by_email: Dict[str, AuthUser] = {}
        self._users_by_id: Dict[int, AuthUser] = {}
        self._devices: Dict[Tuple[int, str], UserDeviceSession] = {}
        self._password_histories: Dict[int, List[PasswordHistoryEntry]] = {}
        self._email_change_requests: Dict[int, EmailChangeRequestEntry] = {}
        self.audit_logs: List[Dict[str, Any]] = []
        self._super_admin_emails = self._parse_super_admin_emails()

    def _parse_super_admin_emails(self) -> set[str]:
        raw = os.getenv("AUTH_SUPER_ADMIN_EMAILS", "1447954419@qq.com")
        emails: set[str] = set()
        for item in str(raw).split(","):
            normalized = item.strip().lower()
            if normalized and "@" in normalized:
                emails.add(normalized)
        return emails

    def _query_product_key_from_db(self, product_key: str) -> Optional[ProductKeyRecord]:
        normalized = product_key.strip().upper()
        try:
            from app.auth_db.models import ProductKey
            from app.auth_db.session import get_auth_session_factory
        except Exception:  # pragma: no cover - auth db unavailable fallback
            return None

        try:
            session_factory = get_auth_session_factory()
        except Exception:  # pragma: no cover - auth db unavailable fallback
            return None

        db = session_factory()
        try:
            try:
                row = db.query(ProductKey).filter(ProductKey.product_key == normalized).one_or_none()
            except Exception as exc:  # pragma: no cover - db schema may be unavailable in isolated tests
                logger.debug("query product key from db skipped: %s", exc)
                return None
            if row is None:
                return None
            metadata = None
            if row.key_metadata:
                try:
                    parsed = json.loads(row.key_metadata)
                    metadata = parsed if isinstance(parsed, dict) else None
                except Exception:
                    metadata = None
            return ProductKeyRecord(
                product_key=row.product_key,
                status=row.status,
                key_type=row.key_type,
                key_sub_type=row.key_sub_type,
                total_quota=int(row.total_quota or 0),
                used_count=int(row.used_count or 0),
                user_id=row.user_id,
                company_id=row.company_id,
                generation_seed=row.generation_seed,
                metadata=metadata,
                signature=None,
            )
        finally:
            db.close()

    def _activate_product_key_in_db(self, product_key: str, user_id: int) -> bool:
        normalized = product_key.strip().upper()
        try:
            from app.auth_db.models import ProductKey
            from app.auth_db.session import get_auth_session_factory
        except Exception:  # pragma: no cover - auth db unavailable fallback
            return False

        try:
            session_factory = get_auth_session_factory()
        except Exception:  # pragma: no cover - auth db unavailable fallback
            return False

        db = session_factory()
        try:
            try:
                row = db.query(ProductKey).filter(ProductKey.product_key == normalized).one_or_none()
            except Exception as exc:  # pragma: no cover - db schema may be unavailable in isolated tests
                logger.debug("activate product key in db skipped: %s", exc)
                return False
            if row is None:
                return False
            if str(row.status).strip().lower() != "unused":
                raise ProductKeyValidationError(f"product key status invalid: {row.status}")
            row.status = "active"
            row.user_id = user_id
            row.used_count = min(int(row.total_quota or 0), int(row.used_count or 0) + 1)
            now = datetime.now(timezone.utc)
            row.activated_at = row.activated_at or now
            row.last_used_at = now
            try:
                db.commit()
            except Exception as exc:  # pragma: no cover - commit failure fallback to memory mode
                logger.warning("activate product key in db commit failed: %s", exc)
                db.rollback()
                return False
            return True
        finally:
            db.close()

    def _apply_super_admin_role_if_needed(self, user: AuthUser) -> None:
        if user.email not in self._super_admin_emails:
            return
        user.role = "super_admin"
        if "admin" not in user.permissions:
            user.permissions.append("admin")
        if "super_admin" not in user.permissions:
            user.permissions.append("super_admin")

    @staticmethod
    def _build_permissions_for_role(role: str) -> List[str]:
        normalized_role = str(role or "user").strip().lower()
        if normalized_role == "super_admin":
            return ["read", "write", "admin", "super_admin"]
        if normalized_role in {"admin", "company_admin", "enterprise"}:
            return ["read", "write", "admin"]
        return ["read"]

    @staticmethod
    def _datetime_to_epoch(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return int(value.timestamp())
        return None

    def _upsert_user_cache_locked(self, user: AuthUser) -> AuthUser:
        existing = self._users_by_id.get(user.id)
        if existing:
            old_email = existing.email
            existing.email = user.email
            existing.username = user.username
            existing.password_hash = user.password_hash
            existing.role = user.role
            existing.permissions = list(user.permissions)
            existing.status = user.status
            existing.last_login_at = user.last_login_at
            existing.is_email_verified = bool(user.is_email_verified)
            existing.failed_login_attempts = int(user.failed_login_attempts or 0)
            existing.lock_until = user.lock_until
            existing.lock_reason = user.lock_reason
            existing.enterprise_id = user.enterprise_id
            if old_email != existing.email:
                self._users_by_email.pop(old_email, None)
            self._users_by_email[existing.email] = existing
            return existing
        self._users_by_id[user.id] = user
        self._users_by_email[user.email] = user
        self._next_user_id = max(self._next_user_id, user.id + 1)
        return user

    def _query_user_from_db(self, normalized_email: str) -> Optional[AuthUser]:
        try:
            from app.auth_db.models import User
            from app.auth_db.session import get_auth_session_factory
        except Exception:
            return None

        try:
            session_factory = get_auth_session_factory()
        except Exception:
            return None

        db = session_factory()
        try:
            row = db.query(User).filter(func.lower(User.email) == normalized_email).one_or_none()
            if row is None:
                return None
            role = str(row.role or "user")
            user = AuthUser(
                id=int(row.id),
                email=str(row.email).strip().lower(),
                username=str(row.username or ""),
                password_hash=str(row.password_hash or ""),
                role=role,
                permissions=self._build_permissions_for_role(role),
                status=str(row.status or "pending"),
                is_email_verified=bool(row.is_email_verified),
                failed_login_attempts=int(row.failed_login_attempts or 0),
                lock_until=self._datetime_to_epoch(row.lock_until),
                lock_reason=row.lock_reason,
                last_login_at=self._datetime_to_epoch(row.last_login_at),
                created_at=self._datetime_to_epoch(row.created_at) or int(time.time()),
                enterprise_id=int(row.company_id) if row.company_id is not None else None,
            )
            with self._lock:
                return self._upsert_user_cache_locked(user)
        except Exception as exc:
            logger.debug("query user from db skipped: %s", exc)
            return None
        finally:
            db.close()

    def _normalize_email(self, email: str) -> str:
        return ensure_safe_text(email, max_len=320, reject_sql=True).lower()

    @staticmethod
    def _user_name_from_email(email: str) -> str:
        local = email.split("@", 1)[0]
        return local or "用户"

    def _audit(
        self,
        *,
        operation: str,
        user_id: Optional[int],
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        success = str(details.get("result", "")).lower() != "failed"
        failure_reason = str(details.get("reason", "")) if not success else None
        masked_ip = self._mask_ip(ip_address)
        encrypted_ip = self.field_cipher.encrypt(ip_address) if ip_address else None
        username = None
        if user_id is not None:
            with self._lock:
                user = self._users_by_id.get(user_id)
            if user:
                username = user.email.split("@", 1)[0]
        entry = {
            "operation": operation,
            "event_type": operation,
            "user_id": user_id,
            "username": username,
            "target_id": details.get("target_id"),
            "target_type": details.get("target_type"),
            "details": details,
            "success": success,
            "failure_reason": failure_reason,
            "ip_address": encrypted_ip,
            "ip_address_masked": masked_ip,
            "user_agent": user_agent,
            "operated_at": int(time.time()),
            "timestamp": int(time.time()),
        }
        self.audit_logs.append(entry)
        logger.info("audit op=%s user=%s details=%s", operation, user_id, details)

    def _is_whitelisted_ip(self, ip_address: Optional[str]) -> bool:
        return self.ip_controller.is_whitelisted(ip_address)

    def _ensure_ip_allowed(self, *, ip_address: Optional[str]) -> None:
        result = self.ip_controller.check(ip_address)
        if result.allowed:
            return
        raise PermissionError("当前IP已被封禁，请稍后再试")

    def _record_failed_login_attempt(self, *, user: AuthUser, ip_address: Optional[str]) -> None:
        now = int(time.time())
        user.failed_login_attempts += 1
        locked_seconds = 0
        lock_reason = None
        if user.failed_login_attempts >= 10:
            locked_seconds = settings.AUTH_ACCOUNT_LOCK_10_FAIL_SECONDS
            lock_reason = "连续10次登录失败"
        elif user.failed_login_attempts >= 5:
            locked_seconds = settings.AUTH_ACCOUNT_LOCK_5_FAIL_SECONDS
            lock_reason = "连续5次登录失败"
        if locked_seconds > 0:
            user.status = "locked"
            user.lock_until = now + locked_seconds
            user.lock_reason = lock_reason
            self._send_security_lock_email(user=user, reason=lock_reason, lock_seconds=locked_seconds)
        auto_banned = self.ip_controller.record_failed_attempt(ip_address)
        if auto_banned:
            self._send_ip_ban_alert(ip_address=ip_address, reason="检测到暴力破解并自动封禁30分钟")

    def _reset_failed_login_attempt(self, *, user: AuthUser) -> None:
        user.failed_login_attempts = 0
        user.lock_until = None
        user.lock_reason = None
        if user.status == "locked":
            user.status = "active"

    def _decrypt_ip(self, encrypted: Optional[str]) -> Optional[str]:
        if not encrypted:
            return None
        try:
            return self.field_cipher.decrypt(encrypted)
        except Exception:
            return encrypted

    def _send_security_lock_email(self, *, user: AuthUser, reason: str, lock_seconds: int) -> None:
        html = (
            "<h3>安全提醒：账号已临时锁定</h3>"
            f"<p>账号：{user.email}</p>"
            f"<p>原因：{reason}</p>"
            f"<p>锁定时长：{lock_seconds} 秒</p>"
            "<p>如果不是本人操作，请尽快修改密码。</p>"
        )
        try:
            self.email_service.send_email(
                to_email=user.email,
                subject="UDAKE 安全提醒：账号锁定",
                html_content=html,
                async_send=True,
            )
        except Exception as exc:
            logger.warning("账号锁定提醒邮件发送失败 user=%s err=%s", user.id, exc)

    def _send_ip_ban_alert(self, *, ip_address: Optional[str], reason: str) -> None:
        security_email = os.getenv("AUTH_SECURITY_ALERT_EMAIL")
        if not security_email:
            return
        html = (
            "<h3>安全提醒：IP自动封禁</h3>"
            f"<p>IP：{ip_address or '-'}</p>"
            f"<p>原因：{reason}</p>"
        )
        try:
            self.email_service.send_email(
                to_email=security_email,
                subject="UDAKE 安全提醒：异常IP已封禁",
                html_content=html,
                async_send=True,
            )
        except Exception as exc:
            logger.warning("IP封禁提醒邮件发送失败 ip=%s err=%s", ip_address, exc)

    def add_product_key(self, product_key: str, *, key_type: str = "personal_standard") -> ProductKeyRecord:
        record = ProductKeyRecord(product_key=product_key, key_type=key_type, status="unused")
        self.product_keys.register_key(record)
        return record

    def validate_email(self, email: str) -> None:
        if not EMAIL_PATTERN.fullmatch(self._normalize_email(email)):
            raise ValueError("邮箱格式无效")

    def validate_password_strength(self, password: str) -> None:
        if not PASSWORD_PATTERN.fullmatch(password):
            raise ValueError("密码强度不足，至少8位且包含大小写字母和数字")

    @staticmethod
    def validate_password_confirmation(new_password: str, confirm_password: str) -> None:
        if new_password != confirm_password:
            raise ValueError("两次输入的密码不一致")

    def _record_password_history(self, user_id: int, password_hash: str) -> None:
        history = self._password_histories.setdefault(user_id, [])
        history.insert(0, PasswordHistoryEntry(password_hash=password_hash))
        if len(history) > 5:
            del history[5:]

    def _check_password_reuse(self, user_id: int, new_password: str) -> bool:
        with self._lock:
            user = self._users_by_id.get(user_id)
            history = list(self._password_histories.get(user_id, []))
        if not user:
            raise ValueError("用户不存在")
        if verify_password(new_password, user.password_hash):
            return True
        return any(verify_password(new_password, entry.password_hash) for entry in history)

    def _send_template_email(
        self,
        *,
        template_key: str,
        to_email: str,
        language: str = "zh-CN",
        variables: Optional[Dict[str, Any]] = None,
    ) -> None:
        template = self.template_manager.render(template_key, language=language, variables=variables or {})
        try:
            self.email_service.send_email(
                to_email=to_email,
                subject=template.subject,
                html_content=template.html,
                async_send=True,
            )
        except Exception as exc:
            logger.warning("邮件异步投递提交失败, template=%s to=%s err=%s", template_key, to_email, exc)

    def _get_user_by_token(self, access_token: str) -> AuthUser:
        payload = self.jwt.verify_token(access_token, expected_type="access", check_blacklist=True)
        user_id = int(payload["user_id"])
        with self._lock:
            user = self._users_by_id.get(user_id)
        if not user:
            raise JWTValidationError("用户不存在或Token无效")
        return user

    def _ensure_rate_limit(self, *, identity: str, action: str) -> Dict[str, int]:
        return self.rate_limiter.check_and_consume(identity=identity, action=action)

    @staticmethod
    def _normalize_device_value(value: Any) -> str:
        text = str(value or "").strip()
        return text

    def generate_device_fingerprint(
        self, *, device_info: Optional[Dict[str, Any]] = None, user_agent: Optional[str] = None
    ) -> str:
        info = device_info or {}
        if info.get("fingerprint"):
            return str(info["fingerprint"])
        screen_resolution = self._normalize_device_value(
            info.get("screen_resolution") or f"{info.get('screen_width', '')}x{info.get('screen_height', '')}"
        )
        timezone = self._normalize_device_value(info.get("timezone"))
        language = self._normalize_device_value(info.get("language"))
        canvas_fingerprint = self._normalize_device_value(
            info.get("canvas_fingerprint") or info.get("canvas") or info.get("canvas_hash")
        )
        payload = "|".join(
            [
                self._normalize_device_value(user_agent).lower(),
                screen_resolution.lower(),
                timezone.lower(),
                language.lower(),
                canvas_fingerprint.lower(),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_device_type(*, user_agent: str) -> str:
        ua = user_agent.lower()
        if any(flag in ua for flag in ("ipad", "tablet")):
            return "平板"
        if any(flag in ua for flag in ("iphone", "android", "mobile")):
            return "手机"
        if ua:
            return "PC"
        return "unknown"

    @staticmethod
    def _extract_os(*, user_agent: str) -> str:
        ua = user_agent.lower()
        if "windows" in ua:
            return "Windows"
        if "mac os x" in ua or "macintosh" in ua:
            return "macOS"
        if "iphone" in ua or "ipad" in ua or "ios" in ua:
            return "iOS"
        if "android" in ua:
            return "Android"
        if "linux" in ua:
            return "Linux"
        return "Unknown"

    @staticmethod
    def _extract_browser(*, user_agent: str) -> str:
        ua = user_agent.lower()
        if "edg/" in ua:
            return "Edge"
        if "opr/" in ua or "opera" in ua:
            return "Opera"
        if "chrome/" in ua and "chromium" not in ua and "edg/" not in ua:
            return "Chrome"
        if "firefox/" in ua:
            return "Firefox"
        if "safari/" in ua and "chrome/" not in ua:
            return "Safari"
        return "Unknown"

    @staticmethod
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

    @staticmethod
    def _parse_device_id_from_token_payload(payload: Dict[str, Any]) -> Optional[str]:
        candidate = str(payload.get("device_id") or "").strip()
        return candidate or None

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _resolve_device_id(self, info: Dict[str, Any], fingerprint: str) -> str:
        raw_device_id = str(info.get("device_id") or "").strip()
        if raw_device_id:
            return raw_device_id
        # 使用指纹派生稳定UUID，同一设备可复用同一device_id
        return str(uuid.uuid5(uuid.NAMESPACE_URL, fingerprint))

    def _token_exp(self, token: str) -> int:
        payload = self.jwt.parse_token(token, verify=False)
        exp = int(payload.get("exp", 0))
        if exp > 0:
            return exp
        return int(time.time()) + 60

    @staticmethod
    def _is_suspicious_user_agent(user_agent: str) -> bool:
        ua = user_agent.lower()
        return any(keyword in ua for keyword in SUSPICIOUS_UA_KEYWORDS)

    def _mark_device_inactive_locked(self, session: UserDeviceSession, *, now: int) -> None:
        session.status = "inactive"
        session.refresh_token_hash = ""
        session.tokens.clear()
        session.updated_at = now

    def _cleanup_expired_tokens_locked(self, session: UserDeviceSession, *, now: int) -> None:
        expired = [token_hash for token_hash, token_meta in session.tokens.items() if int(token_meta.get("exp", 0)) <= now]
        for token_hash in expired:
            session.tokens.pop(token_hash, None)

    def _cleanup_stale_devices_locked(self, *, now: int) -> None:
        for session in self._devices.values():
            self._cleanup_expired_tokens_locked(session, now=now)
            if session.status == "active" and session.last_active_at <= now - DEVICE_INACTIVE_AFTER_SECONDS:
                self._mark_device_inactive_locked(session, now=now)

    def _add_device_token_locked(
        self,
        session: UserDeviceSession,
        *,
        token: str,
        token_type: str,
        now: int,
    ) -> None:
        token_hash = self._token_hash(token)
        session.tokens[token_hash] = {
            "type": token_type,
            "exp": self._token_exp(token),
            "added_at": now,
        }
        session.updated_at = now

    def _blacklist_all_user_device_tokens(self, *, user_id: int, reason: str) -> int:
        now = int(time.time())
        blacklisted = 0
        with self._lock:
            sessions = [item for (uid, _), item in self._devices.items() if uid == user_id]
            for session in sessions:
                for token_hash, token_meta in list(session.tokens.items()):
                    ttl = int(token_meta.get("exp", 0)) - now
                    if ttl <= 0:
                        continue
                    self.jwt.blacklist_token_hash(token_hash, user_id=user_id, ttl=ttl, reason=reason)
                    blacklisted += 1
                self._mark_device_inactive_locked(session, now=now)
        return blacklisted

    def _detect_anomalies(
        self,
        *,
        previous: Optional[UserDeviceSession],
        ip_address: Optional[str],
        location: Optional[str],
        user_agent: str,
        is_new_device: bool,
    ) -> List[Dict[str, Any]]:
        anomalies: List[Dict[str, Any]] = []
        previous_ip = self._decrypt_ip(previous.ip_address) if previous else None
        if is_new_device:
            anomalies.append({"type": "new_device", "severity": "info", "message": "检测到首次登录设备"})
        if previous_ip and ip_address and previous_ip != ip_address:
            anomalies.append(
                {
                    "type": "ip_changed",
                    "severity": "medium",
                    "message": "检测到设备IP变化",
                    "from": self._mask_ip(previous_ip),
                    "to": self._mask_ip(ip_address),
                }
            )
        if previous and previous.location and location and previous.location != location:
            anomalies.append(
                {
                    "type": "location_changed",
                    "severity": "medium",
                    "message": "检测到异地登录",
                    "from": previous.location,
                    "to": location,
                }
            )
        if previous and previous.user_agent and user_agent and previous.user_agent != user_agent:
            anomalies.append(
                {
                    "type": "user_agent_changed",
                    "severity": "medium",
                    "message": "检测到User-Agent变化",
                }
            )
        if user_agent and self._is_suspicious_user_agent(user_agent):
            anomalies.append(
                {
                    "type": "suspicious_user_agent",
                    "severity": "high",
                    "message": "检测到疑似爬虫或自动化User-Agent",
                }
            )
        return anomalies

    def _send_security_alert_email(self, *, user: AuthUser, anomalies: List[Dict[str, Any]], device_id: str) -> None:
        if not anomalies:
            return
        lines = "".join(
            f"<li>{item.get('message', item.get('type', 'unknown'))}</li>"
            for item in anomalies
        )
        html = (
            "<h3>安全提醒：检测到异常设备行为</h3>"
            f"<p>账号：{user.email}</p>"
            f"<p>设备ID：{device_id}</p>"
            f"<ul>{lines}</ul>"
            "<p>如果不是本人操作，请尽快修改密码。</p>"
        )
        try:
            self.email_service.send_email(
                to_email=user.email,
                subject="UDAKE 安全提醒：检测到异常设备行为",
                html_content=html,
                async_send=True,
            )
        except Exception as exc:
            logger.warning("安全提醒邮件发送失败 user=%s err=%s", user.id, exc)

    def register(
        self,
        *,
        email: str,
        password: str,
        product_key: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_email = self._normalize_email(email)
        normalized_product_key = product_key.strip().upper()
        bootstrap_key_alias = str(getattr(self, "_bootstrap_product_key_alias", "") or "").strip().upper()
        bootstrap_key_canonical = str(getattr(self, "_bootstrap_product_key", "") or "").strip().upper()
        validate_product_key = product_key
        use_bootstrap_admin_role = False
        if bootstrap_key_alias and bootstrap_key_canonical and normalized_product_key == bootstrap_key_alias:
            validate_product_key = bootstrap_key_canonical
            use_bootstrap_admin_role = True
        elif bootstrap_key_canonical and normalized_product_key == bootstrap_key_canonical:
            use_bootstrap_admin_role = True

        self.validate_email(normalized_email)
        self.validate_password_strength(password)
        self._ensure_ip_allowed(ip_address=ip_address)
        self._ensure_rate_limit(identity=normalized_email, action="register")

        try:
            record = self.product_keys.validate_key(
                validate_product_key,
                require_unused=True,
                query_func=self._query_product_key_from_db,
            )
        except ProductKeyValidationError as exc:
            self._audit(
                operation="register",
                user_id=None,
                details={"action": "register", "result": "failed", "reason": str(exc)},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise

        try:
            from app.auth_db.models import User
            from app.auth_db.session import get_auth_session_factory
        except ImportError:
            logger.error("Failed to import DB models in register")
            raise RuntimeError("Database access failed")

        session_factory = get_auth_session_factory()
        db_session = session_factory()
        
        try:
            # 检查邮箱是否已在数据库中注册
            existing_db_user = db_session.query(User).filter(func.lower(User.email) == normalized_email).one_or_none()
            if existing_db_user:
                raise ValueError("邮箱已注册")

            with self._lock:
                if normalized_email in self._users_by_email:
                    raise ValueError("邮箱已注册")

                # 生成唯一用户名
                base_name = normalized_email.split("@", 1)[0][:32] or "user"
                username = base_name
                suffix = 1
                while db_session.query(User).filter(User.username == username).one_or_none():
                    suffix += 1
                    username = f"{base_name[:28]}_{suffix}"

                role = "admin" if use_bootstrap_admin_role else "user"
                pwd_hash = hash_password(password)
                
                # 持久化用户到数据库 (pending 状态)
                new_user_row = User(
                    email=normalized_email,
                    username=username,
                    password_hash=pwd_hash,
                    role=role,
                    status="pending",
                    is_email_verified=False,
                    created_at=datetime.now(timezone.utc)
                )
                db_session.add(new_user_row)
                db_session.commit()
                db_session.refresh(new_user_row)
                
                user_id = new_user_row.id
                permissions = self._build_permissions_for_role(role)
                
                user = AuthUser(
                    id=user_id,
                    email=normalized_email,
                    username=username,
                    password_hash=pwd_hash,
                    role=role,
                    permissions=permissions,
                    status="pending",
                )
                self._apply_super_admin_role_if_needed(user)
                self._activate_product_key_in_db(validate_product_key, user_id)
                record.status = "active"
                record.user_id = user_id
                if int(record.total_quota or 0) > 0:
                    record.used_count = min(int(record.total_quota), int(record.used_count or 0) + 1)
                self.product_keys.register_key(record)
                self._users_by_email[normalized_email] = user
                self._users_by_id[user_id] = user
                self._next_user_id = max(self._next_user_id, user_id + 1)
                self._record_password_history(user_id, pwd_hash)
        except Exception as exc:
            db_session.rollback()
            logger.error(f"Register persistence failed: {exc}")
            raise
        finally:
            db_session.close()

        code = self.verifier.issue_code(normalized_email, namespace="verify_code")
        self._send_template_email(
            template_key="register_code",
            to_email=normalized_email,
            variables={"username": username, "code": code, "valid_time": "10分钟"},
        )
        self._audit(
            operation="register",
            user_id=user.id,
            details={
                "action": "register",
                "email": normalized_email,
                "result": "success",
                "role": user.role,
                "used_bootstrap_key": use_bootstrap_admin_role,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {"user_id": user.id, "email": user.email, "role": user.role, "verification_code": code}

    def login(
        self,
        *,
        email: str,
        password: str,
        device_info: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_email = self._normalize_email(email)
        self._ensure_ip_allowed(ip_address=ip_address)
        self._ensure_rate_limit(identity=normalized_email, action="login")
        self._ensure_rate_limit(identity=f"email:{normalized_email}", action="login_email")
        if ip_address and not self._is_whitelisted_ip(ip_address):
            self._ensure_rate_limit(identity=f"ip:{ip_address}", action="login_ip")

        user = self._query_user_from_db(normalized_email)
        if user is None:
            with self._lock:
                user = self._users_by_email.get(normalized_email)
        if not user:
            self._audit(
                operation="login",
                user_id=None,
                details={"result": "failed", "reason": "user_not_found", "email": normalized_email},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self.ip_controller.record_failed_attempt(ip_address)
            raise ValueError("邮箱或密码错误")
        if user.status == "locked":
            now = int(time.time())
            if user.lock_until and user.lock_until > now:
                raise ValueError(f"账号已锁定，请在 {max(1, user.lock_until - now)} 秒后重试")
            self._reset_failed_login_attempt(user=user)
        if user.status != "active":
            raise ValueError("账号不可用")
        if not verify_password(password, user.password_hash):
            self._record_failed_login_attempt(user=user, ip_address=ip_address)
            self._audit(
                operation="login",
                user_id=user.id,
                details={"result": "failed", "reason": "password_invalid"},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise ValueError("邮箱或密码错误")
        with self._lock:
            self._apply_super_admin_role_if_needed(user)

        info = device_info or {}
        normalized_ua = str(user_agent or info.get("user_agent") or "")
        location = str(info.get("location") or UNKNOWN_LOCATION)
        fingerprint = self.generate_device_fingerprint(device_info=info, user_agent=normalized_ua)
        device_id = self._resolve_device_id(info, fingerprint=fingerprint)
        device_name = str(info.get("device_name") or info.get("name") or "") or None
        device_type = self._extract_device_type(user_agent=normalized_ua)
        os_name = self._extract_os(user_agent=normalized_ua)
        browser = self._extract_browser(user_agent=normalized_ua)

        access_token = self.jwt.generate_access_token(
            user_id=user.id,
            role=user.role,
            permissions=user.permissions,
            extra_claims={"device_id": device_id, "fingerprint": fingerprint},
        )
        refresh_token = self.jwt.generate_refresh_token(
            user_id=user.id,
            device_id=device_id,
            extra_claims={"fingerprint": fingerprint},
        )
        refresh_hash = self._token_hash(refresh_token)
        now = int(time.time())
        anomalies: List[Dict[str, Any]] = []

        with self._lock:
            self._cleanup_stale_devices_locked(now=now)
            user.last_login_at = now
            self._reset_failed_login_attempt(user=user)
            self.ip_controller.clear_failed_attempts(ip_address)
            session = self._devices.get((user.id, device_id))
            previous = None
            if session:
                previous = UserDeviceSession(
                    user_id=session.user_id,
                    device_id=session.device_id,
                    fingerprint=session.fingerprint,
                    refresh_token_hash=session.refresh_token_hash,
                    device_name=session.device_name,
                    device_type=session.device_type,
                    os_name=session.os_name,
                    browser=session.browser,
                    ip_address=session.ip_address,
                    location=session.location,
                    user_agent=session.user_agent,
                    status=session.status,
                    tokens=dict(session.tokens),
                    created_at=session.created_at,
                    last_login_at=session.last_login_at,
                    last_active_at=session.last_active_at,
                    updated_at=session.updated_at,
                )
            else:
                session = UserDeviceSession(
                    user_id=user.id,
                    device_id=device_id,
                    fingerprint=fingerprint,
                    refresh_token_hash=refresh_hash,
                    device_name=device_name,
                    device_type=device_type,
                    os_name=os_name,
                    browser=browser,
                    ip_address=self.field_cipher.encrypt(ip_address) if ip_address else None,
                    location=location,
                    user_agent=normalized_ua,
                    status="active",
                    last_login_at=now,
                    last_active_at=now,
                    updated_at=now,
                )
                self._devices[(user.id, device_id)] = session

            anomalies = self._detect_anomalies(
                previous=previous,
                ip_address=ip_address,
                location=location,
                user_agent=normalized_ua,
                is_new_device=previous is None,
            )
            session.fingerprint = fingerprint
            session.device_name = device_name
            session.device_type = device_type
            session.os_name = os_name
            session.browser = browser
            session.ip_address = self.field_cipher.encrypt(ip_address) if ip_address else None
            session.location = location
            session.user_agent = normalized_ua
            session.status = "active"
            session.last_login_at = now
            session.last_active_at = now
            session.refresh_token_hash = refresh_hash
            self._cleanup_expired_tokens_locked(session, now=now)
            self._add_device_token_locked(session, token=access_token, token_type="access", now=now)
            self._add_device_token_locked(session, token=refresh_token, token_type="refresh", now=now)

        self._audit(
            operation="login",
            user_id=user.id,
            details={"result": "success", "device_id": device_id, "anomalies": anomalies},
            ip_address=ip_address,
            user_agent=normalized_ua,
        )
        if previous is None:
            self._audit(
                operation="register_device",
                user_id=user.id,
                details={"result": "success", "device_id": device_id},
                ip_address=ip_address,
                user_agent=normalized_ua,
            )
        if anomalies:
            self._audit(
                operation="device_risk_event",
                user_id=user.id,
                details={"action": "device_anomaly", "device_id": device_id, "events": anomalies},
                ip_address=ip_address,
                user_agent=normalized_ua,
            )
            self._send_security_alert_email(user=user, anomalies=anomalies, device_id=device_id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_info": {
                "user_id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role,
                "permissions": user.permissions,
                "enterprise_id": user.enterprise_id,
            },
        }

    def refresh_access_token(self, refresh_token: str) -> str:
        payload = self.jwt.verify_token(refresh_token, expected_type="refresh", check_blacklist=True)
        user_id = int(payload["user_id"])
        device_id = str(payload["device_id"])
        refresh_hash = self._token_hash(refresh_token)
        with self._lock:
            session = self._devices.get((user_id, device_id))
            user = self._users_by_id.get(user_id)
            now = int(time.time())
            self._cleanup_stale_devices_locked(now=now)
        if not session or session.refresh_token_hash != refresh_hash or session.status != "active" or not user:
            raise JWTValidationError("refresh token invalid")
        access_token = self.jwt.generate_access_token(
            user_id=user.id,
            role=user.role,
            permissions=user.permissions,
            extra_claims={"device_id": device_id, "fingerprint": session.fingerprint},
        )
        now = int(time.time())
        with self._lock:
            session.last_active_at = now
            self._cleanup_expired_tokens_locked(session, now=now)
            self._add_device_token_locked(session, token=access_token, token_type="access", now=now)
        self._audit(
            operation="read",
            user_id=user.id,
            details={"action": "refresh", "result": "success", "device_id": device_id},
        )
        return access_token

    def logout(self, access_token: str) -> None:
        payload = self.jwt.verify_token(access_token, expected_type="access", check_blacklist=True)
        self.jwt.blacklist_token(access_token)
        user_id = int(payload["user_id"])
        device_id = self._parse_device_id_from_token_payload(payload)
        now = int(time.time())
        with self._lock:
            if device_id:
                session = self._devices.get((user_id, device_id))
                if session:
                    session.tokens.pop(self._token_hash(access_token), None)
                    session.last_active_at = now
                    session.updated_at = now
        self._audit(
            operation="logout",
            user_id=user_id,
            details={"action": "logout", "result": "success", "device_id": device_id},
        )

    def list_user_devices(
        self,
        *,
        access_token: str,
        page: int = 1,
        page_size: int = 20,
        current_fingerprint: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = self.jwt.verify_token(access_token, expected_type="access", check_blacklist=True)
        user_id = int(payload["user_id"])
        current_device_id = self._parse_device_id_from_token_payload(payload)
        now = int(time.time())

        with self._lock:
            self._cleanup_stale_devices_locked(now=now)
            user_devices = [device for (uid, _), device in self._devices.items() if uid == user_id]
            if not current_device_id and current_fingerprint:
                matched = next((item for item in user_devices if item.fingerprint == current_fingerprint), None)
                current_device_id = matched.device_id if matched else None

            user_devices.sort(key=lambda item: (item.last_login_at, item.updated_at), reverse=True)
            total = len(user_devices)
            start = max(0, (page - 1) * page_size)
            end = start + page_size
            page_devices = user_devices[start:end]

            items = [
                {
                    "device_id": item.device_id,
                    "device_name": item.device_name or f"{item.os_name} {item.browser}",
                    "device_type": item.device_type,
                    "os": item.os_name,
                    "browser": item.browser,
                    "ip": self._mask_ip(self._decrypt_ip(item.ip_address)),
                    "location": item.location or UNKNOWN_LOCATION,
                    "last_login_at": item.last_login_at,
                    "status": item.status,
                    "is_current": bool(current_device_id and item.device_id == current_device_id),
                }
                for item in page_devices
            ]

        return {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
            "current_device_id": current_device_id,
        }

    def kick_device(
        self,
        *,
        access_token: str,
        target_device_id: str,
        current_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = self.jwt.verify_token(access_token, expected_type="access", check_blacklist=True)
        user_id = int(payload["user_id"])
        current_device_id = self._parse_device_id_from_token_payload(payload)
        now = int(time.time())
        blacklisted_tokens = 0

        with self._lock:
            self._cleanup_stale_devices_locked(now=now)
            if not current_device_id and current_fingerprint:
                current_match = next(
                    (device for (uid, _), device in self._devices.items() if uid == user_id and device.fingerprint == current_fingerprint),
                    None,
                )
                current_device_id = current_match.device_id if current_match else None

            if current_device_id and current_device_id == target_device_id:
                raise PermissionError("不能踢出当前设备")

            session = self._devices.get((user_id, target_device_id))
            if not session:
                raise ValueError("设备不存在")

            for token_hash, token_meta in list(session.tokens.items()):
                ttl = int(token_meta.get("exp", 0)) - now
                if ttl <= 0:
                    continue
                self.jwt.blacklist_token_hash(token_hash, user_id=user_id, ttl=ttl, reason="kick_device")
                blacklisted_tokens += 1
            self._mark_device_inactive_locked(session, now=now)

        self._audit(
            operation="kick_device",
            user_id=user_id,
            details={
                "action": "kick_device",
                "target_device_id": target_device_id,
                "current_device_id": current_device_id,
                "blacklisted_tokens": blacklisted_tokens,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {"device_id": target_device_id, "blacklisted_tokens": blacklisted_tokens}

    def verify_email_code(self, email: str, code: str) -> None:
        normalized_email = self._normalize_email(email)
        self._ensure_rate_limit(identity=normalized_email, action="verify_code")
        self.verifier.verify_code(normalized_email, code, namespace="verify_code")

        try:
            from app.auth_db.models import User
            from app.auth_db.session import get_auth_session_factory
        except ImportError:
            pass

        session_factory = get_auth_session_factory()
        db_session = session_factory()
        
        try:
            # 更新数据库中的用户状态
            row = db_session.query(User).filter(func.lower(User.email) == normalized_email).one_or_none()
            if row:
                row.is_email_verified = True
                row.status = "active"
                db_session.commit()

            with self._lock:
                user = self._users_by_email.get(normalized_email)
                if user:
                    user.is_email_verified = True
                    user.status = "active"
        except Exception as exc:
            db_session.rollback()
            logger.error(f"Verify email persistence failed: {exc}")
            # 继续执行，因为验证码已经校验过了
        finally:
            db_session.close()

        self._audit(
            operation="verify_email",
            user_id=user.id if 'user' in locals() and user else None,
            details={"action": "verify_email", "result": "success", "email": normalized_email},
        )

    def send_reset_password_code(
        self,
        *,
        email: str,
        product_key: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_email = self._normalize_email(email)
        self.validate_email(normalized_email)
        self._ensure_ip_allowed(ip_address=ip_address)
        self._ensure_rate_limit(identity=normalized_email, action="reset_password")

        self.product_keys.validate_key(product_key, require_unused=True)
        with self._lock:
            user = self._users_by_email.get(normalized_email)
        if not user:
            raise ValueError("用户不存在")

        code = self.verifier.issue_code(normalized_email, namespace="reset_code")
        self._send_template_email(
            template_key="reset_password_code",
            to_email=normalized_email,
            variables={"username": self._user_name_from_email(normalized_email), "code": code, "valid_time": "10分钟"},
        )
        self._audit(
            operation="reset_password_send_code",
            user_id=user.id,
            details={"action": "send_reset_password_code", "result": "success", "email": normalized_email},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {"email": normalized_email, "ttl_seconds": 600}

    def reset_password(
        self,
        *,
        email: str,
        code: str,
        new_password: str,
        confirm_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        normalized_email = self._normalize_email(email)
        self._ensure_ip_allowed(ip_address=ip_address)
        self._ensure_rate_limit(identity=normalized_email, action="verify_code")
        self.validate_password_strength(new_password)
        self.validate_password_confirmation(new_password, confirm_password)
        self.verifier.verify_code(normalized_email, code, namespace="reset_code")

        with self._lock:
            user = self._users_by_email.get(normalized_email)
        if not user:
            raise ValueError("用户不存在")
        if self._check_password_reuse(user.id, new_password):
            raise ValueError("新密码不能与最近5次使用过的密码重复")

        new_hash = hash_password(new_password)
        with self._lock:
            user.password_hash = new_hash
            self._record_password_history(user.id, new_hash)

        blacklisted_tokens = self._blacklist_all_user_device_tokens(user_id=user.id, reason="reset_password")
        self.jwt.blacklist_all_user_tokens(user_id=user.id)
        self._audit(
            operation="reset_password",
            user_id=user.id,
            details={"action": "reset_password", "result": "success", "blacklisted_tokens": blacklisted_tokens},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def change_password(
        self,
        *,
        access_token: str,
        old_password: str,
        new_password: str,
        confirm_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self._ensure_ip_allowed(ip_address=ip_address)
        user = self._get_user_by_token(access_token)
        if not verify_password(old_password, user.password_hash):
            raise ValueError("旧密码错误")
        self.validate_password_strength(new_password)
        self.validate_password_confirmation(new_password, confirm_password)
        if self._check_password_reuse(user.id, new_password):
            raise ValueError("新密码不能与最近5次使用过的密码重复")

        new_hash = hash_password(new_password)
        with self._lock:
            user.password_hash = new_hash
            self._record_password_history(user.id, new_hash)

        blacklisted_tokens = self._blacklist_all_user_device_tokens(user_id=user.id, reason="change_password")
        self.jwt.blacklist_all_user_tokens(user_id=user.id)
        self._audit(
            operation="change_password",
            user_id=user.id,
            details={"action": "change_password", "result": "success", "blacklisted_tokens": blacklisted_tokens},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def send_change_email_code(
        self,
        *,
        access_token: str,
        new_email: str,
        current_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_ip_allowed(ip_address=ip_address)
        user = self._get_user_by_token(access_token)
        normalized_new_email = self._normalize_email(new_email)
        self.validate_email(normalized_new_email)
        if not verify_password(current_password, user.password_hash):
            raise ValueError("当前密码错误")

        with self._lock:
            if normalized_new_email in self._users_by_email and normalized_new_email != user.email:
                raise ValueError("新邮箱已被使用")

        key = f"change_email:{user.id}"
        code = self.verifier.generate_code(length=6)
        payload = {
            "new_email": normalized_new_email,
            "code": code,
            "attempts": 0,
            "max_attempts": 3,
            "issued_at": int(time.time()),
        }
        self.cache.set_with_jitter(key, payload, ttl=600, jitter_ratio=0.05)

        with self._lock:
            self._email_change_requests[user.id] = EmailChangeRequestEntry(
                user_id=user.id,
                old_email=user.email,
                new_email=normalized_new_email,
            )

        self._send_template_email(
            template_key="change_email_code",
            to_email=normalized_new_email,
            variables={"username": self._user_name_from_email(user.email), "code": code, "valid_time": "10分钟"},
        )
        self._audit(
            operation="change_email_send_code",
            user_id=user.id,
            details={"action": "send_change_email_code", "result": "success", "new_email": normalized_new_email},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {"new_email": normalized_new_email, "ttl_seconds": 600}

    def verify_change_email(
        self,
        *,
        access_token: str,
        code: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, str]:
        self._ensure_ip_allowed(ip_address=ip_address)
        user = self._get_user_by_token(access_token)
        self._ensure_rate_limit(identity=str(user.id), action="verify_code")

        key = f"change_email:{user.id}"
        payload = self.cache.get(key)
        if not payload:
            raise VerificationCodeError("邮箱修改验证码已过期或不存在")

        attempts = int(payload.get("attempts", 0))
        max_attempts = int(payload.get("max_attempts", 3))
        ttl = self.cache.ttl(key)
        if ttl <= 0:
            self.cache.delete(key)
            raise VerificationCodeError("邮箱修改验证码已过期")
        if attempts >= max_attempts:
            self.cache.delete(key)
            raise VerificationCodeError("邮箱修改验证码尝试次数超限")
        if str(payload.get("code", "")).upper() != code.strip().upper():
            attempts += 1
            payload["attempts"] = attempts
            self.cache.set(key, payload, ttl=ttl)
            if attempts >= max_attempts:
                self.cache.delete(key)
                raise VerificationCodeError("邮箱修改验证码尝试次数超限")
            raise VerificationCodeError("邮箱修改验证码错误")

        new_email = self._normalize_email(str(payload.get("new_email", "")))
        if not new_email:
            self.cache.delete(key)
            raise VerificationCodeError("邮箱修改请求无效")

        with self._lock:
            if new_email in self._users_by_email and new_email != user.email:
                raise ValueError("新邮箱已被使用")
            old_email = user.email
            self._users_by_email.pop(old_email, None)
            user.email = new_email
            self._users_by_email[new_email] = user
            request_entry = self._email_change_requests.get(user.id)
            if request_entry:
                request_entry.status = "verified"
                request_entry.processed_at = int(time.time())

        self.cache.delete(key)
        with self._lock:
            self._email_change_requests.pop(user.id, None)

        self._send_template_email(
            template_key="change_email_notice",
            to_email=old_email,
            variables={
                "username": self._user_name_from_email(new_email),
                "old_email": old_email,
                "new_email": new_email,
            },
        )
        self._audit(
            operation="change_email",
            user_id=user.id,
            details={"action": "verify_change_email", "result": "success", "old_email": old_email, "new_email": new_email},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {"old_email": old_email, "new_email": new_email}

    def get_password_history(self, user_id: int) -> List[PasswordHistoryEntry]:
        with self._lock:
            return list(self._password_histories.get(user_id, []))


_AUTH_SERVICE: Optional[AuthService] = None
_AUTH_SERVICE_LOCK = threading.Lock()


def _resolve_jwt_secret() -> str:
    secret = os.getenv("AUTH_JWT_SECRET") or os.getenv("JWT_SECRET")
    if secret:
        return secret
    return os.urandom(32).hex()


def get_auth_service() -> AuthService:
    global _AUTH_SERVICE
    if _AUTH_SERVICE is None:
        with _AUTH_SERVICE_LOCK:
            if _AUTH_SERVICE is None:
                from app.config import settings

                cache = AuthCacheManager(redis_url=settings.REDIS_URL, pool_size=10, strict_redis=False)
                jwt_manager = JWTManager(secret_key=_resolve_jwt_secret(), cache_manager=cache)
                service = AuthService(cache=cache, jwt_manager=jwt_manager)

                bootstrap_seed = os.getenv("AUTH_BOOTSTRAP_PRODUCT_KEY", "UDAKE-DEFAULT-PRODUCT-KEY")
                bootstrap_record = service.product_keys.generate_key(bootstrap_seed)
                service._bootstrap_product_key_alias = bootstrap_seed.strip().upper()
                service._bootstrap_product_key = bootstrap_record.product_key
                cache.set_with_jitter(
                    "auth:warmup:product_keys",
                    {"keys": [bootstrap_record.product_key], "count": 1},
                    ttl=1800,
                    jitter_ratio=0.2,
                )
                cache.set_with_jitter(
                    "auth:warmup:user_summary",
                    {"total_users": 0, "cached_at": int(time.time())},
                    ttl=1800,
                    jitter_ratio=0.2,
                )
                _AUTH_SERVICE = service
    return _AUTH_SERVICE


def reset_auth_service() -> None:
    global _AUTH_SERVICE
    with _AUTH_SERVICE_LOCK:
        _AUTH_SERVICE = None
