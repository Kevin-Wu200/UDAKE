"""乘积时空模型。"""

from __future__ import annotations

from typing import Dict

import numpy as np

from .base_model import BaseSTModel


class ProductModel(BaseSTModel):
    """空间项与时间项相乘。"""

    name = "product"

    def covariance(self, spatial_dist: np.ndarray, temporal_dist: np.ndarray, params: Dict[str, float]) -> np.ndarray:
        c_spatial, c_temporal = self._common_terms(spatial_dist, temporal_dist, params)
        return c_spatial * c_temporal
