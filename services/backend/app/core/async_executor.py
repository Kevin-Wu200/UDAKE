"""
异步任务执行器
提供异步任务执行、超时控制、任务取消等功能
"""
import asyncio
from typing import Any, Callable, Dict, Optional


class AsyncTaskExecutor:
    """异步任务执行器"""

    def __init__(self, max_concurrent: int = 10):
        """
        初始化异步任务执行器

        Args:
            max_concurrent: 最大并发数
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.task_results: Dict[str, Any] = {}
        self.task_errors: Dict[str, Exception] = {}

    async def execute(
        self,
        task_id: str,
        coro: Callable,
        timeout: Optional[float] = None,
        callback: Optional[Callable] = None
    ) -> Any:
        """
        执行异步任务

        Args:
            task_id: 任务ID
            coro: 协程函数
            timeout: 超时时间（秒）
            callback: 回调函数

        Returns:
            任务结果
        """
        async def _execute_with_semaphore():
            async with self.semaphore:
                try:
                    if timeout:
                        result = await asyncio.wait_for(coro, timeout=timeout)
                    else:
                        result = await coro

                    self.task_results[task_id] = result

                    if callback:
                        await callback(task_id, result)

                    return result

                except asyncio.TimeoutError:
                    error = asyncio.TimeoutError(f"任务 {task_id} 超时")
                    self.task_errors[task_id] = error

                    if callback:
                        await callback(task_id, None, error)

                    raise error

                except Exception as e:
                    self.task_errors[task_id] = e

                    if callback:
                        await callback(task_id, None, e)

                    raise e

        task = asyncio.create_task(_execute_with_semaphore())
        self.running_tasks[task_id] = task

        try:
            result = await task
            return result
        finally:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

    def cancel(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            if not task.done():
                task.cancel()
                return True
        return False

    def get_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态
        """
        status = {
            'task_id': task_id,
            'running': task_id in self.running_tasks,
            'completed': task_id in self.task_results,
            'failed': task_id in self.task_errors
        }

        if status['completed']:
            status['result'] = self.task_results[task_id]

        if status['failed']:
            status['error'] = str(self.task_errors[task_id])

        return status

    def get_all_status(self) -> Dict[str, Any]:
        """
        获取所有任务状态

        Returns:
            所有任务状态
        """
        return {
            'running_tasks': len(self.running_tasks),
            'completed_tasks': len(self.task_results),
            'failed_tasks': len(self.task_errors),
            'available_slots': self.semaphore._value,
            'max_concurrent': self.max_concurrent
        }
