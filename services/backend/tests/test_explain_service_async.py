"""时空解释异步任务服务测试。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from app.dl_services.explain_service import SpatiotemporalExplainTaskService


class _Settings:
    EXPLAIN_CELERY_ENABLED = False
    EXPLAIN_CELERY_TASK_ALWAYS_EAGER = True
    EXPLAIN_TASK_TIMEOUT_SECONDS = 1
    EXPLAIN_TASK_TTL_SECONDS = 1
    EXPLAIN_RESULT_TTL_SECONDS = 60
    EXPLAIN_MAX_CONCURRENT_TASKS = 2
    EXPLAIN_MAX_BATCH_SIZE = 64
    EXPLAIN_DEFAULT_PRIORITY = 5
    EXPLAIN_RESULT_COMPRESSION_THRESHOLD = 256
    EXPLAIN_RATE_LIMIT_PER_MINUTE = 60
    EXPLAIN_ALLOWED_CREATORS = []
    REDIS_URL = None
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = 6379
    REDIS_DB = 0
    WORKFLOW_REDIS_POOL_SIZE = 10
    WORKFLOW_REDIS_TIMEOUT_SECONDS = 1
    WORKFLOW_REDIS_RETRY_TIMES = 1
    WORKFLOW_REDIS_STRICT = False
    WORKFLOW_REDIS_CLUSTER_ENABLED = False
    WORKFLOW_REDIS_CLUSTER_NODES = []


class _DLService:
    def __init__(self) -> None:
        self._calls = 0

    def explain_spatiotemporal(self, **kwargs):  # type: ignore[no-untyped-def]
        self._calls += 1
        return {"ok": True, "echo": kwargs}

    def warmup_spatiotemporal_model(self, model_type: str = "st_transformer") -> dict:
        return {"model_type": model_type, "warmed": True}


def _wait_terminal(svc: SpatiotemporalExplainTaskService, task_id: str, timeout: float = 3.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = svc.get_task(task_id, owner_id="tester")
        if task and task["status"] in {"completed", "failed", "cancelled"}:
            return task
        time.sleep(0.03)
    raise TimeoutError(f"task not finished in {timeout}s: {task_id}")


def test_retry_and_metrics() -> None:
    dl_service = _DLService()
    svc = SpatiotemporalExplainTaskService(settings=_Settings(), dl_service=dl_service)
    state = {"calls": 0}

    def _flaky(payload: dict) -> dict:
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("transient")
        return {"ok": True, "payload": payload}

    svc._execute_explanation = _flaky  # type: ignore[assignment]
    task = svc.create_task(owner_id="tester", payload={"model_type": "st_transformer", "max_retries": 1})
    final = _wait_terminal(svc, task["task_id"])
    assert final["status"] == "completed"
    assert final["retry_count"] == 1
    monitor = svc.queue_metrics()
    assert monitor["retry_count"] >= 1
    assert monitor["success_rate"] >= 0.0


def test_timeout_marks_failed() -> None:
    dl_service = _DLService()
    svc = SpatiotemporalExplainTaskService(settings=_Settings(), dl_service=dl_service)
    svc._execute_with_timeout = lambda payload, timeout_seconds: (_ for _ in ()).throw(TimeoutError("timeout"))  # type: ignore[assignment]
    task = svc.create_task(
        owner_id="tester",
        payload={"model_type": "st_transformer", "max_retries": 0},
    )
    final = _wait_terminal(svc, task["task_id"])
    assert final["status"] == "failed"
    assert final["state"] == "failed"


def test_cleanup_expired_terminal_tasks() -> None:
    dl_service = _DLService()
    svc = SpatiotemporalExplainTaskService(settings=_Settings(), dl_service=dl_service)
    task = svc.create_task(owner_id="tester", payload={"model_type": "st_transformer", "max_retries": 0})
    final = _wait_terminal(svc, task["task_id"])
    assert final["status"] == "completed"

    old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    status = svc.get_task(task["task_id"], owner_id="tester")
    assert status is not None
    status["updated_at"] = old_time
    svc._store_status(task["task_id"], status)  # type: ignore[attr-defined]

    deleted = svc.cleanup_tasks()
    assert deleted >= 1
    assert svc.get_task(task["task_id"], owner_id="tester") is None
