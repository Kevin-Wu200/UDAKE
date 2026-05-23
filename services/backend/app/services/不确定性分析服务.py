"""
不确定性分析服务
"""
from typing import Dict, Tuple

import numpy as np
from scipy import stats


class UncertaintyAnalyzer:
    """不确定性分析器"""

    def analyze_variance(
        self,
        variance: np.ndarray
    ) -> Dict[str, float]:
        """
        分析方差统计特征
        """
        return {
            "mean": float(np.mean(variance)),
            "std": float(np.std(variance)),
            "min": float(np.min(variance)),
            "max": float(np.max(variance)),
            "median": float(np.median(variance)),
            "q25": float(np.percentile(variance, 25)),
            "q75": float(np.percentile(variance, 75))
        }

    def calculate_confidence_intervals(
        self,
        prediction: np.ndarray,
        variance: np.ndarray,
        confidence_level: float = 0.95
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算置信区间
        """
        z_score = stats.norm.ppf((1 + confidence_level) / 2)
        std = np.sqrt(variance)

        lower_bound = prediction - z_score * std
        upper_bound = prediction + z_score * std

        return lower_bound, upper_bound

    def identify_high_uncertainty_regions(
        self,
        variance: np.ndarray,
        threshold_percentile: float = 75
    ) -> np.ndarray:
        """
        识别高不确定性区域
        """
        threshold = np.percentile(variance, threshold_percentile)
        return variance > threshold

    def calculate_risk_index(
        self,
        variance: np.ndarray,
        prediction: np.ndarray
    ) -> np.ndarray:
        """
        计算风险指数
        """
        # 归一化方差
        normalized_variance = (variance - np.min(variance)) / (np.max(variance) - np.min(variance) + 1e-10)

        # 风险指数 = 归一化方差 * 预测值权重
        risk_index = normalized_variance * (1 + np.abs(prediction) / (np.max(np.abs(prediction)) + 1e-10))

        return risk_index
