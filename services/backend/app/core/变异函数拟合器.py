"""
变异函数拟合器
"""
from typing import Tuple

import numpy as np
from scipy.optimize import curve_fit


class VariogramFitter:
    """变异函数拟合器"""

    @staticmethod
    def spherical_model(h: np.ndarray, nugget: float, sill: float, range_: float) -> np.ndarray:
        """球状模型"""
        gamma = np.zeros_like(h)
        mask = h > 0
        gamma[mask] = nugget + (sill - nugget) * (
            1.5 * (h[mask] / range_) - 0.5 * (h[mask] / range_) ** 3
        )
        gamma[h >= range_] = sill
        return gamma

    @staticmethod
    def exponential_model(h: np.ndarray, nugget: float, sill: float, range_: float) -> np.ndarray:
        """指数模型"""
        return nugget + (sill - nugget) * (1 - np.exp(-3 * h / range_))

    @staticmethod
    def gaussian_model(h: np.ndarray, nugget: float, sill: float, range_: float) -> np.ndarray:
        """高斯模型"""
        return nugget + (sill - nugget) * (1 - np.exp(-3 * (h / range_) ** 2))

    def fit_variogram(
        self,
        lags: np.ndarray,
        semivariance: np.ndarray,
        model_type: str = "spherical"
    ) -> Tuple[float, float, float]:
        """
        拟合变异函数
        返回: (nugget, sill, range)
        """
        # 选择模型
        models = {
            "spherical": self.spherical_model,
            "exponential": self.exponential_model,
            "gaussian": self.gaussian_model
        }

        model_func = models.get(model_type, self.spherical_model)

        # 初始参数估计
        nugget_init = semivariance[0] if len(semivariance) > 0 else 0
        sill_init = np.max(semivariance)
        range_init = lags[len(lags) // 2] if len(lags) > 0 else 1.0

        try:
            # 拟合
            params, _ = curve_fit(
                model_func,
                lags,
                semivariance,
                p0=[nugget_init, sill_init, range_init],
                bounds=([0, 0, 0], [np.inf, np.inf, np.inf])
            )
            return tuple(params)
        except Exception:
            # 拟合失败，返回初始估计
            return (nugget_init, sill_init, range_init)
