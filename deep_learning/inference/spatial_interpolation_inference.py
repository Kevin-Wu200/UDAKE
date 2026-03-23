"""Inference service for spatial interpolation neural models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from deep_learning.models.spatial_interpolation import (
    AttentionKrigingModel,
    GNNKrigingModel,
    ResidualKrigingModel,
)


@dataclass
class InferenceResult:
    mean: np.ndarray
    variance: np.ndarray


class SpatialInterpolationInference:
    def __init__(self) -> None:
        self.models = {
            "gnn": GNNKrigingModel(hidden_dim=16),
            "attention": AttentionKrigingModel(dim=24),
            "residual": ResidualKrigingModel(architecture="hybrid"),
        }

    def _get_model(self, model_type: Literal["gnn", "attention", "residual"]):
        if model_type not in self.models:
            raise ValueError(f"unsupported model type: {model_type}")
        return self.models[model_type]

    def predict_single(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coord: np.ndarray,
        model_type: Literal["gnn", "attention", "residual"] = "gnn",
    ) -> InferenceResult:
        return self.predict_batch(
            sample_coords=sample_coords,
            sample_values=sample_values,
            query_coords=np.asarray(query_coord, dtype=float).reshape(1, 2),
            model_type=model_type,
        )

    def predict_batch(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray,
        model_type: Literal["gnn", "attention", "residual"] = "gnn",
    ) -> InferenceResult:
        model = self._get_model(model_type)
        if model_type == "gnn":
            out = model.forward(sample_coords, sample_values, query_coords=query_coords)
        elif model_type == "attention":
            out = model.forward(sample_coords, sample_values, query_coords=query_coords)
        else:
            out = model.forward(sample_coords, sample_values, query_coords=query_coords)

        return InferenceResult(mean=np.asarray(out.mean, dtype=float), variance=np.asarray(out.variance, dtype=float))

    def predict_grid(
        self,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        x_bounds: tuple[float, float],
        y_bounds: tuple[float, float],
        grid_size: int = 20,
        model_type: Literal["gnn", "attention", "residual"] = "gnn",
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        xs = np.linspace(x_bounds[0], x_bounds[1], grid_size)
        ys = np.linspace(y_bounds[0], y_bounds[1], grid_size)
        mesh_x, mesh_y = np.meshgrid(xs, ys)
        query = np.stack([mesh_x.reshape(-1), mesh_y.reshape(-1)], axis=1)

        result = self.predict_batch(sample_coords, sample_values, query, model_type=model_type)
        return mesh_x, mesh_y, result.mean.reshape(grid_size, grid_size)
