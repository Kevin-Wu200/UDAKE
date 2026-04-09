"""异常检测模型缓存组件。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import copy
import threading
import time
from typing import Any, Optional


@dataclass
class _CacheEntry:
    value: dict[str, Any]
    expires_at: float
    created_at: float


@dataclass
class _NamespaceMetrics:
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    expirations: int = 0
    cleanup_runs: int = 0
    cleanup_removed: int = 0

    @property
    def requests(self) -> int:
        return int(self.hits + self.misses)

    @property
    def hit_rate(self) -> float:
        req = self.requests
        if req <= 0:
            return 0.0
        return float(self.hits / req)


class AnomalyModelCache:
    """服务层异常检测结果缓存（预测 + 解释）。"""

    _SUPPORTED_NAMESPACES = ("prediction", "explanation")

    def __init__(self, *, cache_size: int = 256, ttl_seconds: int = 600) -> None:
        self.cache_size = max(8, int(cache_size))
        self.ttl_seconds = max(1, int(ttl_seconds))
        self._lock = threading.Lock()
        self._entries: dict[str, "OrderedDict[str, _CacheEntry]"] = {
            "prediction": OrderedDict(),
            "explanation": OrderedDict(),
        }
        self._metrics: dict[str, _NamespaceMetrics] = {
            "prediction": _NamespaceMetrics(),
            "explanation": _NamespaceMetrics(),
        }

    def _now(self) -> float:
        return time.time()

    def _touch(self, namespace: str, key: str) -> None:
        self._entries[namespace].move_to_end(key)

    def _cleanup_expired(self, namespace: str, now_ts: Optional[float] = None) -> int:
        now = self._now() if now_ts is None else float(now_ts)
        bucket = self._entries[namespace]
        removed = 0
        keys = list(bucket.keys())
        for key in keys:
            entry = bucket.get(key)
            if entry is None:
                continue
            if entry.expires_at <= now:
                bucket.pop(key, None)
                removed += 1
        if removed > 0:
            self._metrics[namespace].expirations += removed
        return removed

    def _assert_namespace(self, namespace: str) -> str:
        ns = str(namespace).strip().lower()
        if ns not in self._SUPPORTED_NAMESPACES:
            raise ValueError(f"unsupported cache namespace: {namespace}")
        return ns

    def get(self, namespace: str, key: str) -> Optional[dict[str, Any]]:
        ns = self._assert_namespace(namespace)
        with self._lock:
            now = self._now()
            bucket = self._entries[ns]
            entry = bucket.get(key)
            if entry is None:
                self._metrics[ns].misses += 1
                return None
            if entry.expires_at <= now:
                bucket.pop(key, None)
                self._metrics[ns].misses += 1
                self._metrics[ns].expirations += 1
                return None
            self._touch(ns, key)
            self._metrics[ns].hits += 1
            return copy.deepcopy(entry.value)

    def set(self, namespace: str, key: str, value: dict[str, Any]) -> None:
        ns = self._assert_namespace(namespace)
        payload = copy.deepcopy(value)
        with self._lock:
            now = self._now()
            self._cleanup_expired(ns, now)
            bucket = self._entries[ns]
            bucket[key] = _CacheEntry(
                value=payload,
                expires_at=now + self.ttl_seconds,
                created_at=now,
            )
            self._touch(ns, key)
            self._metrics[ns].sets += 1

            while len(bucket) > self.cache_size:
                bucket.popitem(last=False)
                self._metrics[ns].evictions += 1

    def cleanup(self, namespace: Optional[str] = None) -> dict[str, int]:
        removed_by_ns: dict[str, int] = {}
        with self._lock:
            targets = [self._assert_namespace(namespace)] if namespace else list(self._SUPPORTED_NAMESPACES)
            now = self._now()
            for ns in targets:
                self._metrics[ns].cleanup_runs += 1
                removed = self._cleanup_expired(ns, now)
                self._metrics[ns].cleanup_removed += removed
                removed_by_ns[ns] = removed
        return removed_by_ns

    def clear(self, namespace: Optional[str] = None) -> dict[str, int]:
        removed_by_ns: dict[str, int] = {}
        with self._lock:
            targets = [self._assert_namespace(namespace)] if namespace else list(self._SUPPORTED_NAMESPACES)
            for ns in targets:
                removed = len(self._entries[ns])
                self._entries[ns].clear()
                removed_by_ns[ns] = removed
        return removed_by_ns

    def stats(self) -> dict[str, Any]:
        with self._lock:
            namespaces: dict[str, dict[str, Any]] = {}
            total_hits = 0
            total_requests = 0
            total_entries = 0
            for ns in self._SUPPORTED_NAMESPACES:
                metric = self._metrics[ns]
                entry_count = len(self._entries[ns])
                total_entries += entry_count
                total_hits += metric.hits
                total_requests += metric.requests
                namespaces[ns] = {
                    "entries": entry_count,
                    "cache_size": self.cache_size,
                    "ttl_seconds": self.ttl_seconds,
                    "hits": metric.hits,
                    "misses": metric.misses,
                    "requests": metric.requests,
                    "hit_rate": round(metric.hit_rate, 4),
                    "sets": metric.sets,
                    "evictions": metric.evictions,
                    "expirations": metric.expirations,
                    "cleanup_runs": metric.cleanup_runs,
                    "cleanup_removed": metric.cleanup_removed,
                }

            overall_hit_rate = 0.0 if total_requests <= 0 else float(total_hits / total_requests)
            return {
                "enabled": True,
                "entries": total_entries,
                "cache_size": self.cache_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": total_hits,
                "requests": total_requests,
                "hit_rate": round(overall_hit_rate, 4),
                "namespaces": namespaces,
            }
