"""异常检测模型缓存组件。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import base64
import copy
import json
from pathlib import Path
import threading
import time
from typing import Any, Optional
import zlib


@dataclass
class _CacheEntry:
    value: dict[str, Any]
    expires_at: float
    created_at: float


@dataclass
class _L2CacheEntry:
    payload: str
    encoding: str
    expires_at: float
    created_at: float


@dataclass
class _NamespaceMetrics:
    hits: int = 0
    l1_hits: int = 0
    l2_hits: int = 0
    misses: int = 0
    sets: int = 0
    l1_evictions: int = 0
    expirations: int = 0
    cleanup_runs: int = 0
    cleanup_removed: int = 0
    invalidations: int = 0
    warmup_sets: int = 0
    persist_writes: int = 0
    compressions: int = 0
    compression_saved_bytes: int = 0

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
    _PLAIN_ENCODING = "json"
    _COMPRESSED_ENCODING = "zlib+base64+json"

    def __init__(
        self,
        *,
        cache_size: int = 256,
        ttl_seconds: int = 600,
        persist_path: str | None = None,
        enable_compression: bool = True,
        compression_threshold_bytes: int = 2048,
    ) -> None:
        self.cache_size = max(8, int(cache_size))
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.persist_path = str(persist_path).strip() if persist_path else None
        self.enable_compression = bool(enable_compression)
        self.compression_threshold_bytes = max(128, int(compression_threshold_bytes))

        self._lock = threading.Lock()
        self._entries: dict[str, "OrderedDict[str, _CacheEntry]"] = {
            "prediction": OrderedDict(),
            "explanation": OrderedDict(),
        }
        self._l2_entries: dict[str, dict[str, _L2CacheEntry]] = {
            "prediction": {},
            "explanation": {},
        }
        self._metrics: dict[str, _NamespaceMetrics] = {
            "prediction": _NamespaceMetrics(),
            "explanation": _NamespaceMetrics(),
        }

        if self.persist_path:
            self._load_persisted()

    def _now(self) -> float:
        return time.time()

    def _touch(self, namespace: str, key: str) -> None:
        self._entries[namespace].move_to_end(key)

    def _assert_namespace(self, namespace: str) -> str:
        ns = str(namespace).strip().lower()
        if ns not in self._SUPPORTED_NAMESPACES:
            raise ValueError(f"unsupported cache namespace: {namespace}")
        return ns

    def _encode_payload(self, value: dict[str, Any]) -> tuple[str, str, int, int]:
        raw_json = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        raw_bytes = raw_json.encode("utf-8")

        if not self.enable_compression or len(raw_bytes) < self.compression_threshold_bytes:
            return self._PLAIN_ENCODING, raw_json, len(raw_bytes), len(raw_bytes)

        compressed = zlib.compress(raw_bytes, level=6)
        compressed_b64 = base64.b64encode(compressed).decode("ascii")
        return self._COMPRESSED_ENCODING, compressed_b64, len(raw_bytes), len(compressed)

    def _decode_payload(self, encoding: str, payload: str) -> dict[str, Any]:
        if encoding == self._PLAIN_ENCODING:
            return json.loads(payload)
        if encoding == self._COMPRESSED_ENCODING:
            raw_json = zlib.decompress(base64.b64decode(payload.encode("ascii"))).decode("utf-8")
            return json.loads(raw_json)
        raise ValueError(f"unsupported payload encoding: {encoding}")

    def _cleanup_expired(self, namespace: str, now_ts: Optional[float] = None) -> int:
        now = self._now() if now_ts is None else float(now_ts)
        removed = 0

        l1_bucket = self._entries[namespace]
        for key in list(l1_bucket.keys()):
            entry = l1_bucket.get(key)
            if entry is None:
                continue
            if entry.expires_at <= now:
                l1_bucket.pop(key, None)
                removed += 1

        l2_bucket = self._l2_entries[namespace]
        for key in list(l2_bucket.keys()):
            entry = l2_bucket.get(key)
            if entry is None:
                continue
            if entry.expires_at <= now:
                l2_bucket.pop(key, None)
                removed += 1

        if removed > 0:
            self._metrics[namespace].expirations += removed
        return removed

    def _evict_l1_if_needed(self, namespace: str) -> None:
        l1_bucket = self._entries[namespace]
        while len(l1_bucket) > self.cache_size:
            l1_bucket.popitem(last=False)
            self._metrics[namespace].l1_evictions += 1

    def _save_persisted_locked(self) -> None:
        if not self.persist_path:
            return

        data: dict[str, Any] = {
            "version": 1,
            "saved_at": self._now(),
            "cache_size": self.cache_size,
            "ttl_seconds": self.ttl_seconds,
            "namespaces": {},
        }
        for ns in self._SUPPORTED_NAMESPACES:
            rows: dict[str, dict[str, Any]] = {}
            for key, entry in self._l2_entries[ns].items():
                rows[key] = {
                    "payload": entry.payload,
                    "encoding": entry.encoding,
                    "expires_at": entry.expires_at,
                    "created_at": entry.created_at,
                }
            data["namespaces"][ns] = rows

        target = Path(self.persist_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_target = target.with_suffix(f"{target.suffix}.tmp")
        temp_target.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temp_target.replace(target)

        for ns in self._SUPPORTED_NAMESPACES:
            self._metrics[ns].persist_writes += 1

    def _load_persisted(self) -> None:
        if not self.persist_path:
            return
        target = Path(self.persist_path)
        if not target.exists():
            return
        try:
            raw = target.read_text(encoding="utf-8")
            payload = json.loads(raw)
            now = self._now()
            namespaces = payload.get("namespaces", {})
            for ns in self._SUPPORTED_NAMESPACES:
                rows = namespaces.get(ns, {})
                if not isinstance(rows, dict):
                    continue
                for key, item in rows.items():
                    try:
                        expires_at = float(item.get("expires_at", now))
                        if expires_at <= now:
                            continue
                        entry = _L2CacheEntry(
                            payload=str(item.get("payload", "")),
                            encoding=str(item.get("encoding", self._PLAIN_ENCODING)),
                            expires_at=expires_at,
                            created_at=float(item.get("created_at", now)),
                        )
                        # 读取阶段只装载 L2，按需提升到 L1。
                        self._l2_entries[ns][str(key)] = entry
                    except Exception:
                        continue
        except Exception:
            # 持久化文件损坏时容错，不影响主链路。
            return

    def get(self, namespace: str, key: str) -> Optional[dict[str, Any]]:
        ns = self._assert_namespace(namespace)
        with self._lock:
            now = self._now()
            l1_bucket = self._entries[ns]
            entry = l1_bucket.get(key)
            if entry is not None:
                if entry.expires_at > now:
                    self._touch(ns, key)
                    self._metrics[ns].hits += 1
                    self._metrics[ns].l1_hits += 1
                    return copy.deepcopy(entry.value)
                l1_bucket.pop(key, None)
                self._metrics[ns].expirations += 1

            l2_entry = self._l2_entries[ns].get(key)
            if l2_entry is not None:
                if l2_entry.expires_at <= now:
                    self._l2_entries[ns].pop(key, None)
                    self._metrics[ns].misses += 1
                    self._metrics[ns].expirations += 1
                    return None
                value = self._decode_payload(l2_entry.encoding, l2_entry.payload)
                l1_bucket[key] = _CacheEntry(value=copy.deepcopy(value), expires_at=l2_entry.expires_at, created_at=l2_entry.created_at)
                self._touch(ns, key)
                self._evict_l1_if_needed(ns)
                self._metrics[ns].hits += 1
                self._metrics[ns].l2_hits += 1
                return copy.deepcopy(value)

            self._metrics[ns].misses += 1
            return None

    def set(self, namespace: str, key: str, value: dict[str, Any], *, ttl_seconds: int | None = None, warmup: bool = False) -> None:
        ns = self._assert_namespace(namespace)
        payload = copy.deepcopy(value)
        with self._lock:
            now = self._now()
            ttl = self.ttl_seconds if ttl_seconds is None else max(1, int(ttl_seconds))
            expires_at = now + ttl
            self._cleanup_expired(ns, now)

            self._entries[ns][key] = _CacheEntry(value=payload, expires_at=expires_at, created_at=now)
            self._touch(ns, key)
            self._evict_l1_if_needed(ns)

            encoding, serialized, raw_size, stored_size = self._encode_payload(payload)
            self._l2_entries[ns][key] = _L2CacheEntry(
                payload=serialized,
                encoding=encoding,
                expires_at=expires_at,
                created_at=now,
            )
            if encoding == self._COMPRESSED_ENCODING:
                self._metrics[ns].compressions += 1
                self._metrics[ns].compression_saved_bytes += max(0, int(raw_size - stored_size))

            self._metrics[ns].sets += 1
            if warmup:
                self._metrics[ns].warmup_sets += 1

            self._save_persisted_locked()

    def warmup(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        summary = {"total": len(items), "succeeded": 0, "failed": 0, "errors": []}
        for item in items:
            namespace = str(item.get("namespace", "")).strip().lower()
            key = str(item.get("key", ""))
            value = item.get("value")
            ttl_seconds = item.get("ttl_seconds")
            if not namespace or not key or not isinstance(value, dict):
                summary["failed"] += 1
                summary["errors"].append({"item": item, "error": "invalid warmup item"})
                continue
            try:
                self.set(namespace, key, value, ttl_seconds=ttl_seconds, warmup=True)
                summary["succeeded"] += 1
            except Exception as exc:
                summary["failed"] += 1
                summary["errors"].append({"item": item, "error": str(exc)})
        return summary

    def invalidate(self, *, namespace: Optional[str] = None, key_prefix: Optional[str] = None) -> dict[str, int]:
        removed_by_ns: dict[str, int] = {}
        with self._lock:
            targets = [self._assert_namespace(namespace)] if namespace else list(self._SUPPORTED_NAMESPACES)
            for ns in targets:
                removed = 0
                prefixes = str(key_prefix or "")
                l1_bucket = self._entries[ns]
                l2_bucket = self._l2_entries[ns]
                if not prefixes:
                    removed += len(l1_bucket)
                    removed += len(l2_bucket)
                    l1_bucket.clear()
                    l2_bucket.clear()
                else:
                    for key in [k for k in l1_bucket.keys() if k.startswith(prefixes)]:
                        l1_bucket.pop(key, None)
                        removed += 1
                    for key in [k for k in l2_bucket.keys() if k.startswith(prefixes)]:
                        l2_bucket.pop(key, None)
                        removed += 1
                self._metrics[ns].invalidations += removed
                removed_by_ns[ns] = removed
            self._save_persisted_locked()
        return removed_by_ns

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
            self._save_persisted_locked()
        return removed_by_ns

    def clear(self, namespace: Optional[str] = None) -> dict[str, int]:
        removed_by_ns: dict[str, int] = {}
        with self._lock:
            targets = [self._assert_namespace(namespace)] if namespace else list(self._SUPPORTED_NAMESPACES)
            for ns in targets:
                removed = len(self._entries[ns]) + len(self._l2_entries[ns])
                self._entries[ns].clear()
                self._l2_entries[ns].clear()
                removed_by_ns[ns] = removed
            self._save_persisted_locked()
        return removed_by_ns

    def persist(self) -> dict[str, Any]:
        with self._lock:
            self._save_persisted_locked()
            return {
                "persist_enabled": bool(self.persist_path),
                "persist_path": self.persist_path,
                "saved": bool(self.persist_path),
                "stats": self.stats(),
            }

    def stats(self) -> dict[str, Any]:
        with self._lock:
            namespaces: dict[str, dict[str, Any]] = {}
            total_hits = 0
            total_requests = 0
            total_l1_entries = 0
            total_l2_entries = 0
            total_compression_saved = 0
            total_compressions = 0

            for ns in self._SUPPORTED_NAMESPACES:
                metric = self._metrics[ns]
                l1_count = len(self._entries[ns])
                l2_count = len(self._l2_entries[ns])
                total_l1_entries += l1_count
                total_l2_entries += l2_count
                total_hits += metric.hits
                total_requests += metric.requests
                total_compression_saved += metric.compression_saved_bytes
                total_compressions += metric.compressions
                namespaces[ns] = {
                    "entries": l1_count,
                    "l1_entries": l1_count,
                    "l2_entries": l2_count,
                    "cache_size": self.cache_size,
                    "ttl_seconds": self.ttl_seconds,
                    "hits": metric.hits,
                    "l1_hits": metric.l1_hits,
                    "l2_hits": metric.l2_hits,
                    "misses": metric.misses,
                    "requests": metric.requests,
                    "hit_rate": round(metric.hit_rate, 4),
                    "sets": metric.sets,
                    "warmup_sets": metric.warmup_sets,
                    "l1_evictions": metric.l1_evictions,
                    "evictions": metric.l1_evictions,
                    "expirations": metric.expirations,
                    "cleanup_runs": metric.cleanup_runs,
                    "cleanup_removed": metric.cleanup_removed,
                    "invalidations": metric.invalidations,
                    "persist_writes": metric.persist_writes,
                    "compressions": metric.compressions,
                    "compression_saved_bytes": metric.compression_saved_bytes,
                }

            overall_hit_rate = 0.0 if total_requests <= 0 else float(total_hits / total_requests)
            return {
                "enabled": True,
                "multi_level": True,
                "entries": total_l1_entries,
                "l1_entries": total_l1_entries,
                "l2_entries": total_l2_entries,
                "cache_size": self.cache_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": total_hits,
                "requests": total_requests,
                "hit_rate": round(overall_hit_rate, 4),
                "compression_enabled": self.enable_compression,
                "compression_threshold_bytes": self.compression_threshold_bytes,
                "compressions": total_compressions,
                "compression_saved_bytes": total_compression_saved,
                "persist_enabled": bool(self.persist_path),
                "persist_path": self.persist_path,
                "namespaces": namespaces,
            }
