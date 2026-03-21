"""
路径规划服务
提供路径规划的核心业务逻辑
"""

import uuid
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from ..models import (
    RoutePlanningRequest,
    RoutePlanningResponse,
    PlannedRoute,
    RouteSegment,
    SamplingPoint,
    RouteConstraint,
    OptimizationGoal,
    VehicleType
)
from ..core import (
    DijkstraAlgorithm,
    AStarAlgorithm,
    TSPSolver,
    ACOAlgorithm
)
from ..utils import (
    build_distance_matrix,
    build_time_matrix,
    build_cost_matrix,
    calculate_route_statistics,
    validate_route,
    check_all_constraints
)


class RoutePlanningService:
    """路径规划服务"""

    def __init__(self):
        """初始化路径规划服务"""
        self._initialize_algorithms()

    def _initialize_algorithms(self):
        """初始化算法实例"""
        self.dijkstra_available = True
        self.astar_available = True
        self.tsp_available = True
        self.aco_available = True

    def plan_route(self, request: RoutePlanningRequest) -> RoutePlanningResponse:
        """
        执行路径规划

        Args:
            request: 路径规划请求

        Returns:
            路径规划响应
        """
        start_time = time.time()
        routes: List[PlannedRoute] = []
        warnings: List[str] = []
        statistics: Dict[str, Any] = {}

        try:
            # 准备采样点数据
            all_points = [request.start_point] + request.sampling_points
            if request.end_point:
                all_points.append(request.end_point)

            # 检查采样点数量
            if len(request.sampling_points) < 2:
                return self._create_error_response("采样点数量不足，至少需要2个采样点")

            # 检查可达性
            unreachable_points = self._check_reachability(all_points)
            if unreachable_points:
                warnings.append(f"以下采样点不可达：{', '.join(unreachable_points)}")

            # 构建矩阵
            point_tuples = [(p.id, p.latitude, p.longitude) for p in all_points]
            distance_matrix = build_distance_matrix(point_tuples)

            # 根据车辆类型调整速度
            speed_factor = self._get_speed_factor(request.constraints.vehicle_type)
            time_matrix = build_time_matrix(distance_matrix, speed_factor * 30.0)  # 基础速度30km/h
            cost_matrix = build_cost_matrix(distance_matrix)

            # 选择算法
            algorithm = request.algorithm.lower()
            if algorithm == "auto":
                algorithm = self._select_best_algorithm(request)

            # 执行路径规划
            if algorithm == "dijkstra":
                routes = self._plan_with_dijkstra(all_points, distance_matrix, time_matrix, cost_matrix, request)
            elif algorithm == "astar":
                routes = self._plan_with_astar(all_points, distance_matrix, time_matrix, cost_matrix, request)
            elif algorithm == "tsp":
                routes = self._plan_with_tsp(all_points, distance_matrix, time_matrix, cost_matrix, request)
            elif algorithm == "aco":
                routes = self._plan_with_aco(all_points, distance_matrix, time_matrix, cost_matrix, request)
            else:
                warnings.append(f"未知算法{algorithm}，使用默认算法")
                routes = self._plan_with_tsp(all_points, distance_matrix, time_matrix, cost_matrix, request)

            # 检查约束条件
            point_dict = {p.id: p for p in all_points}
            valid_routes = []
            for route in routes:
                is_valid, details = check_all_constraints(route, point_dict, request.constraints)
                if is_valid:
                    valid_routes.append(route)
                else:
                    warnings.append(f"路径{route.route_id}违反约束：{details['violations']}")

            routes = valid_routes if valid_routes else routes

            # 选择最优路径
            best_route = self._select_best_route(routes, request.optimization_goal)

            # 计算统计信息
            if best_route:
                statistics = calculate_route_statistics(best_route)
                statistics['algorithm_used'] = algorithm
                statistics['num_sampling_points'] = len(request.sampling_points)
                statistics['num_warnings'] = len(warnings)

            computation_time = time.time() - start_time

            return RoutePlanningResponse(
                success=len(routes) > 0,
                routes=routes,
                best_route=best_route,
                statistics=statistics,
                warnings=warnings,
                computation_time=computation_time
            )

        except Exception as e:
            return self._create_error_response(f"路径规划失败：{str(e)}")

    def _plan_with_dijkstra(self,
                           all_points: List[SamplingPoint],
                           distance_matrix: List[List[float]],
                           time_matrix: List[List[float]],
                           cost_matrix: List[List[float]],
                           request: RoutePlanningRequest) -> List[PlannedRoute]:
        """使用Dijkstra算法规划路径"""
        from ..core.dijkstra import DijkstraAlgorithm, Graph

        # 构建图
        graph = DijkstraAlgorithm.build_graph_from_points(
            [(p.id, p.latitude, p.longitude) for p in all_points]
        )

        dijkstra = DijkstraAlgorithm(graph)

        # 计算所有点之间的最短路径
        all_paths = dijkstra.find_all_shortest_paths(all_points[0].id)

        # 构建路径（简单版本：按顺序访问）
        point_ids = [p.id for p in all_points]
        route = self._build_route_from_sequence(
            point_ids,
            all_points,
            distance_matrix,
            time_matrix,
            cost_matrix
        )

        return [route]

    def _plan_with_astar(self,
                        all_points: List[SamplingPoint],
                        distance_matrix: List[List[float]],
                        time_matrix: List[List[float]],
                        cost_matrix: List[List[float]],
                        request: RoutePlanningRequest) -> List[PlannedRoute]:
        """使用A*算法规划路径"""
        # 构建图
        graph = {}
        coordinates = {}
        for i, p1 in enumerate(all_points):
            graph[p1.id] = {}
            coordinates[p1.id] = (p1.latitude, p1.longitude)
            for j, p2 in enumerate(all_points):
                if i != j:
                    graph[p1.id][p2.id] = distance_matrix[i][j]

        astar = AStarAlgorithm(graph)
        astar.set_coordinates(coordinates)

        # 简单路径：按顺序访问
        point_ids = [p.id for p in all_points]
        route = self._build_route_from_sequence(
            point_ids,
            all_points,
            distance_matrix,
            time_matrix,
            cost_matrix
        )

        return [route]

    def _plan_with_tsp(self,
                      all_points: List[SamplingPoint],
                      distance_matrix: List[List[float]],
                      time_matrix: List[List[float]],
                      cost_matrix: List[List[float]],
                      request: RoutePlanningRequest) -> List[PlannedRoute]:
        """使用TSP算法规划路径"""
        routes = []

        # 使用不同的TSP求解器生成多个方案
        solvers = [
            NearestNeighborTSPSolver(distance_matrix),
            TwoOptTSPSolver(distance_matrix),
            SimulatedAnnealingTSPSolver(distance_matrix)
        ]

        for solver in solvers:
            path_indices, total_distance = solver.solve(start_city=0)

            # 将索引转换为点ID
            point_ids = [all_points[i].id for i in path_indices]

            # 构建路径
            route = self._build_route_from_sequence(
                point_ids,
                all_points,
                distance_matrix,
                time_matrix,
                cost_matrix
            )

            routes.append(route)

        return routes

    def _plan_with_aco(self,
                      all_points: List[SamplingPoint],
                      distance_matrix: List[List[float]],
                      time_matrix: List[List[float]],
                      cost_matrix: List[List[float]],
                      request: RoutePlanningRequest) -> List[PlannedRoute]:
        """使用蚁群算法规划路径"""
        aco = ACOAlgorithm(distance_matrix)
        path_indices, total_distance = aco.solve(start_city=0)

        # 将索引转换为点ID
        point_ids = [all_points[i].id for i in path_indices]

        # 构建路径
        route = self._build_route_from_sequence(
            point_ids,
            all_points,
            distance_matrix,
            time_matrix,
            cost_matrix
        )

        return [route]

    def _build_route_from_sequence(self,
                                   point_ids: List[str],
                                   all_points: List[SamplingPoint],
                                   distance_matrix: List[List[float]],
                                   time_matrix: List[List[float]],
                                   cost_matrix: List[List[float]]) -> PlannedRoute:
        """根据点序列构建路径对象"""
        # 创建点ID到索引的映射
        point_to_index = {p.id: i for i, p in enumerate(all_points)}

        # 构建路径段
        segments = []
        total_distance = 0
        total_duration = 0
        total_cost = 0

        for i in range(len(point_ids) - 1):
            from_idx = point_to_index[point_ids[i]]
            to_idx = point_to_index[point_ids[i + 1]]

            segment = RouteSegment(
                from_point_id=point_ids[i],
                to_point_id=point_ids[i + 1],
                distance=distance_matrix[from_idx][to_idx],
                duration=time_matrix[from_idx][to_idx],
                cost=cost_matrix[from_idx][to_idx],
                instructions=self._generate_instructions(
                    all_points[from_idx],
                    all_points[to_idx]
                )
            )

            segments.append(segment)
            total_distance += segment.distance
            total_duration += segment.duration
            total_cost += segment.cost

        # 创建路径对象
        route = PlannedRoute(
            route_id=str(uuid.uuid4()),
            point_sequence=point_ids,
            segments=segments,
            total_distance=total_distance,
            total_duration=total_duration,
            total_cost=total_cost,
            start_time=datetime.now(),
            end_time=datetime.now() + datetime.timedelta(seconds=total_duration)
        )

        return route

    def _generate_instructions(self, from_point: SamplingPoint, to_point: SamplingPoint) -> List[str]:
        """生成导航指引"""
        instructions = []

        # 计算方位角
        bearing = self._calculate_bearing(
            from_point.latitude, from_point.longitude,
            to_point.latitude, to_point.longitude
        )

        direction = self._get_direction_name(bearing)
        distance = self._calculate_distance(
            from_point.latitude, from_point.longitude,
            to_point.latitude, to_point.longitude
        )

        instructions.append(f"从{from_point.name or from_point.id}出发")
        instructions.append(f"向{direction}方向行驶{distance:.0f}米")
        instructions.append(f"到达{to_point.name or to_point.id}")

        return instructions

    def _calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算方位角"""
        import math
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)

        y = math.sin(delta_lon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))

        bearing = math.atan2(y, x)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360

        return bearing

    def _get_direction_name(self, bearing: float) -> str:
        """获取方向名称"""
        if bearing >= 337.5 or bearing < 22.5:
            return "北"
        elif bearing >= 22.5 and bearing < 67.5:
            return "东北"
        elif bearing >= 67.5 and bearing < 112.5:
            return "东"
        elif bearing >= 112.5 and bearing < 157.5:
            return "东南"
        elif bearing >= 157.5 and bearing < 202.5:
            return "南"
        elif bearing >= 202.5 and bearing < 247.5:
            return "西南"
        elif bearing >= 247.5 and bearing < 292.5:
            return "西"
        else:
            return "西北"

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算两点距离"""
        import math
        R = 6371000
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _select_best_route(self, routes: List[PlannedRoute], goal: OptimizationGoal) -> Optional[PlannedRoute]:
        """根据优化目标选择最优路径"""
        if not routes:
            return None

        if goal == OptimizationGoal.SHORTEST_DISTANCE:
            return min(routes, key=lambda r: r.total_distance)
        elif goal == OptimizationGoal.SHORTEST_TIME:
            return min(routes, key=lambda r: r.total_duration)
        elif goal == OptimizationGoal.LOWEST_COST:
            return min(routes, key=lambda r: r.total_cost)
        else:  # BALANCED
            # 综合评分
            def score(route):
                # 归一化后求和
                return (route.total_distance + route.total_duration + route.total_cost)

            return min(routes, key=score)

    def _select_best_algorithm(self, request: RoutePlanningRequest) -> str:
        """自动选择最佳算法"""
        num_points = len(request.sampling_points)

        if num_points <= 10:
            return "tsp"  # 小规模使用TSP
        elif num_points <= 30:
            return "aco"  # 中等规模使用蚁群算法
        else:
            return "aco"  # 大规模使用蚁群算法

    def _get_speed_factor(self, vehicle_type: VehicleType) -> float:
        """获取车辆类型对应的速度因子"""
        factors = {
            VehicleType.CAR: 1.0,
            VehicleType.SUV: 0.9,
            VehicleType.TRUCK: 0.7,
            VehicleType.WALKING: 0.1
        }
        return factors.get(vehicle_type, 1.0)

    def _check_reachability(self, points: List[SamplingPoint]) -> List[str]:
        """检查采样点可达性"""
        unreachable = []
        for point in points:
            if not point.is_reachable:
                unreachable.append(point.id)
        return unreachable

    def _create_error_response(self, error_message: str) -> RoutePlanningResponse:
        """创建错误响应"""
        return RoutePlanningResponse(
            success=False,
            routes=[],
            best_route=None,
            statistics={},
            warnings=[error_message],
            computation_time=0
        )


# 导入TSP求解器类
from ..core.tsp_solver import (
    NearestNeighborTSPSolver,
    TwoOptTSPSolver,
    SimulatedAnnealingTSPSolver
)