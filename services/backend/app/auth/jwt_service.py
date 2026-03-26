"""JWT generation and validation for auth module (HS256)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any, Dict, Iterable, Optional

from .cache import AuthCacheManager


class JWTValidationError(ValueError):
    """Raised when token is invalid or expired."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


class JWTManager:
    """HS256 JWT manager with blacklist support via cache."""

    def __init__(
        self,
        *,
        secret_key: Optional[str] = None,
        access_ttl_seconds: int = 15 * 60,
        refresh_ttl_seconds: int = 7 * 24 * 60 * 60,
        cache_manager: Optional[AuthCacheManager] = None,
    ) -> None:
        resolved_secret = secret_key or os.getenv("AUTH_JWT_SECRET")
        if not resolved_secret:
            raise ValueError("AUTH_JWT_SECRET is required for JWT")
        self.secret_key = resolved_secret.encode("utf-8")
        self.access_ttl_seconds = access_ttl_seconds
        self.refresh_ttl_seconds = refresh_ttl_seconds
        self.cache = cache_manager

    def _sign(self, signing_input: bytes) -> str:
        digest = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        return _b64url_encode(digest)

    def _encode(self, payload: Dict[str, Any]) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = self._sign(signing_input)
        return f"{encoded_header}.{encoded_payload}.{signature}"

    def _decode_parts(self, token: str) -> tuple[Dict[str, Any], Dict[str, Any], str, str]:
        parts = token.split(".")
        if len(parts) != 3:
            raise JWTValidationError("token structure invalid")
        header_raw, payload_raw, signature = parts
        try:
            header = json.loads(_b64url_decode(header_raw).decode("utf-8"))
            payload = json.loads(_b64url_decode(payload_raw).decode("utf-8"))
        except Exception as exc:
            raise JWTValidationError("token payload malformed") from exc
        return header, payload, signature, f"{header_raw}.{payload_raw}"

    def _ensure_not_blacklisted(self, payload: Dict[str, Any]) -> None:
        if not self.cache:
            return
        jti = payload.get("jti")
        if jti and self.cache.exists(f"jwt_blacklist:{jti}"):
            raise JWTValidationError("token blacklisted")

    def _build_payload(
        self,
        *,
        token_type: str,
        expires_in_seconds: int,
        claims: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = int(time.time())
        payload = dict(claims)
        payload.update(
            {
                "jti": uuid.uuid4().hex,
                "iat": now,
                "nbf": now,
                "exp": now + expires_in_seconds,
                "typ": token_type,
            }
        )
        return payload

    def generate_access_token(
        self,
        *,
        user_id: int | str,
        role: str,
        permissions: Iterable[str],
        extra_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        claims = {
            "user_id": str(user_id),
            "role": role,
            "permissions": list(permissions),
        }
        if extra_claims:
            claims.update(extra_claims)
        payload = self._build_payload(
            token_type="access",
            expires_in_seconds=self.access_ttl_seconds,
            claims=claims,
        )
        return self._encode(payload)

    def generate_refresh_token(
        self,
        *,
        user_id: int | str,
        device_id: str,
        extra_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        claims = {"user_id": str(user_id), "device_id": device_id}
        if extra_claims:
            claims.update(extra_claims)
        payload = self._build_payload(
            token_type="refresh",
            expires_in_seconds=self.refresh_ttl_seconds,
            claims=claims,
        )
        return self._encode(payload)

    def parse_token(self, token: str, *, verify: bool = True) -> Dict[str, Any]:
        header, payload, signature, signing_input = self._decode_parts(token)
        if verify:
            if header.get("alg") != "HS256":
                raise JWTValidationError("unsupported jwt algorithm")
            expected_signature = self._sign(signing_input.encode("ascii"))
            if not hmac.compare_digest(expected_signature, signature):
                raise JWTValidationError("token signature invalid")
        return payload

    def verify_token(
        self,
        token: str,
        *,
        expected_type: Optional[str] = None,
        check_blacklist: bool = True,
    ) -> Dict[str, Any]:
        payload = self.parse_token(token, verify=True)

        now = int(time.time())
        exp = int(payload.get("exp", 0))
        nbf = int(payload.get("nbf", 0))
        if exp <= now:
            raise JWTValidationError("token expired")
        if nbf > now:
            raise JWTValidationError("token not active yet")
        if expected_type and payload.get("typ") != expected_type:
            raise JWTValidationError("token type mismatch")
        if check_blacklist:
            self._ensure_not_blacklisted(payload)
        return payload

    def blacklist_token(self, token: str) -> None:
        if not self.cache:
            return
        payload = self.parse_token(token, verify=False)
        jti = payload.get("jti")
        exp = int(payload.get("exp", 0))
        if not jti or exp <= 0:
            return
        ttl = max(1, exp - int(time.time()))
        self.cache.set(f"jwt_blacklist:{jti}", {"reason": "logout"}, ttl=ttl)
