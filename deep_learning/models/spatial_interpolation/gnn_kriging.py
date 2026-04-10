"""GNN-Kriging model: graph neural prior fusion for spatial interpolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .attention import MultiScaleAttention
from .baselines import UniversalKrigingBaseline
from .feature_extractors import CovarianceFeatureExtractor, SpatialFeatureExtractor, TrendFeatureExtractor
from .graph_builder import SpatialGraphBuilder
from .graph_layers import EdgeConvLayer, GATLayer, GCNLayer
from .heads import MultiTaskHead
from .losses import combined_spatial_loss
from .position_encoding import LearnablePositionEncoding, sinusoidal_position_encoding


@dataclass
class GNNKrigingOutput:
    mean: np.ndarray
    variance: np.ndarray
    residual: np.ndarray
    adjacency: np.ndarray


class GNNKrigingModel:
    """Numpy-based GNN-Kriging model with residual learning over kriging prior."""

    def __init__(self, hidden_dim: int = 16, graph_strategy: str = "knn", seed: int = 42) -> None:
        self.hidden_dim = max(4, int(hidden_dim))
        self.graph_strategy = graph_strategy
        self.seed = seed

        self.graph_builder = SpatialGraphBuilder(default_k=8, default_radius=0.25)
        self.spatial_extractor = SpatialFeatureExtractor()
        self.cov_extractor = CovarianceFeatureExtractor(bandwidth=0.2)
        self.trend_extractor = TrendFeatureExtractor()
        self.pos_encoder = LearnablePositionEncoding(dim=8, seed=seed)

        self.feature_dim = 4 + 2 + 2 + 12 + 8 + 2
        self.gcn = GCNLayer(self.feature_dim, self.hidden_dim, seed=seed)
        self.gat = GATLayer(self.feature_dim, self.hidden_dim, heads=4, seed=seed + 1)
        self.edge_conv = EdgeConvLayer(self.feature_dim, self.hidden_dim, seed=seed + 2)

        rng = np.random.default_rng(seed)
        self.proj = rng.normal(0.0, 0.08, size=(self.hidden_dim * 3, self.hidden_dim))
        self.attention = MultiScaleAttention(dim=self.hidden_dim, heads=4, seed=seed + 3)
        self.head = MultiTaskHead(in_dim=self.hidden_dim, with_aux=True, seed=seed + 4)

        self.kriging_prior = UniversalKrigingBaseline()
        self.residual_gain = 1.0
        self.bias = 0.0

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

    def _build_query_covariance_feature(
        self,
        query_coords: np.ndarray,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
    ) -> np.ndarray:
        diff = query_coords[:, None, :] - sample_coords[None, :, :]
        dist = np.sqrt((diff * diff).sum(axis=-1) + 1e-12)
        kernel = np.exp(-dist / 0.2)
        kernel = kernel / (kernel.sum(axis=1, keepdims=True) + 1e-12)
        local_mean = kernel @ sample_values
        centered = sample_values[None, :] - local_mean[:, None]
        local_var = np.sum(kernel * (centered ** 2), axis=1)
        return np.stack([local_mean, local_var], axis=1)

    def _build_features(
        self,
        query_coords: np.ndarray,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        prior_mean: np.ndarray,
        prior_var: np.ndarray,
    ) -> np.ndarray:
        spatial = self.spatial_extractor.extract(query_coords)
        cov_feat = self._build_query_covariance_feature(query_coords, sample_coords, sample_values)

        self.trend_extractor.fit(sample_coords, sample_values)
        trend = self.trend_extractor.extract(query_coords)

        sin_pos = sinusoidal_position_encoding(query_coords, dim=12)
        learnable_pos = self.pos_encoder.encode(query_coords)
        prior_feat = np.stack([prior_mean, prior_var], axis=1)

        return np.concatenate([spatial, cov_feat, trend, sin_pos, learnable_pos, prior_feat], axis=1)

    def forward(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray | None = None,
    ) -> GNNKrigingOutput:
        samples, values, queries = self._validate_inputs(sample_coords, sample_values, query_coords)

        self.kriging_prior.fit(samples, values)
        prior_mean, prior_var = self.kriging_prior.predict(queries)

        features = self._build_features(queries, samples, values, prior_mean, prior_var)

        graph = self.graph_builder.build(
            coords=queries,
            values=prior_mean,
            strategy=self.graph_strategy if self.graph_strategy in {"knn", "radius", "voronoi", "delaunay"} else "knn",
            weight_mode="hybrid",
        )

        x_gcn = self.gcn.forward(features, graph.adjacency)
        x_gat = self.gat.forward(features, graph.edge_index, n_nodes=len(queries))
        x_edge = self.edge_conv.forward(features, graph.edge_index, n_nodes=len(queries))

        fused = np.concatenate([x_gcn, x_gat, x_edge], axis=1)
        projected = np.maximum(0.0, fused @ self.proj)
        attended = self.attention.forward(projected)

        head_out = self.head.forward(attended)
        residual_raw = head_out["mean"]
        residual = self.residual_gain * residual_raw + self.bias
        pred_mean = prior_mean + residual
        pred_var = np.maximum(prior_var + np.abs(head_out["variance"]), 1e-6)

        return GNNKrigingOutput(mean=pred_mean, variance=pred_var, residual=residual, adjacency=graph.adjacency)

    def preprocess_gnn_kriging_data(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        *,
        query_coords: np.ndarray | None = None,
        batch_size: int | None = None,
        use_runtime_stats: bool = True,
    ) -> dict[str, Any]:
        samples, values, queries = self._validate_inputs(sample_coords, sample_values, query_coords)
        self.kriging_prior.fit(samples, values)
        prior_mean, prior_var = self.kriging_prior.predict(queries)
        features = self._build_features(queries, samples, values, prior_mean, prior_var)

        graph = self.graph_builder.build(
            coords=queries,
            values=prior_mean,
            strategy=self.graph_strategy if self.graph_strategy in {"knn", "radius", "voronoi", "delaunay"} else "knn",
            weight_mode="hybrid",
        )

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
        feature_names = [
            "coord_x",
            "coord_y",
            "radius",
            "angle",
            "local_mean",
            "local_var",
            "trend_bias",
            "trend_x",
            "sin_pos_0",
            "sin_pos_1",
            "sin_pos_2",
            "sin_pos_3",
            "sin_pos_4",
            "sin_pos_5",
            "sin_pos_6",
            "sin_pos_7",
            "sin_pos_8",
            "sin_pos_9",
            "sin_pos_10",
            "sin_pos_11",
            "learn_pos_0",
            "learn_pos_1",
            "learn_pos_2",
            "learn_pos_3",
            "learn_pos_4",
            "learn_pos_5",
            "learn_pos_6",
            "learn_pos_7",
            "prior_mean",
            "prior_var",
        ]

        return {
            "sample_coords": samples,
            "sample_values": values,
            "query_coords": queries,
            "feature_matrix": features.astype(float),
            "processed_features": processed.astype(float),
            "feature_names": feature_names[: processed.shape[1]],
            "prior_mean": prior_mean.astype(float).tolist(),
            "prior_variance": prior_var.astype(float).tolist(),
            "adjacency_matrix": graph.adjacency.astype(float),
            "edge_index": graph.edge_index.astype(int),
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
        preprocessed = self.preprocess_gnn_kriging_data(
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
                "graph_strategy": self.graph_strategy,
                "sample_count": int(samples.shape[0]),
                "query_count": int(queries.shape[0]),
                "adjacency_density": float(np.mean(out.adjacency > 0)),
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
            comp = combined_spatial_loss(
                y_pred=out.mean,
                y_true=targets,
                y_var=out.variance,
                adjacency=out.adjacency,
                min_value=float(np.min(values) - 1.0),
                max_value=float(np.max(values) + 1.0),
                monotonic_axis=coords[:, 0],
            )
            losses.append(comp["total"])

            err = out.mean - targets
            grad_bias = float(np.mean(err))
            grad_gain = float(np.mean(err * out.residual))
            self.bias -= lr * grad_bias
            self.residual_gain -= lr * grad_gain

        return float(np.mean(losses) if losses else 0.0)

    def val_step(self, batch: list[dict[str, Any]]) -> float:
        losses: list[float] = []
        for sample in batch:
            coords = np.asarray(sample["coords"], dtype=float)
            values = np.asarray(sample["values"], dtype=float).reshape(-1)
            targets = np.asarray(sample.get("targets", values), dtype=float).reshape(-1)
            out = self.forward(coords, values, query_coords=coords)
            losses.append(float(np.mean(np.abs(out.mean - targets))))
        return float(np.mean(losses) if losses else 0.0)

    def get_state(self) -> dict[str, float]:
        return {"bias": float(self.bias), "residual_gain": float(self.residual_gain)}

    def load_state(self, state: dict[str, Any]) -> None:
        self.bias = float(state.get("bias", 0.0))
        self.residual_gain = float(state.get("residual_gain", 1.0))
