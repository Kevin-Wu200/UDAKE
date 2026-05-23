"""增量时空克里金：在 IncrementalKriging 基础上扩展时间维度。"""

from __future__ import annotations

from datetime import datetime
from typing import List

import numpy as np

from ..models import DataPoint
from .incremental_kriging import IncrementalKriging


class IncrementalSTKriging(IncrementalKriging):
    """时空增量克里金子类。"""

    def __init__(
        self,
        *args,
        temporal_scale_seconds: float = 86400.0,
        temporal_weight: float = 0.5,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.temporal_scale_seconds = max(float(temporal_scale_seconds), 1.0)
        self.temporal_weight = float(np.clip(temporal_weight, 0.0, 1.0))

    def _point_timestamp(self, point: DataPoint) -> datetime:
        return point.timestamp or datetime.now()

    def _spatiotemporal_distance(self, a: DataPoint, b: DataPoint) -> float:
        spatial = float(np.hypot(a.x - b.x, a.y - b.y))
        ta = self._point_timestamp(a)
        tb = self._point_timestamp(b)
        temporal = abs((ta - tb).total_seconds()) / self.temporal_scale_seconds
        ws = 1.0 - self.temporal_weight
        wt = self.temporal_weight
        return float(np.sqrt((ws * spatial) ** 2 + (wt * temporal) ** 2))

    def _spatiotemporal_covariance(self, a: DataPoint, b: DataPoint) -> float:
        st_distance = self._spatiotemporal_distance(a, b)
        # 使用父类变异函数参数，将时空距离映射为协方差。
        return float(self.variogram._covariance_by_distance(st_distance))

    def _initialize_covariance_matrix(self) -> None:
        n = len(self.data_points)
        if n == 0:
            return

        k = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            for j in range(n):
                k[i, j] = self._spatiotemporal_covariance(self.data_points[i], self.data_points[j])

        self.covariance_matrix = k
        try:
            self.covariance_matrix_inv = np.linalg.inv(k)
        except np.linalg.LinAlgError:
            self.covariance_matrix_inv = np.linalg.pinv(k)

    def _incremental_update_matrix(self, new_point: DataPoint) -> None:
        if self.covariance_matrix_inv is None:
            return

        k_new = np.array(
            [self._spatiotemporal_covariance(new_point, point) for point in self.data_points],
            dtype=np.float64,
        ).reshape(-1)
        c_new = self._spatiotemporal_covariance(new_point, new_point)
        self.covariance_matrix_inv = self.sherman_morrison.add_row_col(self.covariance_matrix_inv, k_new, c_new)

    def incremental_update_st(self, new_points: List[DataPoint]) -> dict:
        """时空批量增量更新。"""
        if not new_points:
            return {"success": True, "updated_points": 0, "total_points": len(self.data_points)}

        updated = 0
        for point in new_points:
            self.incremental_update(point)
            updated += 1

        return {
            "success": True,
            "updated_points": updated,
            "total_points": len(self.data_points),
            "temporal_scale_seconds": self.temporal_scale_seconds,
            "temporal_weight": self.temporal_weight,
        }
