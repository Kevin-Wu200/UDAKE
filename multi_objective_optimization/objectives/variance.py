"""
方差最小化目标函数
Variance Minimization Objective
"""

from typing import Any, Dict, List, Tuple

import numpy as np

from ..core.population import Individual
from .base import BaseObjective


class VarianceObjective(BaseObjective):
    """
    方差最小化目标函数
    Minimize the Kriging variance of sampling points
    """

    def __init__(
        self,
        variance_grid: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        weight: float = 1.0
    ):
        """
        初始化方差目标函数

        Args:
            variance_grid: 方差网格数据 (height, width)
            x_coords: X坐标数组
            y_coords: Y坐标数组
            weight: 权重系数
        """
        super().__init__(name='variance', weight=weight, direction='minimize')
        self.variance_grid = variance_grid
        self.x_coords = x_coords
        self.y_coords = y_coords

        # 预计算网格索引
        self.height, self.width = variance_grid.shape
        self.x_min, self.x_max = x_coords.min(), x_coords.max()
        self.y_min, self.y_max = y_coords.min(), y_coords.max()

        # 创建坐标到网格索引的映射
        self._create_coordinate_mapping()

    def _create_coordinate_mapping(self):
        """创建坐标到网格索引的映射"""
        # 计算步长
        self.x_step = (self.x_max - self.x_min) / (self.width - 1) if self.width > 1 else 1
        self.y_step = (self.y_max - self.y_min) / (self.height - 1) if self.height > 1 else 1

    def _coordinate_to_grid_index(self, x: float, y: float) -> Tuple[int, int]:
        """
        将坐标转换为网格索引

        Args:
            x: X坐标
            y: Y坐标

        Returns:
            Tuple[int, int]: (row, col) 网格索引
        """
        # 计算列索引
        col = int((x - self.x_min) / self.x_step)
        col = max(0, min(col, self.width - 1))

        # 计算行索引
        row = int((y - self.y_min) / self.y_step)
        row = max(0, min(row, self.height - 1))

        return row, col

    def evaluate(self, individual: Individual) -> float:
        """
        评估个体的方差目标函数值

        Args:
            individual: 个体（包含采样点索引）

        Returns:
            float: 平均方差
        """
        if len(individual.genes) == 0:
            return 0.0

        # 获取采样点的方差值
        variances = []

        for gene_idx in individual.genes:
            # 假设genes存储的是网格展平后的索引
            row = gene_idx // self.width
            col = gene_idx % self.width

            # 确保索引在有效范围内
            row = max(0, min(row, self.height - 1))
            col = max(0, min(col, self.width - 1))

            variance = self.variance_grid[row, col]
            variances.append(variance)

        # 计算平均方差
        avg_variance = np.mean(variances)

        return avg_variance

    def evaluate_points(self, points: List[Tuple[float, float]]) -> float:
        """
        评估一组坐标点的方差

        Args:
            points: 坐标点列表 [(x, y), ...]

        Returns:
            float: 平均方差
        """
        if len(points) == 0:
            return 0.0

        variances = []

        for x, y in points:
            row, col = self._coordinate_to_grid_index(x, y)
            variance = self.variance_grid[row, col]
            variances.append(variance)

        return np.mean(variances)

    def get_variance_at_point(self, x: float, y: float) -> float:
        """
        获取指定坐标点的方差

        Args:
            x: X坐标
            y: Y坐标

        Returns:
            float: 方差值
        """
        row, col = self._coordinate_to_grid_index(x, y)
        return self.variance_grid[row, col]

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取方差网格的统计信息

        Returns:
            Dict: 统计信息
        """
        return {
            'min_variance': float(np.min(self.variance_grid)),
            'max_variance': float(np.max(self.variance_grid)),
            'mean_variance': float(np.mean(self.variance_grid)),
            'std_variance': float(np.std(self.variance_grid)),
            'grid_shape': (self.height, self.width),
            'x_range': (self.x_min, self.x_max),
            'y_range': (self.y_min, self.y_max),
        }
