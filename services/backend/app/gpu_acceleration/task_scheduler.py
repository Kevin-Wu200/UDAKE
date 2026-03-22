"""GPU任务调度与状态管理。"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Lock
from typing import Deque, Dict, List, Optional
from uuid import uuid4

from .data_structures import ComputeBackend, GPUComputeTask, TaskStatus


class GPUTaskScheduler:
    """轻量任务调度器，提供任务生命周期管理。"""

    def __init__(self, max_history: int = 500):
        self._tasks: Dict[str, GPUComputeTask] = {}
        self._history: Deque[str] = deque(maxlen=max_history)
        self._lock = Lock()

    def create_task(self, task_type: str, payload: dict, backend: ComputeBackend) -> GPUComputeTask:
        task = GPUComputeTask(
            task_id=str(uuid4()),
            task_type=task_type,
            payload=payload,
            backend=backend,
        )
        with self._lock:
            self._tasks[task.task_id] = task
            self._history.append(task.task_id)
        return task

    def start_task(self, task_id: str) -> Optional[GPUComputeTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            return task

    def complete_task(self, task_id: str) -> Optional[GPUComputeTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.status = TaskStatus.COMPLETED
            task.finished_at = datetime.utcnow()
            return task

    def fail_task(self, task_id: str, error: str) -> Optional[GPUComputeTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.status = TaskStatus.FAILED
            task.error = error
            task.finished_at = datetime.utcnow()
            return task

    def get_task(self, task_id: str) -> Optional[GPUComputeTask]:
        return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 100) -> List[dict]:
        task_ids = list(self._history)[-max(1, limit):]
        return [self._tasks[task_id].to_dict() for task_id in task_ids if task_id in self._tasks]
