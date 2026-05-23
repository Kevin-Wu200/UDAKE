"""Redis cache helpers for authentication services."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CacheUnavailableError(RuntimeError):
    """Raised when cache backends are unavailable."""


@dataclass
class _MemoryValue:
    value: str
    expires_at: Optional[float]


class _MemoryRedisLike:
    """Lightweight in-memory cache fallback with Redis-like API."""

    def __init__(self) -> None:
        self._store: Dict[str, _MemoryValue] = {}
        self._lock = threading.Lock()

    def _purge_if_expired(self, key: str) -> None:
        item = self._store.get(key)
        if item and item.expires_at is not None and item.expires_at <= time.time():
            self._store.pop(key, None)

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            self._purge_if_expired(key)
            item = self._store.get(key)
            return item.value if item else None

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        with self._lock:
            expires_at = time.time() + ex if ex else None
            self._store[key] = _MemoryValue(value=value, expires_at=expires_at)
            return True

    def delete(self, key: str) -> int:
        with self._lock:
            existed = key in self._store
            self._store.pop(key, None)
            return 1 if existed else 0

    def exists(self, key: str) -> int:
        with self._lock:
            self._purge_if_expired(key)
            return 1 if key in self._store else 0

    def ttl(self, key: str) -> int:
        with self._lock:
            self._purge_if_expired(key)
            item = self._store.get(key)
            if not item:
                return -2
            if item.expires_at is None:
                return -1
            return max(0, int(item.expires_at - time.time()))

    def ping(self) -> bool:
        return True


class AuthCacheManager:
    """
    Cache manager used by auth module.

    Supports Redis connection pooling when redis-py exists and falls back to
    in-memory cache when Redis is not available.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        *,
        pool_size: int = 10,
        strict_redis: bool = False,
        persistence_mode: str = "AOF+RDB",
    ) -> None:
        self.redis_url = redis_url
        self.pool_size = max(1, pool_size)
        self.persistence_mode = persistence_mode
        self.strict_redis = strict_redis
        self._client: Any = None
        self._is_memory = True
        self._connect()

    def _connect(self) -> None:
        if not self.redis_url:
            self._client = _MemoryRedisLike()
            self._is_memory = True
            return

        try:
            import redis  # type: ignore

            pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.pool_size,
                decode_responses=True,
            )
            client = redis.Redis(connection_pool=pool)
            client.ping()
            self._client = client
            self._is_memory = False
            logger.info("Auth cache connected to Redis, persistence=%s", self.persistence_mode)
        except Exception as exc:  # pragma: no cover - depends on runtime env
            if self.strict_redis:
                raise CacheUnavailableError("Redis unavailable for auth cache") from exc
            logger.warning("Redis unavailable, fallback to memory cache: %s", exc)
            self._client = _MemoryRedisLike()
            self._is_memory = True

    @property
    def is_memory_backend(self) -> bool:
        return self._is_memory

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception as exc:  # pragma: no cover
            raise CacheUnavailableError("cache ping failed") from exc

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        try:
            return bool(self._client.set(key, payload, ex=ttl))
        except Exception as exc:  # pragma: no cover
            raise CacheUnavailableError(f"cache set failed: key={key}") from exc

    def get(self, key: str) -> Any:
        try:
            raw = self._client.get(key)
        except Exception as exc:  # pragma: no cover
            raise CacheUnavailableError(f"cache get failed: key={key}") from exc
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def delete(self, key: str) -> bool:
        try:
            return bool(self._client.delete(key))
        except Exception as exc:  # pragma: no cover
            raise CacheUnavailableError(f"cache delete failed: key={key}") from exc

    def exists(self, key: str) -> bool:
        try:
            return bool(self._client.exists(key))
        except Exception as exc:  # pragma: no cover
            raise CacheUnavailableError(f"cache exists failed: key={key}") from exc

    def ttl(self, key: str) -> int:
        try:
            return int(self._client.ttl(key))
        except Exception as exc:  # pragma: no cover
            raise CacheUnavailableError(f"cache ttl failed: key={key}") from exc

    def set_with_jitter(
        self,
        key: str,
        value: Any,
        *,
        ttl: int,
        jitter_ratio: float = 0.15,
        min_jitter_seconds: int = 1,
    ) -> bool:
        ttl_value = max(1, int(ttl))
        jitter_span = max(min_jitter_seconds, int(ttl_value * max(0.0, float(jitter_ratio))))
        jitter = random.randint(0, jitter_span)
        return self.set(key, value, ttl=ttl_value + jitter)

    def remember_null(self, key: str, *, ttl: int = 60) -> bool:
        return self.set(key, {"__null__": True}, ttl=max(1, int(ttl)))

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        *,
        ttl: int,
        null_ttl: int = 60,
    ) -> Any:
        cached = self.get(key)
        if isinstance(cached, dict) and cached.get("__null__") is True:
            return None
        if cached is not None:
            return cached

        value = factory()
        if value is None:
            self.remember_null(key, ttl=null_ttl)
            return None
        self.set_with_jitter(key, value, ttl=ttl)
        return value


class BloomFilter:
    """Simple in-memory bloom filter used for cache-penetration protection."""

    def __init__(self, expected_items: int = 20_000, error_rate: float = 0.01) -> None:
        n = max(100, int(expected_items))
        p = min(max(error_rate, 1e-6), 0.5)
        m = int(-(n * math.log(p)) / (math.log(2) ** 2))
        k = max(1, int((m / n) * math.log(2)))
        self._size = max(256, m)
        self._hash_count = k
        self._bits = bytearray((self._size + 7) // 8)
        self._lock = threading.Lock()

    def _indexes(self, value: str) -> list[int]:
        text = str(value)
        indexes: list[int] = []
        for idx in range(self._hash_count):
            digest = hashlib.sha256(f"{idx}:{text}".encode("utf-8")).digest()
            indexes.append(int.from_bytes(digest[:8], "big") % self._size)
        return indexes

    def add(self, value: str) -> None:
        indexes = self._indexes(value)
        with self._lock:
            for index in indexes:
                self._bits[index // 8] |= 1 << (index % 8)

    def __contains__(self, value: str) -> bool:
        indexes = self._indexes(value)
        with self._lock:
            for index in indexes:
                if not (self._bits[index // 8] & (1 << (index % 8))):
                    return False
        return True
