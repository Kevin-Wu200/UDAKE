"""不确定性聚合、分解与可视化数据生成。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import ensure_1d, ensure_2d


@dataclass
class AggregationResult:
    mean: np.ndarray
    variance: np.ndarray
    method: str


class UncertaintyAggregator:
    def variance_aggregation(self, means: np.ndarray, variances: np.ndarray) -> AggregationResult:
        m = ensure_2d(means)
        v = np.maximum(ensure_2d(variances), 1e-8)
        pred_mean = np.mean(m, axis=0)
        aleatoric = np.mean(v, axis=0)
        epistemic = np.var(m, axis=0)
        total = np.maximum(aleatoric + epistemic, 1e-8)
        return AggregationResult(mean=pred_mean, variance=total, method="variance")

    def quantile_aggregation(self, means: np.ndarray, lower_q: float = 10.0, upper_q: float = 90.0) -> dict[str, np.ndarray]:
        m = ensure_2d(means)
        return {
            "q_low": np.percentile(m, float(np.clip(lower_q, 0.0, 100.0)), axis=0),
            "q_med": np.percentile(m, 50.0, axis=0),
            "q_high": np.percentile(m, float(np.clip(upper_q, 0.0, 100.0)), axis=0),
        }

    def bayesian_model_average(
        self,
        means: np.ndarray,
        variances: np.ndarray,
        model_weights: np.ndarray | list[float] | None = None,
    ) -> AggregationResult:
        m = ensure_2d(means)
        v = np.maximum(ensure_2d(variances), 1e-8)
        if m.shape != v.shape:
            raise ValueError("means 与 variances 形状不一致")

        n_models = m.shape[0]
        if model_weights is None:
            w = np.ones(n_models, dtype=float) / n_models
        else:
            w = ensure_1d(model_weights)
            if len(w) != n_models:
                raise ValueError("权重长度与模型数量不一致")
            w = np.maximum(w, 1e-8)
            w = w / np.sum(w)

        mean = np.sum(m * w[:, None], axis=0)
        aleatoric = np.sum(v * w[:, None], axis=0)
        epistemic = np.sum(((m - mean[None, :]) ** 2) * w[:, None], axis=0)
        total = np.maximum(aleatoric + epistemic, 1e-8)
        return AggregationResult(mean=mean, variance=total, method="bma")

    def decompose_uncertainty(self, means: np.ndarray, variances: np.ndarray) -> dict[str, np.ndarray]:
        m = ensure_2d(means)
        v = np.maximum(ensure_2d(variances), 1e-8)
        aleatoric = np.mean(v, axis=0)
        epistemic = np.var(m, axis=0)
        total = np.maximum(aleatoric + epistemic, 1e-8)
        return {
            "aleatoric": aleatoric,
            "epistemic": epistemic,
            "total": total,
        }

    def spatial_uncertainty_decomposition(self, coords: np.ndarray, uncertainty: np.ndarray, k: int = 6) -> dict[str, np.ndarray]:
        c = ensure_2d(coords)
        u = ensure_1d(uncertainty)
        if len(c) != len(u):
            raise ValueError("coords 与 uncertainty 长度不一致")

        diff = c[:, None, :] - c[None, :, :]
        dist = np.sqrt(np.sum(diff ** 2, axis=-1) + 1e-12)
        order = np.argsort(dist, axis=1)
        kk = int(max(1, min(k, len(c) - 1 if len(c) > 1 else 1)))
        idx = order[:, 1 : kk + 1] if len(c) > 1 else np.zeros((len(c), 1), dtype=int)

        local_mean = np.mean(u[idx], axis=1)
        local_std = np.std(u[idx], axis=1)
        residual = u - local_mean
        return {
            "local_mean": local_mean,
            "local_std": local_std,
            "spatial_residual": residual,
        }

    def temporal_uncertainty_decomposition(self, sequence: np.ndarray, window: int = 5) -> dict[str, np.ndarray]:
        arr = ensure_1d(sequence)
        w = int(max(2, min(window, len(arr))))
        trend = np.zeros_like(arr)
        for i in range(len(arr)):
            left = max(0, i - w + 1)
            trend[i] = np.mean(arr[left : i + 1])
        residual = arr - trend
        return {
            "trend": trend,
            "residual": residual,
        }

    def visualization_payload(
        self,
        coords: np.ndarray,
        mean: np.ndarray,
        variance: np.ndarray,
        bins: int = 20,
    ) -> dict[str, Any]:
        c = ensure_2d(coords)
        m = ensure_1d(mean)
        v = np.maximum(ensure_1d(variance), 1e-8)
        if len(c) != len(m) or len(c) != len(v):
            raise ValueError("coords/mean/variance 长度不一致")

        hist_y, hist_x = np.histogram(m, bins=int(max(5, bins)), density=True)
        return {
            "uncertainty_map": [
                {"x": float(x), "y": float(y), "mean": float(mu), "variance": float(var)}
                for (x, y), mu, var in zip(c, m, v)
            ],
            "confidence_interval": {
                "mean": m.tolist(),
                "std": np.sqrt(v).tolist(),
            },
            "density": {
                "x": hist_x.tolist(),
                "y": hist_y.tolist(),
            },
        }
