"""Traditional kriging-like baselines used as prior for neural models."""

from __future__ import annotations

import numpy as np

from .spatial_index import SpatialIndex


class OrdinaryKrigingBaseline:
    """Lightweight ordinary kriging baseline with IDW fallback."""

    def __init__(self, n_neighbors: int = 12) -> None:
        self.n_neighbors = max(1, int(n_neighbors))
        self.coords: np.ndarray | None = None
        self.values: np.ndarray | None = None
        self._spatial_index: SpatialIndex | None = None

    def fit(self, coords: np.ndarray, values: np.ndarray) -> "OrdinaryKrigingBaseline":
        self.coords = np.asarray(coords, dtype=float)
        self.values = np.asarray(values, dtype=float).reshape(-1)
        self._spatial_index = SpatialIndex(self.coords)
        return self

    def predict(self, query_coords: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.coords is None or self.values is None or self._spatial_index is None:
            raise ValueError("baseline is not fitted")

        q = np.asarray(query_coords, dtype=float)
        k = min(self.n_neighbors, int(self.coords.shape[0]))
        knn = self._spatial_index.query_knn(q, k=k, exclude_self=False)
        ids = np.asarray(knn.indices, dtype=int)
        d = np.maximum(np.asarray(knn.distances, dtype=float), 1e-8)
        local_vals = self.values[ids]

        w = 1.0 / d
        w = w / (np.sum(w, axis=1, keepdims=True) + 1e-12)
        preds = np.sum(w * local_vals, axis=1)
        vars_ = np.sum(w * (local_vals - preds[:, None]) ** 2, axis=1)

        return preds, np.maximum(vars_, 1e-6)


class UniversalKrigingBaseline(OrdinaryKrigingBaseline):
    """Universal kriging baseline with linear trend + residual interpolation."""

    def __init__(self, n_neighbors: int = 12) -> None:
        super().__init__(n_neighbors=n_neighbors)
        self.trend_coef: np.ndarray | None = None
        self.residual_baseline = OrdinaryKrigingBaseline(n_neighbors=n_neighbors)

    def fit(self, coords: np.ndarray, values: np.ndarray) -> "UniversalKrigingBaseline":
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        design = np.concatenate([c, np.ones((len(c), 1), dtype=float)], axis=1)
        coef, *_ = np.linalg.lstsq(design, v, rcond=None)
        trend = design @ coef
        residual = v - trend

        self.coords = c
        self.values = v
        self.trend_coef = coef
        self.residual_baseline.fit(c, residual)
        return self

    def predict(self, query_coords: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.trend_coef is None or self.coords is None:
            raise ValueError("baseline is not fitted")

        q = np.asarray(query_coords, dtype=float)
        design = np.concatenate([q, np.ones((len(q), 1), dtype=float)], axis=1)
        trend = design @ self.trend_coef
        residual_mean, residual_var = self.residual_baseline.predict(q)
        return trend + residual_mean, np.maximum(residual_var, 1e-6)
