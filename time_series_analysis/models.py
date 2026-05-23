"""
时序分析数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class TimeSeriesData:
    """时间序列数据"""
    timestamps: List[datetime]
    values: np.ndarray
    location: Optional[tuple] = None  # (x, y) 空间坐标
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if isinstance(self.values, list):
            self.values = np.array(self.values, dtype=np.float64)

    def __len__(self) -> int:
        return len(self.timestamps)

    def to_array(self) -> np.ndarray:
        return self.values.copy()

    def slice(self, start: int, end: int) -> 'TimeSeriesData':
        return TimeSeriesData(
            timestamps=self.timestamps[start:end],
            values=self.values[start:end].copy(),
            location=self.location,
            metadata=self.metadata,
        )


@dataclass
class ForecastResult:
    """预测结果"""
    predictions: np.ndarray
    lower_bound: Optional[np.ndarray] = None
    upper_bound: Optional[np.ndarray] = None
    confidence_interval: float = 0.95
    model_name: str = ''
    metrics: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'predictions': self.predictions.tolist(),
            'confidence_interval': self.confidence_interval,
            'model_name': self.model_name,
        }
        if self.lower_bound is not None:
            result['lower_bound'] = self.lower_bound.tolist()
        if self.upper_bound is not None:
            result['upper_bound'] = self.upper_bound.tolist()
        if self.metrics is not None:
            result['metrics'] = self.metrics
        return result


@dataclass
class ForecastConfig:
    """预测配置"""
    horizon: int = 10  # 预测步长
    confidence_interval: float = 0.95
    seasonality: bool = True
    auto_seasonality: bool = True
    seasonal_period: int = 12  # 季节周期
    use_exogenous: bool = False
    exogenous_data: Optional[np.ndarray] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)
