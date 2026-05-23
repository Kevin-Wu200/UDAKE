"""
ARIMA 时序预测器

实现自回归积分滑动平均模型（ARIMA），支持：
- 自动阶数选择（基于AIC/BIC）
- 差分和季节差分
- 置信区间估计
"""

import numpy as np
from typing import Optional, Dict, Any, Tuple
import logging

from .models import TimeSeriesData, ForecastResult, ForecastConfig

logger = logging.getLogger(__name__)


class ARIMAForecaster:
    """
    ARIMA预测器

    使用statsmodels的ARIMA实现，带自动阶数选择。
    如statsmodels不可用，回退到手动实现的基本ARIMA。
    """

    def __init__(self, order: Optional[Tuple[int, int, int]] = None):
        """
        初始化ARIMA预测器

        Args:
            order: (p, d, q) 阶数，None则自动选择
        """
        self.order = order
        self._fitted_model = None
        self._fitted_order: Optional[Tuple[int, int, int]] = None

    def fit(self, data: TimeSeriesData, config: Optional[ForecastConfig] = None) -> Dict[str, Any]:
        """
        拟合ARIMA模型

        Args:
            data: 时间序列数据
            config: 预测配置

        Returns:
            Dict: 拟合信息
        """
        values = data.values.copy()
        values = self._ensure_stationary(values)

        # 尝试使用statsmodels
        try:
            return self._fit_statsmodels(values, config)
        except ImportError:
            logger.info("statsmodels不可用，使用基本ARIMA实现")
            return self._fit_basic(values, config)

    def _fit_statsmodels(self, values: np.ndarray, config: Optional[ForecastConfig]) -> Dict[str, Any]:
        """使用statsmodels拟合"""
        try:
            from statsmodels.tsa.arima.model import ARIMA
        except ImportError:
            # 尝试旧版导入
            try:
                from statsmodels.tsa.arima_model import ARIMA as ARIMA_old

                if self.order is None:
                    best_order, best_aic = self._auto_select_order(values, max_p=5, max_q=5)
                    self._fitted_order = best_order
                else:
                    self._fitted_order = self.order

                model = ARIMA_old(values, order=self._fitted_order)
                self._fitted_model = model.fit(disp=False)
                return {
                    'order': self._fitted_order,
                    'aic': float(self._fitted_model.aic),
                    'bic': float(self._fitted_model.bic),
                }
            except ImportError:
                raise

        if self.order is None:
            best_order, best_aic = self._auto_select_order_statsmodels(values, max_p=5, max_q=5)
            self._fitted_order = best_order
        else:
            self._fitted_order = self.order

        model = ARIMA(values, order=self._fitted_order)
        self._fitted_model = model.fit()
        return {
            'order': self._fitted_order,
            'aic': float(self._fitted_model.aic),
            'bic': float(self._fitted_model.bic),
        }

    def _fit_basic(self, values: np.ndarray, config: Optional[ForecastConfig]) -> Dict[str, Any]:
        """基本ARIMA实现（不依赖statsmodels）"""
        if self.order is None:
            self._fitted_order = (2, 1, 1)  # 默认阶数
        else:
            self._fitted_order = self.order

        p, d, q = self._fitted_order

        # 差分
        diff_values = values.copy()
        for _ in range(d):
            diff_values = np.diff(diff_values)

        n = len(diff_values)
        self._ar_coeffs = np.zeros(p)
        self._ma_coeffs = np.zeros(q)
        self._residuals = np.zeros(n)

        # 简单AR拟合（Yule-Walker方法）
        if p > 0 and n > p:
            # 构建自相关矩阵
            acf = self._compute_acf(diff_values, p + 1)
            R = np.zeros((p, p))
            for i in range(p):
                for j in range(p):
                    R[i, j] = acf[abs(i - j)]
            r = acf[1:p + 1]
            try:
                self._ar_coeffs = np.linalg.solve(R, r)
            except np.linalg.LinAlgError:
                self._ar_coeffs = np.linalg.lstsq(R, r, rcond=None)[0]

        # 计算残差
        self._residuals = np.zeros(n)
        for t in range(p, n):
            pred = 0.0
            for i in range(p):
                pred += self._ar_coeffs[i] * diff_values[t - 1 - i]
            self._residuals[t] = diff_values[t] - pred

        # 简单MA系数估计
        if q > 0 and n > q:
            for j in range(q):
                if j < n - 1:
                    self._ma_coeffs[j] = np.corrcoef(
                        self._residuals[j + 1:], self._residuals[:-(j + 1)]
                    )[0, 1] if len(self._residuals) > j + 2 else 0.0

        self._fitted_model = True
        self._last_values = values[-p - d:] if len(values) >= p + d else values

        return {
            'order': self._fitted_order,
            'aic': float('inf'),
            'bic': float('inf'),
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
        if hasattr(self, '_fitted_model') and self._fitted_model is True:
            return self._predict_basic(horizon, config)
        else:
            return self._predict_statsmodels(horizon, config)

    def _predict_statsmodels(self, horizon: int, config: Optional[ForecastConfig]) -> ForecastResult:
        """使用statsmodels预测"""
        forecast_result = self._fitted_model.get_forecast(steps=horizon)
        predictions = forecast_result.predicted_mean
        ci = forecast_result.conf_int(alpha=1 - (config.confidence_interval if config else 0.95))

        return ForecastResult(
            predictions=np.array(predictions, dtype=np.float64),
            lower_bound=np.array(ci[:, 0], dtype=np.float64),
            upper_bound=np.array(ci[:, 1], dtype=np.float64),
            confidence_interval=config.confidence_interval if config else 0.95,
            model_name=f'ARIMA{self._fitted_order}',
        )

    def _predict_basic(self, horizon: int, config: Optional[ForecastConfig] = None) -> ForecastResult:
        """基本预测实现"""
        p, d, q = self._fitted_order
        predictions = np.zeros(horizon)

        # 使用最后一个已知值和AR系数进行预测
        last_diff = np.diff(self._last_values) if d > 0 else self._last_values
        current = last_diff[-1] if d > 0 else self._last_values[-1]

        history = list(last_diff[-max(p, 1):])

        for h in range(horizon):
            pred = 0.0
            for i in range(min(p, len(history))):
                pred += self._ar_coeffs[i] * history[-1 - i]
            predictions[h] = pred
            history.append(pred)
            if len(history) > p + 1:
                history = history[-p - 1:]

        # 反差分
        if d > 0:
            original_preds = np.zeros(horizon)
            base = self._last_values[-1]
            cumsum = np.cumsum(predictions)
            original_preds = base + cumsum
            predictions = original_preds

        # 简单置信区间
        std = np.std(self._residuals) if len(self._residuals) > 0 else 1.0
        z = 1.96  # 95% CI

        return ForecastResult(
            predictions=predictions,
            lower_bound=predictions - z * std * np.sqrt(np.arange(1, horizon + 1)),
            upper_bound=predictions + z * std * np.sqrt(np.arange(1, horizon + 1)),
            confidence_interval=config.confidence_interval if config else 0.95,
            model_name=f'ARIMA{self._fitted_order}(basic)',
        )

    def _auto_select_order(
        self, values: np.ndarray, max_p: int = 5, max_q: int = 5
    ) -> Tuple[Tuple[int, int, int], float]:
        """自动选择ARIMA阶数（基于AIC）"""
        best_aic = float('inf')
        best_order = (1, 1, 1)

        try:
            from statsmodels.tsa.arima_model import ARIMA as ARIMA_old
            for p in range(max_p + 1):
                for q in range(max_q + 1):
                    if p == 0 and q == 0:
                        continue
                    try:
                        model = ARIMA_old(values, order=(p, 1, q))
                        fitted = model.fit(disp=False)
                        if fitted.aic < best_aic:
                            best_aic = fitted.aic
                            best_order = (p, 1, q)
                    except Exception:
                        continue
        except ImportError:
            pass

        return best_order, best_aic

    def _auto_select_order_statsmodels(
        self, values: np.ndarray, max_p: int = 5, max_q: int = 5
    ) -> Tuple[Tuple[int, int, int], float]:
        """使用新版statsmodels自动选择阶数"""
        best_aic = float('inf')
        best_order = (1, 1, 1)

        try:
            from statsmodels.tsa.arima.model import ARIMA
            for p in range(max_p + 1):
                for q in range(max_q + 1):
                    if p == 0 and q == 0:
                        continue
                    try:
                        model = ARIMA(values, order=(p, 1, q))
                        fitted = model.fit()
                        if fitted.aic < best_aic:
                            best_aic = fitted.aic
                            best_order = (p, 1, q)
                    except Exception:
                        continue
        except ImportError:
            pass

        return best_order, best_aic

    def _compute_acf(self, data: np.ndarray, nlags: int) -> np.ndarray:
        """计算自相关函数"""
        n = len(data)
        mean = np.mean(data)
        variance = np.var(data)
        if variance == 0:
            return np.zeros(nlags)

        acf = np.zeros(nlags)
        for lag in range(nlags):
            cov = np.mean((data[:n - lag] - mean) * (data[lag:] - mean)) if lag < n else 0
            acf[lag] = cov / variance
        return acf

    def _ensure_stationary(self, values: np.ndarray) -> np.ndarray:
        """确保序列平稳（去除NaN和Inf）"""
        values = np.array(values, dtype=np.float64)
        values = np.nan_to_num(values, nan=np.nanmean(values) if not np.all(np.isnan(values)) else 0.0)
        return values
