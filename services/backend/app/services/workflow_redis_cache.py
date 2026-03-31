"""工作流模块 Redis 缓存管理器。"""

from __future__ import annotations

import fnmatch
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class _MemoryItem:
    value: str
    expires_at: Optional[float]


class _MemoryRedisLike:
    """Redis 不可用时的内存降级后端。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: Dict[str, _MemoryItem] = {}

    def _purge_expired(self, key: str) -> None:
        item = self._store.get(key)
        if item and item.expires_at is not None and item.expires_at <= time.time():
            self._store.pop(key, None)

    def ping(self) -> bool:
        return True

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            self._purge_expired(key)
            item = self._store.get(key)
            return item.value if item else None

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        with self._lock:
            expires_at = time.time() + int(ex) if ex else None
            self._store[key] = _MemoryItem(value=value, expires_at=expires_at)
            return True

    def delete(self, *keys: str) -> int:
        deleted = 0
        with self._lock:
            for key in keys:
                if key in self._store:
                    deleted += 1
                    self._store.pop(key, None)
        return deleted

    def exists(self, key: str) -> int:
        with self._lock:
            self._purge_expired(key)
            return 1 if key in self._store else 0

    def expire(self, key: str, ttl: int) -> bool:
        with self._lock:
            self._purge_expired(key)
            if key not in self._store:
                return False
            self._store[key] = _MemoryItem(value=self._store[key].value, expires_at=time.time() + int(ttl))
            return True

    def keys(self, pattern: str = "*") -> List[str]:
        with self._lock:
            now = time.time()
            expired = [k for k, item in self._store.items() if item.expires_at is not None and item.expires_at <= now]
            for key in expired:
                self._store.pop(key, None)
            return [key for key in self._store.keys() if fnmatch.fnmatch(key, pattern)]

    def scan_iter(self, match: str = "*"):
        for key in self.keys(match):
            yield key

    def info(self, section: str = "memory") -> Dict[str, Any]:
        _ = section
        with self._lock:
            return {
                "used_memory": sum(len(item.value.encode("utf-8")) for item in self._store.values()),
                "key_count": len(self._store),
            }


class WorkflowRedisCacheManager:
    """面向协作与分享场景的 Redis 缓存封装。"""

    def __init__(
        self,
        *,
        redis_url: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        pool_size: int = 20,
        socket_timeout: int = 5,
        retry_times: int = 3,
        strict_redis: bool = False,
        cluster_enabled: bool = False,
        cluster_nodes: Optional[List[str]] = None,
    ) -> None:
        self.redis_url = redis_url
        self.host = host
        self.port = int(port)
        self.db = int(db)
        self.pool_size = min(20, max(10, int(pool_size)))
        self.socket_timeout = max(1, int(socket_timeout))
        self.retry_times = max(1, int(retry_times))
        self.strict_redis = bool(strict_redis)
        self.cluster_enabled = bool(cluster_enabled)
        self.cluster_nodes = list(cluster_nodes or [])

        self._lock = threading.Lock()
        self._client: Any = None
        self._memory_backend = True
        self._ops_log: List[Dict[str, Any]] = []
        self._metrics: Dict[str, Any] = {
            "hits": 0,
            "misses": 0,
            "gets": 0,
            "sets": 0,
            "deletes": 0,
            "batch_sets": 0,
            "batch_deletes": 0,
            "pattern_deletes": 0,
            "manual_invalidations": 0,
            "cascade_invalidations": 0,
            "errors": 0,
            "reconnects": 0,
            "total_get_latency_ms": 0.0,
            "total_set_latency_ms": 0.0,
            "total_delete_latency_ms": 0.0,
        }

        self._connect()

    @classmethod
    def from_settings(cls, settings: Any) -> "WorkflowRedisCacheManager":
        return cls(
            redis_url=getattr(settings, "REDIS_URL", None),
            host=getattr(settings, "REDIS_HOST", "127.0.0.1"),
            port=int(getattr(settings, "REDIS_PORT", 6379)),
            db=int(getattr(settings, "REDIS_DB", 0)),
            pool_size=int(getattr(settings, "WORKFLOW_REDIS_POOL_SIZE", 20)),
            socket_timeout=int(getattr(settings, "WORKFLOW_REDIS_TIMEOUT_SECONDS", 5)),
            retry_times=int(getattr(settings, "WORKFLOW_REDIS_RETRY_TIMES", 3)),
            strict_redis=bool(getattr(settings, "WORKFLOW_REDIS_STRICT", False)),
            cluster_enabled=bool(getattr(settings, "WORKFLOW_REDIS_CLUSTER_ENABLED", False)),
            cluster_nodes=list(getattr(settings, "WORKFLOW_REDIS_CLUSTER_NODES", []) or []),
        )

    @property
    def is_memory_backend(self) -> bool:
        return self._memory_backend

    def _add_op_log(self, operation: str, key: str, latency_ms: float, status: str) -> None:
        with self._lock:
            self._ops_log.append(
                {
                    "ts": time.time(),
                    "operation": operation,
                    "key": key,
                    "latency_ms": round(latency_ms, 3),
                    "status": status,
                }
            )
            if len(self._ops_log) > 1000:
                self._ops_log = self._ops_log[-1000:]

    def _record_error(self) -> None:
        with self._lock:
            self._metrics["errors"] += 1

    def _connect(self) -> None:
        if not self.redis_url and not self.cluster_enabled:
            self._client = _MemoryRedisLike()
            self._memory_backend = True
            return

        try:
            import redis  # type: ignore

            if self.cluster_enabled:
                cluster_nodes = self.cluster_nodes or [f"{self.host}:{self.port}"]
                startup_nodes = []
                for node in cluster_nodes:
                    host, sep, port_text = str(node).partition(":")
                    if not sep:
                        continue
                    startup_nodes.append({"host": host, "port": int(port_text)})
                if not startup_nodes:
                    startup_nodes = [{"host": self.host, "port": self.port}]
                self._client = redis.RedisCluster(
                    startup_nodes=startup_nodes,
                    decode_responses=True,
                    socket_timeout=self.socket_timeout,
                    socket_connect_timeout=self.socket_timeout,
                )
            else:
                if self.redis_url:
                    pool = redis.ConnectionPool.from_url(
                        self.redis_url,
                        max_connections=self.pool_size,
                        decode_responses=True,
                        socket_timeout=self.socket_timeout,
                        socket_connect_timeout=self.socket_timeout,
                    )
                else:
                    pool = redis.ConnectionPool(
                        host=self.host,
                        port=self.port,
                        db=self.db,
                        max_connections=self.pool_size,
                        decode_responses=True,
                        socket_timeout=self.socket_timeout,
                        socket_connect_timeout=self.socket_timeout,
                    )
                self._client = redis.Redis(connection_pool=pool)

            self._client.ping()
            self._memory_backend = False
        except Exception as exc:  # pragma: no cover - 依赖运行环境
            if self.strict_redis:
                raise RuntimeError("workflow redis unavailable") from exc
            logger.warning("Workflow cache fallback to memory backend: %s", exc)
            self._client = _MemoryRedisLike()
            self._memory_backend = True

    def _reconnect(self) -> None:
        with self._lock:
            self._metrics["reconnects"] += 1
        self._connect()

    def _run(self, operation: str, key: str, func: Callable[[], Any], default: Any = None) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retry_times + 1):
            started = time.perf_counter()
            try:
                result = func()
                self._add_op_log(operation, key, (time.perf_counter() - started) * 1000, "ok")
                return result
            except Exception as exc:  # pragma: no cover - 依赖运行环境
                last_error = exc
                self._record_error()
                self._add_op_log(operation, key, (time.perf_counter() - started) * 1000, f"retry_{attempt}")
                if attempt < self.retry_times:
                    time.sleep(min(0.2 * attempt, 1.0))
                    self._reconnect()

        if self.strict_redis and not self._memory_backend and last_error is not None:
            raise RuntimeError(f"cache operation failed: {operation}") from last_error
        return default

    def ping(self) -> bool:
        result = self._run("ping", "__health__", lambda: bool(self._client.ping()), default=False)
        return bool(result)

    def get(self, key: str) -> Any:
        with self._lock:
            self._metrics["gets"] += 1
        started = time.perf_counter()
        raw = self._run("get", key, lambda: self._client.get(key), default=None)
        latency_ms = (time.perf_counter() - started) * 1000
        with self._lock:
            self._metrics["total_get_latency_ms"] += latency_ms
            if raw is None:
                self._metrics["misses"] += 1
            else:
                self._metrics["hits"] += 1
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
        started = time.perf_counter()
        if ttl:
            success = self._run("setex", key, lambda: bool(self._client.set(key, payload, ex=int(ttl))), default=False)
        else:
            success = self._run("set", key, lambda: bool(self._client.set(key, payload)), default=False)
        with self._lock:
            self._metrics["sets"] += 1
            self._metrics["total_set_latency_ms"] += (time.perf_counter() - started) * 1000
        return bool(success)

    def get_or_load(self, key: str, ttl: int, loader: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = loader()
        if value is not None:
            self.set(key, value, ttl=ttl)
        return value

    def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> int:
        if not items:
            return 0
        count = 0
        for key, value in items.items():
            if self.set(key, value, ttl=ttl):
                count += 1
        with self._lock:
            self._metrics["batch_sets"] += 1
        return count

    def delete(self, key: str) -> bool:
        started = time.perf_counter()
        deleted = self._run("delete", key, lambda: int(self._client.delete(key)), default=0)
        with self._lock:
            self._metrics["deletes"] += 1
            self._metrics["total_delete_latency_ms"] += (time.perf_counter() - started) * 1000
            self._metrics["manual_invalidations"] += 1
        return bool(deleted)

    def delete_many(self, keys: List[str]) -> int:
        deleted = 0
        for key in keys:
            deleted += 1 if self.delete(key) else 0
        with self._lock:
            self._metrics["batch_deletes"] += 1
        return deleted

    def delete_pattern(self, pattern: str) -> int:
        matched = list(self._run("keys", pattern, lambda: list(self._client.scan_iter(match=pattern)), default=[]))
        if not matched:
            return 0
        deleted = int(self._run("delete_pattern", pattern, lambda: int(self._client.delete(*matched)), default=0))
        with self._lock:
            self._metrics["pattern_deletes"] += 1
            self._metrics["manual_invalidations"] += 1
        return deleted

    def expire(self, key: str, ttl: int) -> bool:
        return bool(self._run("expire", key, lambda: bool(self._client.expire(key, int(ttl))), default=False))

    def invalidate_cascade(self, root_key: str, related_patterns: Optional[List[str]] = None) -> int:
        deleted = 0
        deleted += 1 if self.delete(root_key) else 0
        for pattern in related_patterns or []:
            deleted += self.delete_pattern(pattern)
        with self._lock:
            self._metrics["cascade_invalidations"] += 1
        return deleted

    def get_memory_usage(self) -> Dict[str, Any]:
        info = self._run("info", "memory", lambda: self._client.info("memory"), default={})
        if not isinstance(info, dict):
            info = {}
        return {
            "used_memory": int(info.get("used_memory", 0) or 0),
            "used_memory_human": str(info.get("used_memory_human", "")),
            "maxmemory": int(info.get("maxmemory", 0) or 0),
            "fragmentation_ratio": float(info.get("mem_fragmentation_ratio", 0.0) or 0.0),
            "backend": "memory" if self._memory_backend else "redis",
        }

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            data = dict(self._metrics)
            logs = list(self._ops_log)

        total = int(data["hits"]) + int(data["misses"])
        hit_rate = (float(data["hits"]) / total) if total > 0 else 0.0
        avg_get = (float(data["total_get_latency_ms"]) / int(data["gets"])) if data["gets"] else 0.0
        avg_set = (float(data["total_set_latency_ms"]) / int(data["sets"])) if data["sets"] else 0.0
        avg_delete = (float(data["total_delete_latency_ms"]) / int(data["deletes"])) if data["deletes"] else 0.0

        data.update(
            {
                "hit_rate": round(hit_rate, 4),
                "avg_get_latency_ms": round(avg_get, 3),
                "avg_set_latency_ms": round(avg_set, 3),
                "avg_delete_latency_ms": round(avg_delete, 3),
                "memory": self.get_memory_usage(),
                "recent_operations": logs[-50:],
                "healthy": self.ping(),
            }
        )
        return data
