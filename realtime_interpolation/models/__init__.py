"""
数据模型定义
Data Models
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np


@dataclass(init=False)
class BoundingBox:
    """边界框"""
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    def __init__(self, *args, **kwargs):
        # 兼容新格式: min_x/max_x/min_y/max_y
        if {'min_x', 'max_x', 'min_y', 'max_y'}.issubset(kwargs.keys()):
            self.min_x = float(kwargs['min_x'])
            self.max_x = float(kwargs['max_x'])
            self.min_y = float(kwargs['min_y'])
            self.max_y = float(kwargs['max_y'])
            return

        # 兼容旧格式: min_lon/min_lat/max_lon/max_lat
        if {'min_lon', 'min_lat', 'max_lon', 'max_lat'}.issubset(kwargs.keys()):
            self.min_x = float(kwargs['min_lon'])
            self.min_y = float(kwargs['min_lat'])
            self.max_x = float(kwargs['max_lon'])
            self.max_y = float(kwargs['max_lat'])
            return

        # 位置参数兼容:
        # 新格式 (min_x, max_x, min_y, max_y)
        # 旧格式 (min_lon, min_lat, max_lon, max_lat)
        if len(args) == 4:
            a, b, c, d = [float(v) for v in args]
            if b < c:
                # 旧格式
                self.min_x = a
                self.min_y = b
                self.max_x = c
                self.max_y = d
            else:
                # 新格式
                self.min_x = a
                self.max_x = b
                self.min_y = c
                self.max_y = d
            return

        raise ValueError("BoundingBox 参数格式错误")

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

    @property
    def min_lon(self) -> float:
        return self.min_x

    @property
    def max_lon(self) -> float:
        return self.max_x

    @property
    def min_lat(self) -> float:
        return self.min_y

    @property
    def max_lat(self) -> float:
        return self.max_y


@dataclass
class DataPoint:
    """数据点"""
    x: float
    y: float
    value: float
    id: str
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    # 协克里金扩展：辅助变量值
    secondary_value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "value": self.value,
            "secondary_value": self.secondary_value,
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
            metadata=data.get("metadata"),
            secondary_value=data.get("secondary_value")
        )


@dataclass(init=False)
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

    def __init__(
        self,
        subscription_id: Optional[str] = None,
        data_type: str = 'generic',
        spatial_extent: Optional[BoundingBox] = None,
        update_frequency: int = 5,
        interpolation_params: Optional[Dict[str, Any]] = None,
        notification_config: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        active: bool = True,
        **legacy_kwargs
    ):
        # 兼容旧版字段: id/name/area/update_interval
        if subscription_id is None and 'id' in legacy_kwargs:
            subscription_id = legacy_kwargs['id']
        if 'name' in legacy_kwargs:
            data_type = legacy_kwargs.get('name') or data_type
        if spatial_extent is None and 'area' in legacy_kwargs:
            spatial_extent = legacy_kwargs['area']
        if 'update_interval' in legacy_kwargs:
            interval = legacy_kwargs['update_interval']
            # 旧版多为毫秒，这里统一转换为秒
            update_frequency = max(1, int(interval / 1000)) if interval > 100 else int(interval)

        self.subscription_id = subscription_id or f"sub_{int(datetime.now().timestamp())}"
        self.data_type = data_type
        self.spatial_extent = spatial_extent or BoundingBox(0.0, 100.0, 0.0, 100.0)
        self.update_frequency = update_frequency
        self.interpolation_params = interpolation_params or {}
        self.notification_config = notification_config or {}
        self.created_at = created_at or datetime.now()
        self.active = active

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

    @property
    def id(self) -> str:
        return self.subscription_id

    @property
    def name(self) -> str:
        return self.data_type

    @property
    def area(self) -> BoundingBox:
        return self.spatial_extent

    @property
    def update_interval(self) -> int:
        return self.update_frequency


@dataclass
class PredictionResult:
    """预测结果（兼容测试接口）"""
    value: float
    variance: float


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
    model_type: str  # spherical, exponential, gaussian, linear, power, logarithmic
    sill: float  # 基台值
    range: float  # 变程
    nugget: float  # 块金值
    power: Optional[float] = None  # 幂函数模型指数（power模型专用）

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

        elif self.model_type == "power":
            p = self.power if self.power is not None else 1.0
            if h <= 1:
                return self.nugget + self.sill * (h ** p)
            else:
                return self.nugget + self.sill

        elif self.model_type == "logarithmic":
            if h > 0 and h <= 1:
                return self.nugget + self.sill * (-np.log(h + 1e-10))
            else:
                return self.nugget + self.sill

        else:
            raise ValueError(f"未知的变异函数模型类型: {self.model_type}")

    def variogram_by_distance(self, distance: float) -> float:
        """根据距离计算变异函数值（半方差）"""
        cov = self._covariance_by_distance(distance)
        return (self.sill + self.nugget) - cov

    def auto_select_model(
        self,
        distances: np.ndarray,
        empirical_variogram: np.ndarray,
        candidate_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        自动选择最优变异函数模型

        Args:
            distances: 距离数组
            empirical_variogram: 经验变异函数值
            candidate_types: 候选模型类型列表

        Returns:
            Dict: 最优模型信息 {model_type, rmse, aic}
        """
        if candidate_types is None:
            candidate_types = ['spherical', 'exponential', 'gaussian', 'power', 'linear', 'logarithmic']

        best_model = None
        best_rmse = float('inf')
        n_points = len(distances)
        results = []

        for model_type in candidate_types:
            # 使用加权最小二乘拟合参数
            fitted = self._fit_model_parameters(distances, empirical_variogram, model_type)
            if fitted is None:
                continue

            rmse = fitted['rmse']
            n_params = 3 if model_type not in ('power',) else 4
            # 使用 BIC 进行模型选择
            bic = n_points * np.log(rmse + 1e-10) + n_params * np.log(n_points) if n_points > 1 else rmse

            results.append({
                'model_type': model_type,
                'rmse': rmse,
                'bic': bic,
                'params': fitted,
            })

            if rmse < best_rmse:
                best_rmse = rmse
                best_model = fitted

        # 按RMSE排序
        results.sort(key=lambda x: x['rmse'])

        return {
            'best_model': best_model,
            'candidates': results,
        }

    def _fit_model_parameters(
        self,
        distances: np.ndarray,
        empirical_variogram: np.ndarray,
        model_type: str,
    ) -> Optional[Dict[str, Any]]:
        """使用加权最小二乘法拟合变异函数参数"""
        max_dist = float(np.max(distances)) * 1.5
        max_semivar = float(np.max(empirical_variogram)) * 1.5

        # 网格搜索粗调
        best_rmse = float('inf')
        best_params = None

        sill_candidates = np.linspace(0.1, max_semivar, 10)
        range_candidates = np.linspace(1.0, max_dist, 10)
        nugget_candidates = np.linspace(0.0, max_semivar * 0.3, 5)
        power_candidates = np.linspace(0.2, 2.0, 10) if model_type == 'power' else [None]

        for sill in sill_candidates:
            for range_val in range_candidates:
                for nugget in nugget_candidates:
                    for power_val in power_candidates:
                        h = distances / range_val
                        h = np.clip(h, 0, 10)

                        if model_type == 'spherical':
                            theoretical = np.where(h <= 1, sill * (1.5 * h - 0.5 * h**3), sill) + nugget
                        elif model_type == 'exponential':
                            theoretical = sill * (1 - np.exp(-3 * h)) + nugget
                        elif model_type == 'gaussian':
                            theoretical = sill * (1 - np.exp(-3 * h**2)) + nugget
                        elif model_type == 'power':
                            theoretical = sill * (h ** (power_val if power_val else 1.0)) + nugget
                        elif model_type == 'linear':
                            theoretical = np.where(h <= 1, sill * h, sill) + nugget
                        elif model_type == 'logarithmic':
                            theoretical = np.where(h > 0, sill * (-np.log(h + 1e-10)), sill) + nugget
                        else:
                            continue

                        weights = 1.0 / (distances + 1e-6)
                        rmse = float(np.sqrt(np.mean(weights * (empirical_variogram - theoretical) ** 2)))

                        if rmse < best_rmse:
                            best_rmse = rmse
                            best_params = {
                                'model_type': model_type,
                                'sill': float(sill),
                                'range': float(range_val),
                                'nugget': float(nugget),
                                'power': float(power_val) if power_val is not None else None,
                                'rmse': float(rmse),
                            }

        return best_params


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
