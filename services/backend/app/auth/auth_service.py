"""Application-level authentication service."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .cache import AuthCacheManager
from .jwt_service import JWTManager, JWTValidationError
from .product_key_service import ProductKeyRecord, ProductKeyRegistry, ProductKeyValidationError
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


@dataclass
class UserDeviceSession:
    user_id: int
    device_id: str
    refresh_token_hash: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    updated_at: int = field(default_factory=lambda: int(time.time()))


class AuthService:
    """Core auth workflow: register/login/refresh/logout."""

    def __init__(
        self,
        *,
        cache: AuthCacheManager,
        jwt_manager: JWTManager,
        product_keys: Optional[ProductKeyRegistry] = None,
        verifier: Optional[EmailVerificationService] = None,
    ) -> None:
        self.cache = cache
        self.jwt = jwt_manager
        self.product_keys = product_keys or ProductKeyRegistry()
        self.verifier = verifier or EmailVerificationService(cache)
        self._lock = threading.Lock()
        self._next_user_id = 1
        self._users_by_email: Dict[str, AuthUser] = {}
        self._users_by_id: Dict[int, AuthUser] = {}
        self._devices: Dict[tuple[int, str], UserDeviceSession] = {}
        self.audit_logs: List[Dict[str, Any]] = []

    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

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

    def register(
        self,
        *,
        email: str,
        password: str,
        product_key: str,
    ) -> Dict[str, Any]:
        normalized_email = self._normalize_email(email)
        self.validate_email(normalized_email)
        self.validate_password_strength(password)

        try:
            record = self.product_keys.validate_key(product_key, require_unused=True)
        except ProductKeyValidationError as exc:
            self._audit(
                operation="create",
                user_id=None,
                details={"action": "register", "result": "failed", "reason": str(exc)},
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

        code = self.verifier.issue_code(normalized_email, namespace="verify_code")
        self._audit(
            operation="create",
            user_id=user.id,
            details={"action": "register", "email": normalized_email, "result": "success"},
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
        device_id = str(info.get("device_id") or info.get("fingerprint") or hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()[:16])
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
        self.verifier.verify_code(self._normalize_email(email), code, namespace="verify_code")


_AUTH_SERVICE: Optional[AuthService] = None


def _resolve_jwt_secret() -> str:
    secret = os.getenv("AUTH_JWT_SECRET") or os.getenv("JWT_SECRET")
    if secret:
        return secret
    # Fallback for local/testing runtime; production should always set env.
    return os.urandom(32).hex()


def get_auth_service() -> AuthService:
    global _AUTH_SERVICE
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
    _AUTH_SERVICE = None
