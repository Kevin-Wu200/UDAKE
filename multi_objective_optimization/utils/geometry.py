"""
几何计算工具
Geometry utility functions
"""

import numpy as np
from typing import List, Tuple, Union
from shapely.geometry import Point, Polygon, MultiPolygon, LineString


def calculate_distance(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    """
    计算两点之间的欧几里得距离

    Args:
        point1: 点1坐标 (x, y)
        point2: 点2坐标 (x, y)

    Returns:
        float: 距离
    """
    p1 = np.array(point1)
    p2 = np.array(point2)
    return np.linalg.norm(p1 - p2)


def calculate_distance_matrix(points: List[Tuple[float, float]]) -> np.ndarray:
    """
    计算点之间的距离矩阵

    Args:
        points: 点坐标列表

    Returns:
        np.ndarray: 距离矩阵
    """
    n = len(points)
    distance_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(n):
            if i != j:
                distance_matrix[i, j] = calculate_distance(points[i], points[j])

    return distance_matrix


def is_point_in_polygon(
    point: Tuple[float, float],
    polygon: Union[Polygon, List[Tuple[float, float]]]
) -> bool:
    """
    判断点是否在多边形内

    Args:
        point: 点坐标
        polygon: 多边形

    Returns:
        bool: 在多边形内返回True
    """
    point_geom = Point(point[0], point[1])

    if isinstance(polygon, (Polygon, MultiPolygon)):
        return polygon.contains(point_geom)
    else:
        polygon_geom = Polygon(polygon)
        return polygon_geom.contains(point_geom)


def filter_points_in_polygon(
    points: List[Tuple[float, float]],
    polygon: Union[Polygon, List[Tuple[float, float]]]
) -> List[Tuple[float, float]]:
    """
    过滤出在多边形内的点

    Args:
        points: 点坐标列表
        polygon: 多边形

    Returns:
        List[Tuple[float, float]]: 在多边形内的点
    """
    if isinstance(polygon, (Polygon, MultiPolygon)):
        polygon_geom = polygon
    else:
        polygon_geom = Polygon(polygon)

    filtered_points = []
    for point in points:
        point_geom = Point(point[0], point[1])
        if polygon_geom.contains(point_geom):
            filtered_points.append(point)

    return filtered_points


def calculate_polygon_area(polygon: Union[Polygon, List[Tuple[float, float]]]) -> float:
    """
    计算多边形面积

    Args:
        polygon: 多边形

    Returns:
        float: 面积
    """
    if isinstance(polygon, (Polygon, MultiPolygon)):
        return polygon.area
    else:
        polygon_geom = Polygon(polygon)
        return polygon_geom.area


def calculate_polygon_centroid(polygon: Union[Polygon, List[Tuple[float, float]]]) -> Tuple[float, float]:
    """
    计算多边形质心

    Args:
        polygon: 多边形

    Returns:
        Tuple[float, float]: 质心坐标
    """
    if isinstance(polygon, (Polygon, MultiPolygon)):
        centroid = polygon.centroid
        return (centroid.x, centroid.y)
    else:
        polygon_geom = Polygon(polygon)
        centroid = polygon_geom.centroid
        return (centroid.x, centroid.y)


def create_regular_polygon(
    center: Tuple[float, float],
    radius: float,
    n_sides: int = 6,
    rotation: float = 0.0
) -> List[Tuple[float, float]]:
    """
    创建正多边形

    Args:
        center: 中心坐标
        radius: 半径
        n_sides: 边数
        rotation: 旋转角度（弧度）

    Returns:
        List[Tuple[float, float]]: 多边形顶点坐标
    """
    vertices = []
    for i in range(n_sides):
        angle = 2 * np.pi * i / n_sides + rotation
        x = center[0] + radius * np.cos(angle)
        y = center[1] + radius * np.sin(angle)
        vertices.append((x, y))

    return vertices


def create_grid_points(
    bounds: Tuple[float, float, float, float],
    spacing: float
) -> List[Tuple[float, float]]:
    """
    创建网格点

    Args:
        bounds: 边界 (min_x, min_y, max_x, max_y)
        spacing: 网格间距

    Returns:
        List[Tuple[float, float]]: 网格点坐标
    """
    min_x, min_y, max_x, max_y = bounds

    x_coords = np.arange(min_x, max_x + spacing, spacing)
    y_coords = np.arange(min_y, max_y + spacing, spacing)

    points = []
    for y in y_coords:
        for x in x_coords:
            points.append((x, y))

    return points


def calculate_convex_hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    计算凸包

    Args:
        points: 点坐标列表

    Returns:
        List[Tuple[float, float]]: 凸包顶点坐标
    """
    from shapely.geometry import MultiPoint

    if len(points) < 3:
        return points

    multi_point = MultiPoint(points)
    convex_hull = multi_point.convex_hull

    if convex_hull.geom_type == 'Polygon':
        return list(convex_hull.exterior.coords)[:-1]  # 移除重复的起点
    else:
        return points


def calculate_minimum_bounding_rectangle(
    points: List[Tuple[float, float]]
) -> List[Tuple[float, float]]:
    """
    计算最小包围矩形

    Args:
        points: 点坐标列表

    Returns:
        List[Tuple[float, float]]: 矩形顶点坐标
    """
    from shapely.geometry import MultiPoint

    if len(points) < 2:
        return points

    multi_point = MultiPoint(points)
    min_rect = multi_point.minimum_rotated_rectangle

    if min_rect.geom_type == 'Polygon':
        return list(min_rect.exterior.coords)[:-1]
    else:
        return points


def calculate_buffer(
    point: Tuple[float, float],
    distance: float
) -> Polygon:
    """
    计算点的缓冲区

    Args:
        point: 点坐标
        distance: 缓冲距离

    Returns:
        Polygon: 缓冲区多边形
    """
    point_geom = Point(point[0], point[1])
    return point_geom.buffer(distance)


def interpolate_line(
    point1: Tuple[float, float],
    point2: Tuple[float, float],
    n_points: int
) -> List[Tuple[float, float]]:
    """
    在两点之间插值

    Args:
        point1: 起点
        point2: 终点
        n_points: 插值点数量

    Returns:
        List[Tuple[float, float]]: 插值点坐标
    """
    line = LineString([point1, point2])
    distances = np.linspace(0, 1, n_points)
    points = []

    for d in distances:
        point = line.interpolate(d, normalized=True)
        points.append((point.x, point.y))

    return points