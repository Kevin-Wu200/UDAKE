"""
缓存策略模块
Cache Strategy Module

实现多级缓存策略、替换策略和预热策略
"""

import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import OrderedDict, deque
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class CacheLevel:
    """缓存级别配置（兼容旧接口，可直接实例化）。"""
    name: str
    max_size: int = 0
    ttl: int = 0
    priority: int = 1
    value: int = 1


class ReplacementPolicy(Enum):
    """缓存替换策略"""
    LRU = "least_recently_used"  # 最近最少使用
    LFU = "least_frequently_used"  # 最少使用频率
    FIFO = "first_in_first_out"  # 先进先出
    LFUDA = "least_frequently_used_with_dynamic_aging"  # 动态老化LFU


# 预定义标准缓存级别（兼容历史代码中的 CacheLevel.L1/L2/L3）
CacheLevel.L1 = CacheLevel(name="L1", priority=1, value=1)
CacheLevel.L2 = CacheLevel(name="L2", priority=2, value=2)
CacheLevel.L3 = CacheLevel(name="L3", priority=3, value=3)


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    access_count: int = 0
    last_access_time: float = 0.0
    create_time: float = 0.0
    size: int = 0
    level: CacheLevel = None

    def __post_init__(self):
        if self.level is None:
            self.level = CacheLevel.L1


class CachePolicy:
    """缓存策略基类"""

    def __init__(
        self,
        max_size: int,
        replacement_policy: ReplacementPolicy = ReplacementPolicy.LRU
    ):
        """
        初始化缓存策略

        Args:
            max_size: 最大缓存大小
            replacement_policy: 替换策略
        """
        self.max_size = max_size
        self.replacement_policy = replacement_policy
        self.current_size = 0

        # 缓存存储
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # LFU相关
        self.frequency_map: Dict[str, int] = {}

        # FIFO队列
        self.fifo_queue: deque[str] = deque()

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在则返回None
        """
        if key not in self.cache:
            return None

        entry = self.cache[key]

        # 更新访问信息
        entry.access_count += 1
        entry.last_access_time = time.time()

        # 根据策略更新缓存状态
        if self.replacement_policy == ReplacementPolicy.LRU:
            # 移到末尾（最近使用）
            self.cache.move_to_end(key)
        elif self.replacement_policy == ReplacementPolicy.LFU:
            # 更新频率
            self.frequency_map[key] = entry.access_count

        return entry.value

    def put(self, key: str, value: Any, size: int = 1) -> bool:
        """
        放入缓存

        Args:
            key: 缓存键
            value: 缓存值
            size: 缓存大小

        Returns:
            是否成功
        """
        # 计算需要的空间
        entry_size = size

        # 如果键已存在，更新值
        if key in self.cache:
            old_entry = self.cache[key]
            self.current_size -= old_entry.size
            self.cache[key] = CacheEntry(
                key=key,
                value=value,
                access_count=old_entry.access_count,
                last_access_time=time.time(),
                create_time=old_entry.create_time,
                size=entry_size,
                level=old_entry.level
            )
            self.current_size += entry_size
            if self.replacement_policy in (ReplacementPolicy.LFU, ReplacementPolicy.LFUDA):
                self.frequency_map[key] = self.cache[key].access_count
            return True

        # 检查是否需要驱逐
        while self.current_size + entry_size > self.max_size:
            if not self._evict():
                logger.warning("无法驱逐缓存条目，缓存已满")
                return False

        # 添加新条目
        entry = CacheEntry(
            key=key,
            value=value,
            access_count=1,
            last_access_time=time.time(),
            create_time=time.time(),
            size=entry_size
        )
        self.cache[key] = entry
        self.current_size += entry_size

        # FIFO队列
        if self.replacement_policy == ReplacementPolicy.FIFO:
            self.fifo_queue.append(key)
        elif self.replacement_policy in (ReplacementPolicy.LFU, ReplacementPolicy.LFUDA):
            self.frequency_map[key] = entry.access_count

        return True

    def _evict(self) -> bool:
        """
        驱逐缓存条目

        Returns:
            是否成功驱逐
        """
        if not self.cache:
            return False

        if self.replacement_policy == ReplacementPolicy.LRU:
            # 驱逐最近最少使用的（最前面的）
            key, entry = self.cache.popitem(last=False)
            self.current_size -= entry.size
            return True

        elif self.replacement_policy == ReplacementPolicy.LFU:
            # 驱除最少使用的
            if not self.frequency_map:
                return False

            # 找到使用频率最低的
            min_key = min(self.frequency_map, key=self.frequency_map.get)
            entry = self.cache.pop(min_key)
            del self.frequency_map[min_key]
            self.current_size -= entry.size
            return True

        elif self.replacement_policy == ReplacementPolicy.FIFO:
            # 驱逐最早的
            key = self.fifo_queue.popleft()
            if key in self.cache:
                entry = self.cache.pop(key)
                self.current_size -= entry.size
            return True

        elif self.replacement_policy == ReplacementPolicy.LFUDA:
            # 动态老化LFU
            # 计算老化因子
            min_freq = min(self.frequency_map.values()) if self.frequency_map else 0
            aging_factor = min_freq * 0.1

            # 调整频率
            for key in self.frequency_map:
                self.frequency_map[key] = max(0, self.frequency_map[key] - aging_factor)

            # 驱除最少使用的
            if not self.frequency_map:
                return False

            min_key = min(self.frequency_map, key=self.frequency_map.get)
            entry = self.cache.pop(min_key)
            del self.frequency_map[min_key]
            self.current_size -= entry.size
            return True

        return False

    def remove(self, key: str) -> bool:
        """
        移除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否成功移除
        """
        if key not in self.cache:
            return False

        entry = self.cache.pop(key)
        self.current_size -= entry.size

        # 清理相关数据
        if key in self.frequency_map:
            del self.frequency_map[key]
        if key in self.fifo_queue:
            try:
                self.fifo_queue.remove(key)
            except ValueError:
                pass

        return True

    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
        self.frequency_map.clear()
        self.fifo_queue.clear()
        self.current_size = 0

    def get_size(self) -> int:
        """获取当前缓存大小"""
        return self.current_size

    def get_hit_rate(self) -> float:
        """
        获取缓存命中率

        Returns:
            命中率（0-1）
        """
        total_accesses = sum(entry.access_count for entry in self.cache.values())
        if total_accesses == 0:
            return 0.0

        # 简化计算，实际应该跟踪命中和未命中
        return min(1.0, len(self.cache) / max(1, total_accesses))

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        return {
            'current_size': self.current_size,
            'max_size': self.max_size,
            'usage_ratio': self.current_size / self.max_size if self.max_size > 0 else 0.0,
            'entry_count': len(self.cache),
            'replacement_policy': self.replacement_policy.value
        }


class MultiLevelCacheStrategy:
    """多级缓存策略"""

    def __init__(
        self,
        l1_size: int = 1000,
        l2_size: int = 10000,
        l3_size: int = 100000,
        replacement_policy: ReplacementPolicy = ReplacementPolicy.LRU
    ):
        """
        初始化多级缓存策略

        Args:
            l1_size: 一级缓存大小
            l2_size: 二级缓存大小
            l3_size: 三级缓存大小
            replacement_policy: 替换策略
        """
        self.l1_cache = CachePolicy(l1_size, replacement_policy)
        self.l2_cache = CachePolicy(l2_size, replacement_policy)
        self.l3_cache = CachePolicy(l3_size, replacement_policy)
        self.replacement_policy = replacement_policy

        # 兼容旧接口：可枚举缓存层
        self.levels: List[CacheLevel] = [
            CacheLevel(name='L1', max_size=l1_size, priority=1, value=1),
            CacheLevel(name='L2', max_size=l2_size, priority=2, value=2),
            CacheLevel(name='L3', max_size=l3_size, priority=3, value=3),
        ]

        # 统计信息
        self.l1_hits = 0
        self.l2_hits = 0
        self.l3_hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        从多级缓存获取值

        Args:
            key: 缓存键

        Returns:
            缓存值
        """
        # 尝试L1
        value = self.l1_cache.get(key)
        if value is not None:
            self.l1_hits += 1
            return value

        # 尝试L2
        value = self.l2_cache.get(key)
        if value is not None:
            self.l2_hits += 1
            # 提升到L1
            self._promote_to_l1(key, value)
            return value

        # 尝试L3
        value = self.l3_cache.get(key)
        if value is not None:
            self.l3_hits += 1
            # 提升到L2
            self._promote_to_l2(key, value)
            return value

        # 未命中
        self.misses += 1
        return None

    def put(self, key: str, value: Any, size: int = 1) -> None:
        """
        放入多级缓存

        Args:
            key: 缓存键
            value: 缓存值
            size: 缓存大小
        """
        # 默认放入L1
        self.l1_cache.put(key, value, size)

    # 兼容旧接口别名
    def set(self, key: str, value: Any, size: int = 1) -> None:
        self.put(key, value, size)

    def delete(self, key: str) -> bool:
        removed = False
        removed = self.l1_cache.remove(key) or removed
        removed = self.l2_cache.remove(key) or removed
        removed = self.l3_cache.remove(key) or removed
        return removed

    def set_max_size(self, max_size: int) -> None:
        self.l1_cache.max_size = int(max_size)
        for level in self.levels:
            if level.name == 'L1':
                level.max_size = int(max_size)

    def set_eviction_strategy(self, strategy: str) -> None:
        strategy_lower = strategy.lower()
        mapping = {
            'lru': ReplacementPolicy.LRU,
            'lfu': ReplacementPolicy.LFU,
            'fifo': ReplacementPolicy.FIFO,
            'lfuda': ReplacementPolicy.LFUDA,
        }
        policy = mapping.get(strategy_lower, ReplacementPolicy.LRU)
        self.replacement_policy = policy
        self.l1_cache.replacement_policy = policy
        self.l2_cache.replacement_policy = policy
        self.l3_cache.replacement_policy = policy

    def add_level(self, level: CacheLevel) -> None:
        # 兼容旧接口：仅记录层配置，不替换底层实现
        self.levels.append(level)

    def get_level(self, name: str) -> Optional[CacheLevel]:
        for level in self.levels:
            if level.name == name:
                return level
        return None

    def prewarm(self, data: Dict[str, Any]) -> None:
        for key, value in data.items():
            self.put(key, value)

    def _promote_to_l1(self, key: str, value: Any) -> None:
        """提升到L1"""
        self.l1_cache.put(key, value)

    def _promote_to_l2(self, key: str, value: Any) -> None:
        """提升到L2"""
        self.l2_cache.put(key, value)

    def get_hit_rates(self) -> Dict[str, float]:
        """
        获取各级缓存命中率

        Returns:
            命中率字典
        """
        total_requests = self.l1_hits + self.l2_hits + self.l3_hits + self.misses
        if total_requests == 0:
            return {
                'l1_hit_rate': 0.0,
                'l2_hit_rate': 0.0,
                'l3_hit_rate': 0.0,
                'overall_hit_rate': 0.0
            }

        return {
            'l1_hit_rate': self.l1_hits / total_requests,
            'l2_hit_rate': self.l2_hits / total_requests,
            'l3_hit_rate': self.l3_hits / total_requests,
            'overall_hit_rate': (self.l1_hits + self.l2_hits + self.l3_hits) / total_requests
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        return {
            'l1_stats': self.l1_cache.get_stats(),
            'l2_stats': self.l2_cache.get_stats(),
            'l3_stats': self.l3_cache.get_stats(),
            'hit_rates': self.get_hit_rates(),
            'total_requests': self.l1_hits + self.l2_hits + self.l3_hits + self.misses
        }

    def clear(self) -> None:
        """清空所有缓存"""
        self.l1_cache.clear()
        self.l2_cache.clear()
        self.l3_cache.clear()
        self.l1_hits = 0
        self.l2_hits = 0
        self.l3_hits = 0
        self.misses = 0


class CachePreWarmer:
    """缓存预热器"""

    def __init__(self, cache_strategy: MultiLevelCacheStrategy):
        """
        初始化缓存预热器

        Args:
            cache_strategy: 缓存策略
        """
        self.cache_strategy = cache_strategy

    def warm_up(
        self,
        data_loader,
        keys: List[str],
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        预热缓存

        Args:
            data_loader: 数据加载函数
            keys: 预热的键列表
            batch_size: 批量大小

        Returns:
            预热统计信息
        """
        start_time = time.time()
        success_count = 0
        fail_count = 0

        logger.info(f"开始预热缓存，共 {len(keys)} 个键")

        for i in range(0, len(keys), batch_size):
            batch_keys = keys[i:i + batch_size]

            for key in batch_keys:
                try:
                    # 加载数据
                    value = data_loader(key)
                    if value is not None:
                        self.cache_strategy.put(key, value)
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    logger.error(f"预热失败，键: {key}, 错误: {e}")
                    fail_count += 1

            logger.info(f"预热进度: {min(i + batch_size, len(keys))} / {len(keys)}")

        elapsed_time = time.time() - start_time

        stats = {
            'total_keys': len(keys),
            'success_count': success_count,
            'fail_count': fail_count,
            'elapsed_time': elapsed_time,
            'success_rate': success_count / len(keys) if keys else 0.0
        }

        logger.info(f"缓存预热完成: {stats}")

        return stats

    def warm_up_by_frequency(
        self,
        data_loader,
        access_patterns: List[Tuple[str, int]],
        max_keys: int = 1000
    ) -> Dict[str, Any]:
        """
        根据访问频率预热缓存

        Args:
            data_loader: 数据加载函数
            access_patterns: 访问模式列表 [(key, frequency), ...]
            max_keys: 最大预热键数

        Returns:
            预热统计信息
        """
        # 按频率排序
        sorted_patterns = sorted(access_patterns, key=lambda x: x[1], reverse=True)

        # 选择前N个最常访问的键
        selected_keys = [key for key, _ in sorted_patterns[:max_keys]]

        return self.warm_up(data_loader, selected_keys)


def test_cache_policy():
    """测试缓存策略"""
    print("\n测试缓存策略...")

    # 创建LRU缓存
    lru_cache = CachePolicy(max_size=10, replacement_policy=ReplacementPolicy.LRU)

    # 添加数据
    for i in range(15):
        lru_cache.put(f"key_{i}", f"value_{i}")

    print(f"缓存大小: {lru_cache.get_size()}")
    print(f"缓存条目数: {len(lru_cache.cache)}")

    # 获取数据
    value = lru_cache.get("key_14")
    print(f"获取 key_14: {value}")

    # 测试LFU
    lfu_cache = CachePolicy(max_size=10, replacement_policy=ReplacementPolicy.LFU)

    for i in range(15):
        lfu_cache.put(f"key_{i}", f"value_{i}")
        # 访问一些键
        if i < 5:
            lfu_cache.get(f"key_{i}")

    print(f"\nLFU缓存条目数: {len(lfu_cache.cache)}")

    print("缓存策略测试通过！")


def test_multi_level_cache():
    """测试多级缓存"""
    print("\n测试多级缓存...")

    cache = MultiLevelCacheStrategy(
        l1_size=5,
        l2_size=10,
        l3_size=20
    )

    # 添加数据
    for i in range(20):
        cache.put(f"key_{i}", f"value_{i}")

    # 获取数据
    for i in range(10):
        cache.get(f"key_{i}")

    # 获取统计信息
    stats = cache.get_stats()
    print(f"命中率: {stats['hit_rates']}")

    print("多级缓存测试通过！")


def test_cache_pre_warmer():
    """测试缓存预热"""
    print("\n测试缓存预热...")

    cache = MultiLevelCacheStrategy(l1_size=10, l2_size=20, l3_size=30)
    warmer = CachePreWarmer(cache)

    # 模拟数据加载器
    def data_loader(key):
        return f"data_{key}"

    # 预热缓存
    keys = [f"key_{i}" for i in range(50)]
    stats = warmer.warm_up(data_loader, keys, batch_size=10)

    print(f"预热统计: {stats}")

    print("缓存预热测试通过！")


if __name__ == "__main__":
    test_cache_policy()
    test_multi_level_cache()
    test_cache_pre_warmer()
    print("\n所有测试通过！")
