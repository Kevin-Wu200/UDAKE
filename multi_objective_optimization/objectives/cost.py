"""
成本最小化目标函数
Cost Minimization Objective
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core.population import Individual
from .base import BaseObjective


class CostObjective(BaseObjective):
    """
    成本最小化目标函数
    Minimize the total cost of sampling points
    """

    def __init__(
        self,
        base_location: Tuple[float, float] = (0, 0),
        cost_per_km: float = 100.0,
        cost_per_hour: float = 50.0,
        terrain_difficulty: Optional[np.ndarray] = None,
        x_coords: Optional[np.ndarray] = None,
        y_coords: Optional[np.ndarray] = None,
        weight: float = 1.0
    ):
        """
        初始化成本目标函数

        Args:
            base_location: 基地坐标 (x, y)
            cost_per_km: 每公里成本
            cost_per_hour: 每小时成本
            terrain_difficulty: 地形难度网格 (0-1)
            x_coords: X坐标数组
            y_coords: Y坐标数组
            weight: 权重系数
        """
        super().__init__(name='cost', weight=weight, direction='minimize')

        self.base_location = np.array(base_location)
        self.cost_per_km = cost_per_km
        self.cost_per_hour = cost_per_hour
        self.terrain_difficulty = terrain_difficulty
        self.x_coords = x_coords
        self.y_coords = y_coords

        # 如果提供了地形难度网格，创建坐标映射
        if terrain_difficulty is not None and x_coords is not None and y_coords is not None:
            self._create_coordinate_mapping()

    def _create_coordinate_mapping(self):
        """创建坐标到地形难度的映射"""
        self.height, self.width = self.terrain_difficulty.shape
        self.x_min, self.x_max = self.x_coords.min(), self.x_coords.max()
        self.y_min, self.y_max = self.y_coords.min(), self.y_coords.max()

        self.x_step = (self.x_max - self.x_min) / (self.width - 1) if self.width > 1 else 1
        self.y_step = (self.y_max - self.y_min) / (self.height - 1) if self.height > 1 else 1

    def _get_terrain_difficulty(self, x: float, y: float) -> float:
        """
        获取指定坐标的地形难度

        Args:
            x: X坐标
            y: Y坐标

        Returns:
            float: 地形难度 (0-1)
        """
        if self.terrain_difficulty is None:
            return 0.5  # 默认中等难度

        row = int((y - self.y_min) / self.y_step)
        col = int((x - self.x_min) / self.x_step)

        row = max(0, min(row, self.height - 1))
        col = max(0, min(col, self.width - 1))

        return self.terrain_difficulty[row, col]

    def _calculate_distance_cost(self, point: np.ndarray) -> float:
        """
        计算距离成本

        Args:
            point: 采样点坐标

        Returns:
            float: 距离成本
        """
        distance = np.linalg.norm(point - self.base_location)
        return distance * self.cost_per_km

    def _calculate_time_cost(self, point: np.ndarray) -> float:
        """
        计算时间成本

        Args:
            point: 采样点坐标

        Returns:
            float: 时间成本
        """
        distance = np.linalg.norm(point - self.base_location)
        terrain_difficulty = self._get_terrain_difficulty(point[0], point[1])

        # 假设速度为30km/h，受地形难度影响
        speed = 30 * (1 - 0.5 * terrain_difficulty)  # 地形越难，速度越慢
        time = distance / max(speed, 1)  # 避免除零

        return time * self.cost_per_hour

    def evaluate(self, individual: Individual) -> float:
        """
        评估个体的成本目标函数值

        Args:
            individual: 个体

        Returns:
            float: 总成本
        """
        total_cost = 0.0

        # 假设individual.metadata中存储了采样点坐标
        if 'points' in individual.metadata:
            points = individual.metadata['points']
            if len(points) == 0:
                return 0.0
            for point in points:
                point_array = np.array(point)
                distance_cost = self._calculate_distance_cost(point_array)
                time_cost = self._calculate_time_cost(point_array)
                total_cost += distance_cost + time_cost
        else:
            if len(individual.genes) == 0:
                return 0.0
            # 如果没有坐标信息，使用简化的成本计算
            # 假设genes是网格索引，需要转换为坐标
            if self.x_coords is not None and self.y_coords is not None:
                for gene_idx in individual.genes:
                    # 将基因索引转换为坐标（简化处理）
                    x_idx = gene_idx % len(self.x_coords)
                    y_idx = gene_idx // len(self.x_coords)
                    x = self.x_coords[x_idx] if x_idx < len(self.x_coords) else 0
                    y = self.y_coords[y_idx] if y_idx < len(self.y_coords) else 0

                    point_array = np.array([x, y])
                    distance_cost = self._calculate_distance_cost(point_array)
                    time_cost = self._calculate_time_cost(point_array)
                    total_cost += distance_cost + time_cost
            else:
                # 使用默认成本
                total_cost = len(individual.genes) * 1000

        return total_cost

    def evaluate_points(self, points: List[Tuple[float, float]]) -> float:
        """
        评估一组坐标点的成本

        Args:
            points: 坐标点列表 [(x, y), ...]

        Returns:
            float: 总成本
        """
        if len(points) == 0:
            return 0.0

        total_cost = 0.0

        for x, y in points:
            point_array = np.array([x, y])
            distance_cost = self._calculate_distance_cost(point_array)
            time_cost = self._calculate_time_cost(point_array)
            total_cost += distance_cost + time_cost

        return total_cost

    def get_cost_breakdown(self, point: Tuple[float, float]) -> Dict[str, float]:
        """
        获取单个采样点的成本明细

        Args:
            point: 采样点坐标

        Returns:
            Dict: 成本明细
        """
        point_array = np.array(point)
        distance_cost = self._calculate_distance_cost(point_array)
        time_cost = self._calculate_time_cost(point_array)
        terrain_difficulty = self._get_terrain_difficulty(point[0], point[1])

        return {
            'distance_cost': distance_cost,
            'time_cost': time_cost,
            'total_cost': distance_cost + time_cost,
            'terrain_difficulty': terrain_difficulty,
        }
