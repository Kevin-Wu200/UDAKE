"""分离时空模型。"""

from __future__ import annotations

from typing import Dict

import numpy as np

from .base_model import BaseSTModel


class SeparatedModel(BaseSTModel):
    """空间与时间项相加。"""

    name = "separated"

    def covariance(self, spatial_dist: np.ndarray, temporal_dist: np.ndarray, params: Dict[str, float]) -> np.ndarray:
        c_spatial, c_temporal = self._common_terms(spatial_dist, temporal_dist, params)
        nugget = float(params.get("nugget", 0.0))
        return c_spatial + c_temporal + nugget
