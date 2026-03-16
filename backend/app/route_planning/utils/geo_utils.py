"""
地理坐标工具函数
"""

import math
from typing import Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    计算从点1到点2的方位角

    Args:
        lat1: 第一个点的纬度
        lon1: 第一个点的经度
        lat2: 第二个点的纬度
        lon2: 第二个点的经度

    Returns:
        方位角（度，0-360）
    """
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


def calculate_midpoint(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
    """
    计算两点之间的中点

    Args:
        lat1: 第一个点的纬度
        lon1: 第一个点的经度
        lat2: 第二个点的纬度
        lon2: 第二个点的经度

    Returns:
        (中点纬度, 中点经度)
    """
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlon = lon2_rad - lon1_rad

    bx = math.cos(lat2_rad) * math.cos(dlon)
    by = math.cos(lat2_rad) * math.sin(dlon)

    lat_mid = math.atan2(
        math.sin(lat1_rad) + math.sin(lat2_rad),
        math.sqrt((math.cos(lat1_rad) + bx) ** 2 + by ** 2)
    )
    lon_mid = lon1_rad + math.atan2(by, math.cos(lat1_rad) + bx)

    return math.degrees(lat_mid), math.degrees(lon_mid)


def coordinate_to_utm(lat: float, lon: float) -> Tuple[float, float, int, str]:
    """
    将经纬度坐标转换为UTM坐标（简化版本）

    Args:
        lat: 纬度
        lon: 经度

    Returns:
        (东伪偏移量, 北伪偏移量, UTM带号, UTM分区)
    """
    # 简化的UTM转换，实际应用中建议使用pyproj库
    zone = int((lon + 180) / 6) + 1
    hemisphere = 'N' if lat >= 0 else 'S'

    # 简化计算（仅用于演示）
    x = (lon - (zone * 6 - 183)) * 111320  # 近似
    y = lat * 110540  # 近似

    return x, y, zone, hemisphere


def utm_to_coordinate(x: float, y: float, zone: int, hemisphere: str) -> Tuple[float, float]:
    """
    将UTM坐标转换为经纬度坐标（简化版本）

    Args:
        x: 东伪偏移量
        y: 北伪偏移量
        zone: UTM带号
        hemisphere: UTM分区（'N'或'S'）

    Returns:
        (纬度, 经度)
    """
    # 简化计算（仅用于演示）
    lon = x / 111320 + (zone * 6 - 183)
    lat = y / 110540

    return lat, lon


def bounding_box(center_lat: float, center_lon: float, radius: float) -> Tuple[float, float, float, float]:
    """
    计算以某点为中心的圆形区域的边界框

    Args:
        center_lat: 中心点纬度
        center_lon: 中心点经度
        radius: 半径（米）

    Returns:
        (最小纬度, 最大纬度, 最小经度, 最大经度)
    """
    R = 6371000  # 地球半径

    # 纬度偏移
    delta_lat = radius / R * (180 / math.pi)
    min_lat = center_lat - delta_lat
    max_lat = center_lat + delta_lat

    # 经度偏移（考虑纬度）
    delta_lon = radius / (R * math.cos(math.radians(center_lat))) * (180 / math.pi)
    min_lon = center_lon - delta_lon
    max_lon = center_lon + delta_lon

    return min_lat, max_lat, min_lon, max_lon


def point_in_polygon(point: Tuple[float, float], polygon: list) -> bool:
    """
    判断点是否在多边形内（射线法）

    Args:
        point: (纬度, 经度)
        polygon: [(纬度1, 经度1), (纬度2, 经度2), ...]

    Returns:
        是否在多边形内
    """
    x, y = point
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside