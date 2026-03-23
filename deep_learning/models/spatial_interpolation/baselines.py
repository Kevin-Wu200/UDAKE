"""Traditional kriging-like baselines used as prior for neural models."""

from __future__ import annotations

import numpy as np


class OrdinaryKrigingBaseline:
    """Lightweight ordinary kriging baseline with IDW fallback."""

    def __init__(self, n_neighbors: int = 12) -> None:
        self.n_neighbors = max(1, int(n_neighbors))
        self.coords: np.ndarray | None = None
        self.values: np.ndarray | None = None

    def fit(self, coords: np.ndarray, values: np.ndarray) -> "OrdinaryKrigingBaseline":
        self.coords = np.asarray(coords, dtype=float)
        self.values = np.asarray(values, dtype=float).reshape(-1)
        return self

    def predict(self, query_coords: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.coords is None or self.values is None:
            raise ValueError("baseline is not fitted")

        q = np.asarray(query_coords, dtype=float)
        preds = np.zeros(len(q), dtype=float)
        vars_ = np.zeros(len(q), dtype=float)

        for i, point in enumerate(q):
            dist = np.sqrt(((self.coords - point) ** 2).sum(axis=1) + 1e-8)
            ids = np.argsort(dist)[: min(self.n_neighbors, len(dist))]
            d = dist[ids]
            w = 1.0 / d
            w = w / (w.sum() + 1e-12)
            local_vals = self.values[ids]
            preds[i] = np.sum(w * local_vals)
            vars_[i] = np.sum(w * (local_vals - preds[i]) ** 2)

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
