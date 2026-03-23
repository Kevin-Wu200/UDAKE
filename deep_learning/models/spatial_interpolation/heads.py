"""Prediction heads for interpolation and uncertainty."""

from __future__ import annotations

import numpy as np


def _softplus(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.exp(np.clip(x, -30.0, 30.0)))


class RegressionHead:
    def __init__(self, in_dim: int, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.weight = rng.normal(0.0, 0.1, size=(in_dim, 1))
        self.bias = np.zeros(1, dtype=float)

    def forward(self, features: np.ndarray) -> np.ndarray:
        return (features @ self.weight + self.bias).reshape(-1)


class UncertaintyHead:
    def __init__(self, in_dim: int, min_variance: float = 1e-4, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.weight = rng.normal(0.0, 0.1, size=(in_dim, 1))
        self.bias = np.zeros(1, dtype=float)
        self.min_variance = float(min_variance)

    def forward(self, features: np.ndarray) -> np.ndarray:
        raw = (features @ self.weight + self.bias).reshape(-1)
        return self.min_variance + _softplus(raw)


class MultiTaskHead:
    """Jointly predict mean/uncertainty and optional auxiliary signal."""

    def __init__(self, in_dim: int, with_aux: bool = True, seed: int = 42) -> None:
        self.regression = RegressionHead(in_dim=in_dim, seed=seed)
        self.uncertainty = UncertaintyHead(in_dim=in_dim, seed=seed + 1)
        self.with_aux = with_aux
        self.aux_head = RegressionHead(in_dim=in_dim, seed=seed + 2) if with_aux else None

    def forward(self, features: np.ndarray) -> dict[str, np.ndarray]:
        out = {
            "mean": self.regression.forward(features),
            "variance": self.uncertainty.forward(features),
        }
        if self.aux_head is not None:
            out["aux"] = self.aux_head.forward(features)
        return out
