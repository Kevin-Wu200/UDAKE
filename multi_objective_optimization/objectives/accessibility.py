"""
可达性最大化目标函数
Accessibility Maximization Objective
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
from .base import BaseObjective
from ..core.population import Individual


class AccessibilityObjective(BaseObjective):
    """
    可达性最大化目标函数
    Maximize the accessibility of sampling points
    """

    def __init__(
        self,
        roads: Optional[List[Tuple[float, float]]] = None,
        road_network: Optional[np.ndarray] = None,
        x_coords: Optional[np.ndarray] = None,
        y_coords: Optional[np.ndarray] = None,
        base_location: Optional[Tuple[float, float]] = None,
        weight: float = 1.0
    ):
        """
        初始化可达性目标函数

        Args:
            roads: 道路点列表 [(x, y), ...]
            road_network: 道路网络网格 (0-1，1表示有道路)
            x_coords: X坐标数组
            y_coords: Y坐标数组
            base_location: 基地坐标
            weight: 权重系数
        """
        super().__init__(name='accessibility', weight=weight, direction='maximize')

        self.roads = np.array(roads) if roads is not None else None
        self.road_network = road_network
        self.x_coords = x_coords
        self.y_coords = y_coords
        self.base_location = np.array(base_location) if base_location is not None else None

        # 如果提供了道路网络网格，创建坐标映射
        if road_network is not None and x_coords is not None and y_coords is not None:
            self._create_coordinate_mapping()

    def _create_coordinate_mapping(self):
        """创建坐标到道路网络的映射"""
        self.height, self.width = self.road_network.shape
        self.x_min, self.x_max = self.x_coords.min(), self.x_coords.max()
        self.y_min, self.y_max = self.y_coords.min(), self.y_coords.max()

        self.x_step = (self.x_max - self.x_min) / (self.width - 1) if self.width > 1 else 1
        self.y_step = (self.y_max - self.y_min) / (self.height - 1) if self.height > 1 else 1

    def _distance_to_nearest_road(self, point: np.ndarray) -> float:
        """
        计算点到最近道路的距离

        Args:
            point: 采样点坐标

        Returns:
            float: 到最近道路的距离
        """
        if self.roads is None:
            # 如果没有道路信息，返回默认距离
            return 1000.0

        distances = np.linalg.norm(self.roads - point, axis=1)
        return np.min(distances)

    def _distance_to_base(self, point: np.ndarray) -> float:
        """
        计算点到基地的距离

        Args:
            point: 采样点坐标

        Returns:
            float: 到基地的距离
        """
        if self.base_location is None:
            return 1000.0

        return np.linalg.norm(point - self.base_location)

    def _is_near_road(self, point: np.ndarray, threshold: float = 100.0) -> bool:
        """
        判断点是否靠近道路

        Args:
            point: 采样点坐标
            threshold: 距离阈值

        Returns:
            bool: 是否靠近道路
        """
        distance = self._distance_to_nearest_road(point)
        return distance <= threshold

    def evaluate(self, individual: Individual) -> float:
        """
        评估个体的可达性目标函数值

        Args:
            individual: 个体

        Returns:
            float: 可达性得分（负值，因为我们要最大化）
        """
        if len(individual.genes) == 0:
            return 0.0

        total_accessibility = 0.0

        # 假设individual.metadata中存储了采样点坐标
        if 'points' in individual.metadata:
            points = individual.metadata['points']
            for point in points:
                point_array = np.array(point)
                accessibility = self._evaluate_point(point_array)
                total_accessibility += accessibility
        else:
            # 如果没有坐标信息，使用简化的可达性计算
            if self.x_coords is not None and self.y_coords is not None:
                for gene_idx in individual.genes:
                    # 将基因索引转换为坐标（简化处理）
                    x_idx = gene_idx % len(self.x_coords)
                    y_idx = gene_idx // len(self.x_coords)
                    x = self.x_coords[x_idx] if x_idx < len(self.x_coords) else 0
                    y = self.y_coords[y_idx] if y_idx < len(self.y_coords) else 0

                    point_array = np.array([x, y])
                    accessibility = self._evaluate_point(point_array)
                    total_accessibility += accessibility
            else:
                # 使用默认可达性
                total_accessibility = len(individual.genes) * 0.5

        # 返回平均可达性（负值，因为是最大化）
        avg_accessibility = total_accessibility / len(individual.genes)
        return -avg_accessibility  # 负值表示我们要最大化

    def _evaluate_point(self, point: np.ndarray) -> float:
        """
        评估单个点的可达性

        Args:
            point: 采样点坐标

        Returns:
            float: 可达性得分 (0-1)
        """
        # 计算到道路的距离（归一化到0-1）
        road_distance = self._distance_to_nearest_road(point)
        road_score = 1.0 / (1.0 + road_distance / 100.0)  # 100米为单位

        # 计算到基地的距离（归一化到0-1）
        if self.base_location is not None:
            base_distance = self._distance_to_base(point)
            base_score = 1.0 / (1.0 + base_distance / 500.0)  # 500米为单位
        else:
            base_score = 0.5

        # 综合得分
        accessibility = 0.6 * road_score + 0.4 * base_score

        return accessibility

    def evaluate_points(self, points: List[Tuple[float, float]]) -> float:
        """
        评估一组坐标点的可达性

        Args:
            points: 坐标点列表 [(x, y), ...]

        Returns:
            float: 平均可达性（负值）
        """
        if len(points) == 0:
            return 0.0

        total_accessibility = 0.0

        for x, y in points:
            point_array = np.array([x, y])
            accessibility = self._evaluate_point(point_array)
            total_accessibility += accessibility

        avg_accessibility = total_accessibility / len(points)
        return -avg_accessibility  # 负值表示我们要最大化

    def get_accessibility_score(self, point: Tuple[float, float]) -> Dict[str, float]:
        """
        获取单个采样点的可达性得分明细

        Args:
            point: 采样点坐标

        Returns:
            Dict: 可达性得分明细
        """
        point_array = np.array(point)

        road_distance = self._distance_to_nearest_road(point_array)
        road_score = 1.0 / (1.0 + road_distance / 100.0)

        if self.base_location is not None:
            base_distance = self._distance_to_base(point_array)
            base_score = 1.0 / (1.0 + base_distance / 500.0)
        else:
            base_distance = 0.0
            base_score = 0.5

        accessibility = 0.6 * road_score + 0.4 * base_score

        return {
            'road_distance': road_distance,
            'road_score': road_score,
            'base_distance': base_distance,
            'base_score': base_score,
            'accessibility': accessibility,
            'is_near_road': self._is_near_road(point_array),
        }