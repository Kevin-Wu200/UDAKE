"""
性能测试
Performance Tests
"""

import pytest
import time
import numpy as np
from datetime import datetime
from typing import List

from ..core.incremental_kriging import IncrementalKriging
from ..cache.cache_manager import CacheManager
from ..api.realtime_service import RealtimeService
from ..models import DataPoint, BoundingBox, Subscription


class TestIncrementalPerformance:
    """增量算法性能测试"""

    @pytest.fixture
    def kriging(self):
        """创建增量克里金实例"""
        return IncrementalKriging()

    def test_incremental_vs_full_computation_time(self, kriging):
        """测试增量更新与全量计算的耗时对比"""
        # 创建初始数据（100个点）
        initial_data = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(100)
        ]

        # 全量计算时间
        full_start = time.time()
        kriging.initial_fit(initial_data)
        full_time = time.time() - full_start

        # 增量更新时间（添加10个新点）
        new_data = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(100, 110)
        ]

        incremental_start = time.time()
        kriging.incremental_update(new_data)
        incremental_time = time.time() - incremental_start

        # 增量更新应该比全量计算快很多（< 10%）
        assert incremental_time < full_time * 0.1

        print(f"全量计算时间: {full_time:.4f}s")
        print(f"增量更新时间: {incremental_time:.4f}s")
        print(f"加速比: {full_time / incremental_time:.2f}x")

    def test_scalability_with_data_size(self, kriging):
        """测试数据规模对性能的影响"""
        data_sizes = [100, 500, 1000, 2000]
        update_times = []

        for size in data_sizes:
            # 初始拟合
            initial_data = [
                DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
                for i in range(size)
            ]
            kriging.initial_fit(initial_data)

            # 测试增量更新时间
            new_data = [
                DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
                for i in range(size, size + 100)
            ]

            start_time = time.time()
            kriging.incremental_update(new_data)
            update_time = time.time() - start_time

            update_times.append(update_time)

        # 更新时间应该随数据规模线性增长（不会指数增长）
        # 验证增长因子
        for i in range(1, len(data_sizes)):
            size_ratio = data_sizes[i] / data_sizes[i-1]
            time_ratio = update_times[i] / update_times[i-1]
            # 时间增长应该不超过规模增长的2倍
            assert time_ratio < size_ratio * 2

        print(f"数据规模: {data_sizes}")
        print(f"更新时间: {[f'{t:.4f}s' for t in update_times]}")

    def test_concurrent_update_performance(self, kriging):
        """测试并发更新性能"""
        import threading

        # 初始拟合
        initial_data = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(100)
        ]
        kriging.initial_fit(initial_data)

        # 单线程更新
        single_start = time.time()
        for i in range(100, 200):
            kriging.incremental_update([
                DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            ])
        single_time = time.time() - single_start

        # 重置
        kriging2 = IncrementalKriging()
        kriging2.initial_fit(initial_data)

        # 多线程更新
        multi_start = time.time()

        def update_task(start_id, count):
            for i in range(start_id, start_id + count):
                kriging2.incremental_update([
                    DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
                ])

        threads = [
            threading.Thread(target=update_task, args=(100, 25)),
            threading.Thread(target=update_task, args=(125, 25)),
            threading.Thread(target=update_task, args=(150, 25)),
            threading.Thread(target=update_task, args=(175, 25)),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        multi_time = time.time() - multi_start

        print(f"单线程时间: {single_time:.4f}s")
        print(f"多线程时间: {multi_time:.4f}s")
        print(f"加速比: {single_time / multi_time:.2f}x")

    def test_memory_efficiency(self, kriging):
        """测试内存效率"""
        import tracemalloc

        tracemalloc.start()

        # 添加大量数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(1000)
        ]

        kriging.initial_fit(data_points)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        memory_per_point = peak / len(data_points)

        print(f"总内存使用: {peak / 1024 / 1024:.2f} MB")
        print(f"每点内存: {memory_per_point / 1024:.2f} KB")

        # 每个点的内存使用应该合理（< 10 KB）
        assert memory_per_point < 10 * 1024


class TestCachePerformance:
    """缓存性能测试"""

    @pytest.fixture
    def cache_manager(self):
        """创建缓存管理器实例"""
        return CacheManager()

    def test_cache_hit_rate_with_various_access_patterns(self, cache_manager):
        """测试不同访问模式下的缓存命中率"""
        # 设置缓存
        for i in range(100):
            cache_manager.set(f'key_{i}', {'value': i})

        # 局部性访问模式（访问某些键多次）
        for _ in range(50):
            cache_manager.get('key_10')
            cache_manager.get('key_20')
            cache_manager.get('key_30')

        # 随机访问
        import random
        for _ in range(47):
            cache_manager.get(f'key_{random.randint(0, 99)}')

        stats = cache_manager.get_stats()
        hit_rate = stats['hit_rate']

        print(f"缓存命中率: {hit_rate * 100:.2f}%")
        print(f"总请求: {stats['total_requests']}")
        print(f"命中: {stats['hits']}")
        print(f"未命中: {stats['misses']}")

        # 命中率应该合理（> 60%）
        assert hit_rate > 0.6

    def test_cache_writing_performance(self, cache_manager):
        """测试缓存写入性能"""
        num_writes = 10000

        start_time = time.time()
        for i in range(num_writes):
            cache_manager.set(f'key_{i}', {'value': i, 'data': 'test' * 10})
        write_time = time.time() - start_time

        throughput = num_writes / write_time

        print(f"写入 {num_writes} 个项目")
        print(f"总时间: {write_time:.4f}s")
        print(f"吞吐量: {throughput:.2f} 写入/秒")

        # 吞吐量应该足够高（> 1000 写入/秒）
        assert throughput > 1000

    def test_cache_reading_performance(self, cache_manager):
        """测试缓存读取性能"""
        # 预填充缓存
        for i in range(1000):
            cache_manager.set(f'key_{i}', {'value': i})

        num_reads = 10000

        start_time = time.time()
        for i in range(num_reads):
            cache_manager.get(f'key_{i % 1000}')
        read_time = time.time() - start_time

        throughput = num_reads / read_time

        print(f"读取 {num_reads} 次")
        print(f"总时间: {read_time:.4f}s")
        print(f"吞吐量: {throughput:.2f} 读取/秒")

        # 吞吐量应该很高（> 10000 读取/秒）
        assert throughput > 10000


class TestRealtimeServicePerformance:
    """实时服务性能测试"""

    @pytest.fixture
    def realtime_service(self):
        """创建实时服务实例"""
        return RealtimeService()

    def test_subscription_creation_performance(self, realtime_service):
        """测试订阅创建性能"""
        num_subscriptions = 100

        start_time = time.time()
        for i in range(num_subscriptions):
            subscription = Subscription(
                id=f'sub_{i}',
                name=f'订阅 {i}',
                area=BoundingBox(
                    min_lon=i * 10.0,
                    min_lat=i * 10.0,
                    max_lon=(i + 1) * 10.0,
                    max_lat=(i + 1) * 10.0
                ),
                update_interval=1000,
                active=True,
                created_at=datetime.now()
            )
            result = realtime_service.create_subscription(subscription)
            assert result.success

        creation_time = time.time() - start_time
        avg_time = creation_time / num_subscriptions

        print(f"创建 {num_subscriptions} 个订阅")
        print(f"总时间: {creation_time:.4f}s")
        print(f"平均时间: {avg_time * 1000:.2f}ms")

        # 每个订阅的创建时间应该很快（< 10ms）
        assert avg_time < 0.01

    def test_data_ingestion_performance(self, realtime_service):
        """测试数据摄取性能"""
        subscription = Subscription(
            id='ingestion_test',
            name='数据摄取测试',
            area=BoundingBox(0.0, 0.0, 100.0, 100.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        num_points = 10000

        start_time = time.time()
        data_points = [
            DataPoint(
                id=str(i),
                x=i % 100,
                y=(i // 100) % 100,
                value=10.0 + (i % 50),
                timestamp=datetime.now()
            )
            for i in range(num_points)
        ]
        result = realtime_service.add_data_points(subscription.id, data_points)
        ingestion_time = time.time() - start_time

        throughput = num_points / ingestion_time

        print(f"摄取 {num_points} 个数据点")
        print(f"总时间: {ingestion_time:.4f}s")
        print(f"吞吐量: {throughput:.2f} 点/秒")

        assert result.success
        assert result.added_points == num_points
        # 吞吐量应该足够高（> 1000 点/秒）
        assert throughput > 1000

    def test_query_performance(self, realtime_service):
        """测试查询性能"""
        subscription = Subscription(
            id='query_test',
            name='查询测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        # 添加数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(100)
        ]
        realtime_service.add_data_points(subscription.id, data_points)

        # 执行查询
        num_queries = 1000
        query_points = [(i * 0.1, i * 0.1) for i in range(num_queries)]

        start_time = time.time()
        for point in query_points:
            predictions = realtime_service.query_predictions(subscription.id, [point])
            assert len(predictions) == 1
        query_time = time.time() - start_time

        throughput = num_queries / query_time

        print(f"执行 {num_queries} 次查询")
        print(f"总时间: {query_time:.4f}s")
        print(f"吞吐量: {throughput:.2f} 查询/秒")

        # 查询吞吐量应该足够高（> 100 查询/秒）
        assert throughput > 100

    def test_end_to_end_latency(self, realtime_service):
        """测试端到端延迟"""
        subscription = Subscription(
            id='latency_test',
            name='延迟测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        # 测量创建订阅延迟
        create_start = time.time()
        realtime_service.create_subscription(subscription)
        create_latency = time.time() - create_start

        # 测量添加数据延迟
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]
        add_start = time.time()
        realtime_service.add_data_points(subscription.id, data_points)
        add_latency = time.time() - add_start

        # 测量更新延迟
        update_start = time.time()
        realtime_service.execute_update(subscription.id)
        update_latency = time.time() - update_start

        # 测量查询延迟
        query_start = time.time()
        realtime_service.query_predictions(subscription.id, [(5.0, 5.0)])
        query_latency = time.time() - query_start

        total_latency = create_latency + add_latency + update_latency + query_latency

        print(f"创建订阅延迟: {create_latency * 1000:.2f}ms")
        print(f"添加数据延迟: {add_latency * 1000:.2f}ms")
        print(f"执行更新延迟: {update_latency * 1000:.2f}ms")
        print(f"查询延迟: {query_latency * 1000:.2f}ms")
        print(f"总延迟: {total_latency * 1000:.2f}ms")

        # 总延迟应该小于1秒
        assert total_latency < 1.0


class TestPerformanceBenchmarks:
    """性能基准测试"""

    def test_incremental_update_benchmark(self):
        """增量更新基准测试"""
        kriging = IncrementalKriging()

        # 不同规模数据的更新时间
        benchmarks = {
            100: [],
            500: [],
            1000: [],
        }

        for size, times in benchmarks.items():
            for run in range(5):  # 运行5次取平均
                initial_data = [
                    DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
                    for i in range(size)
                ]
                kriging.initial_fit(initial_data)

                new_data = [
                    DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
                    for i in range(size, size + 10)
                ]

                start_time = time.time()
                kriging.incremental_update(new_data)
                update_time = time.time() - start_time

                times.append(update_time)

        # 打印基准测试结果
        print("\n增量更新基准测试结果:")
        print("-" * 50)
        for size, times in benchmarks.items():
            avg_time = np.mean(times)
            std_time = np.std(times)
            print(f"数据规模: {size}")
            print(f"  平均时间: {avg_time * 1000:.2f}ms")
            print(f"  标准差: {std_time * 1000:.2f}ms")

    def test_cache_benchmark(self):
        """缓存基准测试"""
        cache_manager = CacheManager()

        # 不同操作的性能
        benchmarks = {
            'write': [],
            'read': [],
            'delete': [],
        }

        # 写入基准
        for run in range(5):
            start_time = time.time()
            for i in range(1000):
                cache_manager.set(f'key_{i}', {'value': i})
            write_time = time.time() - start_time
            benchmarks['write'].append(write_time)

        # 读取基准
        for run in range(5):
            start_time = time.time()
            for i in range(1000):
                cache_manager.get(f'key_{i}')
            read_time = time.time() - start_time
            benchmarks['read'].append(read_time)

        # 删除基准
        for run in range(5):
            start_time = time.time()
            for i in range(1000):
                cache_manager.delete(f'key_{i}')
            delete_time = time.time() - start_time
            benchmarks['delete'].append(delete_time)

        # 打印基准测试结果
        print("\n缓存基准测试结果:")
        print("-" * 50)
        for operation, times in benchmarks.items():
            avg_time = np.mean(times)
            std_time = np.std(times)
            throughput = 1000 / avg_time
            print(f"{operation.upper()}:")
            print(f"  平均时间: {avg_time * 1000:.2f}ms")
            print(f"  标准差: {std_time * 1000:.2f}ms")
            print(f"  吞吐量: {throughput:.2f} 操作/秒")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])