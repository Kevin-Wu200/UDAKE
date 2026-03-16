"""
数据模型定义
Data Models
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np


@dataclass
class BoundingBox:
    """边界框"""
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    def contains(self, x: float, y: float) -> bool:
        """检查点是否在边界框内"""
        return (self.min_x <= x <= self.max_x and
                self.min_y <= y <= self.max_y)

    def intersects(self, other: 'BoundingBox') -> bool:
        """检查两个边界框是否相交"""
        return not (self.max_x < other.min_x or
                   self.min_x > other.max_x or
                   self.max_y < other.min_y or
                   self.min_y > other.max_y)

    def area(self) -> float:
        """计算面积"""
        return (self.max_x - self.min_x) * (self.max_y - self.min_y)

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "min_x": self.min_x,
            "max_x": self.max_x,
            "min_y": self.min_y,
            "max_y": self.max_y
        }


@dataclass
class DataPoint:
    """数据点"""
    x: float
    y: float
    value: float
    id: str
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "value": self.value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata or {}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataPoint':
        """从字典创建"""
        timestamp = None
        if data.get("timestamp"):
            timestamp = datetime.fromisoformat(data["timestamp"])

        return cls(
            id=data["id"],
            x=data["x"],
            y=data["y"],
            value=data["value"],
            timestamp=timestamp,
            metadata=data.get("metadata")
        )


@dataclass
class Subscription:
    """数据订阅"""
    subscription_id: str
    data_type: str
    spatial_extent: BoundingBox
    update_frequency: int  # 更新频率（秒）
    interpolation_params: Dict[str, Any]
    notification_config: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "subscription_id": self.subscription_id,
            "data_type": self.data_type,
            "spatial_extent": self.spatial_extent.to_dict(),
            "update_frequency": self.update_frequency,
            "interpolation_params": self.interpolation_params,
            "notification_config": self.notification_config,
            "created_at": self.created_at.isoformat(),
            "active": self.active
        }


@dataclass
class UpdateResult:
    """更新结果"""
    update_id: str
    subscription_id: str
    timestamp: datetime
    update_type: str  # incremental, full
    affected_region: BoundingBox
    prediction_grid: np.ndarray
    variance_grid: np.ndarray
    version: int
    statistics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "update_id": self.update_id,
            "subscription_id": self.subscription_id,
            "timestamp": self.timestamp.isoformat(),
            "update_type": self.update_type,
            "affected_region": self.affected_region.to_dict(),
            "prediction_grid": self.prediction_grid.tolist(),
            "variance_grid": self.variance_grid.tolist(),
            "version": self.version,
            "statistics": self.statistics
        }


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    version: int
    expire_time: Optional[float] = None
    access_count: int = 0
    last_access: float = field(default_factory=lambda: __import__('time').time())

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expire_time is None:
            return False
        return __import__('time').time() > self.expire_time

    def touch(self) -> None:
        """更新访问时间和计数"""
        self.access_count += 1
        self.last_access = __import__('time').time()


@dataclass
class VariogramModel:
    """变异函数模型"""
    model_type: str  # spherical, exponential, gaussian, linear
    sill: float  # 基台值
    range: float  # 变程
    nugget: float  # 块金值

    def covariance(self, point1: DataPoint, point2: DataPoint) -> float:
        """计算两点之间的协方差"""
        distance = np.sqrt((point1.x - point2.x)**2 + (point1.y - point2.y)**2)
        return self._covariance_by_distance(distance)

    def _covariance_by_distance(self, distance: float) -> float:
        """根据距离计算协方差"""
        if distance == 0:
            return self.sill + self.nugget

        h = distance / self.range

        if self.model_type == "spherical":
            if h <= 1:
                return self.nugget + self.sill * (1.5 * h - 0.5 * h**3)
            else:
                return self.nugget

        elif self.model_type == "exponential":
            return self.nugget + self.sill * (1 - np.exp(-3 * h))

        elif self.model_type == "gaussian":
            return self.nugget + self.sill * (1 - np.exp(-3 * h**2))

        elif self.model_type == "linear":
            if h <= 1:
                return self.nugget + self.sill * h
            else:
                return self.nugget + self.sill

        else:
            raise ValueError(f"未知的变异函数模型类型: {self.model_type}")


@dataclass
class SystemStatus:
    """系统状态"""
    timestamp: datetime
    system_status: str  # healthy, degraded, down
    performance: Dict[str, Any]
    subscriptions: Dict[str, Any]
    alerts: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "system_status": self.system_status,
            "performance": self.performance,
            "subscriptions": self.subscriptions,
            "alerts": self.alerts
        }


@dataclass
class Event:
    """事件"""
    event_type: str
    subscription_id: str
    timestamp: datetime
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "subscription_id": self.subscription_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }