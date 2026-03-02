"""
风险指数计算
"""
import numpy as np
from typing import Dict, Tuple

class RiskIndexCalculator:
    """风险指数计算器"""

    def calculate_risk_index(
        self,
        variance: np.ndarray,
        prediction: np.ndarray,
        threshold_values: Dict[str, float] = None
    ) -> np.ndarray:
        """
        计算风险指数
        """
        # 归一化方差
        normalized_variance = self._normalize(variance)

        # 归一化预测值（绝对值）
        normalized_prediction = self._normalize(np.abs(prediction))

        # 风险指数 = 方差权重 + 预测值权重
        risk_index = (
            normalized_variance * 0.7 +
            normalized_prediction * 0.3
        )

        return risk_index

    def calculate_spatial_risk(
        self,
        variance: np.ndarray,
        prediction: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray
    ) -> Dict[str, any]:
        """
        计算空间风险分布
        """
        risk_index = self.calculate_risk_index(variance, prediction)

        # 统计信息
        stats = {
            "mean": float(np.mean(risk_index)),
            "std": float(np.std(risk_index)),
            "min": float(np.min(risk_index)),
            "max": float(np.max(risk_index)),
            "median": float(np.median(risk_index))
        }

        # 风险等级分布
        risk_levels = self._classify_risk_levels(risk_index)

        # 高风险区域
        high_risk_mask = risk_index > np.percentile(risk_index, 75)
        high_risk_area = np.sum(high_risk_mask)

        return {
            "risk_index": risk_index,
            "statistics": stats,
            "risk_levels": risk_levels,
            "high_risk_area": int(high_risk_area),
            "high_risk_percentage": float(high_risk_area / risk_index.size * 100)
        }

    def _normalize(self, data: np.ndarray) -> np.ndarray:
        """归一化到[0, 1]"""
        min_val = np.min(data)
        max_val = np.max(data)
        if max_val - min_val < 1e-10:
            return np.zeros_like(data)
        return (data - min_val) / (max_val - min_val)

    def _classify_risk_levels(
        self,
        risk_index: np.ndarray
    ) -> Dict[str, int]:
        """分类风险等级"""
        low_risk = np.sum(risk_index < 0.33)
        medium_risk = np.sum((risk_index >= 0.33) & (risk_index < 0.67))
        high_risk = np.sum(risk_index >= 0.67)

        return {
            "low": int(low_risk),
            "medium": int(medium_risk),
            "high": int(high_risk)
        }

    def calculate_temporal_risk_trend(
        self,
        historical_variances: list,
        historical_predictions: list
    ) -> Dict[str, any]:
        """
        计算时间风险趋势
        """
        risk_trends = []

        for variance, prediction in zip(historical_variances, historical_predictions):
            risk_index = self.calculate_risk_index(variance, prediction)
            mean_risk = np.mean(risk_index)
            risk_trends.append(float(mean_risk))

        # 趋势分析
        if len(risk_trends) > 1:
            trend = "上升" if risk_trends[-1] > risk_trends[0] else "下降"
            change_rate = (risk_trends[-1] - risk_trends[0]) / (risk_trends[0] + 1e-10) * 100
        else:
            trend = "稳定"
            change_rate = 0.0

        return {
            "risk_trends": risk_trends,
            "trend_direction": trend,
            "change_rate": float(change_rate)
        }
