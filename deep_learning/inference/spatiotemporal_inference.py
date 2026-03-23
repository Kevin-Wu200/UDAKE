"""Inference service for stage-6 spatiotemporal forecasting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from deep_learning.models.spatiotemporal import SpatioTemporalSystemIntegrator


@dataclass
class SpatioTemporalInferenceResult:
    mean: np.ndarray
    variance: np.ndarray
    source: str


class SpatioTemporalInference:
    def __init__(self) -> None:
        self.integrator = SpatioTemporalSystemIntegrator(cache_ttl_seconds=120)

    def predict_batch(
        self,
        coords: np.ndarray,
        series: np.ndarray,
        model_type: Literal["st_transformer", "gcn_lstm", "convlstm", "stgcn"] = "st_transformer",
        pred_horizon: int = 6,
        fusion_strategy: str = "gating",
    ) -> SpatioTemporalInferenceResult:
        out = self.integrator.predict(
            model_type=model_type,
            coords=np.asarray(coords, dtype=float),
            series=np.asarray(series, dtype=float),
            pred_horizon=pred_horizon,
            fusion_strategy=fusion_strategy,
        )
        return SpatioTemporalInferenceResult(mean=out.mean, variance=out.variance, source=out.source)

    def predict_realtime(
        self,
        coords: np.ndarray,
        long_series: np.ndarray,
        model_type: Literal["st_transformer", "gcn_lstm", "convlstm", "stgcn"] = "st_transformer",
        window_size: int = 24,
        pred_horizon: int = 6,
    ) -> dict:
        return self.integrator.realtime_predict_and_update(
            model_type=model_type,
            coords=np.asarray(coords, dtype=float),
            long_series=np.asarray(long_series, dtype=float),
            window_size=window_size,
            pred_horizon=pred_horizon,
            update_interval=1,
            strategy="standard",
        )
