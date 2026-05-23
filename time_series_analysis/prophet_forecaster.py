"""
Prophet 时序预测器

基于Facebook Prophet的封装，支持趋势、季节性和假期效应建模。
如prophet不可用，回退到基本的季节性分解+趋势预测。
"""

import logging
from typing import Any, Dict, Optional

import numpy as np

from .models import ForecastConfig, ForecastResult, TimeSeriesData

logger = logging.getLogger(__name__)


class ProphetForecaster:
    """
    Prophet预测器

    封装Facebook Prophet库，支持自动季节检测和变点检测。
    """

    def __init__(
        self,
        yearly_seasonality: str = 'auto',
        weekly_seasonality: str = 'auto',
        daily_seasonality: str = 'auto',
        changepoint_prior_scale: float = 0.05,
        seasonality_prior_scale: float = 10.0,
    ):
        """
        初始化Prophet预测器

        Args:
            yearly_seasonality: 年季节性 ('auto', True, False, 或周期数)
            weekly_seasonality: 周季节性
            daily_seasonality: 日季节性
            changepoint_prior_scale: 变点先验尺度
            seasonality_prior_scale: 季节性先验尺度
        """
        self.yearly_seasonality = yearly_seasonality
        self.weekly_seasonality = weekly_seasonality
        self.daily_seasonality = daily_seasonality
        self.changepoint_prior_scale = changepoint_prior_scale
        self.seasonality_prior_scale = seasonality_prior_scale
        self._fitted_model = None

    def fit(self, data: TimeSeriesData, config: Optional[ForecastConfig] = None) -> Dict[str, Any]:
        """
        拟合Prophet模型

        Args:
            data: 时间序列数据
            config: 预测配置

        Returns:
            Dict: 拟合信息
        """
        try:
            return self._fit_prophet(data, config)
        except ImportError:
            logger.info("Prophet不可用，使用基本季节性分解")
            return self._fit_basic(data, config)

    def _fit_prophet(self, data: TimeSeriesData, config: Optional[ForecastConfig]) -> Dict[str, Any]:
        """使用Prophet拟合"""
        import pandas as pd
        from prophet import Prophet

        df = pd.DataFrame({
            'ds': data.timestamps,
            'y': data.values,
        })

        model = Prophet(
            yearly_seasonality=self.yearly_seasonality,
            weekly_seasonality=self.weekly_seasonality,
            daily_seasonality=self.daily_seasonality,
            changepoint_prior_scale=self.changepoint_prior_scale,
            seasonality_prior_scale=self.seasonality_prior_scale,
        )

        if config and config.seasonal_period:
            model.add_seasonality(
                name='custom',
                period=config.seasonal_period,
                fourier_order=5,
            )

        self._fitted_model = model.fit(df)

        return {
            'model': 'Prophet',
            'changepoints': len(model.changepoints) if hasattr(model, 'changepoints') else 0,
        }

    def _fit_basic(self, data: TimeSeriesData, config: Optional[ForecastConfig] = None) -> Dict[str, Any]:
        """基本季节性分解+趋势预测"""
        values = data.values.copy()
        n = len(values)

        # 线性趋势
        x = np.arange(n)
        trend = np.polyfit(x, values, 1)
        trend_line = np.polyval(trend, x)
        detrended = values - trend_line

        # 季节分解
        period = (config.seasonal_period if config and config.seasonal_period else 12)
        self._seasonal = np.zeros(period)
        if n >= period * 2:
            for i in range(period):
                indices = list(range(i, n, period))
                if indices:
                    self._seasonal[i] = np.mean(detrended[indices])

        self._trend = trend
        self._last_value = values[-1]
        self._residuals = detrended - np.tile(self._seasonal, (n // period) + 1)[:n]

        return {
            'model': 'Prophet(basic)',
            'trend_slope': float(trend[0]),
            'trend_intercept': float(trend[1]),
        }

    def predict(self, horizon: int, config: Optional[ForecastConfig] = None) -> ForecastResult:
        """
        预测

        Args:
            horizon: 预测步长
            config: 预测配置

        Returns:
            ForecastResult: 预测结果
        """
        if self._fitted_model is not None and not isinstance(self._fitted_model, dict):
            return self._predict_prophet(horizon, config)
        else:
            return self._predict_basic(horizon, config)

    def _predict_prophet(self, horizon: int, config: Optional[ForecastConfig] = None) -> ForecastResult:
        """使用Prophet预测"""

        future = self._fitted_model.make_future_dataframe(periods=horizon)
        forecast = self._fitted_model.predict(future)

        predictions = forecast['yhat'].values[-horizon:]
        lower = forecast['yhat_lower'].values[-horizon:]
        upper = forecast['yhat_upper'].values[-horizon:]

        return ForecastResult(
            predictions=np.array(predictions, dtype=np.float64),
            lower_bound=np.array(lower, dtype=np.float64),
            upper_bound=np.array(upper, dtype=np.float64),
            confidence_interval=config.confidence_interval if config else 0.95,
            model_name='Prophet',
        )

    def _predict_basic(self, horizon: int, config: Optional[ForecastConfig] = None) -> ForecastResult:
        """基本预测"""
        predictions = np.zeros(horizon)
        period = config.seasonal_period if config and config.seasonal_period else 12

        for h in range(horizon):
            trend_pred = self._last_value + self._trend[0] * (h + 1)
            seasonal_idx = (len(self._residuals) + h) % period if hasattr(self, '_seasonal') else 0
            seasonal = self._seasonal[seasonal_idx] if hasattr(self, '_seasonal') else 0.0
            predictions[h] = trend_pred + seasonal

        std = np.std(self._residuals) if hasattr(self, '_residuals') and len(self._residuals) > 0 else 1.0
        z = 1.96

        return ForecastResult(
            predictions=predictions,
            lower_bound=predictions - z * std * np.sqrt(np.arange(1, horizon + 1)),
            upper_bound=predictions + z * std * np.sqrt(np.arange(1, horizon + 1)),
            confidence_interval=config.confidence_interval if config else 0.95,
            model_name='Prophet(basic)',
        )
