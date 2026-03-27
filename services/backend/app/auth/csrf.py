"""CSRF token management helpers."""

from __future__ import annotations

import hashlib
import secrets
from typing import Optional

from fastapi import Request

from .cache import AuthCacheManager


class CSRFValidationError(ValueError):
    """Raised when CSRF token is missing or invalid."""


class CSRFManager:
    def __init__(
        self,
        cache: AuthCacheManager,
        *,
        cookie_name: str = "csrf_token",
        header_name: str = "x-csrf-token",
        ttl_seconds: int = 2 * 60 * 60,
    ) -> None:
        self.cache = cache
        self.cookie_name = cookie_name
        self.header_name = header_name.lower()
        self.ttl_seconds = max(60, int(ttl_seconds))

    @staticmethod
    def _subject_key(subject: str) -> str:
        digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()
        return f"csrf:{digest}"

    @staticmethod
    def build_subject(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",", 1)[0].strip() if forwarded else ""
        if not ip and request.client:
            ip = request.client.host
        ua = request.headers.get("user-agent", "")
        origin = request.headers.get("origin", "")
        return f"{ip}|{ua}|{origin}"

    def issue_token(self, *, subject: str) -> str:
        token = secrets.token_urlsafe(32)
        self.cache.set(self._subject_key(subject), {"token": token}, ttl=self.ttl_seconds)
        return token

    def verify_token(
        self,
        *,
        subject: str,
        cookie_token: Optional[str],
        header_token: Optional[str],
    ) -> None:
        if not cookie_token or not header_token:
            raise CSRFValidationError("缺少CSRF Token")
        if cookie_token != header_token:
            raise CSRFValidationError("CSRF Token不匹配")
        cached = self.cache.get(self._subject_key(subject)) or {}
        expected = str(cached.get("token") or "")
        if not expected or expected != cookie_token:
            raise CSRFValidationError("CSRF Token无效或已过期")

