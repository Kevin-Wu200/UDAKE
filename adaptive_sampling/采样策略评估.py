"""
采样策略评估
"""
from typing import Dict, List

import numpy as np
from scipy.spatial import distance_matrix


class SamplingStrategyEvaluator:
    """采样策略评估器"""

    def evaluate_sampling_strategy(
        self,
        existing_points: np.ndarray,
        proposed_points: np.ndarray,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray
    ) -> Dict[str, any]:
        """
        评估采样策略
        """
        # 空间覆盖评估
        coverage_score = self._evaluate_spatial_coverage(
            existing_points, proposed_points, x_coords, y_coords
        )

        # 方差减少潜力评估
        variance_reduction_score = self._evaluate_variance_reduction(
            proposed_points, variance, x_coords, y_coords
        )

        # 采样效率评估
        efficiency_score = self._evaluate_sampling_efficiency(
            existing_points, proposed_points
        )

        # 综合评分
        overall_score = (
            coverage_score * 0.3 +
            variance_reduction_score * 0.5 +
            efficiency_score * 0.2
        )

        return {
            "overall_score": float(overall_score),
            "coverage_score": float(coverage_score),
            "variance_reduction_score": float(variance_reduction_score),
            "efficiency_score": float(efficiency_score),
            "rating": self._get_rating(overall_score),
            "recommendations": self._generate_strategy_recommendations(
                coverage_score, variance_reduction_score, efficiency_score
            )
        }

    def _evaluate_spatial_coverage(
        self,
        existing_points: np.ndarray,
        proposed_points: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray
    ) -> float:
        """评估空间覆盖"""
        all_points = np.vstack([existing_points, proposed_points])

        # 计算点之间的平均最小距离
        distances = distance_matrix(all_points, all_points)
        np.fill_diagonal(distances, np.inf)
        min_distances = np.min(distances, axis=1)

        # 覆盖均匀性（距离标准差越小越好）
        uniformity = 1 - (np.std(min_distances) / (np.mean(min_distances) + 1e-10))

        return max(0, min(1, uniformity))

    def _evaluate_variance_reduction(
        self,
        proposed_points: np.ndarray,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray
    ) -> float:
        """评估方差减少潜力"""
        # 计算提议点位置的方差值
        variance_at_proposed = []

        for point in proposed_points:
            x_idx = np.argmin(np.abs(x_coords - point[0]))
            y_idx = np.argmin(np.abs(y_coords - point[1]))
            variance_at_proposed.append(variance[y_idx, x_idx])

        # 归一化方差值
        mean_variance_at_proposed = np.mean(variance_at_proposed)
        max_variance = np.max(variance)

        score = mean_variance_at_proposed / (max_variance + 1e-10)

        return float(score)

    def _evaluate_sampling_efficiency(
        self,
        existing_points: np.ndarray,
        proposed_points: np.ndarray
    ) -> float:
        """评估采样效率"""
        # 计算新点到现有点的最小距离
        distances = distance_matrix(proposed_points, existing_points)
        min_distances = np.min(distances, axis=1)

        # 效率 = 平均距离（避免冗余采样）
        mean_distance = np.mean(min_distances)
        max_possible_distance = np.max(distances)

        efficiency = mean_distance / (max_possible_distance + 1e-10)

        return float(efficiency)

    def _get_rating(self, score: float) -> str:
        """获取评级"""
        if score >= 0.8:
            return "优秀"
        elif score >= 0.6:
            return "良好"
        elif score >= 0.4:
            return "中等"
        else:
            return "需改进"

    def _generate_strategy_recommendations(
        self,
        coverage: float,
        variance_reduction: float,
        efficiency: float
    ) -> List[str]:
        """生成策略建议"""
        recommendations = []

        if coverage < 0.5:
            recommendations.append("建议增加空间覆盖范围")

        if variance_reduction < 0.5:
            recommendations.append("建议更多关注高方差区域")

        if efficiency < 0.5:
            recommendations.append("建议避免在现有采样点附近重复采样")

        if not recommendations:
            recommendations.append("当前采样策略表现良好")

        return recommendations
