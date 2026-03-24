"""Realtime interpolation integration for stage-6 spatiotemporal models."""

from __future__ import annotations

from typing import Any

import numpy as np

from deep_learning.models.spatiotemporal import SpatioTemporalSystemIntegrator, SpatioTemporalTrainingConfig


class RealtimeSpatioTemporalService:
    """在 realtime_interpolation 中复用阶段6时空预测能力。"""

    def __init__(self) -> None:
        self.integrator = SpatioTemporalSystemIntegrator(cache_ttl_seconds=120)

    def _validate_inputs(
        self,
        coords: list[list[float]] | np.ndarray,
        series: list[list[list[float]]] | np.ndarray,
        pred_horizon: int,
    ) -> tuple[np.ndarray, np.ndarray, int]:
        c = np.asarray(coords, dtype=float)
        s = np.asarray(series, dtype=float)
        h = int(max(1, pred_horizon))
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be [[x, y], ...]")
        if s.ndim != 3:
            raise ValueError("series must be [n_nodes, seq_len, n_features]")
        if s.shape[0] != c.shape[0]:
            raise ValueError("coords and series node count mismatch")
        if s.shape[1] < max(4, h):
            raise ValueError("series length is too short")
        return c, s, h

    def train(
        self,
        model_type: str,
        coords: list[list[float]] | np.ndarray,
        series: list[list[list[float]]] | np.ndarray,
        targets: list[list[float]] | np.ndarray | None = None,
        epochs: int = 20,
        pred_horizon: int = 6,
    ) -> dict[str, Any]:
        if model_type not in {"st_transformer", "gcn_lstm", "convlstm", "stgcn"}:
            raise ValueError("model_type must be one of st_transformer/gcn_lstm/convlstm/stgcn")
        c, s, h = self._validate_inputs(coords, series, pred_horizon)

        if targets is None:
            y = s[:, -h:, 0]
            x = s[:, :-h, :]
        else:
            y = np.asarray(targets, dtype=float)
            if y.ndim != 2 or y.shape[0] != c.shape[0] or y.shape[1] != h:
                raise ValueError("targets must be [n_nodes, pred_horizon]")
            x = s

        sample = {
            "coords": c,
            "series": x,
            "targets": y,
            "adjacency": np.ones((len(c), len(c)), dtype=float) - np.eye(len(c), dtype=float),
        }
        dataset = [sample for _ in range(8)]
        result = self.integrator.train(
            model_type=model_type,  # type: ignore[arg-type]
            train_dataset=dataset[:6],
            val_dataset=dataset[6:],
            config=SpatioTemporalTrainingConfig(
                seq_len=int(x.shape[1]),
                pred_horizon=h,
                max_epochs=max(5, int(epochs)),
                learning_rate=0.02,
                warmup_epochs=3,
                early_stopping_patience=5,
                gradient_clip_norm=1.0,
            ),
        )
        return {
            "model_type": model_type,
            "training": result["training"],
            "monitor": result["monitor"],
        }

    def predict(
        self,
        model_type: str,
        coords: list[list[float]] | np.ndarray,
        series: list[list[list[float]]] | np.ndarray,
        pred_horizon: int = 6,
        fusion_strategy: str = "gating",
        uncertainty_method: str | None = None,
        enable_memory_optimization: bool = True,
        enable_gpu_acceleration: bool = False,
        enable_inference_acceleration: bool = True,
        enable_long_sequence_optimization: bool = False,
        long_sequence_chunk: int = 48,
    ) -> dict[str, Any]:
        if model_type not in {"st_transformer", "gcn_lstm", "convlstm", "stgcn"}:
            raise ValueError("model_type must be one of st_transformer/gcn_lstm/convlstm/stgcn")
        c, s, h = self._validate_inputs(coords, series, pred_horizon)

        out = self.integrator.predict(
            model_type=model_type,  # type: ignore[arg-type]
            coords=c,
            series=s,
            pred_horizon=h,
            fusion_strategy=fusion_strategy,
            uncertainty_method=uncertainty_method,
            enable_memory_optimization=bool(enable_memory_optimization),
            enable_gpu_acceleration=bool(enable_gpu_acceleration),
            enable_inference_acceleration=bool(enable_inference_acceleration),
            enable_long_sequence_optimization=bool(enable_long_sequence_optimization),
            long_sequence_chunk=max(8, int(long_sequence_chunk)),
        )

        return {
            "model_type": model_type,
            "prediction": out.mean.tolist(),
            "variance": out.variance.tolist(),
            "source": out.source,
            "uncertainty_method": out.uncertainty_method,
            "optimization": out.optimization,
        }
