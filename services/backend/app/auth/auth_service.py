"""Application-level authentication service."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .cache import AuthCacheManager
from .email_service import SMTPEmailService
from .email_templates import EmailTemplateManager
from .jwt_service import JWTManager, JWTValidationError
from .product_key_service import ProductKeyRecord, ProductKeyRegistry, ProductKeyValidationError
from .rate_limiter import AuthRateLimiter, RateLimitExceededError
from .security import hash_password, verify_password
from .verification import EmailVerificationService, VerificationCodeError

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")


@dataclass
class AuthUser:
    id: int
    email: str
    password_hash: str
    role: str = "user"
    permissions: List[str] = field(default_factory=list)
    status: str = "active"
    created_at: int = field(default_factory=lambda: int(time.time()))
    last_login_at: Optional[int] = None
    is_email_verified: bool = False


@dataclass
class UserDeviceSession:
    user_id: int
    device_id: str
    refresh_token_hash: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
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

        self._lock = threading.Lock()
        self._next_user_id = 1
        self._users_by_email: Dict[str, AuthUser] = {}
        self._users_by_id: Dict[int, AuthUser] = {}
        self._devices: Dict[Tuple[int, str], UserDeviceSession] = {}
        self._password_histories: Dict[int, List[PasswordHistoryEntry]] = {}
        self._email_change_requests: Dict[int, EmailChangeRequestEntry] = {}
        self.audit_logs: List[Dict[str, Any]] = []

    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

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
        entry = {
            "operation": operation,
            "user_id": user_id,
            "details": details,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "operated_at": int(time.time()),
        }
        self.audit_logs.append(entry)
        logger.info("audit op=%s user=%s details=%s", operation, user_id, details)

    def add_product_key(self, product_key: str, *, key_type: str = "personal") -> ProductKeyRecord:
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
        self.validate_email(normalized_email)
        self.validate_password_strength(password)
        self._ensure_rate_limit(identity=normalized_email, action="register")

        try:
            record = self.product_keys.validate_key(product_key, require_unused=True)
        except ProductKeyValidationError as exc:
            self._audit(
                operation="create",
                user_id=None,
                details={"action": "register", "result": "failed", "reason": str(exc)},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise

        with self._lock:
            if normalized_email in self._users_by_email:
                raise ValueError("邮箱已注册")

            user_id = self._next_user_id
            self._next_user_id += 1
            user = AuthUser(
                id=user_id,
                email=normalized_email,
                password_hash=hash_password(password),
                role="user",
                permissions=["read"],
                status="active",
            )
            self._users_by_email[normalized_email] = user
            self._users_by_id[user_id] = user
            record.status = "active"
            self._record_password_history(user_id, user.password_hash)

        code = self.verifier.issue_code(normalized_email, namespace="verify_code")
        self._send_template_email(
            template_key="register_code",
            to_email=normalized_email,
            variables={"username": self._user_name_from_email(normalized_email), "code": code, "valid_time": "10分钟"},
        )
        self._audit(
            operation="create",
            user_id=user.id,
            details={"action": "register", "email": normalized_email, "result": "success"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {"user_id": user.id, "email": user.email, "verification_code": code}

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
        self._ensure_rate_limit(identity=normalized_email, action="login")

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
            raise ValueError("邮箱或密码错误")
        if user.status != "active":
            raise ValueError("账号不可用")
        if not verify_password(password, user.password_hash):
            self._audit(
                operation="login",
                user_id=user.id,
                details={"result": "failed", "reason": "password_invalid"},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise ValueError("邮箱或密码错误")

        info = device_info or {}
        default_device = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()[:16]
        device_id = str(info.get("device_id") or info.get("fingerprint") or default_device)
        access_token = self.jwt.generate_access_token(
            user_id=user.id,
            role=user.role,
            permissions=user.permissions,
        )
        refresh_token = self.jwt.generate_refresh_token(user_id=user.id, device_id=device_id)
        refresh_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()

        with self._lock:
            user.last_login_at = int(time.time())
            self._devices[(user.id, device_id)] = UserDeviceSession(
                user_id=user.id,
                device_id=device_id,
                refresh_token_hash=refresh_hash,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        self._audit(
            operation="login",
            user_id=user.id,
            details={"result": "success", "device_id": device_id},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_info": {
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "permissions": user.permissions,
            },
        }

    def refresh_access_token(self, refresh_token: str) -> str:
        payload = self.jwt.verify_token(refresh_token, expected_type="refresh", check_blacklist=True)
        user_id = int(payload["user_id"])
        device_id = str(payload["device_id"])
        refresh_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        with self._lock:
            session = self._devices.get((user_id, device_id))
            user = self._users_by_id.get(user_id)
        if not session or session.refresh_token_hash != refresh_hash or not user:
            raise JWTValidationError("refresh token invalid")
        access_token = self.jwt.generate_access_token(
            user_id=user.id,
            role=user.role,
            permissions=user.permissions,
        )
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
        self._audit(
            operation="logout",
            user_id=user_id,
            details={"action": "logout", "result": "success"},
        )

    def verify_email_code(self, email: str, code: str) -> None:
        normalized_email = self._normalize_email(email)
        self._ensure_rate_limit(identity=normalized_email, action="verify_code")
        self.verifier.verify_code(normalized_email, code, namespace="verify_code")
        with self._lock:
            user = self._users_by_email.get(normalized_email)
            if user:
                user.is_email_verified = True
        self._audit(
            operation="update",
            user_id=user.id if user else None,
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
            operation="read",
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

        self.jwt.blacklist_all_user_tokens(user_id=user.id)
        self._audit(
            operation="password_change",
            user_id=user.id,
            details={"action": "reset_password", "result": "success"},
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

        self.jwt.blacklist_all_user_tokens(user_id=user.id)
        self._audit(
            operation="password_change",
            user_id=user.id,
            details={"action": "change_password", "result": "success"},
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
        self.cache.set(key, payload, ttl=600)

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
            operation="email_change",
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
            operation="email_change",
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
                service.product_keys.generate_key(bootstrap_seed)
                _AUTH_SERVICE = service
    return _AUTH_SERVICE


def reset_auth_service() -> None:
    global _AUTH_SERVICE
    with _AUTH_SERVICE_LOCK:
        _AUTH_SERVICE = None
