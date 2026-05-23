"""
路径规划模块单元测试
"""

import sys
import unittest
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.route_planning.core.aco import ACOAlgorithm
from app.route_planning.core.astar import AStarAlgorithm
from app.route_planning.core.dijkstra import DijkstraAlgorithm, Graph
from app.route_planning.core.tsp_solver import (
    NearestNeighborTSPSolver,
    SimulatedAnnealingTSPSolver,
    TwoOptTSPSolver,
)
from app.route_planning.utils.constraint_utils import (
    check_cost_constraint,
    check_distance_constraint,
    check_duration_constraint,
)
from app.route_planning.utils.geo_utils import (
    calculate_bearing,
    calculate_midpoint,
    haversine_distance,
)
from app.route_planning.utils.route_utils import (
    build_cost_matrix,
    build_distance_matrix,
    build_time_matrix,
)


class TestDijkstraAlgorithm(unittest.TestCase):
    """测试Dijkstra算法"""

    def setUp(self):
        """设置测试数据"""
        self.graph = Graph()
        self.graph.add_node('A', 39.9042, 116.4074)
        self.graph.add_node('B', 39.9142, 116.4174)
        self.graph.add_node('C', 39.9242, 116.4274)
        self.graph.add_node('D', 39.9342, 116.4374)

        self.graph.add_edge('A', 'B', 1000)
        self.graph.add_edge('B', 'C', 1000)
        self.graph.add_edge('C', 'D', 1000)
        self.graph.add_edge('A', 'C', 2000)

        self.dijkstra = DijkstraAlgorithm(self.graph)

    def test_find_shortest_path(self):
        """测试最短路径查找"""
        distance, path = self.dijkstra.find_shortest_path('A', 'D')

        self.assertEqual(distance, 3000)
        self.assertEqual(path, ['A', 'B', 'C', 'D'])

    def test_find_all_shortest_paths(self):
        """测试查找所有最短路径"""
        all_paths = self.dijkstra.find_all_shortest_paths('A')

        self.assertIn('B', all_paths)
        self.assertIn('C', all_paths)
        self.assertIn('D', all_paths)

        self.assertEqual(all_paths['B'][0], 1000)
        self.assertEqual(all_paths['C'][0], 2000)
        self.assertEqual(all_paths['D'][0], 3000)

    def test_haversine_distance(self):
        """测试Haversine距离计算"""
        distance = DijkstraAlgorithm.calculate_haversine_distance(
            39.9042, 116.4074,
            39.9142, 116.4174
        )

        self.assertGreater(distance, 0)
        self.assertLess(distance, 20000)  # 应该小于20公里


class TestAStarAlgorithm(unittest.TestCase):
    """测试A*算法"""

    def setUp(self):
        """设置测试数据"""
        self.graph = {
            'A': {'B': 1000, 'C': 2000},
            'B': {'A': 1000, 'C': 1000, 'D': 1000},
            'C': {'A': 2000, 'B': 1000, 'D': 1000},
            'D': {'B': 1000, 'C': 1000}
        }

        self.coordinates = {
            'A': (39.9042, 116.4074),
            'B': (39.9142, 116.4174),
            'C': (39.9242, 116.4274),
            'D': (39.9342, 116.4374)
        }

        self.astar = AStarAlgorithm(self.graph)
        self.astar.set_coordinates(self.coordinates)

    def test_find_path(self):
        """测试路径查找"""
        distance, path = self.astar.find_path('A', 'D')

        self.assertGreater(distance, 0)
        self.assertGreater(len(path), 0)
        self.assertEqual(path[0], 'A')
        self.assertEqual(path[-1], 'D')


class TestTSPSolver(unittest.TestCase):
    """测试TSP求解器"""

    def setUp(self):
        """设置测试数据"""
        # 创建一个简单的距离矩阵
        self.distance_matrix = [
            [0, 10, 15, 20],
            [10, 0, 35, 25],
            [15, 35, 0, 30],
            [20, 25, 30, 0]
        ]

    def test_nearest_neighbor(self):
        """测试最近邻算法"""
        solver = NearestNeighborTSPSolver(self.distance_matrix)
        path, distance = solver.solve(start_city=0)

        self.assertEqual(len(path), 5)  # 4个城市 + 回到起点
        self.assertEqual(path[0], 0)
        self.assertEqual(path[-1], 0)
        self.assertGreater(distance, 0)

    def test_two_opt(self):
        """测试2-opt算法"""
        solver = TwoOptTSPSolver(self.distance_matrix)
        path, distance = solver.solve(start_city=0)

        self.assertEqual(len(path), 5)
        self.assertEqual(path[0], 0)
        self.assertEqual(path[-1], 0)
        self.assertGreater(distance, 0)

    def test_simulated_annealing(self):
        """测试模拟退火算法"""
        solver = SimulatedAnnealingTSPSolver(self.distance_matrix)
        path, distance = solver.solve(start_city=0)

        self.assertEqual(len(path), 5)
        self.assertEqual(path[0], 0)
        self.assertEqual(path[-1], 0)
        self.assertGreater(distance, 0)


class TestACOAlgorithm(unittest.TestCase):
    """测试蚁群算法"""

    def setUp(self):
        """设置测试数据"""
        self.distance_matrix = [
            [0, 10, 15, 20],
            [10, 0, 35, 25],
            [15, 35, 0, 30],
            [20, 25, 30, 0]
        ]

    def test_aco(self):
        """测试蚁群算法"""
        aco = ACOAlgorithm(self.distance_matrix, num_ants=10, max_iterations=50)
        path, distance = aco.solve(start_city=0)

        self.assertEqual(len(path), 5)
        self.assertEqual(path[0], 0)
        self.assertEqual(path[-1], 0)
        self.assertGreater(distance, 0)


class TestGeoUtils(unittest.TestCase):
    """测试地理工具函数"""

    def test_haversine_distance(self):
        """测试Haversine距离计算"""
        distance = haversine_distance(
            39.9042, 116.4074,
            39.9142, 116.4174
        )

        self.assertGreater(distance, 0)
        self.assertLess(distance, 20000)

    def test_calculate_bearing(self):
        """测试方位角计算"""
        bearing = calculate_bearing(
            39.9042, 116.4074,
            39.9142, 116.4174
        )

        self.assertGreaterEqual(bearing, 0)
        self.assertLess(bearing, 360)

    def test_calculate_midpoint(self):
        """测试中点计算"""
        lat1, lon1 = 39.9042, 116.4074
        lat2, lon2 = 39.9142, 116.4174

        mid_lat, mid_lon = calculate_midpoint(lat1, lon1, lat2, lon2)

        self.assertGreater(mid_lat, min(lat1, lat2))
        self.assertLess(mid_lat, max(lat1, lat2))
        self.assertGreater(mid_lon, min(lon1, lon2))
        self.assertLess(mid_lon, max(lon1, lon2))


class TestRouteUtils(unittest.TestCase):
    """测试路径工具函数"""

    def setUp(self):
        """设置测试数据"""
        self.points = [
            ('A', 39.9042, 116.4074),
            ('B', 39.9142, 116.4174),
            ('C', 39.9242, 116.4274),
            ('D', 39.9342, 116.4374)
        ]

    def test_build_distance_matrix(self):
        """测试距离矩阵构建"""
        matrix = build_distance_matrix(self.points)

        self.assertEqual(len(matrix), 4)
        self.assertEqual(len(matrix[0]), 4)

        # 对角线应该为0
        for i in range(4):
            self.assertEqual(matrix[i][i], 0)

        # 矩阵应该是对称的
        for i in range(4):
            for j in range(4):
                self.assertEqual(matrix[i][j], matrix[j][i])

    def test_build_time_matrix(self):
        """测试时间矩阵构建"""
        distance_matrix = build_distance_matrix(self.points)
        time_matrix = build_time_matrix(distance_matrix)

        self.assertEqual(len(time_matrix), 4)
        self.assertEqual(len(time_matrix[0]), 4)

        # 时间应该与距离成正比
        for i in range(4):
            for j in range(4):
                if distance_matrix[i][j] > 0:
                    self.assertGreater(time_matrix[i][j], 0)

    def test_build_cost_matrix(self):
        """测试成本矩阵构建"""
        distance_matrix = build_distance_matrix(self.points)
        cost_matrix = build_cost_matrix(distance_matrix)

        self.assertEqual(len(cost_matrix), 4)
        self.assertEqual(len(cost_matrix[0]), 4)

        # 成本应该与距离成正比
        for i in range(4):
            for j in range(4):
                if distance_matrix[i][j] > 0:
                    self.assertGreater(cost_matrix[i][j], 0)


class TestConstraintUtils(unittest.TestCase):
    """测试约束工具函数"""

    def test_check_distance_constraint(self):
        """测试距离约束检查"""
        from app.route_planning.models import PlannedRoute

        route = PlannedRoute(
            route_id='test',
            point_sequence=['A', 'B', 'C'],
            segments=[],
            total_distance=5000,
            total_duration=100,
            total_cost=100
        )

        is_valid, actual = check_distance_constraint(route, 10000)
        self.assertTrue(is_valid)
        self.assertEqual(actual, 5000)

        is_valid, actual = check_distance_constraint(route, 3000)
        self.assertFalse(is_valid)
        self.assertEqual(actual, 5000)

    def test_check_duration_constraint(self):
        """测试时间约束检查"""
        from app.route_planning.models import PlannedRoute

        route = PlannedRoute(
            route_id='test',
            point_sequence=['A', 'B', 'C'],
            segments=[],
            total_distance=5000,
            total_duration=100,
            total_cost=100
        )

        is_valid, actual = check_duration_constraint(route, 200)
        self.assertTrue(is_valid)
        self.assertEqual(actual, 100)

        is_valid, actual = check_duration_constraint(route, 50)
        self.assertFalse(is_valid)
        self.assertEqual(actual, 100)

    def test_check_cost_constraint(self):
        """测试成本约束检查"""
        from app.route_planning.models import PlannedRoute

        route = PlannedRoute(
            route_id='test',
            point_sequence=['A', 'B', 'C'],
            segments=[],
            total_distance=5000,
            total_duration=100,
            total_cost=100
        )

        is_valid, actual = check_cost_constraint(route, 200)
        self.assertTrue(is_valid)
        self.assertEqual(actual, 100)

        is_valid, actual = check_cost_constraint(route, 50)
        self.assertFalse(is_valid)
        self.assertEqual(actual, 100)


if __name__ == '__main__':
    unittest.main()
