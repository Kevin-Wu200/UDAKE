"""
路径处理工具函数
"""

import math
from typing import List, Tuple, Dict, Any
from ..models import SamplingPoint, PlannedRoute, RouteSegment


def build_distance_matrix(points: List[Tuple[str, float, float]]) -> List[List[float]]:
    """
    构建距离矩阵

    Args:
        points: [(id, lat, lon), ...]

    Returns:
        距离矩阵
    """
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j:
                _, lat1, lon1 = points[i]
                _, lat2, lon2 = points[j]
                # 使用Haversine距离
                R = 6371000  # 地球半径（米）
                lat1_rad = math.radians(lat1)
                lat2_rad = math.radians(lat2)
                delta_lat = math.radians(lat2 - lat1)
                delta_lon = math.radians(lon2 - lon1)
                a = (math.sin(delta_lat / 2) ** 2 +
                     math.cos(lat1_rad) * math.cos(lat2_rad) *
                     math.sin(delta_lon / 2) ** 2)
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                matrix[i][j] = R * c

    return matrix


def build_time_matrix(distance_matrix: List[List[float]],
                     average_speed: float = 30.0) -> List[List[float]]:
    """
    构建时间矩阵

    Args:
        distance_matrix: 距离矩阵（米）
        average_speed: 平均速度（km/h）

    Returns:
        时间矩阵（秒）
    """
    speed_mps = average_speed * 1000 / 3600  # 转换为米/秒
    n = len(distance_matrix)
    time_matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if distance_matrix[i][j] > 0:
                time_matrix[i][j] = distance_matrix[i][j] / speed_mps

    return time_matrix


def build_cost_matrix(distance_matrix: List[List[float]],
                     cost_per_km: float = 2.0) -> List[List[float]]:
    """
    构建成本矩阵

    Args:
        distance_matrix: 距离矩阵（米）
        cost_per_km: 每公里成本

    Returns:
        成本矩阵
    """
    n = len(distance_matrix)
    cost_matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if distance_matrix[i][j] > 0:
                cost_matrix[i][j] = distance_matrix[i][j] / 1000 * cost_per_km

    return cost_matrix


def calculate_route_statistics(route: PlannedRoute) -> Dict[str, Any]:
    """
    计算路径统计信息

    Args:
        route: 规划路径对象

    Returns:
        统计信息字典
    """
    stats = {
        'total_distance': route.total_distance,
        'total_duration': route.total_duration,
        'total_cost': route.total_cost,
        'num_points': len(route.point_sequence),
        'num_segments': len(route.segments),
        'average_segment_distance': 0,
        'average_segment_duration': 0,
        'average_segment_cost': 0,
        'longest_segment': 0,
        'shortest_segment': float('inf')
    }

    if route.segments:
        distances = [seg.distance for seg in route.segments]
        durations = [seg.duration for seg in route.segments]
        costs = [seg.cost for seg in route.segments]

        stats['average_segment_distance'] = sum(distances) / len(distances)
        stats['average_segment_duration'] = sum(durations) / len(durations)
        stats['average_segment_cost'] = sum(costs) / len(costs)
        stats['longest_segment'] = max(distances)
        stats['shortest_segment'] = min(distances)

    return stats


def validate_route(route: PlannedRoute,
                  sampling_points: List[SamplingPoint]) -> Tuple[bool, List[str]]:
    """
    验证路径的有效性

    Args:
        route: 规划路径对象
        sampling_points: 采样点列表

    Returns:
        (是否有效, 错误信息列表)
    """
    errors = []

    # 检查路径是否为空
    if not route.point_sequence:
        errors.append("路径为空")
        return False, errors

    # 检查路径段数量
    expected_segments = len(route.point_sequence) - 1
    if len(route.segments) != expected_segments:
        errors.append(f"路径段数量不匹配：预期{expected_segments}，实际{len(route.segments)}")

    # 检查路径段连续性
    for i, segment in enumerate(route.segments):
        expected_from = route.point_sequence[i]
        expected_to = route.point_sequence[i + 1]

        if segment.from_point_id != expected_from:
            errors.append(f"路径段{i}起点不匹配：预期{expected_from}，实际{segment.from_point_id}")

        if segment.to_point_id != expected_to:
            errors.append(f"路径段{i}终点不匹配：预期{expected_to}，实际{segment.to_point_id}")

    # 检查所有采样点是否都被访问
    point_ids = {point.id for point in sampling_points}
    visited_ids = set(route.point_sequence)

    if not point_ids.issubset(visited_ids):
        missing = point_ids - visited_ids
        errors.append(f"未访问的采样点：{missing}")

    # 检查路径总距离
    calculated_distance = sum(seg.distance for seg in route.segments)
    if abs(calculated_distance - route.total_distance) > 1.0:  # 允许1米误差
        errors.append(f"路径总距离不匹配：计算{calculated_distance}，记录{route.total_distance}")

    # 检查路径总时间
    calculated_duration = sum(seg.duration for seg in route.segments)
    if abs(calculated_duration - route.total_duration) > 1.0:  # 允许1秒误差
        errors.append(f"路径总时间不匹配：计算{calculated_duration}，记录{route.total_duration}")

    # 检查路径总成本
    calculated_cost = sum(seg.cost for seg in route.segments)
    if abs(calculated_cost - route.total_cost) > 0.01:  # 允许0.01误差
        errors.append(f"路径总成本不匹配：计算{calculated_cost}，记录{route.total_cost}")

    is_valid = len(errors) == 0
    return is_valid, errors


def calculate_route_distance(route: List[Tuple[float, float]]) -> float:
    """
    计算路径的总距离

    Args:
        route: [(lat1, lon1), (lat2, lon2), ...]

    Returns:
        总距离（米）
    """
    total_distance = 0.0

    for i in range(len(route) - 1):
        lat1, lon1 = route[i]
        lat2, lon2 = route[i + 1]

        # Haversine距离
        R = 6371000
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        total_distance += distance

    return total_distance


def simplify_route(route: List[Tuple[float, float]], tolerance: float = 10.0) -> List[Tuple[float, float]]:
    """
    使用Douglas-Peucker算法简化路径

    Args:
        route: 原始路径点列表
        tolerance: 容差（米）

    Returns:
        简化后的路径点列表
    """
    if len(route) <= 2:
        return route

    # 找到最大距离点
    max_distance = 0
    max_index = 0
    start, end = route[0], route[-1]

    for i in range(1, len(route) - 1):
        distance = perpendicular_distance(route[i], start, end)
        if distance > max_distance:
            max_distance = distance
            max_index = i

    # 递归简化
    if max_distance > tolerance:
        left = simplify_route(route[:max_index + 1], tolerance)
        right = simplify_route(route[max_index:], tolerance)
        return left[:-1] + right
    else:
        return [start, end]


def perpendicular_distance(point: Tuple[float, float],
                          line_start: Tuple[float, float],
                          line_end: Tuple[float, float]) -> float:
    """
    计算点到线段的垂直距离

    Args:
        point: 点坐标
        line_start: 线段起点
        line_end: 线段终点

    Returns:
        垂直距离（米）
    """
    # 使用Haversine距离的简化版本
    lat, lon = point
    lat1, lon1 = line_start
    lat2, lon2 = line_end

    # 将经纬度转换为平面坐标（简化）
    x = lon
    y = lat
    x1 = lon1
    y1 = lat1
    x2 = lon2
    y2 = lat2

    # 计算点到直线的距离
    if x1 == x2:  # 垂直线
        return abs(x - x1) * 111320  # 近似转换

    if y1 == y2:  # 水平线
        return abs(y - y1) * 110540  # 近似转换

    # 斜线
    A = y2 - y1
    B = x1 - x2
    C = x2 * y1 - x1 * y2

    distance = abs(A * x + B * y + C) / math.sqrt(A ** 2 + B ** 2)

    # 转换为米（近似）
    return distance * 110000