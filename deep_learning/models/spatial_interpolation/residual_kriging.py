"""Residual-Kriging model with feature engineering and multi-branch residual nets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .baselines import OrdinaryKrigingBaseline, UniversalKrigingBaseline


@dataclass
class ResidualKrigingOutput:
    mean: np.ndarray
    variance: np.ndarray
    residual: np.ndarray


class ResidualKrigingModel:
    """Residual learning on top of kriging baseline using MLP/CNN/Hybrid branches."""

    def __init__(
        self,
        architecture: Literal["mlp", "cnn", "hybrid"] = "hybrid",
        baseline: Literal["ordinary", "universal"] = "universal",
        seed: int = 42,
    ) -> None:
        self.architecture = architecture
        self.seed = seed

        self.baseline = UniversalKrigingBaseline() if baseline == "universal" else OrdinaryKrigingBaseline()

        rng = np.random.default_rng(seed)
        self.mlp_w1 = rng.normal(0.0, 0.08, size=(8, 12))
        self.mlp_w2 = rng.normal(0.0, 0.08, size=(12, 1))
        self.res_scale = 1.0
        self.bias = 0.0

    def _feature_engineering(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray,
        prior_mean: np.ndarray,
        k: int,
    ) -> np.ndarray:
        s_coords = np.asarray(sample_coords, dtype=float)
        s_vals = np.asarray(sample_values, dtype=float).reshape(-1)
        q_coords = np.asarray(query_coords, dtype=float)

        features = np.zeros((len(q_coords), 8), dtype=float)
        for i, q in enumerate(q_coords):
            diff = s_coords - q[None, :]
            dist = np.sqrt((diff * diff).sum(axis=1) + 1e-12)
            ids = np.argsort(dist)[: min(k, len(dist))]
            local_dist = dist[ids]
            local_vals = s_vals[ids]
            local_diff = diff[ids]

            mean_dist = float(np.mean(local_dist))
            std_dist = float(np.std(local_dist))
            direction = np.mean(local_diff / (local_dist[:, None] + 1e-12), axis=0)
            density = float(len(ids) / (np.pi * (max(local_dist.max(), 1e-6) ** 2)))

            centered = local_vals - np.mean(local_vals)
            std = float(np.std(local_vals) + 1e-12)
            skew = float(np.mean((centered / std) ** 3))
            kurt = float(np.mean((centered / std) ** 4))

            features[i] = np.array(
                [
                    mean_dist,
                    std_dist,
                    direction[0],
                    direction[1],
                    density,
                    skew,
                    kurt,
                    float(prior_mean[i]),
                ],
                dtype=float,
            )

        return features

    def _mlp_branch(self, features: np.ndarray) -> np.ndarray:
        hidden = np.maximum(0.0, features @ self.mlp_w1)
        # ResNet-style skip: add projected prior feature to hidden path.
        hidden = hidden + np.repeat(features[:, -1:].astype(float), hidden.shape[1], axis=1) * 0.01
        # Dense-like concatenation effect through feature averaging.
        dense_mix = 0.9 * hidden + 0.1 * np.repeat(hidden.mean(axis=1, keepdims=True), hidden.shape[1], axis=1)
        return (dense_mix @ self.mlp_w2).reshape(-1)

    def _cnn_branch(self, features: np.ndarray, query_coords: np.ndarray) -> np.ndarray:
        # Grid-style local smoothing branch for residual approximation.
        x = features[:, -1]
        q = np.asarray(query_coords, dtype=float)
        out = np.zeros_like(x)
        for i, point in enumerate(q):
            dist = np.sqrt(((q - point) ** 2).sum(axis=1) + 1e-12)
            w = np.exp(-dist / 0.15)
            w = w / (w.sum() + 1e-12)
            out[i] = float(np.sum(w * x)) - x[i]
        return out

    def _multi_scale_fusion(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray,
        prior_mean: np.ndarray,
    ) -> np.ndarray:
        feat_small = self._feature_engineering(sample_coords, sample_values, query_coords, prior_mean, k=4)
        feat_large = self._feature_engineering(sample_coords, sample_values, query_coords, prior_mean, k=12)

        mlp_small = self._mlp_branch(feat_small)
        mlp_large = self._mlp_branch(feat_large)
        return 0.6 * mlp_small + 0.4 * mlp_large

    def forward(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray,
    ) -> ResidualKrigingOutput:
        s_coords = np.asarray(sample_coords, dtype=float)
        s_vals = np.asarray(sample_values, dtype=float).reshape(-1)
        q_coords = np.asarray(query_coords, dtype=float)

        self.baseline.fit(s_coords, s_vals)
        prior_mean, prior_var = self.baseline.predict(q_coords)

        features = self._feature_engineering(s_coords, s_vals, q_coords, prior_mean, k=8)
        residual_mlp = self._mlp_branch(features)
        residual_cnn = self._cnn_branch(features, q_coords)
        residual_multi_scale = self._multi_scale_fusion(s_coords, s_vals, q_coords, prior_mean)

        if self.architecture == "mlp":
            residual = residual_mlp
        elif self.architecture == "cnn":
            residual = residual_cnn
        else:
            residual = 0.45 * residual_mlp + 0.25 * residual_cnn + 0.30 * residual_multi_scale

        residual = self.res_scale * residual + self.bias
        mean = prior_mean + residual
        variance = np.maximum(prior_var + np.abs(residual) * 0.1, 1e-6)
        return ResidualKrigingOutput(mean=mean, variance=variance, residual=residual)

    def train_step(self, batch: list[dict[str, Any]], lr: float = 1e-2, mixed_precision: bool = False) -> float:
        del mixed_precision
        losses: list[float] = []

        for sample in batch:
            coords = np.asarray(sample["coords"], dtype=float)
            values = np.asarray(sample["values"], dtype=float).reshape(-1)
            targets = np.asarray(sample.get("targets", values), dtype=float).reshape(-1)

            out = self.forward(coords, values, query_coords=coords)
            err = out.mean - targets

            # residual loss + regularization + consistency
            residual_loss = float(np.mean(err ** 2))
            reg_loss = float(1e-3 * (np.mean(self.mlp_w1 ** 2) + np.mean(self.mlp_w2 ** 2)))
            consistency = float(np.mean((out.residual[1:] - out.residual[:-1]) ** 2)) if len(out.residual) > 1 else 0.0
            total = residual_loss + reg_loss + 0.1 * consistency
            losses.append(total)

            self.bias -= lr * float(np.mean(err))
            self.res_scale -= lr * float(np.mean(err * out.residual))

        return float(np.mean(losses) if losses else 0.0)

    def val_step(self, batch: list[dict[str, Any]]) -> float:
        vals: list[float] = []
        for sample in batch:
            coords = np.asarray(sample["coords"], dtype=float)
            values = np.asarray(sample["values"], dtype=float).reshape(-1)
            targets = np.asarray(sample.get("targets", values), dtype=float).reshape(-1)
            out = self.forward(coords, values, query_coords=coords)
            vals.append(float(np.mean(np.abs(out.mean - targets))))
        return float(np.mean(vals) if vals else 0.0)

    def get_state(self) -> dict[str, float]:
        return {"bias": float(self.bias), "res_scale": float(self.res_scale)}

    def load_state(self, state: dict[str, Any]) -> None:
        self.bias = float(state.get("bias", 0.0))
        self.res_scale = float(state.get("res_scale", 1.0))
