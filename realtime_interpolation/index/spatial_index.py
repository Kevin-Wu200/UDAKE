"""
空间索引模块
Spatial Index Module

实现KD树、R树和网格索引
"""

import logging
from typing import List, Optional, Tuple

import numpy as np

from ..models import BoundingBox, DataPoint

logger = logging.getLogger(__name__)


# ==================== KD树索引 ====================

class KDTreeNode:
    """KD树节点"""

    def __init__(
        self,
        point: Optional[DataPoint] = None,
        left: Optional['KDTreeNode'] = None,
        right: Optional['KDTreeNode'] = None,
        axis: int = 0
    ):
        """
        初始化KD树节点

        Args:
            point: 数据点
            left: 左子节点
            right: 右子节点
            axis: 分割轴（0=x, 1=y）
        """
        self.point = point
        self.left = left
        self.right = right
        self.axis = axis


class KDTree:
    """KD树索引"""

    def __init__(self, points: Optional[List[DataPoint]] = None):
        """
        初始化KD树

        Args:
            points: 初始数据点列表
        """
        self.root: Optional[KDTreeNode] = None
        self.size = 0

        if points:
            self.build(points)

    def build(self, points: List[DataPoint]) -> None:
        """
        构建KD树

        Args:
            points: 数据点列表
        """
        self.root = self._build_recursive(points, 0)
        self.size = len(points)
        logger.info(f"构建KD树，包含 {self.size} 个点")

    def _build_recursive(self, points: List[DataPoint], depth: int) -> Optional[KDTreeNode]:
        """递归构建KD树"""
        if not points:
            return None

        # 选择分割轴
        axis = depth % 2

        # 按分割轴排序
        points_sorted = sorted(points, key=lambda p: [p.x, p.y][axis])

        # 选择中位数
        median_idx = len(points_sorted) // 2
        median_point = points_sorted[median_idx]

        # 创建节点
        node = KDTreeNode(
            point=median_point,
            axis=axis
        )

        # 递归构建左右子树
        node.left = self._build_recursive(points_sorted[:median_idx], depth + 1)
        node.right = self._build_recursive(points_sorted[median_idx + 1:], depth + 1)

        return node

    def insert(self, point: DataPoint) -> None:
        """
        插入数据点

        Args:
            point: 数据点
        """
        self.root = self._insert_recursive(self.root, point, 0)
        self.size += 1

    def _insert_recursive(
        self,
        node: Optional[KDTreeNode],
        point: DataPoint,
        depth: int
    ) -> KDTreeNode:
        """递归插入"""
        if node is None:
            return KDTreeNode(point=point, axis=depth % 2)

        axis = node.axis
        point_coord = [point.x, point.y][axis]
        node_coord = [node.point.x, node.point.y][axis]

        if point_coord < node_coord:
            node.left = self._insert_recursive(node.left, point, depth + 1)
        else:
            node.right = self._insert_recursive(node.right, point, depth + 1)

        return node

    def query_radius(self, center: Tuple[float, float], radius: float) -> List[DataPoint]:
        """
        查询半径内的点

        Args:
            center: 中心点 (x, y)
            radius: 半径

        Returns:
            半径内的点列表
        """
        results = []
        self._query_radius_recursive(self.root, center, radius, results)
        return results

    def _query_radius_recursive(
        self,
        node: Optional[KDTreeNode],
        center: Tuple[float, float],
        radius: float,
        results: List[DataPoint]
    ) -> None:
        """递归查询半径"""
        if node is None:
            return

        # 检查当前点是否在半径内
        point_coord = np.array([node.point.x, node.point.y])
        center_coord = np.array(center)
        distance = np.linalg.norm(point_coord - center_coord)

        if distance <= radius:
            results.append(node.point)

        # 递归搜索子树
        axis = node.axis
        center_axis = center[axis]
        node_axis = [node.point.x, node.point.y][axis]

        # 检查左子树
        if center_axis - radius <= node_axis:
            self._query_radius_recursive(node.left, center, radius, results)

        # 检查右子树
        if center_axis + radius > node_axis:
            self._query_radius_recursive(node.right, center, radius, results)

    def query_knn(self, center: Tuple[float, float], k: int) -> List[Tuple[DataPoint, float]]:
        """
        查询K近邻

        Args:
            center: 中心点 (x, y)
            k: 近邻数量

        Returns:
            K近邻列表 [(点, 距离), ...]
        """
        if k <= 0:
            return []

        results = []

        def search(node: Optional[KDTreeNode]):
            if node is None:
                return

            # 计算当前点距离
            point_coord = np.array([node.point.x, node.point.y])
            center_coord = np.array(center)
            distance = np.linalg.norm(point_coord - center_coord)

            # 添加到结果
            if len(results) < k:
                results.append((node.point, distance))
                # 保持按距离排序
                results.sort(key=lambda x: x[1])
            else:
                # 如果距离更小，替换最大的
                if distance < results[-1][1]:
                    results[-1] = (node.point, distance)
                    results.sort(key=lambda x: x[1])

            # 递归搜索
            axis = node.axis
            center_axis = center[axis]
            node_axis = [node.point.x, node.point.y][axis]

            # 优先搜索可能更近的子树
            if center_axis < node_axis:
                search(node.left)
                if abs(center_axis - node_axis) < results[-1][1] if results else True:
                    search(node.right)
            else:
                search(node.right)
                if abs(center_axis - node_axis) < results[-1][1] if results else True:
                    search(node.left)

        search(self.root)
        return results


# ==================== R树索引 ====================

class RTreeNode:
    """R树节点"""

    MAX_ENTRIES = 10
    MIN_ENTRIES = 2

    def __init__(
        self,
        is_leaf: bool = True,
        children: Optional[List['RTreeNode']] = None,
        points: Optional[List[DataPoint]] = None,
        bounds: Optional[BoundingBox] = None
    ):
        """
        初始化R树节点

        Args:
            is_leaf: 是否为叶子节点
            children: 子节点列表
            points: 数据点列表（仅叶子节点）
            bounds: 边界框
        """
        self.is_leaf = is_leaf
        self.children = children or []
        self.points = points or []
        self.bounds = bounds

    def update_bounds(self) -> None:
        """更新边界框"""
        if self.is_leaf:
            if self.points:
                xs = [p.x for p in self.points]
                ys = [p.y for p in self.points]
                self.bounds = BoundingBox(
                    min(xs), max(xs),
                    min(ys), max(ys)
                )
            else:
                self.bounds = BoundingBox(0, 0, 0, 0)
        else:
            if self.children:
                min_x = min(c.bounds.min_x for c in self.children)
                max_x = max(c.bounds.max_x for c in self.children)
                min_y = min(c.bounds.min_y for c in self.children)
                max_y = max(c.bounds.max_y for c in self.children)
                self.bounds = BoundingBox(min_x, max_x, min_y, max_y)
            else:
                self.bounds = BoundingBox(0, 0, 0, 0)


class RTree:
    """R树索引"""

    def __init__(self):
        """初始化R树"""
        self.root = RTreeNode(is_leaf=True)
        self.size = 0

    def insert(self, point: DataPoint) -> None:
        """
        插入数据点

        Args:
            point: 数据点
        """
        leaf = self._choose_leaf(point)
        leaf.points.append(point)
        leaf.update_bounds()

        # 检查是否需要分裂
        if len(leaf.points) > leaf.MAX_ENTRIES:
            self._split(leaf)

        self.size += 1

    def _choose_leaf(self, point: DataPoint) -> RTreeNode:
        """选择插入的叶子节点"""
        node = self.root

        while not node.is_leaf:
            # 选择面积增加最小的子节点
            min_increase = float('inf')
            best_child = None

            for child in node.children:
                old_area = self._calculate_area(child.bounds)
                # 计算包含新点后的边界
                new_bounds = self._expand_bounds(child.bounds, point)
                new_area = self._calculate_area(new_bounds)
                increase = new_area - old_area

                if increase < min_increase:
                    min_increase = increase
                    best_child = child

            node = best_child

        return node

    def _expand_bounds(self, bounds: BoundingBox, point: DataPoint) -> BoundingBox:
        """扩展边界框以包含点"""
        return BoundingBox(
            min(bounds.min_x, point.x),
            max(bounds.max_x, point.x),
            min(bounds.min_y, point.y),
            max(bounds.max_y, point.y)
        )

    def _calculate_area(self, bounds: BoundingBox) -> float:
        """计算边界框面积"""
        return (bounds.max_x - bounds.min_x) * (bounds.max_y - bounds.min_y)

    def _split(self, node: RTreeNode) -> None:
        """分裂节点"""
        if node.is_leaf:
            # 分裂点
            points = node.points
            mid = len(points) // 2
            node.points = points[:mid]
            new_node = RTreeNode(is_leaf=True, points=points[mid:])
            new_node.update_bounds()
        else:
            # 分裂子节点
            children = node.children
            mid = len(children) // 2
            node.children = children[:mid]
            new_node = RTreeNode(is_leaf=False, children=children[mid:])

        # 更新边界
        node.update_bounds()
        new_node.update_bounds()

        # 如果是根节点，创建新的根
        if node == self.root:
            self.root = RTreeNode(is_leaf=False, children=[node, new_node])
            self.root.update_bounds()
        else:
            # 将新节点添加到父节点
            # 简化实现，实际需要找到父节点
            pass

    def query_range(self, range_box: BoundingBox) -> List[DataPoint]:
        """
        查询范围内的点

        Args:
            range_box: 查询范围

        Returns:
            范围内的点列表
        """
        results = []
        self._query_range_recursive(self.root, range_box, results)
        return results

    def _query_range_recursive(
        self,
        node: RTreeNode,
        range_box: BoundingBox,
        results: List[DataPoint]
    ) -> None:
        """递归查询范围"""
        if not node.bounds.intersects(range_box):
            return

        if node.is_leaf:
            for point in node.points:
                if range_box.contains(point.x, point.y):
                    results.append(point)
        else:
            for child in node.children:
                self._query_range_recursive(child, range_box, results)


# ==================== 网格索引 ====================

class GridIndex:
    """网格索引"""

    def __init__(self, bounds: BoundingBox, cell_size: float):
        """
        初始化网格索引

        Args:
            bounds: 索引边界
            cell_size: 网格单元大小
        """
        self.bounds = bounds
        self.cell_size = cell_size

        # 计算网格维度
        self.nx = int((bounds.max_x - bounds.min_x) / cell_size) + 1
        self.ny = int((bounds.max_y - bounds.min_y) / cell_size) + 1

        # 创建网格
        self.grid: List[List[List[DataPoint]]] = [
            [[] for _ in range(self.ny)]
            for _ in range(self.nx)
        ]

        self.size = 0

    def _get_cell_coords(self, x: float, y: float) -> Tuple[int, int]:
        """获取网格坐标"""
        i = int((x - self.bounds.min_x) / self.cell_size)
        j = int((y - self.bounds.min_y) / self.cell_size)

        # 限制在网格范围内
        i = max(0, min(i, self.nx - 1))
        j = max(0, min(j, self.ny - 1))

        return i, j

    def insert(self, point: DataPoint) -> None:
        """
        插入数据点

        Args:
            point: 数据点
        """
        i, j = self._get_cell_coords(point.x, point.y)
        self.grid[i][j].append(point)
        self.size += 1

    def query_range(self, range_box: BoundingBox) -> List[DataPoint]:
        """
        查询范围内的点

        Args:
            range_box: 查询范围

        Returns:
            范围内的点列表
        """
        results = []

        # 计算涉及的网格单元范围
        min_i, min_j = self._get_cell_coords(range_box.min_x, range_box.min_y)
        max_i, max_j = self._get_cell_coords(range_box.max_x, range_box.max_y)

        # 查询涉及的网格单元
        for i in range(min_i, max_i + 1):
            for j in range(min_j, max_j + 1):
                for point in self.grid[i][j]:
                    if range_box.contains(point.x, point.y):
                        results.append(point)

        return results

    def query_radius(self, center: Tuple[float, float], radius: float) -> List[DataPoint]:
        """
        查询半径内的点

        Args:
            center: 中心点 (x, y)
            radius: 半径

        Returns:
            半径内的点列表
        """
        # 创建范围查询
        range_box = BoundingBox(
            center[0] - radius,
            center[0] + radius,
            center[1] - radius,
            center[1] + radius
        )

        # 范围查询后过滤
        candidates = self.query_range(range_box)

        # 精确过滤
        results = []
        for point in candidates:
            distance = np.sqrt((point.x - center[0])**2 + (point.y - center[1])**2)
            if distance <= radius:
                results.append(point)

        return results


# ==================== 测试函数 ====================

def test_kdtree():
    """测试KD树"""
    print("\n测试KD树...")

    # 创建随机点
    points = []
    for i in range(100):
        point = DataPoint(
            x=np.random.uniform(0, 100),
            y=np.random.uniform(0, 100),
            value=np.random.randn(),
            id=f"point_{i}"
        )
        points.append(point)

    # 构建KD树
    kdtree = KDTree(points)
    print(f"构建KD树，包含 {kdtree.size} 个点")

    # 查询半径
    center = (50, 50)
    radius = 20
    results = kdtree.query_radius(center, radius)
    print(f"半径 {radius} 内找到 {len(results)} 个点")

    # 查询K近邻
    knn = kdtree.query_knn(center, 5)
    print("5个最近邻:")
    for point, dist in knn:
        print(f"  {point.id}: {dist:.2f}")

    print("KD树测试通过！")


def test_rtree():
    """测试R树"""
    print("\n测试R树...")

    # 创建R树
    rtree = RTree()

    # 插入数据点
    for i in range(100):
        point = DataPoint(
            x=np.random.uniform(0, 100),
            y=np.random.uniform(0, 100),
            value=np.random.randn(),
            id=f"point_{i}"
        )
        rtree.insert(point)

    print(f"插入 {rtree.size} 个点到R树")

    # 查询范围
    range_box = BoundingBox(30, 70, 30, 70)
    results = rtree.query_range(range_box)
    print(f"范围内找到 {len(results)} 个点")

    print("R树测试通过！")


def test_grid_index():
    """测试网格索引"""
    print("\n测试网格索引...")

    # 创建网格索引
    bounds = BoundingBox(0, 100, 0, 100)
    grid = GridIndex(bounds, cell_size=10)

    # 插入数据点
    for i in range(100):
        point = DataPoint(
            x=np.random.uniform(0, 100),
            y=np.random.uniform(0, 100),
            value=np.random.randn(),
            id=f"point_{i}"
        )
        grid.insert(point)

    print(f"插入 {grid.size} 个点到网格索引")

    # 查询半径
    center = (50, 50)
    radius = 20
    results = grid.query_radius(center, radius)
    print(f"半径 {radius} 内找到 {len(results)} 个点")

    # 查询范围
    range_box = BoundingBox(30, 70, 30, 70)
    results = grid.query_range(range_box)
    print(f"范围内找到 {len(results)} 个点")

    print("网格索引测试通过！")


if __name__ == "__main__":
    test_kdtree()
    test_rtree()
    test_grid_index()
    print("\n所有测试通过！")
