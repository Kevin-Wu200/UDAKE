"""
不确定性分级模型
"""
from enum import Enum
from typing import Dict, List

import numpy as np


class UncertaintyLevel(str, Enum):
    """不确定性等级"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

class UncertaintyClassifier:
    """不确定性分级器"""

    def __init__(self):
        self.thresholds = {
            UncertaintyLevel.VERY_LOW: 0.2,
            UncertaintyLevel.LOW: 0.4,
            UncertaintyLevel.MEDIUM: 0.6,
            UncertaintyLevel.HIGH: 0.8
        }

    def classify_uncertainty(
        self,
        variance: np.ndarray,
        custom_thresholds: Dict[str, float] = None
    ) -> np.ndarray:
        """
        分级不确定性
        """
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)

        # 归一化方差
        normalized_variance = self._normalize(variance)

        # 分级
        classified = np.zeros_like(normalized_variance, dtype=int)

        classified[normalized_variance < self.thresholds[UncertaintyLevel.VERY_LOW]] = 0
        classified[(normalized_variance >= self.thresholds[UncertaintyLevel.VERY_LOW]) &
                   (normalized_variance < self.thresholds[UncertaintyLevel.LOW])] = 1
        classified[(normalized_variance >= self.thresholds[UncertaintyLevel.LOW]) &
                   (normalized_variance < self.thresholds[UncertaintyLevel.MEDIUM])] = 2
        classified[(normalized_variance >= self.thresholds[UncertaintyLevel.MEDIUM]) &
                   (normalized_variance < self.thresholds[UncertaintyLevel.HIGH])] = 3
        classified[normalized_variance >= self.thresholds[UncertaintyLevel.HIGH]] = 4

        return classified

    def get_level_statistics(
        self,
        variance: np.ndarray
    ) -> Dict[str, any]:
        """
        获取各等级统计信息
        """
        classified = self.classify_uncertainty(variance)

        level_names = [
            "very_low", "low", "medium", "high", "very_high"
        ]

        statistics = {}
        for i, level in enumerate(level_names):
            count = np.sum(classified == i)
            percentage = count / classified.size * 100

            statistics[level] = {
                "count": int(count),
                "percentage": float(percentage),
                "level_code": i
            }

        return statistics

    def generate_uncertainty_map(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray
    ) -> Dict[str, any]:
        """
        生成不确定性地图
        """
        classified = self.classify_uncertainty(variance)
        statistics = self.get_level_statistics(variance)

        # 颜色映射
        color_map = {
            0: "#2ecc71",  # 很低 - 绿色
            1: "#3498db",  # 低 - 蓝色
            2: "#f39c12",  # 中等 - 橙色
            3: "#e74c3c",  # 高 - 红色
            4: "#c0392b"   # 很高 - 深红色
        }

        return {
            "classified_map": classified,
            "statistics": statistics,
            "color_map": color_map,
            "x_coords": x_coords.tolist(),
            "y_coords": y_coords.tolist()
        }

    def _normalize(self, data: np.ndarray) -> np.ndarray:
        """归一化"""
        min_val = np.min(data)
        max_val = np.max(data)
        if max_val - min_val < 1e-10:
            return np.zeros_like(data)
        return (data - min_val) / (max_val - min_val)

    def identify_critical_zones(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        critical_level: int = 3
    ) -> List[Dict[str, float]]:
        """
        识别关键区域
        """
        classified = self.classify_uncertainty(variance)
        critical_mask = classified >= critical_level

        # 获取关键区域坐标
        y_indices, x_indices = np.where(critical_mask)

        critical_zones = []
        for y_idx, x_idx in zip(y_indices, x_indices):
            critical_zones.append({
                "x": float(x_coords[x_idx]),
                "y": float(y_coords[y_idx]),
                "variance": float(variance[y_idx, x_idx]),
                "level": int(classified[y_idx, x_idx])
            })

        return critical_zones
