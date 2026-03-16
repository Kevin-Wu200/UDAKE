"""
边界约束条件
Boundary Constraint
"""

import numpy as np
from typing import List, Tuple, Union
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.prepared import prep
from .base import BaseConstraint
from ..core.population import Individual


class BoundaryConstraint(BaseConstraint):
    """
    边界约束条件
    Constraint that all sampling points must be within the specified boundary
    """

    def __init__(
        self,
        boundary: Union[Polygon, MultiPolygon, List[Tuple[float, float]]],
        x_coords: np.ndarray = None,
        y_coords: np.ndarray = None
    ):
        """
        初始化边界约束

        Args:
            boundary: 边界多边形或坐标点列表
            x_coords: X坐标数组（用于坐标映射）
            y_coords: Y坐标数组（用于坐标映射）
        """
        super().__init__(name='boundary')

        # 转换为Shapely多边形
        if isinstance(boundary, (Polygon, MultiPolygon)):
            self.boundary = boundary
        elif isinstance(boundary, list):
            self.boundary = Polygon(boundary)
        else:
            raise ValueError("boundary必须是Polygon、MultiPolygon或坐标点列表")

        # 准备几何对象（加速查询）
        self.prepared_boundary = prep(self.boundary)

        # 存储坐标映射信息
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
            # 如果没有坐标信息，返回默认坐标
            return (0.0, 0.0)

        # 假设index是展平后的网格索引
        row = index // width
        col = index % width

        x = self.x_coords[col] if col < len(self.x_coords) else 0
        y = self.y_coords[row] if row < len(self.y_coords) else 0

        return (x, y)

    def evaluate(self, individual: Individual) -> float:
        """
        评估个体违反边界约束的程度

        Args:
            individual: 个体

        Returns:
            float: 违反程度（0表示满足，>0表示违反）
        """
        if len(individual.genes) == 0:
            return 0.0

        violation_count = 0

        # 检查每个采样点是否在边界内
        if 'points' in individual.metadata:
            # 使用存储的坐标
            points = individual.metadata['points']
            for point in points:
                point_geom = Point(point[0], point[1])
                if not self.prepared_boundary.contains(point_geom):
                    violation_count += 1
        else:
            # 使用基因索引转换为坐标
            if self.x_coords is not None and self.y_coords is not None:
                width = len(self.x_coords)
                for gene_idx in individual.genes:
                    x, y = self._index_to_coordinate(gene_idx, width)
                    point_geom = Point(x, y)
                    if not self.prepared_boundary.contains(point_geom):
                        violation_count += 1
            else:
                # 如果没有坐标信息，假设都满足
                violation_count = 0

        return violation_count

    def filter_points_in_boundary(
        self,
        points: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """
        过滤出在边界内的点

        Args:
            points: 坐标点列表

        Returns:
            List[Tuple[float, float]]: 在边界内的点
        """
        filtered_points = []

        for point in points:
            point_geom = Point(point[0], point[1])
            if self.prepared_boundary.contains(point_geom):
                filtered_points.append(point)

        return filtered_points

    def is_point_in_boundary(self, point: Tuple[float, float]) -> bool:
        """
        判断点是否在边界内

        Args:
            point: 坐标点

        Returns:
            bool: 在边界内返回True
        """
        point_geom = Point(point[0], point[1])
        return self.prepared_boundary.contains(point_geom)

    def get_boundary_area(self) -> float:
        """
        获取边界区域的面积

        Returns:
            float: 面积
        """
        return self.boundary.area

    def get_boundary_bounds(self) -> Tuple[float, float, float, float]:
        """
        获取边界的包围盒

        Returns:
            Tuple[float, float, float, float]: (min_x, min_y, max_x, max_y)
        """
        return self.boundary.bounds