"""
实时插值服务
Realtime Interpolation Service

实现后端API接口、数据处理、性能优化、系统集成和高可用设计
"""

import numpy as np
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
import traceback

from ..models import (
    DataPoint, BoundingBox, Subscription, UpdateResult
)
from ..core import (
    IncrementalKriging,
    MultiScaleUpdater,
    UpdatePriorityManager,
    BatchUpdateManager,
    ThrottleController
)
from ..cache import CacheManager, MultiLevelCacheStrategy
from ..events import (
    EventBus, EventType, EventPriority, Event, EventMonitor
)

logger = logging.getLogger(__name__)


# ==================== 数据接收和验证 ====================

class DataValidator:
    """数据验证器"""

    @staticmethod
    def validate_data_point(data: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[DataPoint]]:
        """
        验证数据点

        Args:
            data: 数据字典

        Returns:
            (是否有效, 错误消息, 数据点对象)
        """
        try:
            # 检查必需字段
            required_fields = ['x', 'y', 'value']
            for field in required_fields:
                if field not in data:
                    return False, f"缺少必需字段: {field}", None

            # 检查数据类型
            x = float(data['x'])
            y = float(data['y'])
            value = float(data['value'])

            # 检查值范围
            if not (-1e10 <= x <= 1e10):
                return False, f"X坐标超出范围: {x}", None
            if not (-1e10 <= y <= 1e10):
                return False, f"Y坐标超出范围: {y}", None
            if not (-1e10 <= value <= 1e10):
                return False, f"值超出范围: {value}", None

            # 创建数据点对象
            point = DataPoint(
                x=x,
                y=y,
                value=value,
                id=data.get('id', f"point_{datetime.now().timestamp()}")
            )

            return True, None, point

        except Exception as e:
            return False, f"数据验证失败: {str(e)}", None

    @staticmethod
    def validate_subscription(data: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[Subscription]]:
        """
        验证订阅

        Args:
            data: 订阅数据字典

        Returns:
            (是否有效, 错误消息, 订阅对象)
        """
        try:
            # 检查必需字段
            required_fields = ['subscription_id', 'spatial_extent']
            for field in required_fields:
                if field not in data:
                    return False, f"缺少必需字段: {field}", None

            # 验证空间范围
            extent_data = data['spatial_extent']
            if not all(k in extent_data for k in ['min_x', 'max_x', 'min_y', 'max_y']):
                return False, "空间范围格式错误", None

            spatial_extent = BoundingBox(
                min_x=float(extent_data['min_x']),
                max_x=float(extent_data['max_x']),
                min_y=float(extent_data['min_y']),
                max_y=float(extent_data['max_y'])
            )

            # 创建订阅对象
            subscription = Subscription(
                subscription_id=data['subscription_id'],
                data_type=data.get('data_type', 'generic'),
                spatial_extent=spatial_extent,
                update_frequency=data.get('update_frequency', 5),
                interpolation_params=data.get('interpolation_params', {}),
                notification_config=data.get('notification_config', {})
            )

            return True, None, subscription

        except Exception as e:
            return False, f"订阅验证失败: {str(e)}", None


# ==================== 实时插值服务 ====================

class RealtimeInterpolationService:
    """实时插值服务"""

    def __init__(
        self,
        max_workers: int = 10,
        enable_cache: bool = True,
        enable_events: bool = True
    ):
        """
        初始化实时插值服务

        Args:
            max_workers: 最大工作线程数
            enable_cache: 是否启用缓存
            enable_events: 是否启用事件系统
        """
        self.max_workers = max_workers
        self.enable_cache = enable_cache
        self.enable_events = enable_events

        # 线程池
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 订阅管理
        self.subscriptions: Dict[str, IncrementalKriging] = {}

        # 更新策略管理器
        self.priority_manager = UpdatePriorityManager()
        self.batch_manager = BatchUpdateManager(batch_size=10)
        self.throttle_controller = ThrottleController(max_updates_per_second=100.0)

        # 缓存系统
        if enable_cache:
            cache_strategy = MultiLevelCacheStrategy(
                l1_size=1000,
                l2_size=10000,
                l3_size=100000
            )
            self.cache_manager = CacheManager(
                cache_strategy=cache_strategy,
                enable_auto_cleanup=True,
                cleanup_interval=300
            )
        else:
            self.cache_manager = None

        # 事件系统
        if enable_events:
            self.event_bus = EventBus(max_queue_size=10000)
            self.event_monitor = EventMonitor()
        else:
            self.event_bus = None
            self.event_monitor = None

        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_updates': 0,
            'avg_processing_time': 0.0
        }

        # 健康检查
        self.healthy = True
        self.start_time = datetime.now()

        logger.info("实时插值服务已初始化")

    def create_subscription(self, subscription_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建订阅

        Args:
            subscription_data: 订阅数据

        Returns:
            响应字典
        """
        try:
            # 验证订阅
            valid, error_msg, subscription = DataValidator.validate_subscription(subscription_data)
            if not valid:
                return {
                    'success': False,
                    'error': error_msg
                }

            # 检查是否已存在
            if subscription.subscription_id in self.subscriptions:
                return {
                    'success': False,
                    'error': f"订阅已存在: {subscription.subscription_id}"
                }

            # 创建插值器
            kriging = IncrementalKriging(subscription)

            # 注册订阅
            self.subscriptions[subscription.subscription_id] = kriging

            # 发布事件
            if self.event_bus:
                event = Event(
                    event_id=f"create_sub_{subscription.subscription_id}",
                    event_type=EventType.DATA_UPDATE,
                    priority=EventPriority.MEDIUM,
                    timestamp=datetime.now(),
                    data={
                        'subscription_id': subscription.subscription_id,
                        'action': 'create'
                    }
                )
                self.event_bus.publish(event)

            logger.info(f"创建订阅: {subscription.subscription_id}")

            return {
                'success': True,
                'subscription_id': subscription.subscription_id,
                'message': '订阅创建成功'
            }

        except Exception as e:
            logger.error(f"创建订阅失败: {e}")
            return {
                'success': False,
                'error': f"创建订阅失败: {str(e)}"
            }

    def delete_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        删除订阅

        Args:
            subscription_id: 订阅ID

        Returns:
            响应字典
        """
        try:
            if subscription_id not in self.subscriptions:
                return {
                    'success': False,
                    'error': f"订阅不存在: {subscription_id}"
                }

            # 删除订阅
            del self.subscriptions[subscription_id]

            # 清理缓存
            if self.cache_manager:
                self.cache_manager.remove(f"sub_{subscription_id}")

            # 发布事件
            if self.event_bus:
                event = Event(
                    event_id=f"delete_sub_{subscription_id}",
                    event_type=EventType.DATA_UPDATE,
                    priority=EventPriority.MEDIUM,
                    timestamp=datetime.now(),
                    data={
                        'subscription_id': subscription_id,
                        'action': 'delete'
                    }
                )
                self.event_bus.publish(event)

            logger.info(f"删除订阅: {subscription_id}")

            return {
                'success': True,
                'message': '订阅删除成功'
            }

        except Exception as e:
            logger.error(f"删除订阅失败: {e}")
            return {
                'success': False,
                'error': f"删除订阅失败: {str(e)}"
            }

    def add_data_point(
        self,
        subscription_id: str,
        data_point_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        添加数据点

        Args:
            subscription_id: 订阅ID
            data_point_data: 数据点数据

        Returns:
            响应字典
        """
        start_time = datetime.now()

        try:
            # 验证数据点
            valid, error_msg, point = DataValidator.validate_data_point(data_point_data)
            if not valid:
                return {
                    'success': False,
                    'error': error_msg
                }

            # 检查订阅是否存在
            if subscription_id not in self.subscriptions:
                return {
                    'success': False,
                    'error': f"订阅不存在: {subscription_id}"
                }

            # 节流控制
            if not self.throttle_controller.should_allow_update():
                return {
                    'success': False,
                    'error': '更新频率过高，被节流'
                }

            # 获取插值器
            kriging = self.subscriptions[subscription_id]

            # 执行增量更新
            update_result = kriging.incremental_update(point)

            # 缓存结果
            if self.cache_manager:
                cache_key = f"update_{subscription_id}_{update_result.version}"
                self.cache_manager.put(cache_key, update_result)

            # 发布事件
            if self.event_bus:
                event = Event(
                    event_id=f"update_{subscription_id}_{update_result.version}",
                    event_type=EventType.INTERPOLATION_UPDATE,
                    priority=EventPriority.HIGH,
                    timestamp=datetime.now(),
                    data={
                        'subscription_id': subscription_id,
                        'update_id': update_result.update_id,
                        'version': update_result.version,
                        'statistics': update_result.statistics
                    }
                )
                self.event_bus.publish(event)

            # 更新统计
            processing_time = (datetime.now() - start_time).total_seconds()
            self.stats['total_requests'] += 1
            self.stats['successful_requests'] += 1
            self.stats['total_updates'] += 1
            self.stats['avg_processing_time'] = (
                self.stats['avg_processing_time'] * (self.stats['successful_requests'] - 1) +
                processing_time
            ) / self.stats['successful_requests']

            logger.info(f"添加数据点成功: {subscription_id}, 版本: {update_result.version}")

            return {
                'success': True,
                'update_id': update_result.update_id,
                'version': update_result.version,
                'processing_time': processing_time,
                'affected_region': {
                    'min_x': update_result.affected_region.min_x,
                    'max_x': update_result.affected_region.max_x,
                    'min_y': update_result.affected_region.min_y,
                    'max_y': update_result.affected_region.max_y
                },
                'statistics': update_result.statistics
            }

        except Exception as e:
            logger.error(f"添加数据点失败: {e}")
            self.stats['total_requests'] += 1
            self.stats['failed_requests'] += 1

            return {
                'success': False,
                'error': f"添加数据点失败: {str(e)}"
            }

    def get_prediction(
        self,
        subscription_id: str,
        x: float,
        y: float
    ) -> Dict[str, Any]:
        """
        获取预测值

        Args:
            subscription_id: 订阅ID
            x: X坐标
            y: Y坐标

        Returns:
            响应字典
        """
        try:
            # 检查订阅是否存在
            if subscription_id not in self.subscriptions:
                return {
                    'success': False,
                    'error': f"订阅不存在: {subscription_id}"
                }

            # 获取插值器
            kriging = self.subscriptions[subscription_id]

            # 获取预测值
            prediction, variance = kriging._interpolate_at_point(x, y)

            return {
                'success': True,
                'x': x,
                'y': y,
                'prediction': prediction,
                'variance': variance,
                'confidence': 1.0 - variance
            }

        except Exception as e:
            logger.error(f"获取预测值失败: {e}")
            return {
                'success': False,
                'error': f"获取预测值失败: {str(e)}"
            }

    def get_stats(self) -> Dict[str, Any]:
        """
        获取服务统计信息

        Returns:
            统计信息字典
        """
        service_stats = {
            'service': {
                'healthy': self.healthy,
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                'start_time': self.start_time.isoformat(),
                'max_workers': self.max_workers
            },
            'requests': self.stats.copy(),
            'subscriptions': {
                'total': len(self.subscriptions),
                'ids': list(self.subscriptions.keys())
            },
            'update_queue': {
                'size': self.priority_manager.get_queue_size(),
                'throttle_rate': self.throttle_controller.get_update_rate()
            }
        }

        # 添加缓存统计
        if self.cache_manager:
            service_stats['cache'] = self.cache_manager.get_stats()

        # 添加事件统计
        if self.event_bus:
            service_stats['events'] = self.event_bus.get_stats()

        if self.event_monitor:
            service_stats['monitor'] = self.event_monitor.get_stats()

        return service_stats

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态字典
        """
        return {
            'healthy': self.healthy,
            'uptime': (datetime.now() - self.start_time).total_seconds(),
            'active_subscriptions': len(self.subscriptions),
            'queue_size': self.priority_manager.get_queue_size(),
            'status': 'OK' if self.healthy else 'ERROR'
        }


# ==================== 服务管理 ====================

class ServiceManager:
    """服务管理器"""

    def __init__(self):
        """初始化服务管理器"""
        self.services: Dict[str, RealtimeInterpolationService] = {}

    def create_service(
        self,
        service_id: str,
        **kwargs
    ) -> RealtimeInterpolationService:
        """
        创建服务实例

        Args:
            service_id: 服务ID
            **kwargs: 服务参数

        Returns:
            服务实例
        """
        if service_id in self.services:
            logger.warning(f"服务已存在: {service_id}")
            return self.services[service_id]

        service = RealtimeInterpolationService(**kwargs)
        self.services[service_id] = service

        logger.info(f"创建服务: {service_id}")
        return service

    def get_service(self, service_id: str) -> Optional[RealtimeInterpolationService]:
        """
        获取服务实例

        Args:
            service_id: 服务ID

        Returns:
            服务实例，如果不存在则返回None
        """
        return self.services.get(service_id)

    def delete_service(self, service_id: str) -> bool:
        """
        删除服务实例

        Args:
            service_id: 服务ID

        Returns:
            是否删除成功
        """
        if service_id in self.services:
            del self.services[service_id]
            logger.info(f"删除服务: {service_id}")
            return True
        return False


# ==================== 测试函数 ====================

def test_realtime_service():
    """测试实时服务"""
    print("\n测试实时服务...")

    # 创建服务
    service = RealtimeInterpolationService(
        max_workers=5,
        enable_cache=True,
        enable_events=True
    )

    # 创建订阅
    subscription_data = {
        'subscription_id': 'test_sub',
        'data_type': 'temperature',
        'spatial_extent': {
            'min_x': 0,
            'max_x': 100,
            'min_y': 0,
            'max_y': 100
        },
        'update_frequency': 5,
        'interpolation_params': {
            'method': 'ordinary_kriging',
            'grid_resolution': 10
        }
    }

    result = service.create_subscription(subscription_data)
    print(f"创建订阅: {result}")

    # 添加数据点
    for i in range(20):
        data_point = {
            'x': np.random.uniform(0, 100),
            'y': np.random.uniform(0, 100),
            'value': np.random.randn()
        }
        result = service.add_data_point('test_sub', data_point)
        if i < 5:
            print(f"添加数据点 {i}: {result['success']}")

    # 获取预测
    prediction = service.get_prediction('test_sub', 50, 50)
    print(f"预测值: {prediction}")

    # 获取统计
    stats = service.get_stats()
    print(f"服务统计:")
    print(f"  订阅数: {stats['subscriptions']['total']}")
    print(f"  总请求数: {stats['requests']['total_requests']}")
    print(f"  成功请求数: {stats['requests']['successful_requests']}")

    # 健康检查
    health = service.health_check()
    print(f"健康状态: {health}")

    print("实时服务测试通过！")


# 为兼容性添加别名
RealtimeService = RealtimeInterpolationService


if __name__ == "__main__":
    test_realtime_service()
    print("\n所有测试通过！")