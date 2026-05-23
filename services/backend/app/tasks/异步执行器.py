"""
异步执行器
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

logger = logging.getLogger(__name__)

class AsyncExecutor:
    """异步任务执行器"""

    def __init__(self, max_workers: int = 5):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def execute_async(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        异步执行函数
        """
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self.executor,
                lambda: func(*args, **kwargs)
            )
            return result
        except Exception as e:
            logger.error(f"异步执行失败: {str(e)}")
            raise

    def shutdown(self):
        """关闭执行器"""
        self.executor.shutdown(wait=True)
