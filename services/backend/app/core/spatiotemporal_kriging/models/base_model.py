"""时空协方差模型基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

import numpy as np


class BaseSTModel(ABC):
    """时空模型抽象基类。"""

    name: str = "base"

    @abstractmethod
    def covariance(self, spatial_dist: np.ndarray, temporal_dist: np.ndarray, params: Dict[str, float]) -> np.ndarray:
        """计算协方差矩阵。"""

    @staticmethod
    def _common_terms(spatial_dist: np.ndarray, temporal_dist: np.ndarray, params: Dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
        spatial_sill = float(params.get("spatial_sill", 1.0))
        spatial_range = max(float(params.get("spatial_range", 1.0)), 1e-8)
        temporal_sill = float(params.get("temporal_sill", 1.0))
        temporal_range = max(float(params.get("temporal_range", 1.0)), 1e-8)
        c_spatial = spatial_sill * np.exp(-spatial_dist / spatial_range)
        c_temporal = temporal_sill * np.exp(-temporal_dist / temporal_range)
        return c_spatial, c_temporal
