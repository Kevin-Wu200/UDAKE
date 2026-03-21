"""
性能监控工具
"""
import time
import psutil
from functools import wraps
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """性能监控器"""

    @staticmethod
    def measure_time(func: Callable) -> Callable:
        """测量函数执行时间"""
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time

            logger.info(
                f"函数 {func.__name__} 执行时间: {execution_time:.2f}秒"
            )
            return result
        return wrapper

    @staticmethod
    def get_memory_usage() -> dict:
        """获取内存使用情况"""
        process = psutil.Process()
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / 1024 / 1024,
            "vms_mb": memory_info.vms / 1024 / 1024,
            "percent": process.memory_percent()
        }

    @staticmethod
    def get_cpu_usage() -> float:
        """获取CPU使用率"""
        return psutil.cpu_percent(interval=1)

    @staticmethod
    def log_system_stats():
        """记录系统统计信息"""
        memory = PerformanceMonitor.get_memory_usage()
        cpu = PerformanceMonitor.get_cpu_usage()

        logger.info(
            f"系统状态 - CPU: {cpu}%, "
            f"内存: {memory['rss_mb']:.2f}MB ({memory['percent']:.1f}%)"
        )
