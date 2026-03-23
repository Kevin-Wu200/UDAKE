"""Online prediction and update for spatiotemporal models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class OnlineUpdateResult:
    updated_steps: int
    mean_loss: float
    strategy: str


class OnlineSpatioTemporalPredictor:
    def sliding_window_predict(
        self,
        model: Any,
        coords: np.ndarray,
        long_series: np.ndarray,
        window_size: int = 24,
        pred_horizon: int = 6,
        step_size: int = 1,
    ) -> dict[str, Any]:
        s = np.asarray(long_series, dtype=float)
        if s.ndim != 3:
            raise ValueError("long_series must be [n_nodes, total_steps, n_features]")

        windows: list[dict[str, Any]] = []
        for start in range(0, s.shape[1] - window_size - pred_horizon + 1, max(1, step_size)):
            seq = s[:, start : start + window_size, :]
            target = s[:, start + window_size : start + window_size + pred_horizon, 0]
            out = model.forward(coords=coords, series=seq)
            windows.append(
                {
                    "start": int(start),
                    "prediction": out.mean,
                    "variance": out.variance,
                    "target": target,
                }
            )
        return {"windows": windows, "count": len(windows)}

    def robust_predict(
        self,
        model: Any,
        coords: np.ndarray,
        series: np.ndarray,
        anomaly_threshold: float = 3.0,
    ) -> dict[str, Any]:
        s = np.asarray(series, dtype=float)
        out = model.forward(coords=coords, series=s)
        pred = np.asarray(out.mean, dtype=float)

        med = np.median(pred)
        mad = np.median(np.abs(pred - med)) + 1e-8
        score = np.abs(pred - med) / mad
        clipped = np.where(score > anomaly_threshold, med + np.sign(pred - med) * anomaly_threshold * mad, pred)

        return {
            "prediction": clipped,
            "variance": out.variance,
            "anomaly_score": score,
        }


class OnlineModelUpdater:
    def online_learning(
        self,
        model: Any,
        stream_batches: list[dict[str, np.ndarray]],
        update_interval: int = 1,
        lr: float = 0.01,
    ) -> OnlineUpdateResult:
        losses: list[float] = []
        updated = 0
        interval = max(1, int(update_interval))

        for i, batch in enumerate(stream_batches):
            if i % interval != 0:
                continue
            loss = float(model.train_step([batch], lr=lr))
            losses.append(loss)
            updated += 1

        return OnlineUpdateResult(
            updated_steps=updated,
            mean_loss=float(np.mean(losses)) if losses else 0.0,
            strategy="online_learning",
        )

    def incremental_training(self, model: Any, new_data: list[dict[str, np.ndarray]], steps: int = 5, lr: float = 0.01) -> OnlineUpdateResult:
        losses: list[float] = []
        for _ in range(max(1, steps)):
            losses.append(float(model.train_step(new_data, lr=lr)))
        return OnlineUpdateResult(
            updated_steps=max(1, steps),
            mean_loss=float(np.mean(losses)),
            strategy="incremental_training",
        )

    def fine_tune(self, model: Any, recent_data: list[dict[str, np.ndarray]], strategy: str = "light") -> OnlineUpdateResult:
        strategy_map = {
            "light": (2, 0.008),
            "standard": (4, 0.012),
            "aggressive": (8, 0.02),
        }
        steps, lr = strategy_map.get(strategy, strategy_map["light"])
        return self.incremental_training(model=model, new_data=recent_data, steps=steps, lr=lr)
