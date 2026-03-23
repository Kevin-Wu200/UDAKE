"""通用缓存管理器。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    created_at: float


class CacheManager:
    def __init__(self, max_items: int = 1024, ttl_seconds: int = 300) -> None:
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if self.ttl_seconds > 0 and (time.time() - entry.created_at) > self.ttl_seconds:
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        self._evict_if_needed()
        self._store[key] = CacheEntry(value=value, created_at=time.time())

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def _evict_if_needed(self) -> None:
        if len(self._store) < self.max_items:
            return
        oldest_key = min(self._store, key=lambda item: self._store[item].created_at)
        self._store.pop(oldest_key, None)
