"""Lightweight scheduler manager for key expiry related tasks."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

from ..config import settings
from .tasks import run_expiry_check_task, run_expiry_reminder_task

logger = logging.getLogger(__name__)


@dataclass
class _ScheduledTask:
    name: str
    runner: Callable[[], Dict[str, object]]
    execute_time: str
    paused: bool = False
    last_run_date: str = ""


def _normalize_hhmm(value: str) -> str:
    text = str(value or "").strip()
    parts = text.split(":")
    if len(parts) != 2:
        return "00:00"
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return "00:00"
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return "00:00"
    return f"{hour:02d}:{minute:02d}"


class KeyExpirySchedulerManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._history: List[Dict[str, object]] = []
        self._poll_seconds = int(max(5, getattr(settings, "KEY_EXPIRY_SCHEDULER_POLL_SECONDS", 20)))
        self._history_limit = int(max(20, getattr(settings, "KEY_EXPIRY_SCHEDULER_HISTORY_LIMIT", 200)))
        self._tasks: Dict[str, _ScheduledTask] = {
            "expiry_check": _ScheduledTask(
                name="expiry_check",
                runner=run_expiry_check_task,
                execute_time=_normalize_hhmm(getattr(settings, "KEY_EXPIRY_SCHEDULER_EXPIRE_TIME", "00:10")),
            ),
            "expiry_reminder": _ScheduledTask(
                name="expiry_reminder",
                runner=run_expiry_reminder_task,
                execute_time=_normalize_hhmm(getattr(settings, "KEY_EXPIRY_SCHEDULER_REMINDER_TIME", "00:20")),
            ),
        }

    def start(self) -> None:
        enabled = bool(getattr(settings, "KEY_EXPIRY_SCHEDULER_ENABLED", True))
        with self._lock:
            if self._running or not enabled:
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, name="key-expiry-scheduler", daemon=True)
            self._thread.start()
            logger.info("密钥调度器已启动，任务=%s", list(self._tasks.keys()))

    def stop(self) -> None:
        with self._lock:
            self._running = False
            thread = self._thread
        if thread:
            thread.join(timeout=2.0)
        logger.info("密钥调度器已停止")

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def pause_task(self, task_name: str) -> Dict[str, object]:
        with self._lock:
            task = self._tasks.get(task_name)
            if not task:
                return {"ok": False, "message": "任务不存在"}
            task.paused = True
            return {"ok": True, "message": "任务已暂停", "task": task_name}

    def resume_task(self, task_name: str) -> Dict[str, object]:
        with self._lock:
            task = self._tasks.get(task_name)
            if not task:
                return {"ok": False, "message": "任务不存在"}
            task.paused = False
            return {"ok": True, "message": "任务已恢复", "task": task_name}

    def update_task_schedule(self, task_name: str, execute_time: str) -> Dict[str, object]:
        with self._lock:
            task = self._tasks.get(task_name)
            if not task:
                return {"ok": False, "message": "任务不存在"}
            task.execute_time = _normalize_hhmm(execute_time)
            return {"ok": True, "message": "执行时间已更新", "task": task_name, "execute_time": task.execute_time}

    def trigger_now(self, task_name: str) -> Dict[str, object]:
        with self._lock:
            task = self._tasks.get(task_name)
        if not task:
            return {"ok": False, "message": "任务不存在"}
        result = task.runner()
        self._push_history({"trigger": "manual", **result})
        return {"ok": True, "message": "任务已触发", "result": result}

    def get_tasks_snapshot(self) -> List[Dict[str, object]]:
        with self._lock:
            running = self._running
            return [
                {
                    "name": task.name,
                    "execute_time": task.execute_time,
                    "paused": task.paused,
                    "last_run_date": task.last_run_date,
                    "scheduler_running": running,
                }
                for task in self._tasks.values()
            ]

    def get_history(self, limit: int = 100) -> List[Dict[str, object]]:
        safe_limit = max(1, min(500, int(limit)))
        with self._lock:
            return list(self._history[-safe_limit:])[::-1]

    def _loop(self) -> None:
        while True:
            with self._lock:
                running = self._running
            if not running:
                break

            now = datetime.now()
            hhmm = now.strftime("%H:%M")
            day = now.strftime("%Y-%m-%d")

            for task in self._tasks.values():
                if task.paused:
                    continue
                if task.execute_time != hhmm:
                    continue
                if task.last_run_date == day:
                    continue

                task.last_run_date = day
                try:
                    result = task.runner()
                    self._push_history({"trigger": "auto", **result})
                except Exception as exc:  # pragma: no cover - defensive branch
                    logger.exception("定时任务执行失败 task=%s err=%s", task.name, exc)
                    self._push_history(
                        {
                            "task_name": task.name,
                            "status": "failed",
                            "trigger": "auto",
                            "started_at": now.isoformat(),
                            "finished_at": datetime.now().isoformat(),
                            "duration_ms": 0,
                            "details": {"error": str(exc)},
                        }
                    )
            time.sleep(self._poll_seconds)

    def _push_history(self, item: Dict[str, object]) -> None:
        with self._lock:
            self._history.append(item)
            overflow = len(self._history) - self._history_limit
            if overflow > 0:
                self._history = self._history[overflow:]


_scheduler_manager = KeyExpirySchedulerManager()


def get_scheduler_manager() -> KeyExpirySchedulerManager:
    return _scheduler_manager

