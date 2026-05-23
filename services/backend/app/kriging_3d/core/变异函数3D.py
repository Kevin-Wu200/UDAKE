"""
3D变异函数模块
支持球状、指数、高斯、线性模型，以及3D变异函数计算和拟合
"""
import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
from scipy.optimize import curve_fit

from .距离计算 import Distance3D

logger = logging.getLogger(__name__)


class Variogram3D:
    """3D变异函数"""

    # ========== 变异函数模型 ==========

    @staticmethod
    def spherical(h: np.ndarray, nugget: float, sill: float, range_: float) -> np.ndarray:
        """球状变异函数"""
        gamma = np.where(h > 0, nugget + (sill - nugget) * (
            1.5 * (h / range_) - 0.5 * (h / range_) ** 3
        ), 0.0)
        gamma = np.where(h >= range_, sill, gamma)
        return gamma

    @staticmethod
    def exponential(h: np.ndarray, nugget: float, sill: float, range_: float) -> np.ndarray:
        """指数变异函数"""
        return np.where(h > 0, nugget + (sill - nugget) * (1 - np.exp(-3 * h / range_)), 0.0)

    @staticmethod
    def gaussian(h: np.ndarray, nugget: float, sill: float, range_: float) -> np.ndarray:
        """高斯变异函数"""
        return np.where(h > 0, nugget + (sill - nugget) * (1 - np.exp(-3 * (h / range_) ** 2)), 0.0)

    @staticmethod
    def linear(h: np.ndarray, nugget: float, sill: float, range_: float) -> np.ndarray:
        """线性变异函数"""
        slope = (sill - nugget) / range_ if range_ > 0 else 0
        gamma = np.where(h > 0, nugget + slope * h, 0.0)
        return np.where(h >= range_, sill, gamma)

    MODELS = {
        "spherical": spherical.__func__,
        "exponential": exponential.__func__,
        "gaussian": gaussian.__func__,
        "linear": linear.__func__,
    }

    # ========== 实验变异函数计算 ==========

    @staticmethod
    def compute_experimental(
        points: np.ndarray,
        values: np.ndarray,
        nlags: int = 12,
        max_lag: Optional[float] = None,
        anisotropy_params: Optional[Dict] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        计算3D实验变异函数
        points: (n, 3) 坐标数组
        values: (n,) 值数组
        返回: (lags, semivariance, counts)
        """
        if anisotropy_params:
            dist_matrix = Distance3D.anisotropic_matrix(points, **anisotropy_params)
        else:
            dist_matrix = Distance3D.euclidean_matrix(points)

        if max_lag is None:
            max_lag = np.max(dist_matrix) / 2.0

        lag_edges = np.linspace(0, max_lag, nlags + 1)
        lags = (lag_edges[:-1] + lag_edges[1:]) / 2.0
        semivariance = np.zeros(nlags)
        counts = np.zeros(nlags, dtype=int)

        n = len(values)
        for i in range(n):
            for j in range(i + 1, n):
                d = dist_matrix[i, j]
                if d <= 0 or d > max_lag:
                    continue
                bin_idx = np.searchsorted(lag_edges[1:], d)
                if bin_idx < nlags:
                    semivariance[bin_idx] += (values[i] - values[j]) ** 2
                    counts[bin_idx] += 1

        valid = counts > 0
        semivariance[valid] /= (2.0 * counts[valid])

        return lags, semivariance, counts

    # ========== 变异函数拟合 ==========

    @classmethod
    def fit(
        cls,
        lags: np.ndarray,
        semivariance: np.ndarray,
        model_type: str = "spherical",
        counts: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        拟合3D变异函数
        返回拟合参数和质量指标
        """
        model_func = cls.MODELS.get(model_type, cls.MODELS["spherical"])

        valid = semivariance > 0
        if np.sum(valid) < 3:
            nugget = 0.0
            sill = float(np.max(semivariance)) if len(semivariance) > 0 else 1.0
            range_ = float(np.max(lags)) / 2.0 if len(lags) > 0 else 1.0
            return {
                "model_type": model_type,
                "nugget": nugget,
                "sill": sill,
                "range": range_,
                "r_squared": 0.0,
                "lags": lags.tolist(),
                "semivariance": semivariance.tolist(),
                "fitted_values": model_func(lags, nugget, sill, range_).tolist(),
            }

        fit_lags = lags[valid]
        fit_sv = semivariance[valid]

        nugget_init = float(fit_sv[0]) * 0.5
        sill_init = float(np.max(fit_sv))
        range_init = float(fit_lags[len(fit_lags) // 2])

        weights = None
        if counts is not None:
            valid_counts = counts[valid]
            weights = np.sqrt(valid_counts.astype(float))
            weights[weights == 0] = 1.0

        try:
            params, _ = curve_fit(
                model_func,
                fit_lags,
                fit_sv,
                p0=[nugget_init, sill_init, range_init],
                bounds=([0, 0, 1e-10], [np.inf, np.inf, np.inf]),
                sigma=1.0 / weights if weights is not None else None,
                maxfev=5000
            )
            nugget, sill, range_ = params
        except Exception:
            nugget, sill, range_ = nugget_init, sill_init, range_init

        fitted = model_func(fit_lags, nugget, sill, range_)
        ss_res = np.sum((fit_sv - fitted) ** 2)
        ss_tot = np.sum((fit_sv - np.mean(fit_sv)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

        return {
            "model_type": model_type,
            "nugget": float(nugget),
            "sill": float(sill),
            "range": float(range_),
            "r_squared": float(r_squared),
            "lags": lags.tolist(),
            "semivariance": semivariance.tolist(),
            "fitted_values": model_func(lags, nugget, sill, range_).tolist(),
        }

    @classmethod
    def auto_fit(
        cls,
        points: np.ndarray,
        values: np.ndarray,
        nlags: int = 12,
        anisotropy_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        自动选择最佳变异函数模型
        尝试所有模型，返回R²最高的
        """
        lags, sv, counts = cls.compute_experimental(
            points, values, nlags=nlags, anisotropy_params=anisotropy_params
        )

        best_result = None
        best_r2 = -np.inf

        for model_type in cls.MODELS:
            result = cls.fit(lags, sv, model_type, counts)
            if result["r_squared"] > best_r2:
                best_r2 = result["r_squared"]
                best_result = result

        logger.info(f"最佳变异函数模型: {best_result['model_type']}, R²={best_r2:.4f}")
        return best_result
