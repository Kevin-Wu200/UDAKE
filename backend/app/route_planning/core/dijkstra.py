"""
Dijkstra最短路径算法实现
用于计算两点之间的最短路径
"""

import heapq
from typing import Dict, List, Optional, Set, Tuple
import math


class Graph:
    """图数据结构"""

    def __init__(self):
        self.nodes: Dict[str, Dict[str, float]] = {}  # 节点到邻居及距离的映射
        self.coordinates: Dict[str, Tuple[float, float]] = {}  # 节点坐标

    def add_node(self, node_id: str, lat: float, lon: float):
        """添加节点"""
        self.nodes[node_id] = {}
        self.coordinates[node_id] = (lat, lon)

    def add_edge(self, from_node: str, to_node: str, distance: float, bidirectional: bool = True):
        """添加边"""
        if from_node not in self.nodes or to_node not in self.nodes:
            raise ValueError("节点不存在")

        self.nodes[from_node][to_node] = distance
        if bidirectional:
            self.nodes[to_node][from_node] = distance

    def get_neighbors(self, node_id: str) -> Dict[str, float]:
        """获取节点的邻居"""
        return self.nodes.get(node_id, {})

    def get_distance(self, from_node: str, to_node: str) -> Optional[float]:
        """获取两点间的距离"""
        if from_node in self.nodes and to_node in self.nodes[from_node]:
            return self.nodes[from_node][to_node]
        return None


class DijkstraAlgorithm:
    """Dijkstra最短路径算法"""

    def __init__(self, graph: Graph):
        """
        初始化Dijkstra算法

        Args:
            graph: 图对象
        """
        self.graph = graph

    def find_shortest_path(self, start_node: str, end_node: str) -> Tuple[float, List[str]]:
        """
        查找从起点到终点的最短路径

        Args:
            start_node: 起点节点ID
            end_node: 终点节点ID

        Returns:
            (总距离, 路径节点列表)
        """
        if start_node not in self.graph.nodes:
            raise ValueError(f"起点节点 {start_node} 不存在")
        if end_node not in self.graph.nodes:
            raise ValueError(f"终点节点 {end_node} 不存在")

        # 初始化距离和前驱节点
        distances: Dict[str, float] = {node: float('inf') for node in self.graph.nodes}
        distances[start_node] = 0
        previous: Dict[str, Optional[str]] = {node: None for node in self.graph.nodes}

        # 优先队列
        pq: List[Tuple[float, str]] = [(0, start_node)]
        visited: Set[str] = set()

        while pq:
            current_distance, current_node = heapq.heappop(pq)

            # 如果已经访问过，跳过
            if current_node in visited:
                continue

            visited.add(current_node)

            # 找到终点
            if current_node == end_node:
                break

            # 遍历邻居
            for neighbor, edge_distance in self.graph.get_neighbors(current_node).items():
                if neighbor in visited:
                    continue

                new_distance = current_distance + edge_distance

                # 如果找到更短的路径
                if new_distance <= distances[neighbor]:
                    distances[neighbor] = new_distance
                    previous[neighbor] = current_node
                    heapq.heappush(pq, (new_distance, neighbor))

        # 重构路径
        path: List[str] = []
        current = end_node
        if distances[end_node] == float('inf'):
            return float('inf'), []

        while current is not None:
            path.append(current)
            current = previous[current]

        path.reverse()

        return distances[end_node], path

    def find_all_shortest_paths(self, start_node: str) -> Dict[str, Tuple[float, List[str]]]:
        """
        查找从起点到所有其他节点的最短路径

        Args:
            start_node: 起点节点ID

        Returns:
            {终点ID: (距离, 路径)}
        """
        # 初始化距离和前驱节点
        distances: Dict[str, float] = {node: float('inf') for node in self.graph.nodes}
        distances[start_node] = 0
        previous: Dict[str, Optional[str]] = {node: None for node in self.graph.nodes}

        # 优先队列
        pq: List[Tuple[float, str]] = [(0, start_node)]
        visited: Set[str] = set()

        while pq:
            current_distance, current_node = heapq.heappop(pq)

            if current_node in visited:
                continue

            visited.add(current_node)

            # 遍历邻居
            for neighbor, edge_distance in self.graph.get_neighbors(current_node).items():
                if neighbor in visited:
                    continue

                new_distance = current_distance + edge_distance

                if new_distance <= distances[neighbor]:
                    distances[neighbor] = new_distance
                    previous[neighbor] = current_node
                    heapq.heappush(pq, (new_distance, neighbor))

        # 重构所有路径
        result: Dict[str, Tuple[float, List[str]]] = {}
        for node in self.graph.nodes:
            if node == start_node:
                continue

            if distances[node] == float('inf'):
                result[node] = (float('inf'), [])
            else:
                path: List[str] = []
                current = node
                while current is not None:
                    path.append(current)
                    current = previous[current]
                path.reverse()
                result[node] = (distances[node], path)

        return result

    @staticmethod
    def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        计算两点之间的Haversine距离（地球表面距离）

        Args:
            lat1: 第一个点的纬度
            lon1: 第一个点的经度
            lat2: 第二个点的纬度
            lon2: 第二个点的经度

        Returns:
            距离（米）
        """
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
    def build_graph_from_points(points: List[Tuple[str, float, float]]) -> Graph:
        """
        从采样点列表构建完全图（所有点之间都有连接）

        Args:
            points: [(id, lat, lon), ...]

        Returns:
            图对象
        """
        graph = Graph()

        # 添加节点
        for point_id, lat, lon in points:
            graph.add_node(point_id, lat, lon)

        # 添加边（完全图）
        for i, (id1, lat1, lon1) in enumerate(points):
            for id2, lat2, lon2 in points[i+1:]:
                distance = DijkstraAlgorithm.calculate_haversine_distance(lat1, lon1, lat2, lon2)
                graph.add_edge(id1, id2, distance)

        return graph
