"""
趋势识别模型
"""
from __future__ import annotations

import logging
from typing import Dict

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

from realtime_interpolation.utils.confidence_calculator import (
    compute_confidence_score,
)

logger = logging.getLogger(__name__)

class TrendIdentifier:
    """趋势识别模型"""

    def __init__(self):
        self.linear_model = LinearRegression()
        self.poly_features = PolynomialFeatures(degree=2)

    def detect_linear_trend(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray
    ) -> Dict[str, float]:
        """
        检测线性趋势
        """
        # 构建特征矩阵
        X = np.column_stack([x, y])

        # 拟合线性模型
        self.linear_model.fit(X, values)

        # 获取系数
        coefficients = self.linear_model.coef_
        intercept = self.linear_model.intercept_
        r2_score = self.linear_model.score(X, values)

        return {
            "x_coefficient": float(coefficients[0]),
            "y_coefficient": float(coefficients[1]),
            "intercept": float(intercept),
            "r2_score": float(r2_score),
            "has_trend": r2_score > 0.3
        }

    def detect_polynomial_trend(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray
    ) -> Dict[str, float]:
        """
        检测多项式趋势
        """
        X = np.column_stack([x, y])
        X_poly = self.poly_features.fit_transform(X)

        poly_model = LinearRegression()
        poly_model.fit(X_poly, values)

        r2_score = poly_model.score(X_poly, values)

        return {
            "r2_score": float(r2_score),
            "has_polynomial_trend": r2_score > 0.4
        }

    def predict_trend(
        self,
        x: np.ndarray,
        y: np.ndarray
    ) -> np.ndarray:
        """
        预测趋势值
        """
        X = np.column_stack([x, y])
        return self.linear_model.predict(X)

    def estimate_trend_confidence(
        self,
        x: "np.ndarray",
        y: "np.ndarray",
        values: "np.ndarray",
        variance: "np.ndarray | None" = None,
        industry: str = "urban_heat",
    ) -> dict:
        """
        基于趋势模型 R² 和方差估算城市热岛趋势置信度

        结合线性趋势拟合的 R² 分数和空间方差，
        使用 UrbanHeatConfidenceCalculator 计算综合置信度。

        Args:
            x: x坐标数组
            y: y坐标数组
            values: 观测值数组
            variance: 可选的外部方差数据
            industry: 行业类型，默认 "urban_heat"

        Returns:
            dict 包含 confidence_score, is_sufficient 等字段
        """
        # 获取趋势拟合的 R²
        trend_info = self.detect_linear_trend(x, y, values)
        r2_score = trend_info.get("r2_score", 0.0)

        # 计算预测值与实际值的残差方差
        if variance is None:
            predicted = self.predict_trend(x, y)
            residuals = values - predicted
            variance = np.var(residuals) * np.ones(len(x))
            if variance.ndim == 0:
                variance = np.array([float(variance)])

        conf_result = compute_confidence_score(
            variance,
            industry=industry,
            r2_score=r2_score,
        )
        return conf_result.to_dict()

    def gate_trend_analysis(
        self,
        x: "np.ndarray",
        y: "np.ndarray",
        values: "np.ndarray",
        variance: "np.ndarray | None" = None,
        industry: str = "urban_heat",
    ) -> dict:
        """
        趋势分析门控函数 —— 城市热岛监测行业专用

        在趋势分析前检查置信度是否达标。
        置信度不足时返回禁用信息和增量采样建议。

        Returns:
            dict:
                - analysis_enabled: bool
                - confidence_result: dict
                - suggestion: str | None
        """
        conf_info = self.estimate_trend_confidence(
            x, y, values, variance=variance, industry=industry
        )
        is_sufficient = conf_info.get("is_sufficient", False)

        if not is_sufficient:
            logger.warning(
                f"城市热岛趋势分析门控触发: confidence={conf_info['confidence_score']:.3f} "
                f"< threshold={conf_info['confidence_threshold']:.2f}"
            )
            return {
                "analysis_enabled": False,
                "confidence_result": conf_info,
                "suggestion": (
                    f"当前置信度为 {conf_info['confidence_score']:.2f}，"
                    f"低于行业阈值 {conf_info['confidence_threshold']:.2f}。"
                    f"建议增加 {max(5, int(len(x) * 0.25))} 个采样点并延长观测周期以提高趋势分析可靠性。"
                ),
            }

        return {
            "analysis_enabled": True,
            "confidence_result": conf_info,
            "suggestion": None,
        }
