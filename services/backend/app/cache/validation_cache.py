"""Validation result cache for product-key API."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional


class ValidationCacheManager:
    def __init__(self, cache_backend: Any, *, ttl_seconds: int = 300) -> None:
        self._cache = cache_backend
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._prefix = "product_key_validation"
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _hash_key(product_key: str) -> str:
        return hashlib.sha256(product_key.encode("utf-8")).hexdigest()

    def _build_cache_key(self, product_key: str) -> str:
        return f"{self._prefix}:{self._hash_key(product_key)}"

    def get(self, product_key: str) -> Optional[Dict[str, Any]]:
        payload = self._cache.get(self._build_cache_key(product_key))
        if isinstance(payload, dict):
            self._hits += 1
            return payload
        self._misses += 1
        return None

    def set(self, product_key: str, result: Dict[str, Any]) -> None:
        payload = {
            "valid": bool(result.get("valid", False)),
            "key_type": result.get("key_type"),
            "message": str(result.get("message", "")),
            "timestamp": int(time.time()),
        }
        self._cache.set(self._build_cache_key(product_key), payload, ttl=self._ttl_seconds)

    def invalidate(self, product_key: str) -> None:
        self._cache.delete(self._build_cache_key(product_key))

    def metrics(self) -> Dict[str, float]:
        total = self._hits + self._misses
        hit_rate = float(self._hits / total) if total else 0.0
        return {
            "hits": float(self._hits),
            "misses": float(self._misses),
            "hit_rate": hit_rate,
            "ttl_seconds": float(self._ttl_seconds),
        }
