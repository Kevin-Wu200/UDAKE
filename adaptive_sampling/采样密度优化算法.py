"""
采样密度优化算法
"""
from typing import Dict, List

import numpy as np
from scipy.spatial import distance_matrix


class SamplingDensityOptimizer:
    """采样密度优化器"""

    def optimize_sampling_density(
        self,
        existing_points: np.ndarray,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        target_density: float = 0.1
    ) -> Dict[str, any]:
        """
        优化采样密度
        """
        # 计算当前密度
        total_area = (x_coords.max() - x_coords.min()) * (y_coords.max() - y_coords.min())
        current_density = len(existing_points) / total_area

        # 计算需要的额外采样点数
        additional_samples_needed = int(
            (target_density - current_density) * total_area
        )

        if additional_samples_needed <= 0:
            return {
                "current_density": float(current_density),
                "target_density": target_density,
                "additional_samples_needed": 0,
                "status": "sufficient"
            }

        # 计算每个网格点到现有点的最小距离
        xx, yy = np.meshgrid(x_coords, y_coords)
        grid_points = np.column_stack([xx.flatten(), yy.flatten()])

        distances = distance_matrix(grid_points, existing_points)
        min_distances = np.min(distances, axis=1)

        # 结合方差和距离计算采样优先级
        variance_flat = variance.flatten()
        normalized_variance = variance_flat / (np.max(variance_flat) + 1e-10)
        normalized_distance = min_distances / (np.max(min_distances) + 1e-10)

        # 优先级 = 方差权重 * 距离权重
        priority = normalized_variance * 0.6 + normalized_distance * 0.4

        return {
            "current_density": float(current_density),
            "target_density": target_density,
            "additional_samples_needed": additional_samples_needed,
            "priority_map": priority.reshape(variance.shape),
            "status": "optimization_needed"
        }

    def calculate_coverage_gaps(
        self,
        existing_points: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        coverage_radius: float = None
    ) -> List[Dict[str, float]]:
        """
        计算覆盖空白区域
        """
        if coverage_radius is None:
            # 自动计算覆盖半径
            coverage_radius = (x_coords.max() - x_coords.min()) / 20

        # 网格点
        xx, yy = np.meshgrid(x_coords, y_coords)
        grid_points = np.column_stack([xx.flatten(), yy.flatten()])

        # 计算到最近采样点的距离
        distances = distance_matrix(grid_points, existing_points)
        min_distances = np.min(distances, axis=1)

        # 找到覆盖空白
        gap_mask = min_distances > coverage_radius
        gap_indices = np.where(gap_mask)[0]

        gaps = []
        for idx in gap_indices:
            gaps.append({
                "x": float(grid_points[idx, 0]),
                "y": float(grid_points[idx, 1]),
                "distance_to_nearest": float(min_distances[idx])
            })

        return gaps
