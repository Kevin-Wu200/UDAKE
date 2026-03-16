"""
缓存系统测试
Cache System Tests
"""

import pytest
import time
from datetime import datetime, timedelta

from ..cache.cache_manager import CacheManager
from ..cache.cache_strategy import MultiLevelCacheStrategy, CacheLevel


class TestCacheManager:
    """缓存管理器测试类"""

    @pytest.fixture
    def cache_manager(self):
        """创建缓存管理器实例"""
        return CacheManager()

    def test_cache_initialization(self, cache_manager):
        """测试缓存初始化"""
        assert cache_manager is not None
        assert cache_manager.strategy is not None

    def test_cache_set_get(self, cache_manager):
        """测试缓存设置和获取"""
        key = 'test_key'
        value = {'data': 'test_value'}

        # 设置缓存
        cache_manager.set(key, value)

        # 获取缓存
        result = cache_manager.get(key)

        assert result is not None
        assert result['data'] == 'test_value'

    def test_cache_miss(self, cache_manager):
        """测试缓存未命中"""
        result = cache_manager.get('nonexistent_key')
        assert result is None

    def test_cache_delete(self, cache_manager):
        """测试缓存删除"""
        key = 'test_key'
        value = {'data': 'test_value'}

        # 设置缓存
        cache_manager.set(key, value)

        # 删除缓存
        cache_manager.delete(key)

        # 验证删除
        result = cache_manager.get(key)
        assert result is None

    def test_cache_clear(self, cache_manager):
        """测试清空缓存"""
        # 设置多个缓存项
        for i in range(5):
            cache_manager.set(f'key_{i}', {'value': i})

        # 清空缓存
        cache_manager.clear()

        # 验证清空
        for i in range(5):
            result = cache_manager.get(f'key_{i}')
            assert result is None

    def test_cache_ttl(self, cache_manager):
        """测试缓存过期时间"""
        key = 'test_key'
        value = {'data': 'test_value'}
        ttl = 1  # 1秒

        # 设置带TTL的缓存
        cache_manager.set(key, value, ttl=ttl)

        # 立即获取应该成功
        result = cache_manager.get(key)
        assert result is not None

        # 等待过期
        time.sleep(ttl + 0.5)

        # 过期后应该返回None
        result = cache_manager.get(key)
        assert result is None

    def test_cache_size_limit(self, cache_manager):
        """测试缓存大小限制"""
        # 设置缓存大小限制
        cache_manager.set_max_size(3)

        # 添加超过限制的缓存项
        for i in range(5):
            cache_manager.set(f'key_{i}', {'value': i})

        # 由于LRU策略，最早的项应该被移除
        result0 = cache_manager.get('key_0')
        result1 = cache_manager.get('key_1')
        result4 = cache_manager.get('key_4')

        assert result0 is None  # 应该被移除
        assert result1 is not None  # 应该还在
        assert result4 is not None  # 应该还在

    def test_cache_hit_rate(self, cache_manager):
        """测试缓存命中率"""
        # 设置缓存
        cache_manager.set('key1', {'value': 1})
        cache_manager.set('key2', {'value': 2})

        # 命中
        cache_manager.get('key1')
        cache_manager.get('key2')

        # 未命中
        cache_manager.get('key3')

        # 获取命中率
        stats = cache_manager.get_stats()
        hit_rate = stats['hit_rate']

        # 2次命中，1次未命中，命中率应该约等于0.667
        assert abs(hit_rate - 0.667) < 0.01

    def test_cache_performance(self, cache_manager):
        """测试缓存性能"""
        import time

        # 设置大量缓存
        start_time = time.time()
        for i in range(1000):
            cache_manager.set(f'key_{i}', {'value': i})
        set_time = time.time() - start_time

        # 获取大量缓存
        start_time = time.time()
        for i in range(1000):
            cache_manager.get(f'key_{i}')
        get_time = time.time() - start_time

        # 操作应该很快（< 1秒）
        assert set_time < 1.0
        assert get_time < 1.0

    def test_cache_concurrent_access(self, cache_manager):
        """测试并发访问"""
        import threading

        results = []

        def set_task(start_id):
            for i in range(start_id, start_id + 100):
                cache_manager.set(f'key_{i}', {'value': i})
            results.append(True)

        def get_task(start_id):
            for i in range(start_id, start_id + 100):
                cache_manager.get(f'key_{i}')
            results.append(True)

        # 创建多个线程
        threads = [
            threading.Thread(target=set_task, args=(0,)),
            threading.Thread(target=set_task, args=(100,)),
            threading.Thread(target=get_task, args=(0,)),
            threading.Thread(target=get_task, args=(100,)),
        ]

        # 启动线程
        for thread in threads:
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 所有操作应该成功
        assert len(results) == 4
        assert all(results)

    def test_cache_stats(self, cache_manager):
        """测试缓存统计"""
        # 设置和获取缓存
        cache_manager.set('key1', {'value': 1})
        cache_manager.get('key1')  # 命中
        cache_manager.get('key2')  # 未命中

        # 获取统计
        stats = cache_manager.get_stats()

        assert 'total_requests' in stats
        assert 'hits' in stats
        assert 'misses' in stats
        assert 'hit_rate' in stats
        assert 'size' in stats

        assert stats['total_requests'] == 2
        assert stats['hits'] == 1
        assert stats['misses'] == 1


class TestMultiLevelCacheStrategy:
    """多级缓存策略测试类"""

    @pytest.fixture
    def cache_strategy(self):
        """创建多级缓存策略实例"""
        return MultiLevelCacheStrategy()

    def test_strategy_initialization(self, cache_strategy):
        """测试策略初始化"""
        assert cache_strategy is not None
        assert len(cache_strategy.levels) > 0

    def test_lru_eviction(self, cache_strategy):
        """测试LRU驱逐策略"""
        cache_strategy.set_max_size(3)

        # 添加3个项目
        cache_strategy.set('key1', 'value1')
        cache_strategy.set('key2', 'value2')
        cache_strategy.set('key3', 'value3')

        # 访问key1使其成为最近使用
        cache_strategy.get('key1')

        # 添加第4个项目，应该驱逐key2
        cache_strategy.set('key4', 'value4')

        assert cache_strategy.get('key1') == 'value1'  # 最近使用
        assert cache_strategy.get('key2') is None  # 被驱逐
        assert cache_strategy.get('key3') == 'value3'  # 还在
        assert cache_strategy.get('key4') == 'value4'  # 新添加

    def test_lfu_eviction(self, cache_strategy):
        """测试LFU驱逐策略"""
        cache_strategy.set_max_size(3)
        cache_strategy.set_eviction_strategy('lfu')

        # 添加3个项目
        cache_strategy.set('key1', 'value1')
        cache_strategy.set('key2', 'value2')
        cache_strategy.set('key3', 'value3')

        # 多次访问key1和key3
        for _ in range(5):
            cache_strategy.get('key1')
        for _ in range(3):
            cache_strategy.get('key3')

        # 添加第4个项目，应该驱逐key2（最少使用）
        cache_strategy.set('key4', 'value4')

        assert cache_strategy.get('key1') == 'value1'  # 最多使用
        assert cache_strategy.get('key2') is None  # 最少使用，被驱逐
        assert cache_strategy.get('key3') == 'value3'  # 中等使用
        assert cache_strategy.get('key4') == 'value4'  # 新添加

    def test_fifo_eviction(self, cache_strategy):
        """测试FIFO驱逐策略"""
        cache_strategy.set_max_size(3)
        cache_strategy.set_eviction_strategy('fifo')

        # 添加3个项目
        cache_strategy.set('key1', 'value1')
        cache_strategy.set('key2', 'value2')
        cache_strategy.set('key3', 'value3')

        # 添加第4个项目，应该驱逐key1（最先添加）
        cache_strategy.set('key4', 'value4')

        assert cache_strategy.get('key1') is None  # 先进先出，被驱逐
        assert cache_strategy.get('key2') == 'value2'
        assert cache_strategy.get('key3') == 'value3'
        assert cache_strategy.get('key4') == 'value4'

    def test_cache_level_priority(self, cache_strategy):
        """测试缓存级别优先级"""
        # 创建多级缓存
        cache_strategy.add_level(CacheLevel(
            name='L1',
            max_size=10,
            ttl=60,
            priority=1
        ))

        cache_strategy.add_level(CacheLevel(
            name='L2',
            max_size=100,
            ttl=300,
            priority=2
        ))

        # 数据应该优先存储在L1
        cache_strategy.set('key1', 'value1')

        # 验证L1中存在
        l1_level = cache_strategy.get_level('L1')
        assert l1_level is not None

    def test_cache_prewarming(self, cache_strategy):
        """测试缓存预热"""
        # 准备预热数据
        prewarm_data = {
            'key1': 'value1',
            'key2': 'value2',
            'key3': 'value3',
        }

        # 预热缓存
        cache_strategy.prewarm(prewarm_data)

        # 验证预热数据
        for key, value in prewarm_data.items():
            assert cache_strategy.get(key) == value

    def test_cache_serialization(self, cache_strategy):
        """测试缓存序列化"""
        # 设置缓存
        cache_strategy.set('key1', {'nested': {'data': 'value'}})

        # 获取缓存
        result = cache_strategy.get('key1')

        assert result is not None
        assert result['nested']['data'] == 'value'


class TestCacheConsistency:
    """缓存一致性测试类"""

    @pytest.fixture
    def cache_manager(self):
        """创建缓存管理器实例"""
        return CacheManager()

    def test_cache_update_notification(self, cache_manager):
        """测试缓存更新通知"""
        notified = []

        def callback(key, value):
            notified.append((key, value))

        # 注册回调
        cache_manager.on_update(callback)

        # 更新缓存
        cache_manager.set('key1', 'value1')

        # 验证通知
        assert len(notified) == 1
        assert notified[0] == ('key1', 'value1')

    def test_cache_invalidation(self, cache_manager):
        """测试缓存失效"""
        # 设置缓存
        cache_manager.set('key1', 'value1')

        # 失效缓存
        cache_manager.invalidate('key1')

        # 验证失效
        result = cache_manager.get('key1')
        assert result is None

    def test_cache_versioning(self, cache_manager):
        """测试缓存版本控制"""
        # 设置版本1
        cache_manager.set('key1', 'value1', version=1)

        # 获取版本1
        result1 = cache_manager.get('key1', version=1)
        assert result1 == 'value1'

        # 设置版本2
        cache_manager.set('key1', 'value2', version=2)

        # 获取版本2
        result2 = cache_manager.get('key1', version=2)
        assert result2 == 'value2'

        # 版本1应该仍然存在
        result1_after = cache_manager.get('key1', version=1)
        assert result1_after == 'value1'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])