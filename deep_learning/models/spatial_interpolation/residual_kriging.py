"""Residual-Kriging model with feature engineering and multi-branch residual nets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .baselines import OrdinaryKrigingBaseline, UniversalKrigingBaseline
from .spatial_index import SpatialIndex


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
        self._feature_index: SpatialIndex | None = None
        self._feature_index_key: tuple[int, int, int] | None = None

    @staticmethod
    def _validate_inputs(
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        samples = np.asarray(sample_coords, dtype=float)
        values = np.asarray(sample_values, dtype=float).reshape(-1)
        queries = np.asarray(query_coords, dtype=float) if query_coords is not None else samples

        if samples.ndim != 2 or samples.shape[1] != 2:
            raise ValueError("sample_coords must be [[x, y], ...]")
        if queries.ndim != 2 or queries.shape[1] != 2:
            raise ValueError("query_coords must be [[x, y], ...]")
        if samples.shape[0] != values.shape[0]:
            raise ValueError("sample_coords and sample_values length mismatch")
        if samples.shape[0] < 2:
            raise ValueError("at least 2 sample points are required")
        if not np.isfinite(samples).all() or not np.isfinite(queries).all() or not np.isfinite(values).all():
            raise ValueError("coords and values must be finite")
        return samples, values, queries

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
        if len(q_coords) == 0:
            return np.zeros((0, 8), dtype=float)

        index = self._get_or_build_index(s_coords)
        k_val = min(max(1, int(k)), int(s_coords.shape[0]))
        knn = index.query_knn(q_coords, k=k_val, exclude_self=False)
        ids = np.asarray(knn.indices, dtype=int)
        local_dist = np.asarray(knn.distances, dtype=float)
        local_vals = s_vals[ids]
        local_diff = s_coords[ids] - q_coords[:, None, :]

        mean_dist = np.mean(local_dist, axis=1)
        std_dist = np.std(local_dist, axis=1)
        direction = np.mean(local_diff / (local_dist[:, :, None] + 1e-12), axis=1)
        local_max_dist = np.maximum(np.max(local_dist, axis=1), 1e-6)
        density = k_val / (np.pi * (local_max_dist**2))

        local_mean = np.mean(local_vals, axis=1, keepdims=True)
        centered = local_vals - local_mean
        local_std = np.std(local_vals, axis=1, keepdims=True) + 1e-12
        z = centered / local_std
        skew = np.mean(z**3, axis=1)
        kurt = np.mean(z**4, axis=1)

        return np.stack(
            [
                mean_dist,
                std_dist,
                direction[:, 0],
                direction[:, 1],
                density,
                skew,
                kurt,
                np.asarray(prior_mean, dtype=float).reshape(-1),
            ],
            axis=1,
        ).astype(float)

    def _get_or_build_index(self, sample_coords: np.ndarray) -> SpatialIndex:
        coords = np.asarray(sample_coords, dtype=float)
        key = (int(coords.shape[0]), int(coords.shape[1]), hash(coords.tobytes()))
        if self._feature_index is not None and self._feature_index_key == key:
            return self._feature_index
        self._feature_index = SpatialIndex(coords)
        self._feature_index_key = key
        return self._feature_index

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
        if len(q) == 0:
            return np.zeros((0,), dtype=float)
        dist = np.sqrt(np.sum((q[:, None, :] - q[None, :, :]) ** 2, axis=2) + 1e-12)
        w = np.exp(-dist / 0.15)
        w = w / (np.sum(w, axis=1, keepdims=True) + 1e-12)
        return (w @ x) - x

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
        s_coords, s_vals, q_coords = self._validate_inputs(sample_coords, sample_values, query_coords)

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

    def preprocess_residual_kriging_data(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        *,
        query_coords: np.ndarray | None = None,
        batch_size: int | None = None,
        use_runtime_stats: bool = True,
    ) -> dict[str, Any]:
        samples, values, queries = self._validate_inputs(sample_coords, sample_values, query_coords)
        self.baseline.fit(samples, values)
        prior_mean, prior_var = self.baseline.predict(queries)

        features = self._feature_engineering(samples, values, queries, prior_mean, k=8)
        feature_names = [
            "mean_neighbor_distance",
            "std_neighbor_distance",
            "direction_x",
            "direction_y",
            "local_density",
            "value_skewness",
            "value_kurtosis",
            "prior_mean",
        ]

        if use_runtime_stats:
            mean = features.mean(axis=0, keepdims=True)
            std = features.std(axis=0, keepdims=True) + 1e-6
            processed = (features - mean) / std
            scaler = {
                "mean": mean.reshape(-1).astype(float).tolist(),
                "std": std.reshape(-1).astype(float).tolist(),
                "source": "runtime",
            }
        else:
            processed = features.copy()
            scaler = {
                "mean": np.zeros((features.shape[1],), dtype=float).tolist(),
                "std": np.ones((features.shape[1],), dtype=float).tolist(),
                "source": "identity",
            }

        size = int(max(1, batch_size or len(queries)))
        slices = [[int(i), int(min(i + size, len(queries)))] for i in range(0, len(queries), size)]
        return {
            "sample_coords": samples,
            "sample_values": values,
            "query_coords": queries,
            "feature_matrix": features.astype(float),
            "processed_features": processed.astype(float),
            "feature_names": feature_names[: processed.shape[1]],
            "prior_mean": prior_mean.astype(float).tolist(),
            "prior_variance": prior_var.astype(float).tolist(),
            "batch_slices": slices,
            "scaler": scaler,
            "validation": {
                "is_valid": bool(np.isfinite(processed).all()),
                "n_samples": int(samples.shape[0]),
                "n_queries": int(queries.shape[0]),
                "batch_size": size,
            },
        }

    def predict_standard(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        *,
        query_coords: np.ndarray | None = None,
        confidence_z: float = 1.96,
    ) -> dict[str, Any]:
        samples, values, queries = self._validate_inputs(sample_coords, sample_values, query_coords)
        preprocessed = self.preprocess_residual_kriging_data(
            sample_coords=samples,
            sample_values=values,
            query_coords=queries,
            use_runtime_stats=True,
        )
        out = self.forward(sample_coords=samples, sample_values=values, query_coords=queries)
        std = np.sqrt(np.maximum(out.variance, 1e-9))
        z = max(0.0, float(confidence_z))
        lower = out.mean - z * std
        upper = out.mean + z * std
        return {
            "prediction": out.mean.astype(float).tolist(),
            "variance": out.variance.astype(float).tolist(),
            "residual": out.residual.astype(float).tolist(),
            "uncertainty": std.astype(float).tolist(),
            "confidence_interval": {
                "z_score": z,
                "lower": lower.astype(float).tolist(),
                "upper": upper.astype(float).tolist(),
            },
            "details": {
                "architecture": self.architecture,
                "sample_count": int(samples.shape[0]),
                "query_count": int(queries.shape[0]),
            },
            "preprocess": {
                "feature_names": list(preprocessed["feature_names"]),
                "batch_slices": list(preprocessed["batch_slices"]),
                "validation": dict(preprocessed["validation"]),
            },
        }

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
