"""时空解释性异步任务服务。"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import queue
import threading
import time
import uuid
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ..services.workflow_redis_cache import WorkflowRedisCacheManager

logger = logging.getLogger(__name__)


class ExplainTaskError(RuntimeError):
    """解释任务通用异常。"""


class ExplainRateLimitError(ExplainTaskError):
    """解释任务限流异常。"""


class ExplainPermissionError(ExplainTaskError):
    """解释任务权限异常。"""


@dataclass
class _ExplainTaskEnvelope:
    task_id: str
    owner_id: str
    payload: dict[str, Any]
    priority: int
    created_at: float
    timeout_seconds: int
    max_retries: int


class _SlidingWindowLimiter:
    """轻量限流器，优先 Redis，降级内存。"""

    def __init__(self, cache: WorkflowRedisCacheManager, max_requests: int, window_seconds: int = 60) -> None:
        self.cache = cache
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(1, int(window_seconds))
        self._lock = threading.Lock()
        self._memory: dict[str, list[float]] = {}

    def _memory_consume(self, key: str) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            bucket = self._memory.setdefault(key, [])
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.pop(0)
            if len(bucket) >= self.max_requests:
                return False, 0
            bucket.append(now)
            return True, self.max_requests - len(bucket)

    def consume(self, identity: str) -> tuple[bool, int]:
        ident = (identity or "anonymous").strip().lower() or "anonymous"
        key = f"dl:explain:rate:{ident}"
        if self.cache.is_memory_backend:
            return self._memory_consume(key)

        payload = self.cache.get(key) or {"timestamps": []}
        now = time.time()
        timestamps = [float(item) for item in payload.get("timestamps", []) if isinstance(item, (int, float))]
        cutoff = now - self.window_seconds
        timestamps = [item for item in timestamps if item >= cutoff]
        if len(timestamps) >= self.max_requests:
            return False, 0
        timestamps.append(now)
        self.cache.set(key, {"timestamps": timestamps}, ttl=self.window_seconds)
        return True, self.max_requests - len(timestamps)


class SpatiotemporalExplainTaskService:
    """时空解释任务管理服务。"""

    def __init__(self, *, settings: Any, dl_service: Any) -> None:
        self.settings = settings
        self.dl_service = dl_service
        self.cache = WorkflowRedisCacheManager.from_settings(settings)
        self.max_concurrent = max(1, int(getattr(settings, "EXPLAIN_MAX_CONCURRENT_TASKS", 4)))
        self.task_timeout = max(30, int(getattr(settings, "EXPLAIN_TASK_TIMEOUT_SECONDS", 900)))
        self.task_ttl = max(60, int(getattr(settings, "EXPLAIN_TASK_TTL_SECONDS", 1800)))
        self.result_ttl = max(60, int(getattr(settings, "EXPLAIN_RESULT_TTL_SECONDS", 3600)))
        self.compress_threshold = max(256, int(getattr(settings, "EXPLAIN_RESULT_COMPRESSION_THRESHOLD", 4096)))
        self.default_priority = int(getattr(settings, "EXPLAIN_DEFAULT_PRIORITY", 5))
        self.max_batch_size = max(16, int(getattr(settings, "EXPLAIN_MAX_BATCH_SIZE", 256)))
        self._limiter = _SlidingWindowLimiter(
            self.cache,
            max_requests=max(1, int(getattr(settings, "EXPLAIN_RATE_LIMIT_PER_MINUTE", 30))),
            window_seconds=60,
        )

        self._local_lock = threading.Lock()
        self._local_status: dict[str, dict[str, Any]] = {}
        self._local_result: dict[str, Any] = {}
        self._queue: "queue.PriorityQueue[tuple[int, float, _ExplainTaskEnvelope]]" = queue.PriorityQueue()
        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=self.max_concurrent, thread_name_prefix="dl-explain")
        self._slots = threading.BoundedSemaphore(self.max_concurrent)
        self._dispatcher = threading.Thread(target=self._dispatch_loop, daemon=True, name="dl-explain-dispatcher")
        self._dispatcher.start()
        self._active_tasks = 0

        self._celery_available = False
        self._celery_app = None
        self._init_celery()

    def _init_celery(self) -> None:
        enabled = bool(getattr(self.settings, "EXPLAIN_CELERY_ENABLED", False))
        if not enabled:
            return
        try:
            from celery import Celery  # type: ignore
        except Exception as exc:
            logger.warning("Celery 不可用，将使用本地线程池队列: %s", exc)
            return
        broker = (
            getattr(self.settings, "EXPLAIN_CELERY_BROKER_URL", None)
            or getattr(self.settings, "REDIS_URL", None)
            or "redis://127.0.0.1:6379/0"
        )
        backend = (
            getattr(self.settings, "EXPLAIN_CELERY_BACKEND_URL", None)
            or getattr(self.settings, "REDIS_URL", None)
            or broker
        )
        app = Celery("udake_spatiotemporal_explain", broker=broker, backend=backend)
        app.conf.update(
            task_always_eager=bool(getattr(self.settings, "EXPLAIN_CELERY_TASK_ALWAYS_EAGER", True)),
            task_serializer="json",
            result_serializer="json",
            accept_content=["json"],
            task_track_started=True,
            task_time_limit=self.task_timeout,
            task_soft_time_limit=max(5, self.task_timeout - 5),
            worker_prefetch_multiplier=1,
        )
        self._celery_app = app
        self._celery_available = True
        logger.info("Explain 任务 Celery 已初始化: broker=%s", broker)

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _status_key(task_id: str) -> str:
        return f"dl:spatiotemporal:explain:task:{task_id}:status"

    @staticmethod
    def _result_key(task_id: str) -> str:
        return f"dl:spatiotemporal:explain:task:{task_id}:result"

    def _store_status(self, task_id: str, payload: dict[str, Any]) -> None:
        with self._local_lock:
            self._local_status[task_id] = payload
        self.cache.set(self._status_key(task_id), payload, ttl=self.task_ttl)

    def _load_status(self, task_id: str) -> Optional[dict[str, Any]]:
        with self._local_lock:
            local = self._local_status.get(task_id)
        if local is not None:
            return dict(local)
        cached = self.cache.get(self._status_key(task_id))
        return dict(cached) if isinstance(cached, dict) else None

    def _store_result(self, task_id: str, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        if len(raw) >= self.compress_threshold:
            compressed = zlib.compress(raw, level=6)
            wrapper = {
                "compressed": True,
                "encoding": "zlib+base64+json",
                "payload": base64.b64encode(compressed).decode("ascii"),
                "raw_size": len(raw),
            }
            cache_payload: Any = wrapper
        else:
            cache_payload = payload
        with self._local_lock:
            self._local_result[task_id] = cache_payload
        self.cache.set(self._result_key(task_id), cache_payload, ttl=self.result_ttl)

    def _load_result(self, task_id: str) -> Optional[dict[str, Any]]:
        with self._local_lock:
            raw = self._local_result.get(task_id)
        if raw is None:
            raw = self.cache.get(self._result_key(task_id))
        if raw is None:
            return None
        if isinstance(raw, dict) and raw.get("compressed") and raw.get("encoding") == "zlib+base64+json":
            payload = str(raw.get("payload", ""))
            decoded = base64.b64decode(payload.encode("ascii"))
            text = zlib.decompress(decoded).decode("utf-8")
            return json.loads(text)
        if isinstance(raw, dict):
            return raw
        return None

    def _dispatch_loop(self) -> None:
        while self._running:
            try:
                priority, created_at, envelope = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            _ = priority, created_at
            if not self._running:
                break
            self._slots.acquire()
            with self._local_lock:
                self._active_tasks += 1
            self._executor.submit(self._execute_envelope, envelope)

    def _execute_envelope(self, envelope: _ExplainTaskEnvelope) -> None:
        started = time.perf_counter()
        task_id = envelope.task_id
        try:
            status = self._load_status(task_id) or {}
            if str(status.get("status")) == "cancelled":
                return
            status.update(
                {
                    "status": "running",
                    "updated_at": self._utc_now_iso(),
                    "progress": 0.2,
                }
            )
            self._store_status(task_id, status)

            last_error: Exception | None = None
            result: dict[str, Any] | None = None
            for attempt in range(envelope.max_retries + 1):
                status = self._load_status(task_id) or status
                if str(status.get("status")) == "cancelled":
                    return
                try:
                    status["retry_count"] = attempt
                    status["updated_at"] = self._utc_now_iso()
                    self._store_status(task_id, status)
                    result = self._execute_explanation(envelope.payload)
                    break
                except Exception as exc:  # pragma: no cover - 异常路径
                    last_error = exc
                    if attempt >= envelope.max_retries:
                        raise
                    status.update(
                        {
                            "status": "retrying",
                            "progress": min(0.9, 0.35 + attempt * 0.2),
                            "updated_at": self._utc_now_iso(),
                            "error": str(exc),
                        }
                    )
                    self._store_status(task_id, status)
                    time.sleep(min(1.5, 0.3 * (attempt + 1)))
            if result is None and last_error is not None:
                raise last_error

            duration_ms = (time.perf_counter() - started) * 1000
            self._store_result(task_id, result)
            status.update(
                {
                    "status": "completed",
                    "progress": 1.0,
                    "updated_at": self._utc_now_iso(),
                    "duration_ms": round(duration_ms, 3),
                }
            )
            self._store_status(task_id, status)
        except Exception as exc:  # pragma: no cover - 异常路径
            duration_ms = (time.perf_counter() - started) * 1000
            status = self._load_status(task_id) or {}
            status.update(
                {
                    "status": "failed",
                    "progress": 1.0,
                    "updated_at": self._utc_now_iso(),
                    "duration_ms": round(duration_ms, 3),
                    "error": str(exc),
                }
            )
            self._store_status(task_id, status)
            logger.exception("Explain 任务执行失败 task_id=%s: %s", task_id, exc)
        finally:
            with self._local_lock:
                self._active_tasks = max(0, self._active_tasks - 1)
            self._slots.release()

    def _execute_explanation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.dl_service.explain_spatiotemporal(
            model_type=str(payload.get("model_type", "st_transformer")),
            coords=payload.get("coords", []),
            series=payload.get("series", []),
            pred_horizon=int(payload.get("pred_horizon", 6)),
            method=str(payload.get("method", "hybrid")),
            top_k=int(payload.get("top_k", 5)),
            include_prediction=bool(payload.get("include_prediction", True)),
            batch_size=min(self.max_batch_size, max(8, int(payload.get("batch_size", self.max_batch_size)))),
        )

    def _normalize_priority(self, priority: Optional[int]) -> int:
        if priority is None:
            return int(self.default_priority)
        return min(9, max(0, int(priority)))

    def _validate_owner(self, owner_id: Optional[str]) -> str:
        owner = (owner_id or "anonymous").strip()
        if not owner:
            return "anonymous"
        return owner

    def check_rate_limit(self, owner_id: str) -> dict[str, Any]:
        allowed, remaining = self._limiter.consume(owner_id)
        if not allowed:
            raise ExplainRateLimitError("请求过于频繁，请稍后重试")
        return {"remaining_per_minute": remaining}

    def can_create_task(self, owner_id: str) -> bool:
        allowlist = set(getattr(self.settings, "EXPLAIN_ALLOWED_CREATORS", []) or [])
        if not allowlist:
            return True
        return owner_id in allowlist

    def create_task(
        self,
        *,
        owner_id: str,
        payload: dict[str, Any],
        priority: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> dict[str, Any]:
        owner = self._validate_owner(owner_id)
        if not self.can_create_task(owner):
            raise ExplainPermissionError("当前用户没有创建解释任务的权限")

        rate_info = self.check_rate_limit(owner)
        task_id = uuid.uuid4().hex
        prio = self._normalize_priority(priority)
        timeout = max(30, int(timeout_seconds or self.task_timeout))

        now_iso = self._utc_now_iso()
        max_retries = max(0, min(3, int(payload.get("max_retries", 1))))
        status_payload = {
            "task_id": task_id,
            "status": "queued",
            "owner_id": owner,
            "created_at": now_iso,
            "updated_at": now_iso,
            "progress": 0.0,
            "priority": prio,
            "backend": "celery" if self._celery_available else "local-threadpool",
            "timeout_seconds": timeout,
            "retry_count": 0,
            "max_retries": max_retries,
        }
        self._store_status(task_id, status_payload)

        envelope = _ExplainTaskEnvelope(
            task_id=task_id,
            owner_id=owner,
            payload=payload,
            priority=prio,
            created_at=time.time(),
            timeout_seconds=timeout,
            max_retries=max_retries,
        )
        self._queue.put((prio, envelope.created_at, envelope))
        queued = self._queue.qsize()
        return {
            "task_id": task_id,
            "status": "queued",
            "queue_size": queued,
            "remaining_per_minute": rate_info["remaining_per_minute"],
            "created_at": now_iso,
        }

    def get_task(self, task_id: str, *, owner_id: str, is_admin: bool = False) -> Optional[dict[str, Any]]:
        status = self._load_status(task_id)
        if status is None:
            return None

        task_owner = str(status.get("owner_id", "anonymous"))
        if not is_admin and task_owner != self._validate_owner(owner_id):
            raise ExplainPermissionError("没有权限访问该任务")

        response = dict(status)
        if response.get("status") == "completed":
            response["result"] = self._load_result(task_id)
        return response

    def delete_task(self, task_id: str, *, owner_id: str, is_admin: bool = False) -> bool:
        status = self._load_status(task_id)
        if status is None:
            return False
        task_owner = str(status.get("owner_id", "anonymous"))
        if not is_admin and task_owner != self._validate_owner(owner_id):
            raise ExplainPermissionError("没有权限删除该任务")

        with self._local_lock:
            self._local_status.pop(task_id, None)
            self._local_result.pop(task_id, None)
        self.cache.delete(self._status_key(task_id))
        self.cache.delete(self._result_key(task_id))
        return True

    def cancel_task(self, task_id: str, *, owner_id: str, is_admin: bool = False) -> bool:
        status = self._load_status(task_id)
        if status is None:
            return False
        task_owner = str(status.get("owner_id", "anonymous"))
        if not is_admin and task_owner != self._validate_owner(owner_id):
            raise ExplainPermissionError("没有权限取消该任务")
        if str(status.get("status")) in {"completed", "failed", "cancelled"}:
            return True
        status.update(
            {
                "status": "cancelled",
                "progress": 1.0,
                "updated_at": self._utc_now_iso(),
                "error": "任务已被用户取消",
            }
        )
        self._store_status(task_id, status)
        return True

    def queue_metrics(self) -> dict[str, Any]:
        with self._local_lock:
            active = int(self._active_tasks)
        return {
            "queue_size": self._queue.qsize(),
            "active_tasks": active,
            "max_concurrent_tasks": self.max_concurrent,
            "cache_backend": "memory" if self.cache.is_memory_backend else "redis",
            "celery_enabled": self._celery_available,
        }

    def warmup_model(self, model_type: str = "st_transformer") -> dict[str, Any]:
        started = time.perf_counter()
        payload = self.dl_service.warmup_spatiotemporal_model(model_type=model_type)
        payload["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return payload

    def stable_payload_hash(self, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def reset_for_testing(self) -> None:
        with self._local_lock:
            self._local_status.clear()
            self._local_result.clear()
            self._active_tasks = 0
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
