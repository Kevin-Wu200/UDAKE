"""
实时插值系统集成测试
Integration Tests for Realtime Interpolation System
"""

import pytest
import asyncio
import time
from datetime import datetime
from typing import List

from ..core.incremental_kriging import IncrementalKriging
from ..cache.cache_manager import CacheManager
from ..events.event_system import EventBus, EventType
from ..api.realtime_service import RealtimeService
from ..models import DataPoint, BoundingBox, Subscription, UpdateResult


class TestRealtimeServiceIntegration:
    """实时服务集成测试"""

    @pytest.fixture
    def realtime_service(self):
        """创建实时服务实例"""
        return RealtimeService()

    @pytest.fixture
    def sample_subscription(self):
        """创建示例订阅"""
        return Subscription(
            id='test_sub_1',
            name='测试订阅',
            area=BoundingBox(
                min_lon=0.0,
                min_lat=0.0,
                max_lon=10.0,
                max_lat=10.0
            ),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

    def test_end_to_end_realtime_workflow(self, realtime_service, sample_subscription):
        """测试端到端实时工作流"""
        # 1. 创建订阅
        result = realtime_service.create_subscription(sample_subscription)
        assert result.success
        assert result.subscription_id == sample_subscription.id

        # 2. 添加数据点
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]

        add_result = realtime_service.add_data_points(sample_subscription.id, data_points)
        assert add_result.success
        assert add_result.added_points == len(data_points)

        # 3. 执行实时更新
        update_result = realtime_service.execute_update(sample_subscription.id)
        assert update_result.success
        assert update_result.updated_points > 0

        # 4. 查询结果
        predictions = realtime_service.query_predictions(
            sample_subscription.id,
            [(5.0, 5.0), (7.5, 7.5)]
        )
        assert len(predictions) == 2

        # 5. 取消订阅
        cancel_result = realtime_service.cancel_subscription(sample_subscription.id)
        assert cancel_result.success

    def test_concurrent_subscriptions(self, realtime_service):
        """测试并发订阅"""
        subscriptions = []
        for i in range(5):
            sub = Subscription(
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
            subscriptions.append(sub)

        # 创建所有订阅
        for sub in subscriptions:
            result = realtime_service.create_subscription(sub)
            assert result.success

        # 验证所有订阅都已创建
        active_subs = realtime_service.get_active_subscriptions()
        assert len(active_subs) == len(subscriptions)

    def test_large_scale_data_update(self, realtime_service, sample_subscription):
        """测试大规模数据更新"""
        # 创建订阅
        realtime_service.create_subscription(sample_subscription)

        # 添加大量数据点
        large_data = [
            DataPoint(
                id=str(i),
                x=i % 100,
                y=(i // 100) % 100,
                value=10.0 + (i % 50),
                timestamp=datetime.now()
            )
            for i in range(10000)
        ]

        start_time = time.time()
        add_result = realtime_service.add_data_points(sample_subscription.id, large_data)
        add_time = time.time() - start_time

        assert add_result.success
        assert add_result.added_points == len(large_data)
        # 添加10,000个点应该在合理时间内完成（< 5秒）
        assert add_time < 5.0

        # 执行更新
        start_time = time.time()
        update_result = realtime_service.execute_update(sample_subscription.id)
        update_time = time.time() - start_time

        assert update_result.success
        # 更新应该在合理时间内完成（< 10秒）
        assert update_time < 10.0

    def test_cache_integration(self, realtime_service, sample_subscription):
        """测试缓存集成"""
        # 创建订阅
        realtime_service.create_subscription(sample_subscription)

        # 添加数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]
        realtime_service.add_data_points(sample_subscription.id, data_points)

        # 第一次查询
        start_time = time.time()
        predictions1 = realtime_service.query_predictions(
            sample_subscription.id,
            [(5.0, 5.0)]
        )
        query_time1 = time.time() - start_time

        # 第二次查询相同位置（应该使用缓存）
        start_time = time.time()
        predictions2 = realtime_service.query_predictions(
            sample_subscription.id,
            [(5.0, 5.0)]
        )
        query_time2 = time.time() - start_time

        # 第二次查询应该更快（由于缓存）
        assert query_time2 < query_time1
        # 结果应该相同
        assert predictions1[0].value == predictions2[0].value


class TestEventSystemIntegration:
    """事件系统集成测试"""

    @pytest.fixture
    def event_bus(self):
        """创建事件总线"""
        return EventBus()

    def test_realtime_update_events(self, event_bus):
        """测试实时更新事件"""
        events_received = []

        def on_update(event):
            events_received.append(event)

        # 订阅事件
        event_bus.subscribe(EventType.DATA_UPDATE, on_update)

        # 发布事件
        event_bus.publish(EventType.DATA_UPDATE, {
            'subscription_id': 'test_sub',
            'updated_points': 10,
            'timestamp': datetime.now()
        })

        # 验证事件被接收
        assert len(events_received) == 1
        assert events_received[0].type == EventType.DATA_UPDATE

    def test_hotspot_alert_events(self, event_bus):
        """测试热点告警事件"""
        alerts_received = []

        def on_alert(event):
            alerts_received.append(event)

        # 订阅告警事件
        event_bus.subscribe(EventType.HOTSPOT_ALERT, on_alert)

        # 发布告警事件
        event_bus.publish(EventType.HOTSPOT_ALERT, {
            'hotspots': [
                {
                    'id': 'hotspot_1',
                    'center': {'x': 5.0, 'y': 5.0},
                    'intensity': 0.8
                }
            ],
            'timestamp': datetime.now()
        })

        # 验证告警被接收
        assert len(alerts_received) == 1
        assert len(alerts_received[0].data['hotspots']) == 1

    def test_event_filtering(self, event_bus):
        """测试事件过滤"""
        high_priority_events = []

        def filter_func(event):
            return event.priority.value >= 3  # 只接收高优先级事件

        def on_high_priority(event):
            high_priority_events.append(event)

        # 订阅带过滤的事件
        event_bus.subscribe(
            EventType.DATA_UPDATE,
            on_high_priority,
            filter_func=filter_func
        )

        # 发布低优先级事件
        event_bus.publish(EventType.DATA_UPDATE, {
            'data': 'low priority',
            'priority': 1
        })

        # 发布高优先级事件
        event_bus.publish(EventType.DATA_UPDATE, {
            'data': 'high priority',
            'priority': 5
        })

        # 只应该接收到高优先级事件
        assert len(high_priority_events) == 1
        assert high_priority_events[0].data['data'] == 'high priority'


class TestPerformanceIntegration:
    """性能集成测试"""

    @pytest.fixture
    def realtime_service(self):
        """创建实时服务实例"""
        return RealtimeService()

    def test_response_time(self, realtime_service):
        """测试响应时间"""
        subscription = Subscription(
            id='perf_test',
            name='性能测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        # 创建订阅
        create_start = time.time()
        realtime_service.create_subscription(subscription)
        create_time = time.time() - create_start

        # 创建订阅应该很快（< 100ms）
        assert create_time < 0.1

        # 添加数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(100)
        ]

        add_start = time.time()
        realtime_service.add_data_points(subscription.id, data_points)
        add_time = time.time() - add_start

        # 添加数据应该很快（< 500ms）
        assert add_time < 0.5

        # 查询预测
        query_start = time.time()
        predictions = realtime_service.query_predictions(
            subscription.id,
            [(5.0, 5.0), (7.5, 7.5)]
        )
        query_time = time.time() - query_start

        # 查询应该很快（< 1秒）
        assert query_time < 1.0
        assert len(predictions) == 2

    def test_throughput(self, realtime_service):
        """测试吞吐量"""
        subscription = Subscription(
            id='throughput_test',
            name='吞吐量测试',
            area=BoundingBox(0.0, 0.0, 100.0, 100.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        # 模拟连续数据流
        batch_size = 100
        num_batches = 10

        start_time = time.time()
        total_points = 0

        for batch in range(num_batches):
            data_points = [
                DataPoint(
                    id=f'{batch}_{i}',
                    x=batch * 10 + i % 10,
                    y=batch * 10 + i // 10,
                    value=10.0 + (batch * 10 + i) % 50,
                    timestamp=datetime.now()
                )
                for i in range(batch_size)
            ]

            result = realtime_service.add_data_points(subscription.id, data_points)
            total_points += result.added_points

        end_time = time.time()
        total_time = end_time - start_time

        # 计算吞吐量（点/秒）
        throughput = total_points / total_time

        # 吞吐量应该大于 100 点/秒
        assert throughput > 100
        assert total_points == batch_size * num_batches

    def test_cache_hit_rate(self, realtime_service):
        """测试缓存命中率"""
        subscription = Subscription(
            id='cache_test',
            name='缓存测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        # 添加数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]
        realtime_service.add_data_points(subscription.id, data_points)

        # 第一次查询（缓存未命中）
        realtime_service.query_predictions(subscription.id, [(5.0, 5.0)])

        # 多次查询相同位置（缓存命中）
        for _ in range(10):
            realtime_service.query_predictions(subscription.id, [(5.0, 5.0)])

        # 获取缓存统计
        stats = realtime_service.get_cache_stats()

        # 缓存命中率应该很高（> 80%）
        assert stats['hit_rate'] > 0.8


class TestAccuracyIntegration:
    """准确性集成测试"""

    @pytest.fixture
    def realtime_service(self):
        """创建实时服务实例"""
        return RealtimeService()

    def test_incremental_vs_full_prediction(self, realtime_service):
        """测试增量预测与全量预测的对比"""
        subscription = Subscription(
            id='accuracy_test',
            name='准确性测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        # 初始数据
        initial_data = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(5)
        ]
        realtime_service.add_data_points(subscription.id, initial_data)

        # 获取初始预测
        initial_predictions = realtime_service.query_predictions(
            subscription.id,
            [(2.5, 2.5)]
        )

        # 增量添加数据
        new_data = [
            DataPoint(id='5', x=5.0, y=5.0, value=15.0, timestamp=datetime.now()),
            DataPoint(id='6', x=6.0, y=6.0, value=16.0, timestamp=datetime.now()),
        ]
        realtime_service.add_data_points(subscription.id, new_data)

        # 获取增量预测
        incremental_predictions = realtime_service.query_predictions(
            subscription.id,
            [(2.5, 2.5)]
        )

        # 重新计算全量预测
        all_data = initial_data + new_data
        realtime_service.reset_subscription(subscription.id)
        realtime_service.add_data_points(subscription.id, all_data)
        full_predictions = realtime_service.query_predictions(
            subscription.id,
            [(2.5, 2.5)]
        )

        # 增量预测和全量预测应该非常接近（误差 < 1%）
        error = abs(incremental_predictions[0].value - full_predictions[0].value)
        relative_error = error / full_predictions[0].value
        assert relative_error < 0.01

    def test_prediction_variance(self, realtime_service):
        """测试预测方差"""
        subscription = Subscription(
            id='variance_test',
            name='方差测试',
            area=BoundingBox(0.0, 0.0, 10.0, 10.0),
            update_interval=1000,
            active=True,
            created_at=datetime.now()
        )

        realtime_service.create_subscription(subscription)

        # 添加数据
        data_points = [
            DataPoint(id=str(i), x=i, y=i, value=10.0 + i, timestamp=datetime.now())
            for i in range(10)
        ]
        realtime_service.add_data_points(subscription.id, data_points)

        # 在数据点附近预测（方差应该小）
        near_predictions = realtime_service.query_predictions(
            subscription.id,
            [(5.0, 5.0)]
        )

        # 在远离数据点处预测（方差应该大）
        far_predictions = realtime_service.query_predictions(
            subscription.id,
            [(20.0, 20.0)]
        )

        # 远离数据点的方差应该更大
        assert far_predictions[0].variance > near_predictions[0].variance


if __name__ == '__main__':
    pytest.main([__file__, '-v'])