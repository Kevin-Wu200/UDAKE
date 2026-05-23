"""
时空联合预测管道
Spatiotemporal Prediction Pipeline

将时序预测与空间插值结合，实现时空联合预测。
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from .models import TimeSeriesData, ForecastResult, ForecastConfig
from .arima import ARIMAForecaster
from .prophet_forecaster import ProphetForecaster

logger = logging.getLogger(__name__)


class SpatiotemporalPipeline:
    """
    时空联合预测管道

    工作流程：
    1. 对每个空间位置的时序数据进行时序预测
    2. 对预测值进行空间插值（克里金），得到连续空间预测
    3. 融合时序预测不确定性与空间插值不确定性
    """

    def __init__(
        self,
        spatial_interpolator=None,  # 可传入 Kriging/CoKriging 实例
        forecaster_type: str = 'arima',
        forecaster_config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化时空预测管道

        Args:
            spatial_interpolator: 空间插值器（Kriging/CoKriging实例）
            forecaster_type: 时序预测器类型 ('arima', 'prophet')
            forecaster_config: 预测器配置
        """
        self.spatial_interpolator = spatial_interpolator
        self.forecaster_type = forecaster_type
        self.forecaster_config = forecaster_config or {}
        self._location_forecasters: Dict[tuple, Any] = {}
        self._location_data: Dict[tuple, TimeSeriesData] = {}

    def add_location_data(self, location: Tuple[float, float], data: TimeSeriesData) -> None:
        """
        添加空间位置的时序数据

        Args:
            location: 空间坐标 (x, y)
            data: 时序数据
        """
        data = data.copy() if hasattr(data, 'copy') else data
        if data.location is None:
            data.location = location
        self._location_data[location] = data

    def fit_all(self) -> Dict[str, Any]:
        """
        拟合所有位置的时序模型

        Returns:
            Dict: 拟合统计信息
        """
        stats = {}
        for location, data in self._location_data.items():
            try:
                forecaster = self._create_forecaster()
                result = forecaster.fit(data)
                self._location_forecasters[location] = forecaster
                stats[str(location)] = result
            except Exception as e:
                logger.warning(f"位置 {location} 拟合失败: {e}")
                stats[str(location)] = {'error': str(e)}
        return stats

    def _create_forecaster(self):
        """创建预测器实例"""
        if self.forecaster_type == 'prophet':
            return ProphetForecaster(**self.forecaster_config)
        else:
            order = self.forecaster_config.get('order')
            return ARIMAForecaster(order=order)

    def predict_temporal(
        self,
        horizon: int = 10,
        config: Optional[ForecastConfig] = None,
    ) -> Dict[Tuple[float, float], ForecastResult]:
        """
        对所有位置进行时序预测

        Args:
            horizon: 预测步长
            config: 预测配置

        Returns:
            Dict: 位置 -> 预测结果
        """
        results = {}
        for location, forecaster in self._location_forecasters.items():
            try:
                results[location] = forecaster.predict(horizon, config)
            except Exception as e:
                logger.warning(f"位置 {location} 预测失败: {e}")
        return results

    def predict_spatiotemporal(
        self,
        target_locations: List[Tuple[float, float]],
        horizon: int = 10,
        config: Optional[ForecastConfig] = None,
    ) -> Dict[str, Any]:
        """
        时空联合预测

        步骤：
        1. 对各已知位置进行时序预测
        2. 使用空间插值器对目标位置进行插值
        3. 融合不确定度

        Args:
            target_locations: 目标位置列表
            horizon: 预测步长
            config: 预测配置

        Returns:
            Dict: {
                'predictions': 预测值矩阵 [n_locations × horizon],
                'variances': 方差矩阵 [n_locations × horizon],
                'target_locations': 目标位置列表,
            }
        """
        if config is None:
            config = ForecastConfig(horizon=horizon)

        # Step 1: 时序预测
        temporal_forecasts = self.predict_temporal(horizon, config)

        n_targets = len(target_locations)
        predictions = np.zeros((n_targets, horizon), dtype=np.float64)
        variances = np.zeros((n_targets, horizon), dtype=np.float64)

        if self.spatial_interpolator is not None:
            # Step 2: 对每个时间步进行空间插值
            from ..realtime_interpolation.models import DataPoint as RTDataPoint

            for t in range(horizon):
                # 收集各位置在时间t的预测值作为插值点
                interpolation_points = []
                for location, forecast in temporal_forecasts.items():
                    point = RTDataPoint(
                        x=float(location[0]),
                        y=float(location[1]),
                        value=float(forecast.predictions[t]),
                        id=f'st_point_{location[0]}_{location[1]}_t{t}',
                        metadata={'temporal_variance': float(
                            forecast.lower_bound[t] - forecast.upper_bound[t]
                        ) if forecast.lower_bound is not None else 0.0},
                    )
                    interpolation_points.append(point)

                # 空间插值
                if hasattr(self.spatial_interpolator, 'predict_batch'):
                    results = self.spatial_interpolator.predict_batch(target_locations)
                    for i, result in enumerate(results):
                        predictions[i, t] = result.value
                        variances[i, t] = result.variance
                else:
                    for i, loc in enumerate(target_locations):
                        result = self.spatial_interpolator.predict(loc[0], loc[1])
                        predictions[i, t] = result.value
                        variances[i, t] = result.variance
        else:
            # 无空间插值器：使用最近邻插值
            logger.warning("无空间插值器，使用IDW回退")
            for i, target in enumerate(target_locations):
                for t in range(horizon):
                    pred, var = self._idw_interpolate(target, temporal_forecasts, t)
                    predictions[i, t] = pred
                    variances[i, t] = var

        return {
            'predictions': predictions,
            'variances': variances,
            'target_locations': target_locations,
            'temporal_forecasts': temporal_forecasts,
        }

    def _idw_interpolate(
        self,
        target: Tuple[float, float],
        forecasts: Dict[Tuple[float, float], ForecastResult],
        time_step: int,
        power: float = 2.0,
    ) -> Tuple[float, float]:
        """IDW插值回退方案"""
        total_weight = 0.0
        weighted_sum = 0.0
        weighted_var = 0.0

        for location, forecast in forecasts.items():
            dist = np.sqrt((target[0] - location[0]) ** 2 + (target[1] - location[1]) ** 2)
            if dist < 1e-10:
                return float(forecast.predictions[time_step]), 0.0

            w = 1.0 / (dist ** power)
            total_weight += w
            weighted_sum += w * float(forecast.predictions[time_step])
            temporal_var = (float(forecast.upper_bound[time_step]) -
                          float(forecast.lower_bound[time_step])) / 4.0 if forecast.lower_bound is not None else 0.0
            weighted_var += w * temporal_var

        if total_weight > 0:
            return float(weighted_sum / total_weight), float(weighted_var / total_weight)
        return 0.0, float('inf')
