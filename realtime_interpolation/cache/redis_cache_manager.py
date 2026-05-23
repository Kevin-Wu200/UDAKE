"""
Redis 缓存集成管理器
Redis Cache Integration Manager

提供以下能力：
1. Redis 连接池、重试、健康检查与内存降级
2. 适用于插值场景的数据结构（Hash/ZSet/List）
3. 缓存预热、失效、分布式失效通知
4. 基础一致性保障（分布式锁 + 版本控制 + CAS）
"""

from __future__ import annotations

import fnmatch
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .cache_manager import CacheManager
from .cache_strategy import MultiLevelCacheStrategy

logger = logging.getLogger(__name__)


@dataclass
class _MemoryItem:
    value: Any
    expires_at: Optional[float] = None


class _MemoryRedisLike:
    """Redis 不可用时的内存后端（最小 Redis API 子集）。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._kv: Dict[str, _MemoryItem] = {}
        self._hash: Dict[str, Dict[str, str]] = {}
        self._zset: Dict[str, Dict[str, float]] = {}
        self._list: Dict[str, List[str]] = {}

    def _is_expired(self, key: str) -> bool:
        item = self._kv.get(key)
        if item is None:
            return False
        if item.expires_at is None:
            return False
        return item.expires_at <= time.time()

    def _purge_if_expired(self, key: str) -> None:
        if self._is_expired(key):
            self._kv.pop(key, None)
            self._hash.pop(key, None)
            self._zset.pop(key, None)
            self._list.pop(key, None)

    def ping(self) -> bool:
        return True

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            self._purge_if_expired(key)
            item = self._kv.get(key)
            if item is None:
                return None
            return str(item.value)

    def set(self, key: str, value: str, ex: Optional[int] = None, nx: bool = False) -> bool:
        with self._lock:
            self._purge_if_expired(key)
            if nx and key in self._kv:
                return False
            expires_at = time.time() + int(ex) if ex else None
            self._kv[key] = _MemoryItem(value=value, expires_at=expires_at)
            return True

    def ttl(self, key: str) -> int:
        with self._lock:
            self._purge_if_expired(key)
            item = self._kv.get(key)
            if item is None:
                return -2
            if item.expires_at is None:
                return -1
            return max(0, int(item.expires_at - time.time()))

    def expire(self, key: str, ttl: int) -> bool:
        with self._lock:
            self._purge_if_expired(key)
            if key not in self._kv:
                # 支持对 hash/zset/list 设置 ttl
                if key in self._hash or key in self._zset or key in self._list:
                    self._kv[key] = _MemoryItem(value="__structure__", expires_at=time.time() + int(ttl))
                    return True
                return False
            self._kv[key].expires_at = time.time() + int(ttl)
            return True

    def delete(self, *keys: str) -> int:
        deleted = 0
        with self._lock:
            for key in keys:
                existed = key in self._kv or key in self._hash or key in self._zset or key in self._list
                self._kv.pop(key, None)
                self._hash.pop(key, None)
                self._zset.pop(key, None)
                self._list.pop(key, None)
                if existed:
                    deleted += 1
        return deleted

    def exists(self, key: str) -> int:
        with self._lock:
            self._purge_if_expired(key)
            exists = key in self._kv or key in self._hash or key in self._zset or key in self._list
            return 1 if exists else 0

    def scan_iter(self, match: str = "*"):
        with self._lock:
            keys = set(self._kv.keys()) | set(self._hash.keys()) | set(self._zset.keys()) | set(self._list.keys())
            for key in list(keys):
                self._purge_if_expired(key)
            keys = set(self._kv.keys()) | set(self._hash.keys()) | set(self._zset.keys()) | set(self._list.keys())
            for key in sorted(keys):
                if fnmatch.fnmatch(key, match):
                    yield key

    def hset(self, key: str, mapping: Dict[str, str]) -> int:
        with self._lock:
            self._purge_if_expired(key)
            self._hash.setdefault(key, {}).update(mapping)
            return len(mapping)

    def hgetall(self, key: str) -> Dict[str, str]:
        with self._lock:
            self._purge_if_expired(key)
            return dict(self._hash.get(key, {}))

    def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        with self._lock:
            self._purge_if_expired(key)
            self._hash.setdefault(key, {})
            current = int(self._hash[key].get(field, "0"))
            new_value = current + int(amount)
            self._hash[key][field] = str(new_value)
            return new_value

    def zadd(self, key: str, mapping: Dict[str, float]) -> int:
        with self._lock:
            self._purge_if_expired(key)
            self._zset.setdefault(key, {})
            for member, score in mapping.items():
                self._zset[key][member] = float(score)
            return len(mapping)

    def zrangebyscore(self, key: str, min_score: float, max_score: float, start: int = 0, num: Optional[int] = None) -> List[str]:
        with self._lock:
            self._purge_if_expired(key)
            members = self._zset.get(key, {})
            matched = [(member, score) for member, score in members.items() if float(min_score) <= score <= float(max_score)]
            matched.sort(key=lambda item: item[1])
            values = [member for member, _ in matched]
            sliced = values[start:]
            if num is not None:
                sliced = sliced[: max(0, int(num))]
            return sliced

    def rpush(self, key: str, value: str) -> int:
        with self._lock:
            self._purge_if_expired(key)
            self._list.setdefault(key, []).append(value)
            return len(self._list[key])

    def ltrim(self, key: str, start: int, end: int) -> bool:
        with self._lock:
            self._purge_if_expired(key)
            if key not in self._list:
                return True
            values = self._list[key]
            length = len(values)
            s = max(0, start if start >= 0 else length + start)
            e = end if end >= 0 else length + end
            e = min(length - 1, e)
            if e < s:
                self._list[key] = []
                return True
            self._list[key] = values[s:e + 1]
            return True

    def lrange(self, key: str, start: int, end: int) -> List[str]:
        with self._lock:
            self._purge_if_expired(key)
            values = self._list.get(key, [])
            if not values:
                return []
            length = len(values)
            s = max(0, start if start >= 0 else length + start)
            e = end if end >= 0 else length + end
            e = min(length - 1, e)
            if e < s:
                return []
            return list(values[s:e + 1])

    def publish(self, channel: str, message: str) -> int:
        _ = channel
        _ = message
        return 1


class RedisCacheManager(CacheManager):
    """
    Redis 集成缓存管理器（L1 本地 + L2 Redis/内存降级）。

    兼容 CacheManager 的通用接口，并扩展插值场景专用 API。
    """

    def __init__(
        self,
        *,
        cache_strategy: Optional[MultiLevelCacheStrategy] = None,
        redis_url: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        pool_size: int = 20,
        socket_timeout: int = 5,
        retry_times: int = 3,
        strict_redis: bool = False,
        namespace: str = "kriging",
        invalidation_channel: str = "kriging:invalidate",
        enable_auto_cleanup: bool = True,
        cleanup_interval: int = 300,
        ttl: int = 3600,
    ) -> None:
        super().__init__(
            cache_strategy=cache_strategy,
            enable_auto_cleanup=enable_auto_cleanup,
            cleanup_interval=cleanup_interval,
            ttl=ttl,
        )
        self.redis_url = redis_url
        self.host = host
        self.port = int(port)
        self.db = int(db)
        self.password = password
        self.pool_size = max(1, int(pool_size))
        self.socket_timeout = max(1, int(socket_timeout))
        self.retry_times = max(1, int(retry_times))
        self.strict_redis = bool(strict_redis)
        self.namespace = namespace.strip() or "kriging"
        self.invalidation_channel = invalidation_channel

        self._redis_client: Any = None
        self._memory_backend = True
        self._backend_lock = threading.RLock()
        self._invalidation_listeners: List[Callable[[str, str], None]] = []

        self._redis_metrics: Dict[str, Any] = {
            "gets": 0,
            "sets": 0,
            "deletes": 0,
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "retries": 0,
            "reconnects": 0,
            "total_get_latency_ms": 0.0,
            "total_set_latency_ms": 0.0,
            "total_delete_latency_ms": 0.0,
        }
        self._connect_backend()

    @property
    def is_memory_backend(self) -> bool:
        return self._memory_backend

    def _connect_backend(self) -> None:
        if not self.redis_url and not self.host:
            self._redis_client = _MemoryRedisLike()
            self._memory_backend = True
            return

        try:
            import redis  # type: ignore

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
                    password=self.password,
                    max_connections=self.pool_size,
                    decode_responses=True,
                    socket_timeout=self.socket_timeout,
                    socket_connect_timeout=self.socket_timeout,
                )
            client = redis.Redis(connection_pool=pool)
            client.ping()
            self._redis_client = client
            self._memory_backend = False
            logger.info("RedisCacheManager 已连接 Redis")
        except Exception as exc:  # pragma: no cover - 依赖运行环境
            if self.strict_redis:
                raise RuntimeError("Redis 不可用，且 strict_redis=True") from exc
            logger.warning("Redis 不可用，回退内存后端: %s", exc)
            self._redis_client = _MemoryRedisLike()
            self._memory_backend = True

    def _reconnect(self) -> None:
        with self._backend_lock:
            self._redis_metrics["reconnects"] += 1
        self._connect_backend()

    def _run(self, op: str, func: Callable[[], Any], default: Any = None) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retry_times + 1):
            try:
                return func()
            except Exception as exc:  # pragma: no cover - 依赖运行环境
                last_error = exc
                with self._backend_lock:
                    self._redis_metrics["errors"] += 1
                    self._redis_metrics["retries"] += 1
                if attempt < self.retry_times:
                    time.sleep(min(0.2 * attempt, 1.0))
                    self._reconnect()
        if self.strict_redis and not self._memory_backend and last_error is not None:
            raise RuntimeError(f"Redis 操作失败: {op}") from last_error
        return default

    def _key(self, key: str) -> str:
        return f"{self.namespace}:kv:{key}"

    def _grid_key(self, task_id: str) -> str:
        return f"{self.namespace}:grid:{task_id}"

    def _points_key(self, task_id: str) -> str:
        return f"{self.namespace}:points:{task_id}"

    def _history_key(self, task_id: str) -> str:
        return f"{self.namespace}:history:{task_id}"

    def _stats_key(self, task_id: str) -> str:
        return f"{self.namespace}:stats:{task_id}"

    def _version_key(self, task_id: str) -> str:
        return f"{self.namespace}:version:{task_id}"

    def _lock_key(self, task_id: str) -> str:
        return f"{self.namespace}:lock:{task_id}"

    def _record_task_metric(self, task_id: str, field: str, value: int = 1) -> None:
        key = self._stats_key(task_id)
        self._run("hincrby", lambda: self._redis_client.hincrby(key, field, int(value)), default=0)

    def get(self, key: str, version: Optional[int] = None) -> Optional[Any]:
        local_value = super().get(key, version=version)
        if local_value is not None:
            if key.startswith("pred_"):
                self._record_task_metric(key.split("_", 2)[1], "hits", 1)
            return local_value

        internal_key = key if version is None else f"{key}::v{int(version)}"
        redis_key = self._key(internal_key)

        started = time.perf_counter()
        raw = self._run("get", lambda: self._redis_client.get(redis_key), default=None)
        with self._backend_lock:
            self._redis_metrics["gets"] += 1
            self._redis_metrics["total_get_latency_ms"] += (time.perf_counter() - started) * 1000

        if raw is None:
            with self._backend_lock:
                self._redis_metrics["misses"] += 1
            if key.startswith("pred_"):
                self._record_task_metric(key.split("_", 2)[1], "misses", 1)
            return None

        with self._backend_lock:
            self._redis_metrics["hits"] += 1

        try:
            value = json.loads(raw)
        except Exception:
            value = raw

        super().put(key, value, ttl=self.ttl if self.ttl > 0 else None, version=version)
        if key.startswith("pred_"):
            self._record_task_metric(key.split("_", 2)[1], "hits", 1)
        return value

    def put(
        self,
        key: str,
        value: Any,
        size: int = 1,
        ttl: Optional[int] = None,
        version: Optional[int] = None
    ) -> None:
        super().put(key, value, size=size, ttl=ttl, version=version)

        internal_key = key if version is None else f"{key}::v{int(version)}"
        redis_key = self._key(internal_key)
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

        started = time.perf_counter()
        if ttl:
            self._run("setex", lambda: self._redis_client.set(redis_key, payload, ex=int(ttl)), default=False)
        else:
            self._run("set", lambda: self._redis_client.set(redis_key, payload), default=False)

        with self._backend_lock:
            self._redis_metrics["sets"] += 1
            self._redis_metrics["total_set_latency_ms"] += (time.perf_counter() - started) * 1000

    def remove(self, key: str) -> bool:
        removed = super().remove(key)
        self._run("delete", lambda: self._redis_client.delete(self._key(key)), default=0)
        with self._backend_lock:
            self._redis_metrics["deletes"] += 1
        return removed

    def clear(self) -> None:
        super().clear()
        pattern = f"{self.namespace}:*"
        keys = list(self._run("scan_iter", lambda: list(self._redis_client.scan_iter(match=pattern)), default=[]))
        if keys:
            self._run("delete_many", lambda: self._redis_client.delete(*keys), default=0)

    def check_health(self) -> Dict[str, Any]:
        started = time.perf_counter()
        healthy = bool(self._run("ping", lambda: self._redis_client.ping(), default=False))
        latency_ms = (time.perf_counter() - started) * 1000
        return {
            "healthy": healthy,
            "backend": "memory" if self._memory_backend else "redis",
            "latency_ms": round(latency_ms, 3),
        }

    def set_grid_data(
        self,
        task_id: str,
        grid_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        ttl: Optional[int] = None,
        version: Optional[int] = None,
    ) -> int:
        now_ts = int(time.time())
        version_value = int(version) if version is not None else self.get_version(task_id) + 1
        payload = {
            "grid_data": json.dumps(grid_data, ensure_ascii=False, separators=(",", ":"), default=str),
            "metadata": json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"), default=str),
            "timestamp": str(now_ts),
            "version": str(version_value),
        }
        key = self._grid_key(task_id)
        self._run("hset", lambda: self._redis_client.hset(key, mapping=payload), default=0)
        if ttl is not None:
            self._run("expire", lambda: self._redis_client.expire(key, int(ttl)), default=False)
        self._run("set_version", lambda: self._redis_client.set(self._version_key(task_id), str(version_value)), default=False)
        self._record_task_metric(task_id, "updates", 1)
        return version_value

    def get_grid_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        key = self._grid_key(task_id)
        data = self._run("hgetall", lambda: self._redis_client.hgetall(key), default={})
        if not data:
            return None
        try:
            grid_data = json.loads(data.get("grid_data", "null"))
        except Exception:
            grid_data = data.get("grid_data")
        try:
            metadata = json.loads(data.get("metadata", "{}"))
        except Exception:
            metadata = {}
        return {
            "grid_data": grid_data,
            "metadata": metadata,
            "timestamp": int(data.get("timestamp", "0") or 0),
            "version": int(data.get("version", "0") or 0),
        }

    def add_sampling_point(
        self,
        task_id: str,
        point: Dict[str, Any],
        *,
        score: Optional[float] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        score_value = float(score if score is not None else time.time())
        member = json.dumps(point, ensure_ascii=False, separators=(",", ":"), default=str)
        key = self._points_key(task_id)
        self._run("zadd", lambda: self._redis_client.zadd(key, {member: score_value}), default=0)
        if ttl is not None:
            self._run("expire", lambda: self._redis_client.expire(key, int(ttl)), default=False)
        return True

    def get_sampling_points(
        self,
        task_id: str,
        *,
        start_score: float = float("-inf"),
        end_score: float = float("inf"),
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        key = self._points_key(task_id)
        start = 0
        num = int(limit) if limit is not None else None
        members = self._run(
            "zrangebyscore",
            lambda: self._redis_client.zrangebyscore(key, start_score, end_score, start=start, num=num),
            default=[],
        )
        points: List[Dict[str, Any]] = []
        for item in members:
            try:
                points.append(json.loads(item))
            except Exception:
                continue
        return points

    def append_history(
        self,
        task_id: str,
        event: Dict[str, Any],
        *,
        ttl: Optional[int] = None,
        max_length: int = 200,
    ) -> bool:
        key = self._history_key(task_id)
        payload = json.dumps(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "event": event,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        self._run("rpush", lambda: self._redis_client.rpush(key, payload), default=0)
        if max_length > 0:
            self._run("ltrim", lambda: self._redis_client.ltrim(key, -int(max_length), -1), default=True)
        if ttl is not None:
            self._run("expire", lambda: self._redis_client.expire(key, int(ttl)), default=False)
        return True

    def get_history(self, task_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        key = self._history_key(task_id)
        rows = self._run("lrange", lambda: self._redis_client.lrange(key, -int(limit), -1), default=[])
        result: List[Dict[str, Any]] = []
        for row in rows:
            try:
                result.append(json.loads(row))
            except Exception:
                continue
        return result

    def prewarm_tasks(
        self,
        task_ids: Iterable[str],
        loader: Callable[[str], Optional[Tuple[Any, Optional[Dict[str, Any]]]]],
        *,
        ttl: Optional[int] = None,
        async_mode: bool = True,
        max_workers: int = 4,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        task_list = list(task_ids)
        total = len(task_list)
        started_at = time.time()
        progress = {"total": total, "completed": 0, "success": 0, "failed": 0}
        lock = threading.Lock()

        def _update_progress(success: bool) -> None:
            with lock:
                progress["completed"] += 1
                if success:
                    progress["success"] += 1
                else:
                    progress["failed"] += 1
                if progress_callback:
                    progress_callback(dict(progress))

        def _warm_single(task_id: str) -> None:
            ok = False
            try:
                payload = loader(task_id)
                if payload is not None:
                    grid_data, metadata = payload
                    self.set_grid_data(task_id, grid_data, metadata, ttl=ttl)
                    ok = True
            except Exception as exc:
                logger.warning("预热任务失败 task_id=%s err=%s", task_id, exc)
            _update_progress(ok)

        if async_mode and total > 1:
            from concurrent.futures import ThreadPoolExecutor, wait

            with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
                futures = [executor.submit(_warm_single, task_id) for task_id in task_list]
                wait(futures)
        else:
            for task_id in task_list:
                _warm_single(task_id)

        elapsed = time.time() - started_at
        return {
            **progress,
            "elapsed_time": elapsed,
            "success_rate": progress["success"] / total if total else 0.0,
        }

    def prewarm_by_frequency(
        self,
        access_patterns: Iterable[Tuple[str, int]],
        loader: Callable[[str], Optional[Tuple[Any, Optional[Dict[str, Any]]]]],
        *,
        max_tasks: int = 1000,
        ttl: Optional[int] = None,
    ) -> Dict[str, Any]:
        sorted_tasks = sorted(access_patterns, key=lambda item: int(item[1]), reverse=True)
        selected = [task_id for task_id, _ in sorted_tasks[: max(0, int(max_tasks))]]
        return self.prewarm_tasks(selected, loader, ttl=ttl, async_mode=True)

    def register_invalidation_listener(self, listener: Callable[[str, str], None]) -> None:
        with self._backend_lock:
            self._invalidation_listeners.append(listener)

    def publish_invalidation(self, task_id: str, reason: str = "manual") -> None:
        payload = json.dumps({"task_id": task_id, "reason": reason}, ensure_ascii=False, separators=(",", ":"))
        self._run("publish", lambda: self._redis_client.publish(self.invalidation_channel, payload), default=0)
        for listener in list(self._invalidation_listeners):
            try:
                listener(task_id, reason)
            except Exception as exc:
                logger.warning("失效监听回调失败: %s", exc)

    def invalidate_task(self, task_id: str, *, reason: str = "manual", notify: bool = True) -> int:
        keys = [
            self._grid_key(task_id),
            self._points_key(task_id),
            self._history_key(task_id),
            self._stats_key(task_id),
            self._version_key(task_id),
        ]
        kv_pattern = f"{self.namespace}:kv:*{task_id}*"
        keys.extend(list(self._run("scan_kv", lambda: list(self._redis_client.scan_iter(match=kv_pattern)), default=[])))
        deleted = int(self._run("delete", lambda: self._redis_client.delete(*keys), default=0)) if keys else 0
        if notify:
            self.publish_invalidation(task_id, reason=reason)
        return deleted

    def acquire_lock(
        self,
        task_id: str,
        *,
        ttl: int = 10,
        blocking_timeout: float = 3.0,
        retry_interval: float = 0.05,
    ) -> Optional[str]:
        token = uuid.uuid4().hex
        key = self._lock_key(task_id)
        deadline = time.time() + max(0.0, float(blocking_timeout))

        while True:
            locked = bool(self._run("lock", lambda: self._redis_client.set(key, token, nx=True, ex=max(1, int(ttl))), default=False))
            if locked:
                return token
            if time.time() >= deadline:
                return None
            time.sleep(max(0.01, float(retry_interval)))

    def release_lock(self, task_id: str, token: str) -> bool:
        key = self._lock_key(task_id)
        current = self._run("lock_get", lambda: self._redis_client.get(key), default=None)
        if current is None or str(current) != str(token):
            return False
        deleted = self._run("lock_del", lambda: self._redis_client.delete(key), default=0)
        return bool(deleted)

    def get_version(self, task_id: str) -> int:
        raw = self._run("get_version", lambda: self._redis_client.get(self._version_key(task_id)), default=None)
        try:
            return int(raw)
        except Exception:
            data = self.get_grid_data(task_id)
            if not data:
                return 0
            return int(data.get("version", 0) or 0)

    def compare_and_set_grid(
        self,
        task_id: str,
        *,
        expected_version: int,
        new_grid_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> Dict[str, Any]:
        token = self.acquire_lock(task_id, ttl=10, blocking_timeout=2.0)
        if token is None:
            return {"success": False, "reason": "lock_unavailable"}
        try:
            current_version = self.get_version(task_id)
            if int(current_version) != int(expected_version):
                return {
                    "success": False,
                    "reason": "version_conflict",
                    "current_version": int(current_version),
                    "expected_version": int(expected_version),
                }
            new_version = self.set_grid_data(
                task_id,
                new_grid_data,
                metadata=metadata,
                ttl=ttl,
                version=int(expected_version) + 1,
            )
            return {
                "success": True,
                "new_version": int(new_version),
            }
        finally:
            self.release_lock(task_id, token)

    def get_task_stats(self, task_id: str) -> Dict[str, int]:
        stats = self._run("hgetall_stats", lambda: self._redis_client.hgetall(self._stats_key(task_id)), default={}) or {}
        result: Dict[str, int] = {}
        for key, value in stats.items():
            try:
                result[str(key)] = int(value)
            except Exception:
                continue
        return result

    def get_stats(self) -> Dict[str, Any]:
        base = super().get_stats()
        with self._backend_lock:
            redis_metrics = dict(self._redis_metrics)
        base.update(
            {
                "backend": "memory" if self._memory_backend else "redis",
                "redis_metrics": redis_metrics,
                "health": self.check_health(),
            }
        )
        return base
