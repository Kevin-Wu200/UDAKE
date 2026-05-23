"""
预算约束条件
Budget Constraint
"""

from typing import List, Optional, Tuple

import numpy as np

from ..core.population import Individual
from .base import BaseConstraint


class BudgetConstraint(BaseConstraint):
    """
    预算约束条件
    Constraint that total sampling cost must not exceed the budget
    """

    def __init__(
        self,
        budget: float,
        base_location: Optional[Tuple[float, float]] = None,
        cost_per_km: float = 100.0,
        cost_per_hour: float = 50.0,
        x_coords: Optional[np.ndarray] = None,
        y_coords: Optional[np.ndarray] = None
    ):
        """
        初始化预算约束

        Args:
            budget: 预算上限
            base_location: 基地坐标
            cost_per_km: 每公里成本
            cost_per_hour: 每小时成本
            x_coords: X坐标数组（用于坐标映射）
            y_coords: Y坐标数组（用于坐标映射）
        """
        super().__init__(name='budget')

        self.budget = budget
        self.base_location = np.array(base_location) if base_location is not None else np.array([0, 0])
        self.cost_per_km = cost_per_km
        self.cost_per_hour = cost_per_hour
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

    def _calculate_point_cost(self, point: np.ndarray) -> float:
        """
        计算单个采样点的成本

        Args:
            point: 采样点坐标

        Returns:
            float: 成本
        """
        # 计算距离成本
        distance = np.linalg.norm(point - self.base_location)
        distance_cost = distance * self.cost_per_km

        # 计算时间成本（假设速度为30km/h）
        time = distance / 30.0
        time_cost = time * self.cost_per_hour

        return distance_cost + time_cost

    def evaluate(self, individual: Individual) -> float:
        """
        评估个体违反预算约束的程度

        Args:
            individual: 个体

        Returns:
            float: 违反程度（0表示满足，>0表示超出预算的金额）
        """
        if len(individual.genes) == 0:
            return 0.0

        total_cost = 0.0

        # 获取采样点坐标
        points = []

        if 'points' in individual.metadata:
            points = individual.metadata['points']
        elif 'total_cost' in individual.metadata:
            # 如果已经计算了总成本，直接使用
            total_cost = individual.metadata['total_cost']
            return max(0, total_cost - self.budget)
        else:
            if self.x_coords is not None and self.y_coords is not None:
                width = len(self.x_coords)
                for gene_idx in individual.genes:
                    x, y = self._index_to_coordinate(gene_idx, width)
                    points.append((x, y))
            else:
                # 如果没有坐标信息，使用默认成本
                total_cost = len(individual.genes) * 1000
                return max(0, total_cost - self.budget)

        # 计算总成本
        for point in points:
            point_array = np.array(point)
            total_cost += self._calculate_point_cost(point_array)

        # 保存总成本到metadata
        individual.metadata['total_cost'] = total_cost

        # 返回超出预算的金额
        return max(0, total_cost - self.budget)

    def get_total_cost(self, individual: Individual) -> float:
        """
        获取个体的总成本

        Args:
            individual: 个体

        Returns:
            float: 总成本
        """
        if 'total_cost' in individual.metadata:
            return individual.metadata['total_cost']

        # 计算总成本
        total_cost = 0.0

        if 'points' in individual.metadata:
            points = individual.metadata['points']
            for point in points:
                point_array = np.array(point)
                total_cost += self._calculate_point_cost(point_array)
        else:
            if self.x_coords is not None and self.y_coords is not None:
                width = len(self.x_coords)
                for gene_idx in individual.genes:
                    x, y = self._index_to_coordinate(gene_idx, width)
                    point_array = np.array([x, y])
                    total_cost += self._calculate_point_cost(point_array)
            else:
                total_cost = len(individual.genes) * 1000

        individual.metadata['total_cost'] = total_cost
        return total_cost

    def get_budget_utilization(self, individual: Individual) -> float:
        """
        获取预算利用率

        Args:
            individual: 个体

        Returns:
            float: 预算利用率（0-1）
        """
        total_cost = self.get_total_cost(individual)
        utilization = total_cost / self.budget
        return min(1.0, utilization)

    def get_remaining_budget(self, individual: Individual) -> float:
        """
        获取剩余预算

        Args:
            individual: 个体

        Returns:
            float: 剩余预算
        """
        total_cost = self.get_total_cost(individual)
        remaining = self.budget - total_cost
        return max(0, remaining)

    def get_max_samples_within_budget(
        self,
        points: List[Tuple[float, float]]
    ) -> int:
        """
        计算在预算内最多可以采样多少个点

        Args:
            points: 候选采样点列表

        Returns:
            int: 最大采样点数量
        """
        # 计算每个点的成本
        point_costs = []
        for point in points:
            point_array = np.array(point)
            cost = self._calculate_point_cost(point_array)
            point_costs.append(cost)

        # 按成本排序（从低到高）
        sorted_costs = sorted(point_costs)

        # 选择尽可能多的点
        total_cost = 0.0
        n_samples = 0

        for cost in sorted_costs:
            if total_cost + cost <= self.budget:
                total_cost += cost
                n_samples += 1
            else:
                break

        return n_samples
