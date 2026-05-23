"""
A*启发式搜索算法实现
用于在图中寻找从起点到终点的最短路径
"""

import heapq
import math
from typing import Callable, Dict, List, Optional, Set, Tuple


class AStarAlgorithm:
    """A*算法"""

    def __init__(self,
                 graph: Dict[str, Dict[str, float]],
                 heuristic: Optional[Callable[[Tuple[float, float], Tuple[float, float]], float]] = None):
        """
        初始化A*算法

        Args:
            graph: 图的邻接表表示 {节点ID: {邻居ID: 距离}}
            heuristic: 启发式函数 (默认使用Haversine距离)
        """
        self.graph = graph
        self.heuristic = heuristic or self.haversine_distance
        self.coordinates: Dict[str, Tuple[float, float]] = {}

    def set_coordinates(self, coordinates: Dict[str, Tuple[float, float]]):
        """
        设置节点坐标

        Args:
            coordinates: {节点ID: (纬度, 经度)}
        """
        self.coordinates = coordinates

    def find_path(self,
                  start_node: str,
                  end_node: str,
                  max_iterations: int = 10000) -> Tuple[float, List[str]]:
        """
        使用A*算法查找最短路径

        Args:
            start_node: 起点节点ID
            end_node: 终点节点ID
            max_iterations: 最大迭代次数

        Returns:
            (总距离, 路径节点列表)
        """
        if start_node not in self.graph:
            raise ValueError(f"起点节点 {start_node} 不在图中")
        if end_node not in self.graph:
            raise ValueError(f"终点节点 {end_node} 不在图中")

        # 初始化
        g_score: Dict[str, float] = {node: float('inf') for node in self.graph}
        g_score[start_node] = 0

        f_score: Dict[str, float] = {node: float('inf') for node in self.graph}
        if start_node in self.coordinates and end_node in self.coordinates:
            f_score[start_node] = self.heuristic(self.coordinates[start_node],
                                                self.coordinates[end_node])
        else:
            f_score[start_node] = 0

        # 优先队列 (f_score, 节点ID)
        open_set: List[Tuple[float, str]] = [(f_score[start_node], start_node)]
        closed_set: Set[str] = set()
        previous: Dict[str, Optional[str]] = {}

        iterations = 0

        while open_set:
            iterations += 1
            if iterations > max_iterations:
                raise RuntimeError(f"超过最大迭代次数 {max_iterations}")

            # 取出f_score最小的节点
            current_f, current_node = heapq.heappop(open_set)

            # 找到终点
            if current_node == end_node:
                path = self._reconstruct_path(previous, end_node)
                return g_score[end_node], path

            closed_set.add(current_node)

            # 遍历邻居
            for neighbor, edge_cost in self.graph.get(current_node, {}).items():
                if neighbor in closed_set:
                    continue

                # 计算新的g_score
                tentative_g = g_score[current_node] + edge_cost

                # 如果找到更短的路径
                if tentative_g < g_score[neighbor]:
                    previous[neighbor] = current_node
                    g_score[neighbor] = tentative_g

                    # 计算f_score = g_score + h_score
                    if neighbor in self.coordinates and end_node in self.coordinates:
                        h_score = self.heuristic(self.coordinates[neighbor],
                                               self.coordinates[end_node])
                    else:
                        h_score = 0

                    f_score[neighbor] = tentative_g + h_score

                    # 添加到open_set
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        # 没有找到路径
        return float('inf'), []

    def _reconstruct_path(self, previous: Dict[str, Optional[str]], end_node: str) -> List[str]:
        """重构路径"""
        path: List[str] = []
        current = end_node

        while current is not None:
            path.append(current)
            current = previous.get(current)

        path.reverse()
        return path

    @staticmethod
    def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        计算两点之间的Haversine距离

        Args:
            coord1: (纬度, 经度)
            coord2: (纬度, 经度)

        Returns:
            距离（米）
        """
        lat1, lon1 = coord1
        lat2, lon2 = coord2

        R = 6371000  # 地球半径（米）

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    @staticmethod
    def euclidean_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        计算欧几里得距离

        Args:
            coord1: (x, y)
            coord2: (x, y)

        Returns:
            距离
        """
        x1, y1 = coord1
        x2, y2 = coord2
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    @staticmethod
    def manhattan_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        计算曼哈顿距离

        Args:
            coord1: (x, y)
            coord2: (x, y)

        Returns:
            距离
        """
        x1, y1 = coord1
        x2, y2 = coord2
        return abs(x2 - x1) + abs(y2 - y1)
