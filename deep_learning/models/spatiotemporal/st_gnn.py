"""时空图神经网络适配器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from .integration import SpatioTemporalSystemIntegrator


@dataclass
class STGNNResult:
    mean: np.ndarray
    variance: np.ndarray
    metadata: Dict[str, Any]


class STGNNPredictor:
    """基于现有 Stage-6 集成器提供时空 GNN 推理。"""

    def __init__(self, seed: int = 42) -> None:
        self.integrator = SpatioTemporalSystemIntegrator(seed=seed)

    def predict(
        self,
        coords: np.ndarray,
        series: np.ndarray,
        pred_horizon: int = 6,
        enable_gpu_acceleration: bool = False,
    ) -> STGNNResult:
        output = self.integrator.predict(
            model_type="stgcn",
            coords=np.asarray(coords, dtype=float),
            series=np.asarray(series, dtype=float),
            pred_horizon=int(pred_horizon),
            enable_gpu_acceleration=bool(enable_gpu_acceleration),
            enable_inference_acceleration=True,
        )
        return STGNNResult(
            mean=np.asarray(output.mean, dtype=float),
            variance=np.asarray(output.variance, dtype=float),
            metadata={
                "model_type": output.model_type,
                "source": output.source,
                "optimization": output.optimization or {},
            },
        )
