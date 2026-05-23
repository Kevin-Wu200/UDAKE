"""
3D距离计算模块
支持欧氏距离、方向距离、各向异性距离
"""
from typing import Optional, Tuple

import numpy as np


class Distance3D:
    """3D距离计算器"""

    @staticmethod
    def euclidean(p1: np.ndarray, p2: np.ndarray) -> np.ndarray:
        """
        3D欧氏距离
        p1, p2: shape (n, 3) 或 (3,)
        """
        diff = p1 - p2
        return np.sqrt(np.sum(diff ** 2, axis=-1))

    @staticmethod
    def euclidean_matrix(points: np.ndarray) -> np.ndarray:
        """
        计算所有点对之间的欧氏距离矩阵
        points: shape (n, 3)
        返回: shape (n, n)
        """
        n = len(points)
        dist = np.zeros((n, n))
        for i in range(n):
            diff = points[i] - points[i + 1:]
            dist[i, i + 1:] = np.sqrt(np.sum(diff ** 2, axis=1))
        dist += dist.T
        return dist

    @staticmethod
    def anisotropic_matrix(
        points: np.ndarray,
        ratio_xy: float = 1.0,
        ratio_xz: float = 1.0,
        angle_xy: float = 0.0,
        angle_xz: float = 0.0,
        angle_yz: float = 0.0
    ) -> np.ndarray:
        """
        各向异性距离矩阵
        通过坐标变换实现各向异性
        """
        transformed = Distance3D._anisotropic_transform(
            points, ratio_xy, ratio_xz, angle_xy, angle_xz, angle_yz
        )
        return Distance3D.euclidean_matrix(transformed)

    @staticmethod
    def _anisotropic_transform(
        points: np.ndarray,
        ratio_xy: float,
        ratio_xz: float,
        angle_xy: float,
        angle_xz: float,
        angle_yz: float
    ) -> np.ndarray:
        """
        各向异性坐标变换
        使用三个旋转角度和两个各向异性比进行变换
        """
        rad_xy = np.radians(angle_xy)
        rad_xz = np.radians(angle_xz)
        rad_yz = np.radians(angle_yz)

        # Z轴旋转（XY平面）
        Rz = np.array([
            [np.cos(rad_xy), -np.sin(rad_xy), 0],
            [np.sin(rad_xy), np.cos(rad_xy), 0],
            [0, 0, 1]
        ])
        # Y轴旋转（XZ平面）
        Ry = np.array([
            [np.cos(rad_xz), 0, np.sin(rad_xz)],
            [0, 1, 0],
            [-np.sin(rad_xz), 0, np.cos(rad_xz)]
        ])
        # X轴旋转（YZ平面）
        Rx = np.array([
            [1, 0, 0],
            [0, np.cos(rad_yz), -np.sin(rad_yz)],
            [0, np.sin(rad_yz), np.cos(rad_yz)]
        ])

        # 组合旋转
        R = Rz @ Ry @ Rx

        # 各向异性缩放
        S = np.diag([1.0, 1.0 / ratio_xy, 1.0 / ratio_xz])

        # 变换矩阵
        T = S @ R

        return (T @ points.T).T

    @staticmethod
    def directional_distance(
        points: np.ndarray,
        azimuth: float,
        dip: float,
        tolerance: float = 22.5,
        bandwidth: Optional[float] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        方向距离计算（用于方向变异函数）
        azimuth: 方位角（度，从北顺时针）
        dip: 倾角（度，从水平面向下）
        tolerance: 角度容差（度）
        bandwidth: 带宽限制
        返回: (距离矩阵, 有效对掩码)
        """
        n = len(points)
        az_rad = np.radians(azimuth)
        dip_rad = np.radians(dip)

        # 方向向量
        direction = np.array([
            np.sin(az_rad) * np.cos(dip_rad),
            np.cos(az_rad) * np.cos(dip_rad),
            -np.sin(dip_rad)
        ])

        tol_rad = np.radians(tolerance)
        dist_matrix = np.zeros((n, n))
        mask = np.zeros((n, n), dtype=bool)

        for i in range(n):
            for j in range(i + 1, n):
                diff = points[j] - points[i]
                d = np.linalg.norm(diff)
                if d < 1e-10:
                    continue

                unit_diff = diff / d
                cos_angle = abs(np.dot(unit_diff, direction))
                cos_angle = min(cos_angle, 1.0)
                angle = np.arccos(cos_angle)

                if angle <= tol_rad:
                    if bandwidth is None or (d * np.sin(angle) <= bandwidth):
                        dist_matrix[i, j] = d
                        dist_matrix[j, i] = d
                        mask[i, j] = True
                        mask[j, i] = True

        return dist_matrix, mask
