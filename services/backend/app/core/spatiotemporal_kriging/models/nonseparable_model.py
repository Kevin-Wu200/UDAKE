"""非分离时空模型。"""

from __future__ import annotations

from typing import Dict

import numpy as np

from .base_model import BaseSTModel


class NonseparableModel(BaseSTModel):
    """引入耦合系数的非分离协方差。"""

    name = "nonseparable"

    def covariance(self, spatial_dist: np.ndarray, temporal_dist: np.ndarray, params: Dict[str, float]) -> np.ndarray:
        c_spatial, c_temporal = self._common_terms(spatial_dist, temporal_dist, params)
        coupling = max(float(params.get("coupling", 0.5)), 1e-8)
        beta = max(float(params.get("beta", 1.2)), 1e-8)
        coupled = np.exp(-((spatial_dist * temporal_dist) / coupling) ** beta)
        return (c_spatial + c_temporal) * coupled
