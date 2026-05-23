"""并行执行运行时：任务队列、资源分配与监控。"""

from __future__ import annotations

import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")


@dataclass(order=True)
class ParallelTask(Generic[T]):
    priority: int
    created_at: float = field(default_factory=time.perf_counter, compare=True)
    task_id: str = field(default="", compare=False)
    payload: T = field(default=None, compare=False)  # type: ignore[assignment]


@dataclass
class ParallelRunReport:
    manager: str
    task_count: int
    workers: int
    queue_peak: int
    wait_ms_avg: float
    exec_ms_avg: float
    duration_ms: float
    failed_tasks: int
    task_type: str


class ParallelExecutionManager:
    """轻量并行执行器：支持优先级队列、动态 worker 与运行指标。"""

    def __init__(
        self,
        *,
        name: str,
        max_workers: int = 4,
        min_workers: int = 1,
    ) -> None:
        self.name = name
        self.max_workers = max(1, int(max_workers))
        self.min_workers = max(1, int(min_workers))
        self.cpu_count = max(1, int(os.cpu_count() or 1))
        self._lock = threading.Lock()
        self._active_workers = 0
        self._metrics = {
            "submitted_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_wait_ms": 0.0,
            "total_exec_ms": 0.0,
            "peak_queue_size": 0,
            "last_workers": 1,
            "last_duration_ms": 0.0,
        }

    def _allocate_workers(self, task_count: int, task_type: str) -> int:
        if task_count <= 1:
            return 1
        cpu_budget = max(1, self.cpu_count - 1)
        hard_cap = max(1, min(self.max_workers, cpu_budget))
        if task_type == "io":
            hard_cap = min(self.max_workers, max(hard_cap, 2))
        return max(self.min_workers, min(task_count, hard_cap))

    def run_tasks(
        self,
        *,
        tasks: list[ParallelTask[T]],
        worker_fn: Callable[[T], R],
        task_type: str = "cpu",
    ) -> tuple[list[R], ParallelRunReport]:
        if not tasks:
            report = ParallelRunReport(
                manager=self.name,
                task_count=0,
                workers=0,
                queue_peak=0,
                wait_ms_avg=0.0,
                exec_ms_avg=0.0,
                duration_ms=0.0,
                failed_tasks=0,
                task_type=task_type,
            )
            return [], report

        started_at = time.perf_counter()
        workers = self._allocate_workers(len(tasks), task_type=task_type)
        pending: "queue.PriorityQueue[tuple[int, float, int, ParallelTask[T]]]" = queue.PriorityQueue()
        enqueue_times: dict[int, float] = {}

        for idx, task in enumerate(tasks):
            enqueue_ts = time.perf_counter()
            enqueue_times[idx] = enqueue_ts
            pending.put((int(task.priority), float(task.created_at), idx, task))

        queue_peak = pending.qsize()
        failed = 0
        total_wait_ms = 0.0
        total_exec_ms = 0.0
        ordered: list[tuple[int, R]] = []

        def _timed(payload: T) -> tuple[R, float]:
            local_started = time.perf_counter()
            result = worker_fn(payload)
            elapsed_ms = (time.perf_counter() - local_started) * 1000.0
            return result, elapsed_ms

        with self._lock:
            self._active_workers += workers
            self._metrics["submitted_tasks"] += len(tasks)
            self._metrics["peak_queue_size"] = max(int(self._metrics["peak_queue_size"]), int(queue_peak))
            self._metrics["last_workers"] = int(workers)

        try:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"{self.name}-parallel") as pool:
                future_map = {}
                while not pending.empty():
                    _, _, idx, task = pending.get_nowait()
                    wait_ms = (time.perf_counter() - enqueue_times.get(idx, started_at)) * 1000.0
                    total_wait_ms += wait_ms
                    future = pool.submit(_timed, task.payload)
                    future_map[future] = idx

                for future in as_completed(future_map):
                    idx = int(future_map[future])
                    try:
                        value, exec_ms = future.result()
                        total_exec_ms += float(exec_ms)
                        ordered.append((idx, value))
                    except Exception:
                        failed += 1
                        raise
        finally:
            duration_ms = (time.perf_counter() - started_at) * 1000.0
            with self._lock:
                self._active_workers = max(0, self._active_workers - workers)
                self._metrics["completed_tasks"] += max(0, len(tasks) - failed)
                self._metrics["failed_tasks"] += failed
                self._metrics["total_wait_ms"] += total_wait_ms
                self._metrics["total_exec_ms"] += total_exec_ms
                self._metrics["last_duration_ms"] = duration_ms

        ordered.sort(key=lambda item: item[0])
        results = [item[1] for item in ordered]
        task_count = len(tasks)
        report = ParallelRunReport(
            manager=self.name,
            task_count=task_count,
            workers=workers,
            queue_peak=queue_peak,
            wait_ms_avg=float(total_wait_ms / task_count),
            exec_ms_avg=float(total_exec_ms / task_count) if task_count > 0 else 0.0,
            duration_ms=(time.perf_counter() - started_at) * 1000.0,
            failed_tasks=failed,
            task_type=task_type,
        )
        return results, report

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            submitted = int(self._metrics["submitted_tasks"])
            completed = int(self._metrics["completed_tasks"])
            failed = int(self._metrics["failed_tasks"])
            total_done = max(1, completed + failed)
            return {
                "name": self.name,
                "cpu_count": self.cpu_count,
                "max_workers": self.max_workers,
                "min_workers": self.min_workers,
                "active_workers": int(self._active_workers),
                "submitted_tasks": submitted,
                "completed_tasks": completed,
                "failed_tasks": failed,
                "average_wait_ms": float(self._metrics["total_wait_ms"]) / max(1, submitted),
                "average_exec_ms": float(self._metrics["total_exec_ms"]) / total_done,
                "peak_queue_size": int(self._metrics["peak_queue_size"]),
                "last_workers": int(self._metrics["last_workers"]),
                "last_duration_ms": float(self._metrics["last_duration_ms"]),
            }
