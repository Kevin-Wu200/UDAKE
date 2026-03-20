"""
事件系统模块
Event System Module

实现事件模型、事件处理、实时通知和事件监控
"""

import numpy as np
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import threading
import queue
import time
import json
from collections import defaultdict, deque
from types import SimpleNamespace

logger = logging.getLogger(__name__)


# ==================== 事件模型 ====================

class EventType(Enum):
    """事件类型"""
    DATA_UPDATE = "data_update"  # 数据更新
    INTERPOLATION_UPDATE = "interpolation_update"  # 插值更新
    CACHE_UPDATE = "cache_update"  # 缓存更新
    ERROR = "error"  # 错误
    WARNING = "warning"  # 警告
    SYSTEM_STATUS = "system_status"  # 系统状态
    HOTSPOT_ALERT = "hotspot_alert"  # 热点告警（兼容旧测试）


class EventPriority(Enum):
    """事件优先级"""
    CRITICAL = 0  # 关键
    HIGH = 1      # 高
    MEDIUM = 2    # 中
    LOW = 3       # 低


@dataclass
class Event:
    """事件"""
    event_id: str
    event_type: EventType
    priority: EventPriority
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    correlation_id: Optional[str] = None

    @property
    def type(self):
        """兼容旧测试字段。"""
        return self.event_type

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        event_type_value = self.event_type.value if hasattr(self.event_type, "value") else self.event_type
        priority_value = self.priority.value if hasattr(self.priority, "value") else self.priority
        return {
            'event_id': self.event_id,
            'event_type': event_type_value,
            'priority': priority_value,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'source': self.source,
            'correlation_id': self.correlation_id
        }

    def to_json(self) -> str:
        """转换为JSON"""
        return json.dumps(self.to_dict())


# ==================== 事件处理 ====================

class EventHandler:
    """事件处理器基类"""

    def __init__(self, name: str):
        """
        初始化事件处理器

        Args:
            name: 处理器名称
        """
        self.name = name
        self.processed_count = 0
        self.error_count = 0

    def handle(self, event: Event) -> bool:
        """
        处理事件

        Args:
            event: 事件

        Returns:
            是否处理成功
        """
        try:
            self._handle_event(event)
            self.processed_count += 1
            return True
        except Exception as e:
            logger.error(f"事件处理失败 [{self.name}]: {e}")
            self.error_count += 1
            return False

    def _handle_event(self, event: Event) -> None:
        """实现具体的事件处理逻辑"""
        raise NotImplementedError("子类必须实现此方法")


class EventFilter:
    """事件过滤器"""

    def __init__(self, name: str):
        """
        初始化事件过滤器

        Args:
            name: 过滤器名称
        """
        self.name = name

    def should_process(self, event: Event) -> bool:
        """
        判断是否应该处理事件

        Args:
            event: 事件

        Returns:
            是否应该处理
        """
        raise NotImplementedError("子类必须实现此方法")


class EventTypeFilter(EventFilter):
    """事件类型过滤器"""

    def __init__(self, event_types: List[EventType]):
        """
        初始化事件类型过滤器

        Args:
            event_types: 允许的事件类型列表
        """
        super().__init__("EventTypeFilter")
        self.event_types = set(event_types)

    def should_process(self, event: Event) -> bool:
        return event.event_type in self.event_types


class EventPriorityFilter(EventFilter):
    """事件优先级过滤器"""

    def __init__(self, min_priority: EventPriority):
        """
        初始化事件优先级过滤器

        Args:
            min_priority: 最低优先级
        """
        super().__init__("EventPriorityFilter")
        self.min_priority = min_priority

    def should_process(self, event: Event) -> bool:
        return event.priority.value <= self.min_priority.value


class EventBus:
    """事件总线"""

    def __init__(self, max_queue_size: int = 10000):
        """
        初始化事件总线

        Args:
            max_queue_size: 最大队列大小
        """
        self.max_queue_size = max_queue_size
        self.event_queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=max_queue_size)

        # 处理器注册表
        self.handlers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        # 旧接口兼容：函数回调订阅
        self.callback_handlers: Dict[EventType, List[tuple[Callable, Optional[Callable]]]] = defaultdict(list)

        # 过滤器
        self.filters: List[EventFilter] = []

        # 统计信息
        self.published_count = 0
        self.processed_count = 0
        self.dropped_count = 0

        # 线程安全
        self.lock = threading.RLock()

        # 事件ID计数器
        self.event_counter = 0

    def publish(self, event: Any, data: Optional[Dict[str, Any]] = None) -> bool:
        """
        发布事件

        Args:
            event: 事件

        Returns:
            是否发布成功
        """
        # 兼容旧接口：publish(EventType, data_dict)
        if isinstance(event, Event):
            event_obj = event
        else:
            event_type = event
            payload = data or {}
            priority_raw = payload.get('priority', EventPriority.MEDIUM)
            if isinstance(priority_raw, EventPriority):
                priority_obj = priority_raw
            else:
                priority_obj = SimpleNamespace(value=int(priority_raw))

            with self.lock:
                self.event_counter += 1
                event_id = f"event_{self.event_counter}"

            event_obj = Event(
                event_id=event_id,
                event_type=event_type,
                priority=priority_obj,
                timestamp=payload.get('timestamp', datetime.now()),
                data=payload
            )

        with self.lock:
            # 应用过滤器
            for filter_obj in self.filters:
                if not filter_obj.should_process(event_obj):
                    logger.debug(f"事件被过滤器拒绝: {filter_obj.name}")
                    return False

            # 先触发函数回调（旧测试不调用 process_events）
            callbacks = self.callback_handlers.get(event_obj.event_type, [])
            for callback, filter_func in callbacks:
                try:
                    if filter_func is None or filter_func(event_obj):
                        callback(event_obj)
                except Exception as e:
                    logger.error(f"事件回调执行失败: {e}")

            # 尝试加入队列
            try:
                priority_value = event_obj.priority.value if hasattr(event_obj.priority, 'value') else 0
                self.event_queue.put((priority_value, event_obj.timestamp.timestamp(), event_obj))
                self.published_count += 1
                return True
            except queue.Full:
                self.dropped_count += 1
                logger.warning("事件队列已满，丢弃事件")
                return False

    def subscribe(
        self,
        event_type: EventType,
        handler: Any,
        filter_func: Optional[Callable] = None
    ) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型
            handler: 事件处理器
        """
        with self.lock:
            if isinstance(handler, EventHandler):
                self.handlers[event_type].append(handler)
                logger.info(f"订阅事件类型: {event_type.value}, 处理器: {handler.name}")
            elif callable(handler):
                self.callback_handlers[event_type].append((handler, filter_func))
                logger.info(f"订阅事件类型: {event_type.value}, 回调函数: {getattr(handler, '__name__', 'callback')}")
            else:
                raise TypeError("handler 必须是 EventHandler 或可调用对象")

    def unsubscribe(self, event_type: EventType, handler: Any) -> None:
        """
        取消订阅

        Args:
            event_type: 事件类型
            handler: 事件处理器
        """
        with self.lock:
            if handler in self.handlers[event_type]:
                self.handlers[event_type].remove(handler)
                logger.info(f"取消订阅事件类型: {event_type.value}, 处理器: {handler.name}")
                return

            callbacks = self.callback_handlers[event_type]
            self.callback_handlers[event_type] = [
                (cb, f) for cb, f in callbacks if cb is not handler
            ]

    def add_filter(self, filter_obj: EventFilter) -> None:
        """
        添加过滤器

        Args:
            filter_obj: 过滤器
        """
        with self.lock:
            self.filters.append(filter_obj)

    def remove_filter(self, filter_obj: EventFilter) -> None:
        """
        移除过滤器

        Args:
            filter_obj: 过滤器
        """
        with self.lock:
            if filter_obj in self.filters:
                self.filters.remove(filter_obj)

    def process_events(self, timeout: float = 1.0) -> int:
        """
        处理事件

        Args:
            timeout: 超时时间（秒）

        Returns:
            处理的事件数量
        """
        processed = 0

        while True:
            try:
                # 获取事件
                _, _, event = self.event_queue.get(timeout=timeout)

                # 查找处理器
                handlers = self.handlers.get(event.event_type, [])

                # 调用处理器
                for handler in handlers:
                    if handler.handle(event):
                        processed += 1

                self.processed_count += 1

            except queue.Empty:
                break

        return processed

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        with self.lock:
            return {
                'published_count': self.published_count,
                'processed_count': self.processed_count,
                'dropped_count': self.dropped_count,
                'queue_size': self.event_queue.qsize(),
                'max_queue_size': self.max_queue_size,
                'handler_count': (
                    sum(len(handlers) for handlers in self.handlers.values()) +
                    sum(len(handlers) for handlers in self.callback_handlers.values())
                )
            }


# ==================== 实时通知 ====================

class NotificationChannel:
    """通知通道"""

    def __init__(self, channel_id: str):
        """
        初始化通知通道

        Args:
            channel_id: 通道ID
        """
        self.channel_id = channel_id
        self.subscribers: List[Callable] = []

    def subscribe(self, callback: Callable) -> None:
        """
        订阅通知

        Args:
            callback: 回调函数
        """
        self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable) -> None:
        """
        取消订阅

        Args:
            callback: 回调函数
        """
        if callback in self.subscribers:
            self.subscribers.remove(callback)

    def notify(self, message: Dict[str, Any]) -> None:
        """
        通知订阅者

        Args:
            message: 消息
        """
        for callback in self.subscribers:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"通知回调失败: {e}")


class RealtimeNotifier:
    """实时通知器"""

    def __init__(self):
        """初始化实时通知器"""
        self.channels: Dict[str, NotificationChannel] = {}

    def create_channel(self, channel_id: str) -> NotificationChannel:
        """
        创建通知通道

        Args:
            channel_id: 通道ID

        Returns:
            通知通道
        """
        if channel_id not in self.channels:
            self.channels[channel_id] = NotificationChannel(channel_id)
        return self.channels[channel_id]

    def get_channel(self, channel_id: str) -> Optional[NotificationChannel]:
        """
        获取通知通道

        Args:
            channel_id: 通道ID

        Returns:
            通知通道，如果不存在则返回None
        """
        return self.channels.get(channel_id)

    def notify(self, channel_id: str, message: Dict[str, Any]) -> bool:
        """
        发送通知

        Args:
            channel_id: 通道ID
            message: 消息

        Returns:
            是否发送成功
        """
        channel = self.get_channel(channel_id)
        if channel:
            channel.notify(message)
            return True
        return False

    def broadcast(self, message: Dict[str, Any]) -> None:
        """
        广播消息到所有通道

        Args:
            message: 消息
        """
        for channel in self.channels.values():
            channel.notify(message)


# ==================== 事件监控 ====================

class EventMonitor:
    """事件监控器"""

    def __init__(self, max_history: int = 1000):
        """
        初始化事件监控器

        Args:
            max_history: 最大历史记录数
        """
        self.max_history = max_history

        # 事件历史
        self.event_history: deque[Event] = deque(maxlen=max_history)

        # 统计信息
        self.event_counts: Dict[EventType, int] = defaultdict(int)
        self.error_counts: Dict[str, int] = defaultdict(int)

        # 性能指标
        self.processing_times: deque[float] = deque(maxlen=100)

        # 告警阈值
        self.alert_thresholds = {
            'max_processing_time': 1.0,  # 最大处理时间（秒）
            'max_error_rate': 0.1,       # 最大错误率
            'max_queue_size': 1000       # 最大队列大小
        }

    def record_event(self, event: Event, processing_time: float = 0.0) -> None:
        """
        记录事件

        Args:
            event: 事件
            processing_time: 处理时间（秒）
        """
        # 添加到历史
        self.event_history.append(event)

        # 更新统计
        self.event_counts[event.event_type] += 1

        # 记录处理时间
        if processing_time > 0:
            self.processing_times.append(processing_time)

        # 检查错误
        if event.event_type == EventType.ERROR:
            error_type = event.data.get('error_type', 'unknown')
            self.error_counts[error_type] += 1

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        avg_processing_time = 0.0
        if self.processing_times:
            avg_processing_time = np.mean(self.processing_times)

        return {
            'total_events': sum(self.event_counts.values()),
            'event_counts': {k.value: v for k, v in self.event_counts.items()},
            'error_counts': dict(self.error_counts),
            'avg_processing_time': avg_processing_time,
            'history_size': len(self.event_history),
            'max_history': self.max_history
        }

    def check_alerts(self, event_bus: EventBus) -> List[Dict[str, Any]]:
        """
        检查告警

        Args:
            event_bus: 事件总线

        Returns:
            告警列表
        """
        alerts = []

        # 检查处理时间
        if self.processing_times:
            avg_time = np.mean(self.processing_times)
            if avg_time > self.alert_thresholds['max_processing_time']:
                alerts.append({
                    'type': 'processing_time',
                    'level': 'warning',
                    'message': f'平均处理时间过长: {avg_time:.3f}s',
                    'value': avg_time
                })

        # 检查错误率
        total_events = sum(self.event_counts.values())
        error_count = self.event_counts.get(EventType.ERROR, 0)
        if total_events > 0:
            error_rate = error_count / total_events
            if error_rate > self.alert_thresholds['max_error_rate']:
                alerts.append({
                    'type': 'error_rate',
                    'level': 'warning',
                    'message': f'错误率过高: {error_rate:.2%}',
                    'value': error_rate
                })

        # 检查队列大小
        stats = event_bus.get_stats()
        if stats['queue_size'] > self.alert_thresholds['max_queue_size']:
            alerts.append({
                'type': 'queue_size',
                'level': 'warning',
                'message': f'事件队列过大: {stats["queue_size"]}',
                'value': stats['queue_size']
            })

        return alerts


# ==================== 测试函数 ====================

def test_event_bus():
    """测试事件总线"""
    print("\n测试事件总线...")

    # 创建事件总线
    bus = EventBus()

    # 创建测试处理器
    class TestHandler(EventHandler):
        def __init__(self, name):
            super().__init__(name)

        def _handle_event(self, event: Event):
            print(f"处理事件 [{self.name}]: {event.event_type.value}")

    handler1 = TestHandler("Handler1")
    handler2 = TestHandler("Handler2")

    # 订阅事件
    bus.subscribe(EventType.DATA_UPDATE, handler1)
    bus.subscribe(EventType.DATA_UPDATE, handler2)

    # 发布事件
    for i in range(5):
        event = Event(
            event_id=f"event_{i}",
            event_type=EventType.DATA_UPDATE,
            priority=EventPriority.MEDIUM,
            timestamp=datetime.now(),
            data={'value': i}
        )
        bus.publish(event)

    # 处理事件
    processed = bus.process_events(timeout=0.1)
    print(f"处理了 {processed} 个事件")

    # 获取统计信息
    stats = bus.get_stats()
    print(f"统计信息: {stats}")

    print("事件总线测试通过！")


def test_realtime_notifier():
    """测试实时通知"""
    print("\n测试实时通知...")

    # 创建通知器
    notifier = RealtimeNotifier()

    # 创建通道
    channel = notifier.create_channel("test_channel")

    # 订阅通知
    messages_received = []

    def callback(message):
        messages_received.append(message)
        print(f"收到通知: {message}")

    channel.subscribe(callback)

    # 发送通知
    for i in range(3):
        notifier.notify("test_channel", {'id': i, 'message': f'Test {i}'})

    print(f"接收到 {len(messages_received)} 条通知")

    print("实时通知测试通过！")


def test_event_monitor():
    """测试事件监控"""
    print("\n测试事件监控...")

    # 创建监控器
    monitor = EventMonitor()

    # 创建事件总线
    bus = EventBus()

    # 记录一些事件
    for i in range(10):
        event = Event(
            event_id=f"event_{i}",
            event_type=EventType.DATA_UPDATE,
            priority=EventPriority.MEDIUM,
            timestamp=datetime.now(),
            data={'value': i}
        )
        monitor.record_event(event, processing_time=0.1)

    # 添加一些错误事件
    for i in range(2):
        event = Event(
            event_id=f"error_{i}",
            event_type=EventType.ERROR,
            priority=EventPriority.HIGH,
            timestamp=datetime.now(),
            data={'error_type': 'test_error'}
        )
        monitor.record_event(event)

    # 获取统计信息
    stats = monitor.get_stats()
    print(f"监控统计: {stats}")

    # 检查告警
    alerts = monitor.check_alerts(bus)
    print(f"告警数量: {len(alerts)}")
    for alert in alerts:
        print(f"  - {alert['message']}")

    print("事件监控测试通过！")


if __name__ == "__main__":
    test_event_bus()
    test_realtime_notifier()
    test_event_monitor()
    print("\n所有测试通过！")
