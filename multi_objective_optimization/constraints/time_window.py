"""
时间窗约束条件
Time Window Constraint
"""

from typing import List, Optional, Tuple

import numpy as np

from ..core.population import Individual
from .base import BaseConstraint


class TimeWindowConstraint(BaseConstraint):
    """
    时间窗约束条件
    限制每个采样点的采集时间必须在指定的时间窗内，且总时间不超过最大总时间
    Constraint that each sampling point must be visited within its time window,
    and total travel+sampling time must not exceed max_total_time.
    """

    def __init__(
        self,
        time_windows: Optional[List[Tuple[float, float]]] = None,
        max_total_time: float = 480.0,
        time_per_sample: float = 15.0,
        travel_speed: float = 30.0,
        base_location: Optional[Tuple[float, float]] = None,
        x_coords: Optional[np.ndarray] = None,
        y_coords: Optional[np.ndarray] = None,
        start_time: float = 0.0,
    ):
        """
        初始化时间窗约束

        Args:
            time_windows: 各采样点的时间窗列表 [(start, end), ...]，单位为分钟
            max_total_time: 最大总时间（分钟），默认8小时=480分钟
            time_per_sample: 每个采样点的采集时间（分钟）
            travel_speed: 移动速度（km/h）
            base_location: 基地坐标 (x, y)
            x_coords: X坐标数组（用于坐标映射）
            y_coords: Y坐标数组（用于坐标映射）
            start_time: 起始时间（分钟），默认0
        """
        super().__init__(name='time_window')

        self.time_windows = time_windows or []
        self.max_total_time = max_total_time
        self.time_per_sample = time_per_sample
        self.travel_speed = travel_speed
        self.base_location = np.array(base_location) if base_location is not None else np.array([0.0, 0.0])
        self.start_time = start_time
        self.x_coords = x_coords
        self.y_coords = y_coords

        if x_coords is not None and y_coords is not None:
            self._create_coordinate_mapping()

    def _create_coordinate_mapping(self):
        """创建坐标到网格索引的映射"""
        self.x_min, self.x_max = self.x_coords.min(), self.x_coords.max()
        self.y_min, self.y_max = self.y_coords.min(), self.y_coords.max()

    def _index_to_coordinate(self, index: int, width: int) -> Tuple[float, float]:
        """将网格索引转换为坐标"""
        if self.x_coords is None or self.y_coords is None:
            return (0.0, 0.0)

        row = index // width
        col = index % width

        x = self.x_coords[col] if col < len(self.x_coords) else 0
        y = self.y_coords[row] if row < len(self.y_coords) else 0

        return (x, y)

    def _calculate_travel_time(self, point_a: np.ndarray, point_b: np.ndarray) -> float:
        """计算两点之间的旅行时间（分钟）"""
        distance = np.linalg.norm(point_a - point_b)
        # 距离单位假设为km，速度km/h，转换为分钟
        travel_time_minutes = (distance / self.travel_speed) * 60.0
        return travel_time_minutes

    def evaluate(self, individual: Individual) -> float:
        """
        评估个体违反时间窗约束的程度

        违反包括：
        1. 采样点到达时间超出其时间窗
        2. 总时间超出最大总时间

        Returns:
            float: 违反程度（0表示满足，>0表示违反的分钟数）
        """
        if len(individual.genes) == 0:
            return 0.0

        # 获取采样点坐标
        points = self._get_points(individual)

        # 模拟采样路径，计算各点到达时间
        violation_minutes = 0.0
        current_time = self.start_time
        current_location = self.base_location.copy()

        for i, point in enumerate(points):
            point_array = np.array(point)

            # 到达该点的旅行时间
            travel_time = self._calculate_travel_time(current_location, point_array)
            arrival_time = current_time + travel_time

            # 检查时间窗约束
            if self.time_windows and i < len(self.time_windows):
                tw_start, tw_end = self.time_windows[i]
                if arrival_time < tw_start:
                    # 需要等待，等待时间也算入违反
                    waiting_time = tw_start - arrival_time
                    violation_minutes += waiting_time
                    current_time = tw_start
                elif arrival_time > tw_end:
                    # 超出时间窗
                    violation_minutes += arrival_time - tw_end
                    current_time = arrival_time
                else:
                    current_time = arrival_time
            else:
                current_time = arrival_time

            # 加上采样时间
            current_time += self.time_per_sample
            current_location = point_array

        # 检查总时间约束
        total_time = current_time - self.start_time
        if total_time > self.max_total_time:
            violation_minutes += total_time - self.max_total_time

        return violation_minutes

    def _get_points(self, individual: Individual) -> List[Tuple[float, float]]:
        """获取个体对应的采样点坐标列表"""
        if 'points' in individual.metadata:
            return individual.metadata['points']

        points = []
        if self.x_coords is not None and self.y_coords is not None:
            width = len(self.x_coords)
            for gene_idx in individual.genes:
                x, y = self._index_to_coordinate(gene_idx, width)
                points.append((x, y))
        else:
            # 无坐标信息时，按基因索引生成默认坐标
            for gene_idx in individual.genes:
                points.append((float(gene_idx), 0.0))

        return points

    def get_total_time(self, individual: Individual) -> float:
        """
        获取个体的总时间

        Args:
            individual: 个体

        Returns:
            float: 总时间（分钟）
        """
        if 'total_time' in individual.metadata:
            return individual.metadata['total_time']

        points = self._get_points(individual)
        current_time = self.start_time
        current_location = self.base_location.copy()

        for point in points:
            point_array = np.array(point)
            travel_time = self._calculate_travel_time(current_location, point_array)
            current_time += travel_time + self.time_per_sample
            current_location = point_array

        total_time = current_time - self.start_time
        individual.metadata['total_time'] = total_time
        return total_time

    def get_time_window_violations(self, individual: Individual) -> List[dict]:
        """
        获取各采样点的时间窗违反详情

        Returns:
            List[dict]: 每个采样点的违反详情
        """
        violations = []
        points = self._get_points(individual)
        current_time = self.start_time
        current_location = self.base_location.copy()

        for i, point in enumerate(points):
            point_array = np.array(point)
            travel_time = self._calculate_travel_time(current_location, point_array)
            arrival_time = current_time + travel_time
            current_time = arrival_time + self.time_per_sample
            current_location = point_array

            violation = {
                "point_index": i,
                "point": point,
                "arrival_time": arrival_time,
                "in_window": True,
                "violation_minutes": 0.0,
            }

            if self.time_windows and i < len(self.time_windows):
                tw_start, tw_end = self.time_windows[i]
                if arrival_time < tw_start:
                    violation["in_window"] = False
                    violation["violation_minutes"] = tw_start - arrival_time
                    violation["detail"] = f"提前 {tw_start - arrival_time:.1f} 分钟到达，需等待"
                elif arrival_time > tw_end:
                    violation["in_window"] = False
                    violation["violation_minutes"] = arrival_time - tw_end
                    violation["detail"] = f"延迟 {arrival_time - tw_end:.1f} 分钟到达"

            violations.append(violation)

        return violations
