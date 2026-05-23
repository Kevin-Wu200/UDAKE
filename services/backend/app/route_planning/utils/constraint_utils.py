"""
约束条件检查工具函数
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from ..models import PlannedRoute, RouteConstraint, SamplingPoint


def check_time_window_constraint(route: PlannedRoute,
                                sampling_points: Dict[str, SamplingPoint]) -> Tuple[bool, List[str]]:
    """
    检查时间窗约束

    Args:
        route: 规划路径
        sampling_points: 采样点字典

    Returns:
        (是否满足, 违反的约束列表)
    """
    violations = []

    if not route.start_time:
        violations.append("缺少开始时间")
        return False, violations

    current_time = route.start_time

    for i, point_id in enumerate(route.point_sequence):
        point = sampling_points.get(point_id)

        if not point:
            continue

        if point.time_window_start and point.time_window_end:
            # 解析时间窗
            window_start = parse_time(point.time_window_start)
            window_end = parse_time(point.time_window_end)

            arrival_time = current_time

            # 检查是否在时间窗内
            if not (window_start <= arrival_time.time() <= window_end):
                violations.append(
                    f"采样点{point_id}违反时间窗："
                    f"到达时间{arrival_time.strftime('%H:%M')}，"
                    f"时间窗{point.time_window_start}-{point.time_window_end}"
                )

        # 更新当前时间（增加服务时间）
        if i < len(route.segments):
            current_time += timedelta(seconds=route.segments[i].duration)
        current_time += timedelta(minutes=point.service_time)

    is_valid = len(violations) == 0
    return is_valid, violations


def check_distance_constraint(route: PlannedRoute,
                              max_distance: float) -> Tuple[bool, float]:
    """
    检查距离约束

    Args:
        route: 规划路径
        max_distance: 最大距离

    Returns:
        (是否满足, 实际距离)
    """
    is_valid = route.total_distance <= max_distance
    return is_valid, route.total_distance


def check_duration_constraint(route: PlannedRoute,
                               max_duration: float) -> Tuple[bool, float]:
    """
    检查时间约束

    Args:
        route: 规划路径
        max_duration: 最大时间

    Returns:
        (是否满足, 实际时间)
    """
    is_valid = route.total_duration <= max_duration
    return is_valid, route.total_duration


def check_cost_constraint(route: PlannedRoute,
                          max_cost: float) -> Tuple[bool, float]:
    """
    检查成本约束

    Args:
        route: 规划路径
        max_cost: 最大成本

    Returns:
        (是否满足, 实际成本)
    """
    is_valid = route.total_cost <= max_cost
    return is_valid, route.total_cost


def check_priority_constraint(route: PlannedRoute,
                              sampling_points: Dict[str, SamplingPoint]) -> Tuple[bool, List[str]]:
    """
    检查优先级约束（高优先级采样点应尽早访问）

    Args:
        route: 规划路径
        sampling_points: 采样点字典

    Returns:
        (是否满足, 违反的约束列表)
    """
    violations = []

    # 获取路径中所有采样点的优先级
    point_priorities = []
    for point_id in route.point_sequence:
        point = sampling_points.get(point_id)
        if point:
            point_priorities.append((point_id, point.priority))

    # 检查优先级顺序
    for i in range(1, len(point_priorities)):
        prev_id, prev_priority = point_priorities[i - 1]
        curr_id, curr_priority = point_priorities[i]

        # 如果后一个点的优先级比前一个高，记录警告
        if curr_priority > prev_priority:
            violations.append(
                f"优先级顺序问题：{curr_id}(优先级{curr_priority})在{prev_id}(优先级{prev_priority})之后访问"
            )

    is_valid = len(violations) == 0
    return is_valid, violations


def check_all_constraints(route: PlannedRoute,
                          sampling_points: Dict[str, SamplingPoint],
                          constraints: RouteConstraint) -> Tuple[bool, Dict[str, Any]]:
    """
    检查所有约束条件

    Args:
        route: 规划路径
        sampling_points: 采样点字典
        constraints: 约束条件

    Returns:
        (是否满足所有约束, 详细信息)
    """
    details = {
        'is_valid': True,
        'violations': [],
        'constraint_results': {}
    }

    # 检查距离约束
    if constraints.max_distance:
        is_valid, actual = check_distance_constraint(route, constraints.max_distance)
        details['constraint_results']['distance'] = {
            'is_valid': is_valid,
            'constraint': constraints.max_distance,
            'actual': actual
        }
        if not is_valid:
            details['is_valid'] = False
            details['violations'].append(
                f"距离约束：{actual:.2f}米超过最大值{constraints.max_distance:.2f}米"
            )

    # 检查时间约束
    if constraints.max_duration:
        is_valid, actual = check_duration_constraint(route, constraints.max_duration)
        details['constraint_results']['duration'] = {
            'is_valid': is_valid,
            'constraint': constraints.max_duration,
            'actual': actual
        }
        if not is_valid:
            details['is_valid'] = False
            details['violations'].append(
                f"时间约束：{actual:.2f}秒超过最大值{constraints.max_duration:.2f}秒"
            )

    # 检查成本约束
    if constraints.max_cost:
        is_valid, actual = check_cost_constraint(route, constraints.max_cost)
        details['constraint_results']['cost'] = {
            'is_valid': is_valid,
            'constraint': constraints.max_cost,
            'actual': actual
        }
        if not is_valid:
            details['is_valid'] = False
            details['violations'].append(
                f"成本约束：{actual:.2f}超过最大值{constraints.max_cost:.2f}"
            )

    # 检查时间窗约束
    if constraints.time_windows:
        is_valid, violations = check_time_window_constraint(route, sampling_points)
        details['constraint_results']['time_windows'] = {
            'is_valid': is_valid,
            'violations': violations
        }
        if not is_valid:
            details['is_valid'] = False
            details['violations'].extend(violations)

    # 检查优先级约束
    if constraints.priority_constraint:
        is_valid, violations = check_priority_constraint(route, sampling_points)
        details['constraint_results']['priority'] = {
            'is_valid': is_valid,
            'violations': violations
        }
        if not is_valid:
            details['is_valid'] = False
            details['violations'].extend(violations)

    return details['is_valid'], details


def parse_time(time_str: str) -> datetime.time:
    """
    解析时间字符串

    Args:
        time_str: 时间字符串 (HH:MM)

    Returns:
        datetime.time对象
    """
    parts = time_str.split(':')
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return datetime.time(hour, minute)


def calculate_arrival_times(route: PlannedRoute,
                            sampling_points: Dict[str, SamplingPoint],
                            start_time: datetime) -> Dict[str, datetime]:
    """
    计算到达每个采样点的时间

    Args:
        route: 规划路径
        sampling_points: 采样点字典
        start_time: 开始时间

    Returns:
        {采样点ID: 到达时间}
    """
    arrival_times = {}
    current_time = start_time

    for i, point_id in enumerate(route.point_sequence):
        arrival_times[point_id] = current_time

        point = sampling_points.get(point_id)
        if point:
            # 增加服务时间
            current_time += timedelta(minutes=point.service_time)

        # 增加路段时间
        if i < len(route.segments):
            current_time += timedelta(seconds=route.segments[i].duration)

    return arrival_times


def is_reachable(point: SamplingPoint,
                 current_location: Tuple[float, float],
                 max_distance: float = 10000) -> bool:
    """
    检查采样点是否可达

    Args:
        point: 采样点
        current_location: 当前位置 (lat, lon)
        max_distance: 最大可达距离

    Returns:
        是否可达
    """
    from .geo_utils import haversine_distance

    distance = haversine_distance(
        current_location[0], current_location[1],
        point.latitude, point.longitude
    )

    return distance <= max_distance and point.is_reachable
