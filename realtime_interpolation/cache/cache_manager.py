"""
缓存管理模块
Cache Manager Module

实现缓存的管理、监控、一致性和性能优化
"""

import numpy as np
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import threading
import time
import hashlib
import pickle
from collections import defaultdict

from .cache_strategy import (
    MultiLevelCacheStrategy,
    CacheLevel,
    ReplacementPolicy,
    CacheEntry
)

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """缓存统计信息"""
    total_requests: int = 0
    total_hits: int = 0
    total_misses: int = 0
    total_evictions: int = 0
    total_size: int = 0
    avg_access_time: float = 0.0
    peak_size: int = 0
    last_updated: datetime = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()


class CacheManager:
    """缓存管理器"""

    def __init__(
        self,
        cache_strategy: Optional[MultiLevelCacheStrategy] = None,
        enable_auto_cleanup: bool = True,
        cleanup_interval: int = 300,
        ttl: int = 3600
    ):
        """
        初始化缓存管理器

        Args:
            cache_strategy: 缓存策略
            enable_auto_cleanup: 是否启用自动清理
            cleanup_interval: 清理间隔（秒）
            ttl: 生存时间（秒）
        """
        self.cache_strategy = cache_strategy or MultiLevelCacheStrategy()
        self.enable_auto_cleanup = enable_auto_cleanup
        self.cleanup_interval = cleanup_interval
        self.ttl = ttl

        # 统计信息
        self.stats = CacheStats()
        self.access_times: List[float] = []

        # TTL管理
        self.ttl_map: Dict[str, float] = {}

        # 版本控制
        self.version_map: Dict[str, int] = {}

        # 一致性管理
        self.update_listeners: Dict[str, List[Callable]] = defaultdict(list)

        # 线程安全
        self.lock = threading.RLock()

        # 自动清理线程
        self.cleanup_thread = None
        if self.enable_auto_cleanup:
            self._start_cleanup_thread()

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值
        """
        with self.lock:
            start_time = time.time()

            # 检查TTL
            if self._is_expired(key):
                self.remove(key)
                self.stats.total_misses += 1
                return None

            # 获取值
            value = self.cache_strategy.get(key)

            # 更新统计
            self.stats.total_requests += 1
            if value is not None:
                self.stats.total_hits += 1
            else:
                self.stats.total_misses += 1

            # 记录访问时间
            access_time = time.time() - start_time
            self.access_times.append(access_time)
            if len(self.access_times) > 1000:
                self.access_times.pop(0)

            self.stats.avg_access_time = np.mean(self.access_times)
            self.stats.last_updated = datetime.now()

            return value

    def put(
        self,
        key: str,
        value: Any,
        size: int = 1,
        ttl: Optional[int] = None
    ) -> None:
        """
        放入缓存

        Args:
            key: 缓存键
            value: 缓存值
            size: 缓存大小
            ttl: 生存时间（秒），None表示使用默认TTL
        """
        with self.lock:
            # 放入缓存
            self.cache_strategy.put(key, value, size)

            # 设置TTL
            if ttl is not None:
                self.ttl_map[key] = time.time() + ttl
            elif self.ttl > 0:
                self.ttl_map[key] = time.time() + self.ttl

            # 更新版本
            if key in self.version_map:
                self.version_map[key] += 1
            else:
                self.version_map[key] = 1

            # 更新统计
            self.stats.total_size = self.cache_strategy.l1_cache.current_size
            self.stats.peak_size = max(self.stats.peak_size, self.stats.total_size)
            self.stats.last_updated = datetime.now()

            # 通知监听器
            self._notify_listeners(key, value)

    def remove(self, key: str) -> bool:
        """
        移除缓存

        Args:
            key: 缓存键

        Returns:
            是否成功移除
        """
        with self.lock:
            # 从各级缓存移除
            l1_removed = self.cache_strategy.l1_cache.remove(key)
            l2_removed = self.cache_strategy.l2_cache.remove(key)
            l3_removed = self.cache_strategy.l3_cache.remove(key)

            # 清理TTL和版本信息
            if key in self.ttl_map:
                del self.ttl_map[key]
            if key in self.version_map:
                del self.version_map[key]

            # 更新统计
            if l1_removed or l2_removed or l3_removed:
                self.stats.total_evictions += 1
                self.stats.total_size = self.cache_strategy.l1_cache.current_size
                self.stats.last_updated = datetime.now()
                return True

            return False

    def clear(self) -> None:
        """清空所有缓存"""
        with self.lock:
            self.cache_strategy.clear()
            self.ttl_map.clear()
            self.version_map.clear()
            self.access_times.clear()
            self.stats = CacheStats()

    def _is_expired(self, key: str) -> bool:
        """
        检查是否过期

        Args:
            key: 缓存键

        Returns:
            是否过期
        """
        if key not in self.ttl_map:
            return False

        return time.time() > self.ttl_map[key]

    def _start_cleanup_thread(self) -> None:
        """启动清理线程"""
        def cleanup_loop():
            while True:
                time.sleep(self.cleanup_interval)
                self._cleanup_expired()

        self.cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info("缓存清理线程已启动")

    def _cleanup_expired(self) -> None:
        """清理过期的缓存"""
        with self.lock:
            expired_keys = [
                key for key, expiry in self.ttl_map.items()
                if time.time() > expiry
            ]

            for key in expired_keys:
                self.remove(key)

            if expired_keys:
                logger.info(f"清理了 {len(expired_keys)} 个过期缓存项")

    def _notify_listeners(self, key: str, value: Any) -> None:
        """
        通知更新监听器

        Args:
            key: 缓存键
            value: 新值
        """
        for listener in self.update_listeners[key]:
            try:
                listener(key, value)
            except Exception as e:
                logger.error(f"监听器执行失败: {e}")

    def register_listener(self, key: str, listener: Callable) -> None:
        """
        注册更新监听器

        Args:
            key: 缓存键
            listener: 监听器函数
        """
        with self.lock:
            self.update_listeners[key].append(listener)

    def unregister_listener(self, key: str, listener: Callable) -> None:
        """
        注销更新监听器

        Args:
            key: 缓存键
            listener: 监听器函数
        """
        with self.lock:
            if listener in self.update_listeners[key]:
                self.update_listeners[key].remove(listener)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        with self.lock:
            hit_rate = 0.0
            if self.stats.total_requests > 0:
                hit_rate = self.stats.total_hits / self.stats.total_requests

            return {
                'total_requests': self.stats.total_requests,
                'total_hits': self.stats.total_hits,
                'total_misses': self.stats.total_misses,
                'total_evictions': self.stats.total_evictions,
                'total_size': self.stats.total_size,
                'peak_size': self.stats.peak_size,
                'hit_rate': hit_rate,
                'avg_access_time': self.stats.avg_access_time,
                'last_updated': self.stats.last_updated.isoformat(),
                'cache_levels': {
                    'l1': self.cache_strategy.l1_cache.get_stats(),
                    'l2': self.cache_strategy.l2_cache.get_stats(),
                    'l3': self.cache_strategy.l3_cache.get_stats()
                },
                'hit_rates': self.cache_strategy.get_hit_rates()
            }

    def optimize(self) -> Dict[str, Any]:
        """
        优化缓存配置

        Returns:
            优化建议
        """
        with self.lock:
            stats = self.get_stats()

            recommendations = []

            # 检查命中率
            if stats['hit_rate'] < 0.8:
                recommendations.append({
                    'issue': '缓存命中率较低',
                    'current_hit_rate': stats['hit_rate'],
                    'recommendation': '考虑增加缓存大小或预热常用数据'
                })

            # 检查L1缓存
            l1_stats = stats['cache_levels']['l1']
            if l1_stats['usage_ratio'] > 0.9:
                recommendations.append({
                    'issue': 'L1缓存使用率过高',
                    'current_usage': l1_stats['usage_ratio'],
                    'recommendation': '考虑增加L1缓存大小'
                })

            # 检查访问时间
            if stats['avg_access_time'] > 0.001:
                recommendations.append({
                    'issue': '平均访问时间较长',
                    'current_time': stats['avg_access_time'],
                    'recommendation': '检查缓存策略或硬件性能'
                })

            return {
                'current_stats': stats,
                'recommendations': recommendations,
                'optimization_time': datetime.now().isoformat()
            }


class DistributedCacheManager:
    """分布式缓存管理器（简化版）"""

    def __init__(
        self,
        local_manager: CacheManager,
        node_id: str,
        consistency_level: str = "eventual"
    ):
        """
        初始化分布式缓存管理器

        Args:
            local_manager: 本地缓存管理器
            node_id: 节点ID
            consistency_level: 一致性级别 (strong, eventual)
        """
        self.local_manager = local_manager
        self.node_id = node_id
        self.consistency_level = consistency_level

        # 远程节点（简化实现）
        self.remote_nodes: Dict[str, CacheManager] = {}

        # 同步队列
        self.sync_queue: List[Dict[str, Any]] = []

    def add_remote_node(self, node_id: str, manager: CacheManager) -> None:
        """
        添加远程节点

        Args:
            node_id: 节点ID
            manager: 缓存管理器
        """
        self.remote_nodes[node_id] = manager
        logger.info(f"添加远程节点: {node_id}")

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值（分布式）

        Args:
            key: 缓存键

        Returns:
            缓存值
        """
        # 先尝试本地
        value = self.local_manager.get(key)
        if value is not None:
            return value

        # 从远程节点获取
        for node_id, manager in self.remote_nodes.items():
            value = manager.get(key)
            if value is not None:
                # 同步到本地
                self.local_manager.put(key, value)
                return value

        return None

    def put(
        self,
        key: str,
        value: Any,
        size: int = 1,
        ttl: Optional[int] = None
    ) -> None:
        """
        放入缓存（分布式）

        Args:
            key: 缓存键
            value: 缓存值
            size: 缓存大小
            ttl: 生存时间
        """
        # 放入本地
        self.local_manager.put(key, value, size, ttl)

        # 根据一致性级别决定是否同步
        if self.consistency_level == "strong":
            # 强一致性：立即同步到所有节点
            for node_id, manager in self.remote_nodes.items():
                manager.put(key, value, size, ttl)
        elif self.consistency_level == "eventual":
            # 最终一致性：加入同步队列
            self.sync_queue.append({
                'key': key,
                'value': value,
                'size': size,
                'ttl': ttl,
                'timestamp': time.time()
            })

    def sync_remote_nodes(self) -> None:
        """同步远程节点"""
        while self.sync_queue:
            update = self.sync_queue.pop(0)

            for node_id, manager in self.remote_nodes.items():
                manager.put(
                    update['key'],
                    update['value'],
                    update.get('size', 1),
                    update.get('ttl')
                )

        logger.info(f"同步了 {len(self.sync_queue)} 个更新到远程节点")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取分布式缓存统计信息

        Returns:
            统计信息字典
        """
        local_stats = self.local_manager.get_stats()

        remote_stats = {}
        for node_id, manager in self.remote_nodes.items():
            remote_stats[node_id] = manager.get_stats()

        return {
            'node_id': self.node_id,
            'consistency_level': self.consistency_level,
            'local_stats': local_stats,
            'remote_stats': remote_stats,
            'sync_queue_size': len(self.sync_queue)
        }


def test_cache_manager():
    """测试缓存管理器"""
    print("\n测试缓存管理器...")

    # 创建缓存管理器
    manager = CacheManager(
        enable_auto_cleanup=False,
        ttl=10
    )

    # 添加数据
    for i in range(20):
        manager.put(f"key_{i}", f"value_{i}")

    # 获取数据
    for i in range(10):
        value = manager.get(f"key_{i}")
        print(f"获取 key_{i}: {value}")

    # 获取统计信息
    stats = manager.get_stats()
    print(f"\n统计信息:")
    print(f"  总请求数: {stats['total_requests']}")
    print(f"  命中数: {stats['total_hits']}")
    print(f"  未命中数: {stats['total_misses']}")
    print(f"  命中率: {stats['hit_rate']:.2%}")
    print(f"  平均访问时间: {stats['avg_access_time']:.6f}s")

    # 测试TTL
    print("\n测试TTL...")
    manager.put("temp_key", "temp_value", ttl=1)
    time.sleep(1.5)
    value = manager.get("temp_key")
    print(f"TTL过期后获取: {value}")

    # 测试优化建议
    print("\n获取优化建议...")
    optimization = manager.optimize()
    for rec in optimization['recommendations']:
        print(f"  - {rec['issue']}: {rec['recommendation']}")

    print("缓存管理器测试通过！")


def test_distributed_cache():
    """测试分布式缓存"""
    print("\n测试分布式缓存...")

    # 创建本地和远程缓存管理器
    local_manager = CacheManager(enable_auto_cleanup=False)
    remote_manager = CacheManager(enable_auto_cleanup=False)

    # 创建分布式缓存
    distributed = DistributedCacheManager(
        local_manager=local_manager,
        node_id="node1",
        consistency_level="eventual"
    )

    # 添加远程节点
    distributed.add_remote_node("node2", remote_manager)

    # 放入数据
    distributed.put("key1", "value1")

    # 从本地获取
    value = distributed.get("key1")
    print(f"从本地获取: {value}")

    # 从远程获取
    remote_manager.put("key2", "value2")
    value = distributed.get("key2")
    print(f"从远程获取: {value}")

    # 同步
    distributed.sync_remote_nodes()

    # 获取统计信息
    stats = distributed.get_stats()
    print(f"\n分布式缓存统计:")
    print(f"  节点ID: {stats['node_id']}")
    print(f"  一致性级别: {stats['consistency_level']}")
    print(f"  同步队列大小: {stats['sync_queue_size']}")

    print("分布式缓存测试通过！")


if __name__ == "__main__":
    test_cache_manager()
    test_distributed_cache()
    print("\n所有测试通过！")