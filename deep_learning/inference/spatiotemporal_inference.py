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
    uncertainty_method: str = "model_variance"
    optimization: dict | None = None


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
        uncertainty_method: str | None = None,
        enable_memory_optimization: bool = False,
        enable_gpu_acceleration: bool = False,
        enable_inference_acceleration: bool = True,
        enable_long_sequence_optimization: bool = False,
        long_sequence_chunk: int = 48,
    ) -> SpatioTemporalInferenceResult:
        out = self.integrator.predict(
            model_type=model_type,
            coords=np.asarray(coords, dtype=float),
            series=np.asarray(series, dtype=float),
            pred_horizon=pred_horizon,
            fusion_strategy=fusion_strategy,
            uncertainty_method=uncertainty_method,
            enable_memory_optimization=enable_memory_optimization,
            enable_gpu_acceleration=enable_gpu_acceleration,
            enable_inference_acceleration=enable_inference_acceleration,
            enable_long_sequence_optimization=enable_long_sequence_optimization,
            long_sequence_chunk=long_sequence_chunk,
        )
        return SpatioTemporalInferenceResult(
            mean=out.mean,
            variance=out.variance,
            source=out.source,
            uncertainty_method=out.uncertainty_method,
            optimization=out.optimization,
        )

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
