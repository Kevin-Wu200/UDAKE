"""时空不确定性量化适配器。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal

import numpy as np

from .integration import SpatioTemporalSystemIntegrator

UncertaintyMethod = Literal["mc_dropout", "deep_ensemble", "bayesian", "bnn"]


@dataclass
class STUncertaintyResult:
    mean: np.ndarray
    variance: np.ndarray
    confidence_low: np.ndarray
    confidence_high: np.ndarray
    metadata: Dict[str, Any]


class STUncertaintyQuantifier:
    """调用统一时空集成器并附加置信区间。"""

    def __init__(self, seed: int = 42) -> None:
        self.integrator = SpatioTemporalSystemIntegrator(seed=seed)

    def quantify(
        self,
        coords: np.ndarray,
        series: np.ndarray,
        pred_horizon: int = 6,
        method: UncertaintyMethod = "mc_dropout",
    ) -> STUncertaintyResult:
        output = self.integrator.predict(
            model_type="st_transformer",
            coords=np.asarray(coords, dtype=float),
            series=np.asarray(series, dtype=float),
            pred_horizon=int(pred_horizon),
            uncertainty_method=method,
            enable_inference_acceleration=True,
        )
        mean = np.asarray(output.mean, dtype=float)
        var = np.maximum(np.asarray(output.variance, dtype=float), 1e-9)
        std = np.sqrt(var)
        low = mean - 1.96 * std
        high = mean + 1.96 * std
        return STUncertaintyResult(
            mean=mean,
            variance=var,
            confidence_low=low,
            confidence_high=high,
            metadata={
                "uncertainty_method": output.uncertainty_method,
                "source": output.source,
                "optimization": output.optimization or {},
            },
        )
