"""Authentication rate limiter backed by cache."""

from __future__ import annotations

import functools
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .cache import AuthCacheManager


class RateLimitExceededError(RuntimeError):
    """Raised when rate limit check rejects current request."""

    def __init__(self, message: str, *, locked_seconds: int = 0) -> None:
        super().__init__(message)
        self.locked_seconds = max(0, int(locked_seconds))


@dataclass(frozen=True)
class RateRule:
    hourly: int
    daily: int


class AuthRateLimiter:
    """Redis-like rate limiter with hourly/daily counters and lockout."""

    DEFAULT_RULES: Dict[str, RateRule] = {
        "login": RateRule(hourly=10, daily=30),
        "register": RateRule(hourly=3, daily=10),
        "reset_password": RateRule(hourly=3, daily=5),
        "verify_code": RateRule(hourly=10, daily=10_000_000),
    }

    def __init__(
        self,
        cache: AuthCacheManager,
        *,
        lock_seconds: int = 1800,
        rules: Optional[Dict[str, RateRule]] = None,
    ) -> None:
        self.cache = cache
        self.lock_seconds = max(1, lock_seconds)
        self.rules = dict(rules or self.DEFAULT_RULES)

    @staticmethod
    def _identity(identity: str) -> str:
        text = str(identity).strip().lower()
        return text or "anonymous"

    @staticmethod
    def _hourly_key(identity: str, action: str) -> str:
        return f"rate_limit:{identity}:{action}"

    @staticmethod
    def _daily_key(identity: str, action: str) -> str:
        return f"rate_limit_daily:{identity}:{action}"

    @staticmethod
    def _lock_key(identity: str, action: str) -> str:
        return f"rate_limit_lock:{identity}:{action}"

    def _increment_counter(self, key: str, limit: int, ttl: int) -> int:
        payload = self.cache.get(key) or {"count": 0}
        current = int(payload.get("count", 0))
        if current >= limit:
            return current
        next_value = current + 1
        current_ttl = self.cache.ttl(key)
        effective_ttl = ttl if current_ttl <= 0 else current_ttl
        self.cache.set(key, {"count": next_value, "updated_at": int(time.time())}, ttl=effective_ttl)
        return next_value

    def check_and_consume(self, *, identity: str, action: str) -> Dict[str, int]:
        ident = self._identity(identity)
        rule = self.rules.get(action)
        if not rule:
            return {"remaining_hourly": -1, "remaining_daily": -1}

        lock_key = self._lock_key(ident, action)
        lock_payload = self.cache.get(lock_key)
        if lock_payload:
            locked_seconds = self.cache.ttl(lock_key)
            raise RateLimitExceededError(
                f"请求过于频繁，已锁定，请在 {max(1, locked_seconds)} 秒后重试",
                locked_seconds=max(1, locked_seconds),
            )

        hourly_key = self._hourly_key(ident, action)
        hourly_payload = self.cache.get(hourly_key) or {"count": 0}
        hourly_count = int(hourly_payload.get("count", 0))
        if hourly_count >= rule.hourly:
            self.cache.set(lock_key, {"reason": "hourly_exceeded"}, ttl=self.lock_seconds)
            raise RateLimitExceededError("请求频率超过每小时限制，已锁定30分钟", locked_seconds=self.lock_seconds)

        daily_key = self._daily_key(ident, action)
        daily_payload = self.cache.get(daily_key) or {"count": 0}
        daily_count = int(daily_payload.get("count", 0))
        if daily_count >= rule.daily:
            self.cache.set(lock_key, {"reason": "daily_exceeded"}, ttl=self.lock_seconds)
            raise RateLimitExceededError("请求频率超过每日限制，已锁定30分钟", locked_seconds=self.lock_seconds)

        new_hourly = self._increment_counter(hourly_key, rule.hourly, ttl=3600)
        new_daily = self._increment_counter(daily_key, rule.daily, ttl=86400)
        return {
            "remaining_hourly": max(0, rule.hourly - new_hourly),
            "remaining_daily": max(0, rule.daily - new_daily),
        }


_RATE_LIMITER: Optional[AuthRateLimiter] = None
_RATE_LIMITER_LOCK = threading.Lock()


def get_auth_rate_limiter() -> AuthRateLimiter:
    global _RATE_LIMITER
    if _RATE_LIMITER is None:
        with _RATE_LIMITER_LOCK:
            if _RATE_LIMITER is None:
                from app.config import settings

                cache = AuthCacheManager(redis_url=settings.REDIS_URL, pool_size=10, strict_redis=False)
                _RATE_LIMITER = AuthRateLimiter(cache, lock_seconds=_resolve_lock_seconds_from_env())
    return _RATE_LIMITER


def reset_auth_rate_limiter() -> None:
    global _RATE_LIMITER
    with _RATE_LIMITER_LOCK:
        _RATE_LIMITER = None


def rate_limit(action: str, *, identity_getter: Optional[Callable[..., str]] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator helper used in API layer when needed."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            limiter = get_auth_rate_limiter()
            identity = identity_getter(*args, **kwargs) if identity_getter else kwargs.get("identity", "anonymous")
            limiter.check_and_consume(identity=str(identity), action=action)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def _resolve_lock_seconds_from_env() -> int:
    value = os.getenv("AUTH_RATE_LIMIT_LOCK_SECONDS")
    if not value:
        return 1800
    try:
        return max(1, int(value))
    except ValueError:
        return 1800
