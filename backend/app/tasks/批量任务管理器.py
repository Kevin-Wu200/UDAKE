"""
批量任务管理器
"""
from ..schemas.批量处理模型 import (
    BatchTaskStatus, BatchTaskSummary, BatchTaskDetail,
    BatchTaskExecutionMode, BatchTaskPriority,
    BatchTaskControlResponse
)
from ..schemas.输出结果模型 import TaskStatus, TaskStatusResponse
from ..schemas.插值参数模型 import KrigingParameters
from .任务管理器 import TaskManager
from datetime import datetime
from typing import Dict, Optional, List, Any
import threading
import queue
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

class BatchTaskManager:
    """批量任务管理器"""

    def __init__(self):
        self.batch_tasks: Dict[str, Dict[str, Any]] = {}
        self.batch_to_tasks: Dict[str, List[str]] = {}
        self.lock = threading.Lock()
        self.task_manager = TaskManager()
        self.executor = ThreadPoolExecutor(max_workers=10)

    def create_batch_task(
        self,
        data_ids: List[str],
        parameters: Optional[KrigingParameters] = None,
        individual_parameters: Optional[Dict[str, KrigingParameters]] = None,
        execution_mode: BatchTaskExecutionMode = BatchTaskExecutionMode.PARALLEL,
        priority: BatchTaskPriority = BatchTaskPriority.MEDIUM,
        max_concurrent: int = 4,
        description: Optional[str] = None
    ) -> str:
        """创建批量任务"""
        batch_id = str(uuid.uuid4())

        # 为每个数据ID创建任务ID
        task_ids = []
        for data_id in data_ids:
            task_id = str(uuid.uuid4())
            task_ids.append(task_id)

            # 确定任务参数
            task_params = parameters
            if individual_parameters and data_id in individual_parameters:
                task_params = individual_parameters[data_id]

            # 创建单个任务
            self.task_manager.create_task(task_id, task_params)

        with self.lock:
            self.batch_tasks[batch_id] = {
                "batch_id": batch_id,
                "data_ids": data_ids,
                "task_ids": task_ids,
                "parameters": parameters.model_dump() if parameters else None,
                "individual_parameters": {
                    k: v.model_dump() for k, v in individual_parameters.items()
                } if individual_parameters else None,
                "execution_mode": execution_mode,
                "priority": priority,
                "max_concurrent": max_concurrent,
                "description": description,
                "status": BatchTaskStatus.PENDING,
                "total_tasks": len(data_ids),
                "completed_tasks": 0,
                "running_tasks": 0,
                "failed_tasks": 0,
                "pending_tasks": len(data_ids),
                "overall_progress": 0.0,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "message": "批量任务已创建",
                "estimated_duration": None,
                "control_flags": {
                    "pause": False,
                    "cancel": False
                },
                "task_start_times": {},
                "task_completion_times": {}
            }

            self.batch_to_tasks[batch_id] = task_ids

        return batch_id

    def update_batch_task_status(
        self,
        batch_id: str,
        status: BatchTaskStatus,
        message: Optional[str] = None
    ):
        """更新批量任务状态"""
        with self.lock:
            if batch_id not in self.batch_tasks:
                return

            self.batch_tasks[batch_id]["status"] = status
            self.batch_tasks[batch_id]["updated_at"] = datetime.now()
            if message:
                self.batch_tasks[batch_id]["message"] = message

    def update_task_progress(
        self,
        batch_id: str,
        task_id: str,
        status: TaskStatus,
        progress: float,
        message: Optional[str] = None,
        error: Optional[str] = None
    ):
        """更新任务进度并更新批量任务摘要"""
        with self.lock:
            if batch_id not in self.batch_tasks:
                return

            # 更新单个任务状态
            self.task_manager.update_task_status(task_id, status, progress, message, error)

            # 更新批量任务统计
            batch = self.batch_tasks[batch_id]
            task_ids = batch["task_ids"]

            completed = 0
            running = 0
            failed = 0
            pending = 0

            for tid in task_ids:
                task_status = self.task_manager.get_task_status(tid)
                if task_status:
                    if task_status.status == TaskStatus.COMPLETED:
                        completed += 1
                    elif task_status.status == TaskStatus.RUNNING:
                        running += 1
                    elif task_status.status == TaskStatus.FAILED:
                        failed += 1
                    else:
                        pending += 1

            batch["completed_tasks"] = completed
            batch["running_tasks"] = running
            batch["failed_tasks"] = failed
            batch["pending_tasks"] = pending
            batch["overall_progress"] = (completed / batch["total_tasks"]) * 100.0
            batch["updated_at"] = datetime.now()

            # 计算预计剩余时间
            if completed > 0 and running > 0:
                avg_time = sum(
                    (batch["task_completion_times"].get(tid, 0) -
                     batch["task_start_times"].get(tid, datetime.now())).total_seconds()
                    for tid in task_ids
                    if tid in batch["task_completion_times"] and tid in batch["task_start_times"]
                ) / completed
                batch["estimated_remaining_time"] = avg_time * (batch["total_tasks"] - completed)

            # 更新批量任务状态
            if failed == batch["total_tasks"]:
                batch["status"] = BatchTaskStatus.FAILED
                batch["message"] = "所有任务均失败"
            elif completed == batch["total_tasks"]:
                batch["status"] = BatchTaskStatus.COMPLETED
                batch["message"] = "所有任务已完成"
            elif batch["control_flags"]["cancel"]:
                batch["status"] = BatchTaskStatus.CANCELLED
                batch["message"] = "批量任务已取消"
            elif batch["control_flags"]["pause"]:
                batch["status"] = BatchTaskStatus.PAUSED
                batch["message"] = "批量任务已暂停"
            elif running > 0:
                batch["status"] = BatchTaskStatus.RUNNING
                batch["message"] = f"任务进行中：{running}/{batch['total_tasks']}"

    def get_batch_summary(self, batch_id: str) -> Optional[BatchTaskSummary]:
        """获取批量任务摘要"""
        with self.lock:
            if batch_id not in self.batch_tasks:
                return None

            batch = self.batch_tasks[batch_id]
            return BatchTaskSummary(
                batch_id=batch_id,
                total_tasks=batch["total_tasks"],
                completed_tasks=batch["completed_tasks"],
                running_tasks=batch["running_tasks"],
                failed_tasks=batch["failed_tasks"],
                pending_tasks=batch["pending_tasks"],
                overall_progress=batch["overall_progress"],
                status=batch["status"],
                created_at=batch["created_at"],
                updated_at=batch["updated_at"],
                message=batch.get("message"),
                estimated_remaining_time=batch.get("estimated_remaining_time")
            )

    def get_batch_details(self, batch_id: str) -> Optional[List[BatchTaskDetail]]:
        """获取批量任务详情"""
        with self.lock:
            if batch_id not in self.batch_tasks:
                return None

            batch = self.batch_tasks[batch_id]
            task_ids = batch["task_ids"]
            data_ids = batch["data_ids"]

            details = []
            for i, task_id in enumerate(task_ids):
                task_info = self.task_manager.get_task_info(task_id)
                if task_info:
                    details.append(BatchTaskDetail(
                        task_id=task_id,
                        data_id=data_ids[i],
                        status=task_info["status"],
                        progress=task_info["progress"],
                        message=task_info.get("message"),
                        error=task_info.get("error"),
                        created_at=task_info["created_at"],
                        updated_at=task_info["updated_at"],
                        parameters=task_info.get("params", {}),
                        result={k: v for k, v in task_info.items()
                                if k not in ["task_id", "status", "progress", "message",
                                           "error", "created_at", "updated_at", "params"]}
                    ))

            return details

    def control_batch_task(
        self,
        batch_id: str,
        action: str
    ) -> Optional[BatchTaskControlResponse]:
        """控制批量任务（暂停/恢复/取消）"""
        with self.lock:
            if batch_id not in self.batch_tasks:
                return None

            batch = self.batch_tasks[batch_id]

            if action == "pause":
                if batch["status"] != BatchTaskStatus.RUNNING:
                    return BatchTaskControlResponse(
                        batch_id=batch_id,
                        action=action,
                        status="failed",
                        message=f"无法暂停：当前状态为 {batch['status']}"
                    )
                batch["control_flags"]["pause"] = True
                batch["status"] = BatchTaskStatus.PAUSED
                batch["message"] = "批量任务已暂停"
                batch["updated_at"] = datetime.now()

            elif action == "resume":
                if batch["status"] != BatchTaskStatus.PAUSED:
                    return BatchTaskControlResponse(
                        batch_id=batch_id,
                        action=action,
                        status="failed",
                        message=f"无法恢复：当前状态为 {batch['status']}"
                    )
                batch["control_flags"]["pause"] = False
                batch["status"] = BatchTaskStatus.RUNNING
                batch["message"] = "批量任务已恢复"
                batch["updated_at"] = datetime.now()

            elif action == "cancel":
                if batch["status"] in [BatchTaskStatus.COMPLETED, BatchTaskStatus.FAILED, BatchTaskStatus.CANCELLED]:
                    return BatchTaskControlResponse(
                        batch_id=batch_id,
                        action=action,
                        status="failed",
                        message=f"无法取消：当前状态为 {batch['status']}"
                    )
                batch["control_flags"]["cancel"] = True
                batch["status"] = BatchTaskStatus.CANCELLED
                batch["message"] = "批量任务已取消"
                batch["updated_at"] = datetime.now()

            else:
                return BatchTaskControlResponse(
                    batch_id=batch_id,
                    action=action,
                    status="failed",
                    message=f"未知操作：{action}"
                )

            return BatchTaskControlResponse(
                batch_id=batch_id,
                action=action,
                status="success",
                message=f"操作成功：{action}"
            )

    def record_task_start(self, batch_id: str, task_id: str):
        """记录任务开始时间"""
        with self.lock:
            if batch_id in self.batch_tasks:
                self.batch_tasks[batch_id]["task_start_times"][task_id] = datetime.now()

    def record_task_completion(self, batch_id: str, task_id: str):
        """记录任务完成时间"""
        with self.lock:
            if batch_id in self.batch_tasks:
                self.batch_tasks[batch_id]["task_completion_times"][task_id] = datetime.now()

    def get_batch_results(self, batch_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取批量任务结果"""
        with self.lock:
            if batch_id not in self.batch_tasks:
                return None

            batch = self.batch_tasks[batch_id]
            task_ids = batch["task_ids"]
            data_ids = batch["data_ids"]

            results = []
            for i, task_id in enumerate(task_ids):
                task_result = self.task_manager.get_task_info(task_id)
                if task_result:
                    results.append({
                        "task_id": task_id,
                        "data_id": data_ids[i],
                        "status": task_result["status"],
                        "result": {k: v for k, v in task_result.items()
                                  if k not in ["task_id", "status", "progress", "message",
                                             "error", "created_at", "updated_at", "params"]}
                    })

            return results

    def get_all_batch_tasks(self) -> List[str]:
        """获取所有批量任务ID"""
        with self.lock:
            return list(self.batch_tasks.keys())