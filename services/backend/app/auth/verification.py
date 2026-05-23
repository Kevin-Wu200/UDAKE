"""Email verification code generation and validation."""

from __future__ import annotations

import random
import string
import time
from dataclasses import dataclass

from .cache import AuthCacheManager


class VerificationCodeError(ValueError):
    """Raised when verification code is invalid or expired."""


@dataclass
class VerificationResult:
    success: bool
    message: str


class EmailVerificationService:
    """Verification code service backed by cache (Redis preferred)."""

    def __init__(
        self,
        cache_manager: AuthCacheManager,
        *,
        code_ttl_seconds: int = 600,
        max_attempts: int = 3,
    ) -> None:
        self.cache = cache_manager
        self.code_ttl_seconds = code_ttl_seconds
        self.max_attempts = max_attempts

    @staticmethod
    def _cache_key(email: str, namespace: str = "verify_code") -> str:
        return f"{namespace}:{email.lower().strip()}"

    def generate_code(self, *, length: int = 6) -> str:
        if length <= 0:
            raise ValueError("verification code length must be positive")
        chars = string.ascii_uppercase + string.digits
        return "".join(random.SystemRandom().choice(chars) for _ in range(length))

    def issue_code(self, email: str, *, namespace: str = "verify_code") -> str:
        code = self.generate_code(length=6)
        key = self._cache_key(email, namespace=namespace)
        payload = {
            "code": code,
            "attempts": 0,
            "max_attempts": self.max_attempts,
            "issued_at": int(time.time()),
        }
        self.cache.set(key, payload, ttl=self.code_ttl_seconds)
        return code

    def verify_code(self, email: str, code: str, *, namespace: str = "verify_code") -> VerificationResult:
        key = self._cache_key(email, namespace=namespace)
        payload = self.cache.get(key)
        if not payload:
            raise VerificationCodeError("verification code expired or not found")

        attempts = int(payload.get("attempts", 0))
        max_attempts = int(payload.get("max_attempts", self.max_attempts))
        if attempts >= max_attempts:
            self.cache.delete(key)
            raise VerificationCodeError("verification code exceeded max attempts")

        expected = str(payload.get("code", "")).upper()
        provided = code.strip().upper()
        ttl = self.cache.ttl(key)
        if ttl == -2:
            raise VerificationCodeError("verification code expired or not found")
        if ttl <= 0:
            self.cache.delete(key)
            raise VerificationCodeError("verification code expired")

        if provided != expected:
            payload["attempts"] = attempts + 1
            self.cache.set(key, payload, ttl=ttl)
            if payload["attempts"] >= max_attempts:
                self.cache.delete(key)
                raise VerificationCodeError("verification code exceeded max attempts")
            raise VerificationCodeError("verification code mismatch")

        self.cache.delete(key)
        return VerificationResult(success=True, message="verification code validated")
