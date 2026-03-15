"""
任务队列管理器
优化版本：使用分段锁和异步执行器提升并发性能
"""
import threading
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from queue import PriorityQueue, Empty
from ..schemas.任务队列模型 import (
    QueueTaskInfo, QueueTaskStatus, QueueTaskPriority,
    QueueStatistics, QueueVisualization, QueueConfig,
    TaskControlResponse
)
from ..schemas.输出结果模型 import TaskStatus
from ..tasks.任务管理器 import TaskManager
from .websocket_service import websocket_service
from ..core.lock_manager import LockManager
from ..core.async_executor import AsyncTaskExecutor
from ..core.task_storage import FileTaskStorage
import uuid

class TaskQueueManager:
    """任务队列管理器"""

    def __init__(self):
        self.config = QueueConfig()
        self.tasks: Dict[str, QueueTaskInfo] = {}
        self.task_queue: PriorityQueue = PriorityQueue()
        self.running_tasks: Dict[str, QueueTaskInfo] = {}
        self.lock = threading.Lock()
        # 新增：使用分段锁管理器替代全局锁
        self.lock_manager = LockManager()
        # 新增：异步执行器用于并发执行任务
        self.async_executor = AsyncTaskExecutor(max_concurrent=10)
        # 新增：任务持久化存储
        self.task_storage = FileTaskStorage(storage_dir="tasks")
        self.scheduler_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.task_manager = TaskManager()
        self.task_history: List[QueueTaskInfo] = []

    def start(self):
        """启动队列管理器"""
        if not self.is_running:
            self.is_running = True
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()

    def stop(self):
        """停止队列管理器"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)

    def _scheduler_loop(self):
        """调度器循环"""
        while self.is_running:
            try:
                self._schedule_next_task()
                self._check_task_timeouts()
                self._retry_failed_tasks()
                time.sleep(1)
            except Exception as e:
                print(f"调度器错误: {str(e)}")
                time.sleep(1)

    def _schedule_next_task(self):
        """调度下一个任务"""
        with self.lock:
            # 检查是否达到并发限制
            if len(self.running_tasks) >= self.config.max_concurrent_tasks:
                return

            # 从队列中获取下一个任务
            try:
                priority, task_id = self.task_queue.get_nowait()
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    if task.status == QueueTaskStatus.WAITING:
                        self._start_task(task)
            except Empty:
                pass

    def _start_task(self, task: QueueTaskInfo):
        """启动任务"""
        task.status = QueueTaskStatus.RUNNING
        task.started_at = datetime.now()
        self.running_tasks[task.task_id] = task

        # 这里应该实际执行任务，这里只是示例
        print(f"启动任务: {task.task_id}, 优先级: {task.priority}")

    def _check_task_timeouts(self):
        """检查任务超时"""
        if not self.config.enable_task_timeout:
            return

        with self.lock:
            now = datetime.now()
            timeout_tasks = []

            for task_id, task in self.running_tasks.items():
                if task.started_at:
                    elapsed = (now - task.started_at).total_seconds()
                    if elapsed > self.config.task_timeout:
                        timeout_tasks.append(task_id)

            for task_id in timeout_tasks:
                self._timeout_task(task_id)

    def _timeout_task(self, task_id: str):
        """任务超时处理"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.status = QueueTaskStatus.FAILED
            task.error = "任务超时"
            task.completed_at = datetime.now()
            if task.started_at:
                task.actual_duration = (task.completed_at - task.started_at).total_seconds()
            del self.running_tasks[task_id]
            self.task_history.append(task)

    def _retry_failed_tasks(self):
        """重试失败任务"""
        if not self.config.enable_auto_retry:
            return

        with self.lock:
            now = datetime.now()
            for task_id, task in list(self.tasks.items()):
                if (task.status == QueueTaskStatus.FAILED and
                    task.retry_count < self.config.max_retry_attempts):

                    # 检查是否到了重试时间
                    if task.completed_at:
                        elapsed = (now - task.completed_at).total_seconds()
                        if elapsed >= self.config.retry_delay:
                            self._retry_task(task)

    def _retry_task(self, task: QueueTaskInfo):
        """重试任务"""
        task.status = QueueTaskStatus.WAITING
        task.retry_count += 1
        task.error = None
        task.started_at = None
        task.completed_at = None
        task.actual_duration = None

        # 重新加入队列
        priority = self._get_priority_value(task.priority)
        self.task_queue.put((priority, task.task_id))

    def _get_priority_value(self, priority: QueueTaskPriority) -> int:
        """获取优先级数值"""
        priority_map = {
            QueueTaskPriority.URGENT: 0,
            QueueTaskPriority.HIGH: 1,
            QueueTaskPriority.MEDIUM: 2,
            QueueTaskPriority.LOW: 3
        }
        return priority_map.get(priority, 2)

    def add_task(
        self,
        task_type: str,
        parameters: Dict[str, Any],
        priority: QueueTaskPriority = QueueTaskPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """添加任务到队列（优化版本：使用分段锁）"""
        task_id = str(uuid.uuid4())

        task = QueueTaskInfo(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            status=QueueTaskStatus.WAITING,
            parameters=parameters,
            metadata=metadata or {}
        )

        # 使用分段锁替代全局锁
        with self.lock_manager.get_task_lock(task_id):
            # 检查队列大小限制
            if len(self.tasks) >= self.config.queue_size_limit:
                self.lock_manager.release_task_lock(task_id)
                raise Exception("队列已满，无法添加新任务")

            self.tasks[task_id] = task

            # 加入优先级队列
            priority_value = self._get_priority_value(priority)
            self.task_queue.put((priority_value, task_id))

        # 异步保存任务到持久化存储
        asyncio.create_task(self._save_task_async(task_id, task))

        return task_id

    async def _save_task_async(self, task_id: str, task: QueueTaskInfo):
        """异步保存任务到持久化存储"""
        try:
            task_data = {
                'task_id': task.task_id,
                'task_type': task.task_type,
                'priority': task.priority.value,
                'status': task.status.value,
                'parameters': task.parameters,
                'metadata': task.metadata,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'progress': task.progress,
                'error': task.error,
                'retry_count': task.retry_count,
                'actual_duration': task.actual_duration
            }
            await self.task_storage.save_task(task_id, task_data)
        except Exception as e:
            print(f"保存任务失败: {e}")

    def control_task(self, task_id: str, action: str) -> TaskControlResponse:
        """控制任务"""
        with self.lock:
            if task_id not in self.tasks:
                return TaskControlResponse(
                    task_id=task_id,
                    action=action,
                    status="failed",
                    message="任务不存在"
                )

            task = self.tasks[task_id]

            if action == "pause":
                if task.status != QueueTaskStatus.RUNNING:
                    return TaskControlResponse(
                        task_id=task_id,
                        action=action,
                        status="failed",
                        message=f"无法暂停：当前状态为 {task.status}"
                    )
                task.status = QueueTaskStatus.PAUSED
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]

            elif action == "resume":
                if task.status != QueueTaskStatus.PAUSED:
                    return TaskControlResponse(
                        task_id=task_id,
                        action=action,
                        status="failed",
                        message=f"无法恢复：当前状态为 {task.status}"
                    )
                task.status = QueueTaskStatus.RUNNING
                task.started_at = datetime.now()
                self.running_tasks[task_id] = task

            elif action == "cancel":
                if task.status in [QueueTaskStatus.COMPLETED, QueueTaskStatus.FAILED, QueueTaskStatus.CANCELLED]:
                    return TaskControlResponse(
                        task_id=task_id,
                        action=action,
                        status="failed",
                        message=f"无法取消：当前状态为 {task.status}"
                    )
                task.status = QueueTaskStatus.CANCELLED
                task.completed_at = datetime.now()
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
                self.task_history.append(task)

            elif action == "retry":
                if task.status != QueueTaskStatus.FAILED:
                    return TaskControlResponse(
                        task_id=task_id,
                        action=action,
                        status="failed",
                        message=f"无法重试：当前状态为 {task.status}"
                    )
                self._retry_task(task)

            else:
                return TaskControlResponse(
                    task_id=task_id,
                    action=action,
                    status="failed",
                    message=f"未知操作：{action}"
                )

            return TaskControlResponse(
                task_id=task_id,
                action=action,
                status="success",
                message=f"操作成功：{action}"
            )

    def batch_control_tasks(self, task_ids: List[str], action: str) -> Dict[str, Any]:
        """批量控制任务"""
        results = []
        successful = 0
        failed = 0

        for task_id in task_ids:
            result = self.control_task(task_id, action)
            results.append(result)
            if result.status == "success":
                successful += 1
            else:
                failed += 1

        return {
            "total_tasks": len(task_ids),
            "successful_tasks": successful,
            "failed_tasks": failed,
            "results": results
        }

    def update_task_priority(self, task_id: str, priority: QueueTaskPriority) -> bool:
        """更新任务优先级"""
        with self.lock:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]

            # 只能更新等待中的任务
            if task.status != QueueTaskStatus.WAITING:
                return False

            task.priority = priority

            # 重新加入队列
            priority_value = self._get_priority_value(priority)
            self.task_queue.put((priority_value, task_id))

            return True

    def complete_task(self, task_id: str, success: bool = True, error: Optional[str] = None):
        """完成任务"""
        with self.lock:
            if task_id in self.running_tasks:
                task = self.running_tasks[task_id]
                if success:
                    task.status = QueueTaskStatus.COMPLETED
                    task.progress = 100
                else:
                    task.status = QueueTaskStatus.FAILED
                    task.error = error

                task.completed_at = datetime.now()
                if task.started_at:
                    task.actual_duration = (task.completed_at - task.started_at).total_seconds()

                del self.running_tasks[task_id]
                self.task_history.append(task)

                # 通过 WebSocket 通知订阅者
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                update = {
                    'status': task.status.value,
                    'progress': task.progress,
                    'error': task.error,
                    'updated_at': datetime.now().isoformat()
                }
                if success:
                    update['result'] = {'task_id': task_id, 'completed_at': task.completed_at.isoformat()}
                loop.run_until_complete(
                    websocket_service.notify_task_update(task_id, update)
                )

    def update_task_progress(self, task_id: str, progress: float):
        """更新任务进度"""
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id].progress = progress

                # 通过 WebSocket 通知订阅者
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                task = self.tasks[task_id]
                update = {
                    'status': task.status.value,
                    'progress': progress,
                    'updated_at': datetime.now().isoformat()
                }
                loop.run_until_complete(
                    websocket_service.notify_task_update(task_id, update)
                )

    def get_task(self, task_id: str) -> Optional[QueueTaskInfo]:
        """获取任务信息（优化版本：使用分段锁）"""
        with self.lock_manager.get_task_lock(task_id):
            task = self.tasks.get(task_id)
            return task

    def get_all_tasks(self, status: Optional[QueueTaskStatus] = None) -> List[QueueTaskInfo]:
        """获取所有任务"""
        with self.lock:
            tasks = list(self.tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            return tasks

    def get_statistics(self) -> QueueStatistics:
        """获取队列统计信息（优化版本：包含锁统计信息）"""
        with self.lock:
            tasks = list(self.tasks.values())

            total = len(tasks)
            waiting = len([t for t in tasks if t.status == QueueTaskStatus.WAITING])
            running = len([t for t in tasks if t.status == QueueTaskStatus.RUNNING])
            completed = len([t for t in tasks if t.status == QueueTaskStatus.COMPLETED])
            failed = len([t for t in tasks if t.status == QueueTaskStatus.FAILED])
            paused = len([t for t in tasks if t.status == QueueTaskStatus.PAUSED])
            cancelled = len([t for t in tasks if t.status == QueueTaskStatus.CANCELLED])

            # 计算平均完成时间
            completed_tasks = [t for t in tasks if t.status == QueueTaskStatus.COMPLETED and t.actual_duration]
            avg_completion_time = sum(t.actual_duration for t in completed_tasks) / len(completed_tasks) if completed_tasks else None

            # 计算成功率
            finished_tasks = completed + failed + cancelled
            success_rate = (completed / finished_tasks * 100) if finished_tasks > 0 else 0.0

            # 计算吞吐量（任务/小时）
            completed_in_last_hour = len([
                t for t in completed_tasks
                if t.completed_at and (datetime.now() - t.completed_at).total_seconds() <= 3600
            ])
            throughput = completed_in_last_hour

            # 获取锁统计信息
            lock_stats = self.lock_manager.get_lock_stats()

            return QueueStatistics(
                total_tasks=total,
                waiting_tasks=waiting,
                running_tasks=running,
                completed_tasks=completed,
                failed_tasks=failed,
                paused_tasks=paused,
                cancelled_tasks=cancelled,
                avg_completion_time=avg_completion_time,
                success_rate=success_rate,
                throughput=throughput
            )

    def get_lock_statistics(self) -> Dict[str, Any]:
        """
        获取锁统计信息

        Returns:
            锁统计信息
        """
        return self.lock_manager.get_lock_stats()

    def get_visualization(self) -> QueueVisualization:
        """获取队列可视化数据"""
        with self.lock:
            statistics = self.get_statistics()
            tasks = list(self.tasks.values())

            # 按状态分组
            tasks_by_status = {}
            for status in QueueTaskStatus:
                tasks_by_status[status.value] = len([t for t in tasks if t.status == status])

            # 按优先级分组
            tasks_by_priority = {}
            for priority in QueueTaskPriority:
                tasks_by_priority[priority.value] = len([t for t in tasks if t.priority == priority])

            # 时间线（最近10个任务）
            timeline = []
            recent_tasks = sorted(self.task_history, key=lambda t: t.completed_at or datetime.min, reverse=True)[:10]
            for task in recent_tasks:
                timeline.append({
                    "task_id": task.task_id,
                    "status": task.status.value,
                    "duration": task.actual_duration,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None
                })

            # 队列流程图
            queue_flow = [
                {"stage": "waiting", "count": statistics.waiting_tasks, "label": "等待中"},
                {"stage": "running", "count": statistics.running_tasks, "label": "运行中"},
                {"stage": "completed", "count": statistics.completed_tasks, "label": "已完成"},
                {"stage": "failed", "count": statistics.failed_tasks, "label": "失败"}
            ]

            return QueueVisualization(
                statistics=statistics,
                tasks_by_status=tasks_by_status,
                tasks_by_priority=tasks_by_priority,
                timeline=timeline,
                queue_flow=queue_flow
            )

    def update_config(self, config: QueueConfig):
        """更新队列配置"""
        with self.lock:
            self.config = config

    def get_config(self) -> QueueConfig:
        """获取队列配置"""
        return self.config

    def clear_completed_tasks(self):
        """清除已完成的任务"""
        with self.lock:
            task_ids_to_remove = [
                task_id for task_id, task in self.tasks.items()
                if task.status in [QueueTaskStatus.COMPLETED, QueueTaskStatus.CANCELLED]
            ]
            for task_id in task_ids_to_remove:
                del self.tasks[task_id]

    def clear_history(self):
        """清除历史记录"""
        with self.lock:
            self.task_history = []

# 创建全局实例
task_queue_manager = TaskQueueManager()