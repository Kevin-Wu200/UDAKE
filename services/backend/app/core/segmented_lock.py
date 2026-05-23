"""
分段锁实现
通过将数据分成多个段，每个段有独立的锁，减少锁竞争，提升并发性能
"""
import hashlib
import threading
from typing import Dict


class SegmentedLock:
    """分段锁，用于减少锁竞争"""

    def __init__(self, segments: int = 16):
        """
        初始化分段锁

        Args:
            segments: 锁的分段数，默认16
        """
        self.segments = segments
        self.locks: Dict[int, threading.Lock] = {}
        for i in range(segments):
            self.locks[i] = threading.Lock()

    def _get_segment(self, key: str) -> int:
        """
        根据键获取对应的分段索引

        Args:
            key: 用于分段的键

        Returns:
            分段索引
        """
        hash_value = hashlib.md5(key.encode()).hexdigest()
        return int(hash_value, 16) % self.segments

    def acquire(self, key: str) -> bool:
        """
        获取对应分段的锁

        Args:
            key: 用于获取分段的键

        Returns:
            是否成功获取锁
        """
        segment = self._get_segment(key)
        return self.locks[segment].acquire()

    def release(self, key: str) -> None:
        """
        释放对应分段的锁

        Args:
            key: 用于获取分段的键
        """
        segment = self._get_segment(key)
        self.locks[segment].release()

    def __enter__(self):
        """支持 with 语句"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时释放所有锁"""
        for lock in self.locks.values():
            if lock.locked():
                lock.release()

    def acquire_segment(self, segment: int) -> bool:
        """
        直接获取指定分段的锁

        Args:
            segment: 分段索引

        Returns:
            是否成功获取锁
        """
        if 0 <= segment < self.segments:
            return self.locks[segment].acquire()
        return False

    def release_segment(self, segment: int) -> None:
        """
        直接释放指定分段的锁

        Args:
            segment: 分段索引
        """
        if 0 <= segment < self.segments:
            self.locks[segment].release()

    def get_locked_count(self) -> int:
        """
        获取当前被锁住的分段数量

        Returns:
            被锁住的分段数量
        """
        return sum(1 for lock in self.locks.values() if lock.locked())
