"""时空 Transformer 推理适配器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np

from .integration import SpatioTemporalSystemIntegrator


@dataclass
class STTransformerResult:
    mean: np.ndarray
    variance: np.ndarray
    metadata: Dict[str, Any]


class STTransformerPredictor:
    """复用 Stage-6 集成器执行时空 Transformer 推理。"""

    def __init__(self, seed: int = 42) -> None:
        self.integrator = SpatioTemporalSystemIntegrator(seed=seed)

    def predict(self, coords: np.ndarray, series: np.ndarray, pred_horizon: int = 6) -> STTransformerResult:
        output = self.integrator.predict(
            model_type="st_transformer",
            coords=np.asarray(coords, dtype=float),
            series=np.asarray(series, dtype=float),
            pred_horizon=int(pred_horizon),
            enable_inference_acceleration=True,
        )
        return STTransformerResult(
            mean=np.asarray(output.mean, dtype=float),
            variance=np.asarray(output.variance, dtype=float),
            metadata={
                "source": output.source,
                "optimization": output.optimization or {},
            },
        )
