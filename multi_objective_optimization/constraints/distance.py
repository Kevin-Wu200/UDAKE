"""
距离约束条件
Distance Constraint
"""

from typing import List, Tuple

import numpy as np

from ..core.population import Individual
from .base import BaseConstraint


class DistanceConstraint(BaseConstraint):
    """
    距离约束条件
    Constraint that sampling points must maintain a minimum distance from each other
    """

    def __init__(
        self,
        min_distance: float = 50.0,
        x_coords: np.ndarray = None,
        y_coords: np.ndarray = None
    ):
        """
        初始化距离约束

        Args:
            min_distance: 最小距离（米）
            x_coords: X坐标数组（用于坐标映射）
            y_coords: Y坐标数组（用于坐标映射）
        """
        super().__init__(name='distance')

        self.min_distance = min_distance
        self.x_coords = x_coords
        self.y_coords = y_coords

        if x_coords is not None and y_coords is not None:
            self._create_coordinate_mapping()

    def _create_coordinate_mapping(self):
        """创建坐标到网格索引的映射"""
        self.x_min, self.x_max = self.x_coords.min(), self.x_coords.max()
        self.y_min, self.y_max = self.y_coords.min(), self.y_coords.max()

    def _index_to_coordinate(self, index: int, width: int) -> Tuple[float, float]:
        """
        将网格索引转换为坐标

        Args:
            index: 网格索引
            width: 网格宽度

        Returns:
            Tuple[float, float]: (x, y) 坐标
        """
        if self.x_coords is None or self.y_coords is None:
            return (0.0, 0.0)

        # 假设index是展平后的网格索引
        row = index // width
        col = index % width

        x = self.x_coords[col] if col < len(self.x_coords) else 0
        y = self.y_coords[row] if row < len(self.y_coords) else 0

        return (x, y)

    def evaluate(self, individual: Individual) -> float:
        """
        评估个体违反距离约束的程度

        Args:
            individual: 个体

        Returns:
            float: 违反程度（0表示满足，>0表示违反）
        """
        if len(individual.genes) < 2:
            return 0.0

        violation_count = 0
        total_violation = 0.0

        # 获取采样点坐标
        points = []

        if 'points' in individual.metadata:
            points = individual.metadata['points']
        else:
            if self.x_coords is not None and self.y_coords is not None:
                width = len(self.x_coords)
                for gene_idx in individual.genes:
                    x, y = self._index_to_coordinate(gene_idx, width)
                    points.append((x, y))
            else:
                # 如果没有坐标信息，假设都满足
                return 0.0

        # 计算所有点对之间的距离
        n_points = len(points)

        for i in range(n_points):
            for j in range(i + 1, n_points):
                point1 = np.array(points[i])
                point2 = np.array(points[j])

                distance = np.linalg.norm(point1 - point2)

                if distance < self.min_distance:
                    violation_count += 1
                    total_violation += (self.min_distance - distance)

        # 返回总违反程度
        return total_violation

    def count_violations(self, individual: Individual) -> int:
        """
        计算违反约束的点对数量

        Args:
            individual: 个体

        Returns:
            int: 违反约束的点对数量
        """
        if len(individual.genes) < 2:
            return 0

        violation_count = 0

        # 获取采样点坐标
        points = []

        if 'points' in individual.metadata:
            points = individual.metadata['points']
        else:
            if self.x_coords is not None and self.y_coords is not None:
                width = len(self.x_coords)
                for gene_idx in individual.genes:
                    x, y = self._index_to_coordinate(gene_idx, width)
                    points.append((x, y))
            else:
                return 0

        # 计算所有点对之间的距离
        n_points = len(points)

        for i in range(n_points):
            for j in range(i + 1, n_points):
                point1 = np.array(points[i])
                point2 = np.array(points[j])

                distance = np.linalg.norm(point1 - point2)

                if distance < self.min_distance:
                    violation_count += 1

        return violation_count

    def get_distance_matrix(self, points: List[Tuple[float, float]]) -> np.ndarray:
        """
        计算点之间的距离矩阵

        Args:
            points: 坐标点列表

        Returns:
            np.ndarray: 距离矩阵
        """
        n = len(points)
        distance_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(n):
                if i != j:
                    point1 = np.array(points[i])
                    point2 = np.array(points[j])
                    distance_matrix[i, j] = np.linalg.norm(point1 - point2)

        return distance_matrix

    def get_minimum_distance(self, individual: Individual) -> float:
        """
        获取个体中采样点之间的最小距离

        Args:
            individual: 个体

        Returns:
            float: 最小距离
        """
        if len(individual.genes) < 2:
            return float('inf')

        # 获取采样点坐标
        points = []

        if 'points' in individual.metadata:
            points = individual.metadata['points']
        else:
            if self.x_coords is not None and self.y_coords is not None:
                width = len(self.x_coords)
                for gene_idx in individual.genes:
                    x, y = self._index_to_coordinate(gene_idx, width)
                    points.append((x, y))
            else:
                return float('inf')

        # 计算所有点对之间的距离
        n_points = len(points)
        min_distance = float('inf')

        for i in range(n_points):
            for j in range(i + 1, n_points):
                point1 = np.array(points[i])
                point2 = np.array(points[j])

                distance = np.linalg.norm(point1 - point2)
                min_distance = min(min_distance, distance)

        return min_distance

    def enforce_constraint(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        强制执行距离约束，移除过近的点

        Args:
            points: 原始坐标点列表

        Returns:
            List[Tuple[float, float]]: 满足约束的点列表
        """
        if len(points) < 2:
            return points

        filtered_points = [points[0]]

        for point in points[1:]:
            is_valid = True
            point_array = np.array(point)

            for existing_point in filtered_points:
                existing_array = np.array(existing_point)
                distance = np.linalg.norm(point_array - existing_array)

                if distance < self.min_distance:
                    is_valid = False
                    break

            if is_valid:
                filtered_points.append(point)

        return filtered_points
