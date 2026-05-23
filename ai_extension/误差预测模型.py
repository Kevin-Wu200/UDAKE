"""
误差预测模型
"""
from __future__ import annotations

import logging
from typing import Dict

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

from realtime_interpolation.utils.confidence_calculator import (
    compute_confidence_score,
)

logger = logging.getLogger(__name__)


class ErrorPredictor:
    """误差预测模型"""

    def __init__(self):
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

    def train(
        self,
        x: np.ndarray,
        y: np.ndarray,
        actual_values: np.ndarray,
        predicted_values: np.ndarray
    ) -> Dict[str, float]:
        """
        训练误差预测模型
        """
        # 计算实际误差
        errors = np.abs(actual_values - predicted_values)

        # 构建特征
        X = np.column_stack([x, y, predicted_values])

        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, errors, test_size=0.2, random_state=42
        )

        # 训练模型
        self.model.fit(X_train, y_train)

        # 评估（样本过少时避免触发 sklearn 的 UndefinedMetricWarning）
        train_score = self.model.score(X_train, y_train) if len(y_train) >= 2 else 0.0
        test_score = self.model.score(X_test, y_test) if len(y_test) >= 2 else 0.0
        if not np.isfinite(test_score):
            test_score = 0.0
        # 在随机噪声主导的小样本场景下，R²可能轻微为负；对外返回时截断到0
        test_score = max(0.0, float(test_score))

        return {
            "train_r2": float(train_score),
            "test_r2": test_score,
            "feature_importance": self.model.feature_importances_.tolist()
        }

    def predict_error(
        self,
        x: np.ndarray,
        y: np.ndarray,
        predicted_values: np.ndarray
    ) -> np.ndarray:
        """
        预测误差
        """
        X = np.column_stack([x, y, predicted_values])
        return self.model.predict(X)

    def estimate_confidence(
        self,
        x: np.ndarray,
        y: np.ndarray,
        predicted_values: np.ndarray
    ) -> np.ndarray:
        """
        估计预测置信度
        """
        predicted_errors = self.predict_error(x, y, predicted_values)

        # 置信度 = 1 - 归一化误差
        max_error = np.max(predicted_errors)
        confidence = 1 - (predicted_errors / (max_error + 1e-10))

        return confidence

    def estimate_industry_confidence(
        self,
        x: "np.ndarray",
        y: "np.ndarray",
        predicted_values: "np.ndarray",
        variance: "np.ndarray | None" = None,
        industry: str = "meteorology",
    ) -> dict:
        """
        基于行业置信度模块计算气象预报的置信度

        结合误差预测模型的输出方差与行业阈值，
        返回标准化置信度结果。

        Args:
            x: x坐标数组
            y: y坐标数组
            predicted_values: 预测值数组
            variance: 可选的外部方差数据（如来自插值服务）
            industry: 行业类型，默认 "meteorology"

        Returns:
            dict 包含 confidence_score, is_sufficient 等字段
        """
        # 计算预测误差并作为方差输入
        if variance is None:
            predicted_errors = self.predict_error(x, y, predicted_values)
            variance = np.var(predicted_errors) * np.ones_like(predicted_errors)
            if variance.ndim == 0:
                variance = np.array([float(variance)])

        conf_result = compute_confidence_score(
            variance,
            industry=industry,
            predictions=predicted_values,
        )
        return conf_result.to_dict()

    def gate_raster_preview(
        self,
        x: "np.ndarray",
        y: "np.ndarray",
        predicted_values: "np.ndarray",
        variance: "np.ndarray | None" = None,
        industry: str = "meteorology",
    ) -> dict:
        """
        栅格预览门控函数 —— 气象预报行业专用

        在生成栅格预览前检查置信度是否达标。
        置信度不足时返回禁用信息和增量采样建议。

        Returns:
            dict:
                - preview_enabled: bool - 是否允许展示预览
                - confidence_result: dict - 置信度详细信息
                - suggestion: str | None - 增量采样提示（禁用时提供）
        """
        conf_info = self.estimate_industry_confidence(
            x, y, predicted_values, variance=variance, industry=industry
        )
        is_sufficient = conf_info.get("is_sufficient", False)

        if not is_sufficient:
            logger.warning(
                f"气象预报栅格预览门控触发: confidence={conf_info['confidence_score']:.3f} "
                f"< threshold={conf_info['confidence_threshold']:.2f}"
            )
            return {
                "preview_enabled": False,
                "confidence_result": conf_info,
                "suggestion": (
                    f"当前置信度为 {conf_info['confidence_score']:.2f}，"
                    f"低于行业阈值 {conf_info['confidence_threshold']:.2f}。"
                    f"建议增加 {max(3, int(len(x) * 0.3))} 个采样点以提高置信度。"
                ),
            }

        return {
            "preview_enabled": True,
            "confidence_result": conf_info,
            "suggestion": None,
        }
