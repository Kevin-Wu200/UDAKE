"""
四叉树空间索引
QuadTree Spatial Index

实现高效的2D空间索引，用于快速查询和更新
"""

import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
import logging

from ..models import DataPoint, BoundingBox

logger = logging.getLogger(__name__)


class QuadTreeNode:
    """四叉树节点"""

    MAX_CAPACITY = 10  # 每个节点最大数据点数
    MAX_DEPTH = 20     # 最大深度

    def __init__(self, boundary: BoundingBox, depth: int = 0):
        """
        初始化四叉树节点

        Args:
            boundary: 节点边界
            depth: 节点深度
        """
        self.boundary = boundary
        self.depth = depth
        self.points: List[DataPoint] = []
        self.children: Optional[List['QuadTreeNode']] = None
        self.is_divided = False

    def insert(self, point: DataPoint) -> bool:
        """
        插入数据点

        Args:
            point: 数据点

        Returns:
            是否插入成功
        """
        # 检查点是否在边界内
        if not self.boundary.contains(point.x, point.y):
            return False

        # 如果未达到最大容量或最大深度，直接插入
        if len(self.points) < self.MAX_CAPACITY or self.depth >= self.MAX_DEPTH:
            self.points.append(point)
            return True

        # 如果已达到容量，分割节点
        if not self.is_divided:
            self._subdivide()

        # 尝试插入到子节点
        for child in self.children:
            if child.insert(point):
                return True

        # 如果所有子节点都无法插入，添加到当前节点
        self.points.append(point)
        return True

    def _subdivide(self) -> None:
        """分割节点为四个子节点"""
        if self.is_divided:
            return

        mid_x = (self.boundary.min_x + self.boundary.max_x) / 2
        mid_y = (self.boundary.min_y + self.boundary.max_y) / 2

        # 创建四个子节点
        self.children = [
            QuadTreeNode(BoundingBox(
                self.boundary.min_x, mid_x,
                self.boundary.min_y, mid_y
            ), self.depth + 1),  # 西北
            QuadTreeNode(BoundingBox(
                mid_x, self.boundary.max_x,
                self.boundary.min_y, mid_y
            ), self.depth + 1),  # 东北
            QuadTreeNode(BoundingBox(
                self.boundary.min_x, mid_x,
                mid_y, self.boundary.max_y
            ), self.depth + 1),  # 西南
            QuadTreeNode(BoundingBox(
                mid_x, self.boundary.max_x,
                mid_y, self.boundary.max_y
            ), self.depth + 1),  # 东南
        ]

        self.is_divided = True

        # 重新分配已有数据点到子节点
        for point in self.points:
            for child in self.children:
                if child.insert(point):
                    break

        self.points.clear()

    def query_radius(self, center: Tuple[float, float], radius: float) -> List[DataPoint]:
        """
        查询半径内的数据点

        Args:
            center: 中心点 (x, y)
            radius: 半径

        Returns:
            半径内的数据点列表
        """
        x, y = center

        # 检查边界是否与圆相交
        if not self._circle_intersects_boundary(x, y, radius):
            return []

        result = []

        # 添加当前节点在半径内的点
        for point in self.points:
            distance = np.sqrt((point.x - x)**2 + (point.y - y)**2)
            if distance <= radius:
                result.append(point)

        # 递归查询子节点
        if self.is_divided:
            for child in self.children:
                result.extend(child.query_radius(center, radius))

        return result

    def _circle_intersects_boundary(self, x: float, y: float, radius: float) -> bool:
        """检查圆是否与边界框相交"""
        # 找到边界框上距离圆心最近的点
        closest_x = max(self.boundary.min_x, min(x, self.boundary.max_x))
        closest_y = max(self.boundary.min_y, min(y, self.boundary.max_y))

        # 计算距离
        distance = np.sqrt((closest_x - x)**2 + (closest_y - y)**2)

        return distance <= radius

    def query_range(self, range_box: BoundingBox) -> List[DataPoint]:
        """
        查询范围内的数据点

        Args:
            range_box: 查询范围

        Returns:
            范围内的数据点列表
        """
        # 检查范围是否与边界相交
        if not self.boundary.intersects(range_box):
            return []

        result = []

        # 添加当前节点在范围内的点
        for point in self.points:
            if range_box.contains(point.x, point.y):
                result.append(point)

        # 递归查询子节点
        if self.is_divided:
            for child in self.children:
                result.extend(child.query_range(range_box))

        return result

    def remove(self, point_id: str) -> bool:
        """
        删除数据点

        Args:
            point_id: 数据点ID

        Returns:
            是否删除成功
        """
        # 检查当前节点
        for i, point in enumerate(self.points):
            if point.id == point_id:
                self.points.pop(i)
                return True

        # 递归检查子节点
        if self.is_divided:
            for child in self.children:
                if child.remove(point_id):
                    # 检查是否可以合并子节点
                    self._try_merge()
                    return True

        return False

    def _try_merge(self) -> None:
        """尝试合并子节点"""
        if not self.is_divided:
            return

        # 检查是否所有子节点都是叶子节点且总点数小于容量
        total_points = 0
        all_leaves = True

        for child in self.children:
            if child.is_divided:
                all_leaves = False
                break
            total_points += len(child.points)

        if all_leaves and total_points <= self.MAX_CAPACITY:
            # 合并子节点
            self.points = []
            for child in self.children:
                self.points.extend(child.points)

            self.children = None
            self.is_divided = False

    def get_all_points(self) -> List[DataPoint]:
        """获取所有数据点"""
        result = list(self.points)

        if self.is_divided:
            for child in self.children:
                result.extend(child.get_all_points())

        return result

    def count_points(self) -> int:
        """统计数据点数量"""
        count = len(self.points)

        if self.is_divided:
            for child in self.children:
                count += child.count_points()

        return count


class QuadTree:
    """四叉树索引"""

    def __init__(self, boundary: BoundingBox):
        """
        初始化四叉树

        Args:
            boundary: 根节点边界
        """
        self.root = QuadTreeNode(boundary)

    def insert(self, point: DataPoint) -> bool:
        """插入数据点"""
        return self.root.insert(point)

    def query_radius(self, center: Tuple[float, float], radius: float) -> List[DataPoint]:
        """查询半径内的数据点"""
        return self.root.query_radius(center, radius)

    def query_range(self, range_box: BoundingBox) -> List[DataPoint]:
        """查询范围内的数据点"""
        return self.root.query_range(range_box)

    def remove(self, point_id: str) -> bool:
        """删除数据点"""
        return self.root.remove(point_id)

    def get_all_points(self) -> List[DataPoint]:
        """获取所有数据点"""
        return self.root.get_all_points()

    def count_points(self) -> int:
        """统计数据点数量"""
        return self.root.count_points()

    def clear(self) -> None:
        """清空四叉树"""
        self.root.points.clear()
        self.root.children = None
        self.root.is_divided = False


def test_quadtree():
    """测试四叉树"""
    print("测试四叉树...")

    # 创建边界
    boundary = BoundingBox(0, 100, 0, 100)

    # 创建四叉树
    qt = QuadTree(boundary)

    # 插入数据点
    for i in range(100):
        point = DataPoint(
            x=np.random.uniform(0, 100),
            y=np.random.uniform(0, 100),
            value=np.random.randn(),
            id=f"point_{i}"
        )
        qt.insert(point)

    print(f"插入了 {qt.count_points()} 个数据点")

    # 查询半径
    center = (50, 50)
    radius = 20
    results = qt.query_radius(center, radius)
    print(f"半径 {radius} 内找到 {len(results)} 个点")

    # 查询范围
    range_box = BoundingBox(30, 70, 30, 70)
    results = qt.query_range(range_box)
    print(f"范围内找到 {len(results)} 个点")

    # 删除点
    if results:
        qt.remove(results[0].id)
        print(f"删除了一个点，剩余 {qt.count_points()} 个点")

    print("四叉树测试通过！")


if __name__ == "__main__":
    test_quadtree()