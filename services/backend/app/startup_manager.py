"""
应用启动管理器
实现分阶段超时控制、三级降级策略、状态轮播与性能数据采集。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Deque, Dict, List, Literal, Optional

from .config import settings

logger = logging.getLogger(__name__)

StartupDegradationLevel = Literal["none", "experience", "functional", "fatal"]
TaskCallable = Callable[[], Awaitable[Optional[Dict[str, Any]]]]


class StartupPriority(str, Enum):
    """启动任务优先级。"""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


@dataclass
class StartupTask:
    """单个启动任务定义。"""

    task_id: str
    label: str
    priority: StartupPriority
    timeout_seconds: float
    status_text: str
    handler: TaskCallable


@dataclass
class StartupTaskReport:
    """单个启动任务执行报告。"""

    task_id: str
    label: str
    priority: str
    status_text: str
    success: bool
    degraded: bool
    degradation_level: StartupDegradationLevel
    duration_ms: int
    started_at: float
    finished_at: float
    error: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class StartupManager:
    """应用启动管理器。"""

    # 分阶段超时
    CRITICAL_TIMEOUT_SECONDS = 3.0
    NON_CRITICAL_TIMEOUT_SECONDS = 8.0
    OVERALL_TIMEOUT_SECONDS = 8.0

    # 文字状态轮播文案
    STATUS_MESSAGES: List[str] = [
        "正在加载配置...",
        "正在连接服务器...",
        "正在准备地图数据...",
        "即将完成...",
    ]

    # 硬编码任务顺序
    TASK_ORDER: List[str] = [
        "loadConfig",
        "connectBackend",
        "loadUserData",
        "initPushService",
    ]

    def __init__(self) -> None:
        self._status_cursor = 0
        self._task_reports: List[StartupTaskReport] = []
        self._performance_events: Deque[Dict[str, Any]] = deque(maxlen=300)
        self._startup_started_at: Optional[float] = None
        self._startup_finished_at: Optional[float] = None
        self._ready: bool = False
        self._fatal_error: Optional[str] = None
        self._degradation_level: StartupDegradationLevel = "none"
        self._preloaded_context: Dict[str, Any] = {}
        self._tasks: Dict[str, StartupTask] = self._build_default_tasks()

    def _build_default_tasks(self) -> Dict[str, StartupTask]:
        return {
            "loadConfig": StartupTask(
                task_id="loadConfig",
                label="加载基础配置",
                priority=StartupPriority.P0,
                timeout_seconds=self.CRITICAL_TIMEOUT_SECONDS,
                status_text="正在加载配置...",
                handler=self._task_load_config,
            ),
            "connectBackend": StartupTask(
                task_id="connectBackend",
                label="检查后端依赖",
                priority=StartupPriority.P1,
                timeout_seconds=self.CRITICAL_TIMEOUT_SECONDS,
                status_text="正在连接服务器...",
                handler=self._task_connect_backend,
            ),
            "loadUserData": StartupTask(
                task_id="loadUserData",
                label="预加载业务数据",
                priority=StartupPriority.P1,
                timeout_seconds=self.NON_CRITICAL_TIMEOUT_SECONDS,
                status_text="正在准备地图数据...",
                handler=self._task_load_user_data,
            ),
            "initPushService": StartupTask(
                task_id="initPushService",
                label="初始化推送服务",
                priority=StartupPriority.P2,
                timeout_seconds=self.NON_CRITICAL_TIMEOUT_SECONDS,
                status_text="即将完成...",
                handler=self._task_init_push_service,
            ),
        }

    async def run(self) -> Dict[str, Any]:
        """
        以硬编码顺序执行启动任务。
        - P0失败 -> 致命降级
        - P1失败 -> 功能降级
        - P2失败 -> 体验降级
        """
        self.reset_runtime_state()
        self._startup_started_at = time.time()
        startup_start_perf = time.perf_counter()
        self.record_performance_event("backend", {"event": "startup_begin"})

        try:
            await asyncio.wait_for(
                self._run_ordered_tasks(),
                timeout=self.OVERALL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            timeout_msg = (
                f"启动总流程超时，超过 {self.OVERALL_TIMEOUT_SECONDS:.1f} 秒，进入功能降级模式"
            )
            logger.warning(timeout_msg)
            self._raise_degradation("functional")
            self.record_performance_event(
                "backend",
                {"event": "startup_overall_timeout", "message": timeout_msg},
            )
        finally:
            self._startup_finished_at = time.time()
            total_duration_ms = int((time.perf_counter() - startup_start_perf) * 1000)
            self.record_performance_event(
                "backend",
                {"event": "startup_end", "duration_ms": total_duration_ms},
            )

        self._ready = self._fatal_error is None
        return self.get_health_snapshot()

    async def _run_ordered_tasks(self) -> None:
        for task_id in self.TASK_ORDER:
            task = self._tasks[task_id]
            report = await self._run_single_task(task)
            self._task_reports.append(report)

            if not report.success and task.priority == StartupPriority.P0:
                self._fatal_error = report.error or f"{task.label} 执行失败"
                logger.error("P0 致命任务失败: %s", self._fatal_error)
                break

    async def _run_single_task(self, task: StartupTask) -> StartupTaskReport:
        started_at = time.time()
        stage_start_perf = time.perf_counter()
        error_text: Optional[str] = None
        payload: Optional[Dict[str, Any]] = None
        success = True

        self.record_performance_event(
            "backend",
            {
                "event": "task_start",
                "task_id": task.task_id,
                "priority": task.priority.value,
                "status_text": task.status_text,
            },
        )

        try:
            payload = await asyncio.wait_for(task.handler(), timeout=task.timeout_seconds)
        except asyncio.TimeoutError:
            success = False
            error_text = f"{task.label} 超时（>{task.timeout_seconds:.1f}s）"
            logger.warning(error_text)
        except Exception as exc:  # pylint: disable=broad-except
            success = False
            error_text = str(exc)
            logger.exception("启动任务执行失败: %s", task.task_id)

        duration_ms = int((time.perf_counter() - stage_start_perf) * 1000)
        finished_at = time.time()

        degradation_level = self._resolve_degradation_level(task.priority, success)
        degraded = degradation_level != "none"
        if degraded:
            self._raise_degradation(degradation_level)

        report = StartupTaskReport(
            task_id=task.task_id,
            label=task.label,
            priority=task.priority.value,
            status_text=task.status_text,
            success=success,
            degraded=degraded,
            degradation_level=degradation_level,
            duration_ms=duration_ms,
            started_at=started_at,
            finished_at=finished_at,
            error=error_text,
            payload=payload,
        )

        self.record_performance_event(
            "backend",
            {
                "event": "task_end",
                "task_id": task.task_id,
                "success": success,
                "duration_ms": duration_ms,
                "degradation_level": degradation_level,
                "error": error_text,
            },
        )
        return report

    @staticmethod
    def _resolve_degradation_level(
        priority: StartupPriority, success: bool
    ) -> StartupDegradationLevel:
        if success:
            return "none"
        if priority == StartupPriority.P0:
            return "fatal"
        if priority == StartupPriority.P1:
            return "functional"
        return "experience"

    def _raise_degradation(self, level: StartupDegradationLevel) -> None:
        order = {"none": 0, "experience": 1, "functional": 2, "fatal": 3}
        if order[level] > order[self._degradation_level]:
            self._degradation_level = level

    async def _task_load_config(self) -> Dict[str, Any]:
        await asyncio.sleep(0)
        return {
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "version": settings.VERSION,
        }

    async def _task_connect_backend(self) -> Dict[str, Any]:
        await asyncio.sleep(0)
        results_exists = settings.RESULTS_DIR.exists()
        data_exists = settings.DATA_DIR.exists()
        results_writable = Path(settings.RESULTS_DIR).is_dir()
        return {
            "results_dir_exists": results_exists,
            "data_dir_exists": data_exists,
            "results_dir_writable": results_writable,
        }

    async def _task_load_user_data(self) -> Dict[str, Any]:
        await asyncio.sleep(0)
        templates_dir = Path(__file__).resolve().parent / "templates"
        template_count = len(list(templates_dir.glob("*.geojson")))
        self._preloaded_context["template_count"] = template_count
        return {"template_count": template_count}

    async def _task_init_push_service(self) -> Dict[str, Any]:
        # 后端当前未接入推送服务，按 P2 可选任务处理。
        await asyncio.sleep(0)
        return {"push_service": "disabled"}

    def next_status_message(self) -> str:
        message = self.STATUS_MESSAGES[self._status_cursor % len(self.STATUS_MESSAGES)]
        self._status_cursor += 1
        return message

    def record_performance_event(self, source: str, payload: Dict[str, Any]) -> None:
        self._performance_events.append(
            {
                "timestamp": time.time(),
                "source": source,
                **payload,
            }
        )

    def get_performance_report(self, limit: int = 50) -> Dict[str, Any]:
        events = list(self._performance_events)[-max(1, min(limit, 200)) :]
        return {
            "startup_started_at": self._startup_started_at,
            "startup_finished_at": self._startup_finished_at,
            "startup_duration_ms": self.get_startup_duration_ms(),
            "task_reports": [asdict(report) for report in self._task_reports],
            "events": events,
        }

    def get_startup_duration_ms(self) -> Optional[int]:
        if self._startup_started_at is None:
            return None
        end = self._startup_finished_at or time.time()
        return int((end - self._startup_started_at) * 1000)

    def get_health_snapshot(self) -> Dict[str, Any]:
        return {
            "status": "ready" if self._ready else "degraded",
            "ready": self._ready,
            "degradation_level": self._degradation_level,
            "fatal_error": self._fatal_error,
            "startup_duration_ms": self.get_startup_duration_ms(),
            "current_status_text": self.next_status_message(),
            "task_reports": [asdict(report) for report in self._task_reports],
            "preloaded_context": self._preloaded_context,
        }

    async def shutdown(self) -> None:
        self.record_performance_event("backend", {"event": "startup_manager_shutdown"})

    def reset_runtime_state(self) -> None:
        self._task_reports = []
        self._startup_started_at = None
        self._startup_finished_at = None
        self._ready = False
        self._fatal_error = None
        self._degradation_level = "none"
        self._preloaded_context = {}
        self._status_cursor = 0
