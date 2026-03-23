"""Feature extraction utilities for spatial interpolation."""

from __future__ import annotations

import numpy as np


class SpatialFeatureExtractor:
    """Extract geometry-aware spatial features."""

    def extract(self, coords: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        radius = np.linalg.norm(c, axis=1, keepdims=True)
        angle = np.arctan2(c[:, 1], c[:, 0]).reshape(-1, 1)
        return np.concatenate([c, radius, angle], axis=1)


class CovarianceFeatureExtractor:
    """Extract local covariance statistics around each point."""

    def __init__(self, bandwidth: float = 0.2) -> None:
        self.bandwidth = max(float(bandwidth), 1e-6)

    def extract(self, coords: np.ndarray, values: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        diff = c[:, None, :] - c[None, :, :]
        dist = np.sqrt((diff * diff).sum(axis=-1) + 1e-12)
        kernel = np.exp(-(dist / self.bandwidth))
        kernel = kernel / (kernel.sum(axis=1, keepdims=True) + 1e-12)

        local_mean = kernel @ v
        local_var = np.sum(kernel * ((v[None, :] - local_mean[:, None]) ** 2), axis=1)
        return np.stack([local_mean, local_var], axis=1)


class TrendFeatureExtractor:
    """Linear trend extractor z = ax + by + c."""

    def __init__(self) -> None:
        self.coefficients: np.ndarray | None = None

    def fit(self, coords: np.ndarray, values: np.ndarray) -> "TrendFeatureExtractor":
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        design = np.concatenate([c, np.ones((len(c), 1), dtype=float)], axis=1)
        coef, *_ = np.linalg.lstsq(design, v, rcond=None)
        self.coefficients = coef
        return self

    def extract(self, coords: np.ndarray, values: np.ndarray | None = None) -> np.ndarray:
        if self.coefficients is None:
            raise ValueError("TrendFeatureExtractor must be fitted before extract")
        c = np.asarray(coords, dtype=float)
        design = np.concatenate([c, np.ones((len(c), 1), dtype=float)], axis=1)
        trend = design @ self.coefficients
        if values is None:
            residual = np.zeros_like(trend)
        else:
            residual = np.asarray(values, dtype=float).reshape(-1) - trend
        return np.stack([trend, residual], axis=1)
