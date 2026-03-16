"""
路径优化器
用于对现有路径进行优化和改进
"""

from typing import List, Dict, Any, Optional
from ..models import PlannedRoute, SamplingPoint, RouteConstraint, OptimizationGoal
from ..core.tsp_solver import TwoOptTSPSolver, SimulatedAnnealingTSPSolver
from ..utils import build_distance_matrix, build_time_matrix, build_cost_matrix


class RouteOptimizer:
    """路径优化器"""

    def __init__(self):
        """初始化路径优化器"""
        pass

    def optimize_route(self,
                      route: PlannedRoute,
                      sampling_points: Dict[str, SamplingPoint],
                      optimization_goal: OptimizationGoal = OptimizationGoal.SHORTEST_DISTANCE,
                      max_iterations: int = 10) -> PlannedRoute:
        """
        优化现有路径

        Args:
            route: 原始路径
            sampling_points: 采样点字典
            optimization_goal: 优化目标
            max_iterations: 最大迭代次数

        Returns:
            优化后的路径
        """
        if len(route.point_sequence) < 3:
            return route  # 路径太短，无需优化

        # 获取路径中的采样点
        points_in_route = [sampling_points[pid] for pid in route.point_sequence if pid in sampling_points]

        if len(points_in_route) < 2:
            return route

        # 构建矩阵
        point_tuples = [(p.id, p.latitude, p.longitude) for p in points_in_route]
        distance_matrix = build_distance_matrix(point_tuples)
        time_matrix = build_time_matrix(distance_matrix)
        cost_matrix = build_cost_matrix(distance_matrix)

        # 根据优化目标选择矩阵
        matrix = self._select_matrix(distance_matrix, time_matrix, cost_matrix, optimization_goal)

        # 使用2-opt优化
        two_opt = TwoOptTSPSolver(matrix, max_iterations=max_iterations)
        optimized_indices, _ = two_opt.solve(start_city=0)

        # 构建新的路径
        optimized_point_ids = [points_in_route[i].id for i in optimized_indices]

        # 重建路径对象
        optimized_route = self._rebuild_route(
            optimized_point_ids,
            sampling_points,
            distance_matrix,
            time_matrix,
            cost_matrix
        )

        return optimized_route

    def _select_matrix(self,
                      distance_matrix: List[List[float]],
                      time_matrix: List[List[float]],
                      cost_matrix: List[List[float]],
                      goal: OptimizationGoal) -> List[List[float]]:
        """根据优化目标选择矩阵"""
        if goal == OptimizationGoal.SHORTEST_DISTANCE:
            return distance_matrix
        elif goal == OptimizationGoal.SHORTEST_TIME:
            return time_matrix
        elif goal == OptimizationGoal.LOWEST_COST:
            return cost_matrix
        else:
            # 综合目标：归一化后求和
            return self._combine_matrices(distance_matrix, time_matrix, cost_matrix)

    def _combine_matrices(self,
                         distance_matrix: List[List[float]],
                         time_matrix: List[List[float]],
                         cost_matrix: List[List[float]]) -> List[List[float]]:
        """组合多个矩阵"""
        n = len(distance_matrix)
        combined = [[0.0] * n for _ in range(n)]

        # 归一化
        max_dist = max(max(row) for row in distance_matrix)
        max_time = max(max(row) for row in time_matrix)
        max_cost = max(max(row) for row in cost_matrix)

        for i in range(n):
            for j in range(n):
                if i != j:
                    combined[i][j] = (
                        distance_matrix[i][j] / max_dist +
                        time_matrix[i][j] / max_time +
                        cost_matrix[i][j] / max_cost
                    )

        return combined

    def _rebuild_route(self,
                      point_ids: List[str],
                      sampling_points: Dict[str, SamplingPoint],
                      distance_matrix: List[List[float]],
                      time_matrix: List[List[float]],
                      cost_matrix: List[List[float]]) -> PlannedRoute:
        """重建路径对象"""
        from datetime import datetime, timedelta
        import uuid

        # 创建点ID到索引的映射
        point_list = [sampling_points[pid] for pid in point_ids if pid in sampling_points]
        point_to_index = {p.id: i for i, p in enumerate(point_list)}

        # 构建路径段
        from ..models import RouteSegment

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
                instructions=[]
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
            end_time=datetime.now() + timedelta(seconds=total_duration)
        )

        return route

    def optimize_multiple_routes(self,
                                 routes: List[PlannedRoute],
                                 sampling_points: Dict[str, SamplingPoint],
                                 optimization_goal: OptimizationGoal = OptimizationGoal.SHORTEST_DISTANCE) -> List[PlannedRoute]:
        """
        优化多个路径

        Args:
            routes: 路径列表
            sampling_points: 采样点字典
            optimization_goal: 优化目标

        Returns:
            优化后的路径列表
        """
        optimized_routes = []

        for route in routes:
            optimized = self.optimize_route(route, sampling_points, optimization_goal)
            optimized_routes.append(optimized)

        return optimized_routes

    def add_point_to_route(self,
                          route: PlannedRoute,
                          new_point: SamplingPoint,
                          sampling_points: Dict[str, SamplingPoint],
                          insert_position: Optional[int] = None) -> PlannedRoute:
        """
        向路径中添加新采样点

        Args:
            route: 原始路径
            new_point: 新采样点
            sampling_points: 采样点字典
            insert_position: 插入位置（None表示自动选择最优位置）

        Returns:
            添加新点后的路径
        """
        # 添加新点到采样点字典
        all_sampling_points = sampling_points.copy()
        all_sampling_points[new_point.id] = new_point

        # 确定插入位置
        if insert_position is None:
            insert_position = self._find_best_insert_position(route, new_point, all_sampling_points)

        # 创建新的点序列
        new_sequence = route.point_sequence.copy()
        new_sequence.insert(insert_position, new_point.id)

        # 构建新路径
        point_tuples = [
            (all_sampling_points[pid].id,
             all_sampling_points[pid].latitude,
             all_sampling_points[pid].longitude)
            for pid in new_sequence
            if pid in all_sampling_points
        ]

        from ..utils import build_distance_matrix, build_time_matrix, build_cost_matrix

        distance_matrix = build_distance_matrix(point_tuples)
        time_matrix = build_time_matrix(distance_matrix)
        cost_matrix = build_cost_matrix(distance_matrix)

        new_route = self._rebuild_route(
            new_sequence,
            all_sampling_points,
            distance_matrix,
            time_matrix,
            cost_matrix
        )

        return new_route

    def _find_best_insert_position(self,
                                   route: PlannedRoute,
                                   new_point: SamplingPoint,
                                   sampling_points: Dict[str, SamplingPoint]) -> int:
        """
        找到最佳插入位置

        Args:
            route: 原始路径
            new_point: 新采样点
            sampling_points: 采样点字典

        Returns:
            最佳插入位置索引
        """
        from ..utils import haversine_distance

        best_position = 1  # 默认插入第二个位置
        min_additional_distance = float('inf')

        # 尝试每个可能的位置
        for position in range(1, len(route.point_sequence)):
            # 计算插入该位置后的额外距离
            additional_distance = 0

            # 前一个点到新点的距离
            prev_point = sampling_points.get(route.point_sequence[position - 1])
            if prev_point:
                additional_distance += haversine_distance(
                    prev_point.latitude, prev_point.longitude,
                    new_point.latitude, new_point.longitude
                )

            # 新点到后一个点的距离
            next_point = sampling_points.get(route.point_sequence[position])
            if next_point:
                additional_distance += haversine_distance(
                    new_point.latitude, new_point.longitude,
                    next_point.latitude, next_point.longitude
                )

            # 减去原来的距离
            if prev_point and next_point:
                original_distance = haversine_distance(
                    prev_point.latitude, prev_point.longitude,
                    next_point.latitude, next_point.longitude
                )
                additional_distance -= original_distance

            # 更新最优位置
            if additional_distance < min_additional_distance:
                min_additional_distance = additional_distance
                best_position = position

        return best_position

    def remove_point_from_route(self,
                               route: PlannedRoute,
                               point_id: str,
                               sampling_points: Dict[str, SamplingPoint]) -> Optional[PlannedRoute]:
        """
        从路径中移除采样点

        Args:
            route: 原始路径
            point_id: 要移除的点ID
            sampling_points: 采样点字典

        Returns:
            移除后的路径，如果点不存在则返回None
        """
        if point_id not in route.point_sequence:
            return None

        # 创建新的点序列
        new_sequence = [pid for pid in route.point_sequence if pid != point_id]

        # 构建新路径
        point_tuples = [
            (sampling_points[pid].id,
             sampling_points[pid].latitude,
             sampling_points[pid].longitude)
            for pid in new_sequence
            if pid in sampling_points
        ]

        distance_matrix = build_distance_matrix(point_tuples)
        time_matrix = build_time_matrix(distance_matrix)
        cost_matrix = build_cost_matrix(distance_matrix)

        new_route = self._rebuild_route(
            new_sequence,
            sampling_points,
            distance_matrix,
            time_matrix,
            cost_matrix
        )

        return new_route

    def reorder_route(self,
                     route: PlannedRoute,
                     sampling_points: Dict[str, SamplingPoint],
                     optimization_goal: OptimizationGoal = OptimizationGoal.SHORTEST_DISTANCE) -> PlannedRoute:
        """
        重新排序路径中的采样点

        Args:
            route: 原始路径
            sampling_points: 采样点字典
            optimization_goal: 优化目标

        Returns:
            重新排序后的路径
        """
        # 获取路径中的采样点（不包括起点和终点）
        middle_points = [pid for pid in route.point_sequence[1:-1] if pid in sampling_points]

        if len(middle_points) < 2:
            return route  # 中间点太少，无需重新排序

        # 构建矩阵
        points_in_middle = [sampling_points[pid] for pid in middle_points]
        point_tuples = [(p.id, p.latitude, p.longitude) for p in points_in_middle]
        distance_matrix = build_distance_matrix(point_tuples)
        time_matrix = build_time_matrix(distance_matrix)
        cost_matrix = build_cost_matrix(distance_matrix)

        # 使用TSP算法重新排序
        matrix = self._select_matrix(distance_matrix, time_matrix, cost_matrix, optimization_goal)
        two_opt = TwoOptTSPSolver(matrix)
        optimized_indices, _ = two_opt.solve(start_city=0)

        # 构建新的完整路径序列
        new_sequence = [route.point_sequence[0]]  # 起点
        new_sequence.extend([points_in_middle[i].id for i in optimized_indices])
        new_sequence.append(route.point_sequence[-1])  # 终点

        # 构建新路径
        all_point_tuples = [
            (sampling_points[pid].id,
             sampling_points[pid].latitude,
             sampling_points[pid].longitude)
            for pid in new_sequence
            if pid in sampling_points
        ]

        distance_matrix_all = build_distance_matrix(all_point_tuples)
        time_matrix_all = build_time_matrix(distance_matrix_all)
        cost_matrix_all = build_cost_matrix(distance_matrix_all)

        new_route = self._rebuild_route(
            new_sequence,
            sampling_points,
            distance_matrix_all,
            time_matrix_all,
            cost_matrix_all
        )

        return new_route