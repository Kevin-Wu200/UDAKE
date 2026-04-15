"""In-memory async queue for product-key validation tasks."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass
class ValidationTask:
    task_id: str
    status: str
    product_key: str
    created_at: int
    updated_at: int
    result: Optional[Dict[str, Any]] = None
    error: str = ""


class ProductKeyValidationQueue:
    def __init__(
        self,
        *,
        processor: Callable[[Dict[str, Any]], Dict[str, Any]],
        result_ttl_seconds: int = 1800,
    ) -> None:
        self._processor = processor
        self._result_ttl = max(60, int(result_ttl_seconds))
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._tasks: Dict[str, ValidationTask] = {}
        self._lock = threading.RLock()
        self._worker = threading.Thread(target=self._run_worker, name="product-key-validate-worker", daemon=True)
        self._worker.start()

    def submit(self, payload: Dict[str, Any]) -> str:
        task_id = f"pkv_{uuid.uuid4().hex[:16]}"
        now = int(time.time())
        task = ValidationTask(
            task_id=task_id,
            status="queued",
            product_key=str(payload.get("product_key") or ""),
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._tasks[task_id] = task
        self._queue.put({"task_id": task_id, **payload})
        return task_id

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        self._cleanup_expired()
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            return {
                "task_id": task.task_id,
                "status": task.status,
                "product_key": task.product_key,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "result": dict(task.result or {}),
                "error": task.error,
            }

    def metrics(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._tasks)
            queued = 0
            processing = 0
            completed = 0
            failed = 0
            for row in self._tasks.values():
                if row.status == "queued":
                    queued += 1
                elif row.status == "processing":
                    processing += 1
                elif row.status == "completed":
                    completed += 1
                elif row.status == "failed":
                    failed += 1
        return {
            "queue_size": int(self._queue.qsize()),
            "tracked_tasks": total,
            "queued": queued,
            "processing": processing,
            "completed": completed,
            "failed": failed,
        }

    def _run_worker(self) -> None:
        while True:
            payload = self._queue.get()
            task_id = str(payload.get("task_id") or "")
            with self._lock:
                task = self._tasks.get(task_id)
                if task:
                    task.status = "processing"
                    task.updated_at = int(time.time())
            try:
                result = self._processor(payload)
                with self._lock:
                    task = self._tasks.get(task_id)
                    if task:
                        task.status = "completed"
                        task.result = dict(result)
                        task.updated_at = int(time.time())
            except Exception as exc:  # pylint: disable=broad-except
                with self._lock:
                    task = self._tasks.get(task_id)
                    if task:
                        task.status = "failed"
                        task.error = str(exc)
                        task.updated_at = int(time.time())
            finally:
                self._queue.task_done()

    def _cleanup_expired(self) -> None:
        now = int(time.time())
        with self._lock:
            obsolete = [
                task_id
                for task_id, task in self._tasks.items()
                if task.status in {"completed", "failed"} and now - int(task.updated_at) >= self._result_ttl
            ]
            for task_id in obsolete:
                self._tasks.pop(task_id, None)
