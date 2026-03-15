"""
锁管理器
管理不同类型的分段锁，提供统一的锁管理接口
"""
from typing import Dict, Any
from .segmented_lock import SegmentedLock


class LockManager:
    """锁管理器，管理不同类型的分段锁"""

    def __init__(self):
        """
        锁管理器，管理不同类型的分段锁
        """
        self.task_lock = SegmentedLock(segments=16)
        self.user_lock = SegmentedLock(segments=8)
        self.resource_lock = SegmentedLock(segments=32)

    def get_task_lock(self, task_id: str) -> SegmentedLock:
        """
        获取任务锁

        Args:
            task_id: 任务ID

        Returns:
            分段锁实例
        """
        self.task_lock.acquire(task_id)
        return self.task_lock

    def get_user_lock(self, user_id: str) -> SegmentedLock:
        """
        获取用户锁

        Args:
            user_id: 用户ID

        Returns:
            分段锁实例
        """
        self.user_lock.acquire(user_id)
        return self.user_lock

    def get_resource_lock(self, resource_id: str) -> SegmentedLock:
        """
        获取资源锁

        Args:
            resource_id: 资源ID

        Returns:
            分段锁实例
        """
        self.resource_lock.acquire(resource_id)
        return self.resource_lock

    def release_task_lock(self, task_id: str):
        """
        释放任务锁

        Args:
            task_id: 任务ID
        """
        self.task_lock.release(task_id)

    def release_user_lock(self, user_id: str):
        """
        释放用户锁

        Args:
            user_id: 用户ID
        """
        self.user_lock.release(user_id)

    def release_resource_lock(self, resource_id: str):
        """
        释放资源锁

        Args:
            resource_id: 资源ID
        """
        self.resource_lock.release(resource_id)

    def get_lock_stats(self) -> Dict[str, Any]:
        """
        获取锁统计信息

        Returns:
            锁统计信息
        """
        return {
            'task_lock': {
                'segments': self.task_lock.segments,
                'locked_count': self.task_lock.get_locked_count()
            },
            'user_lock': {
                'segments': self.user_lock.segments,
                'locked_count': self.user_lock.get_locked_count()
            },
            'resource_lock': {
                'segments': self.resource_lock.segments,
                'locked_count': self.resource_lock.get_locked_count()
            }
        }


# 创建全局锁管理器实例
lock_manager = LockManager()