"""Position encoding blocks for spatial interpolation models."""

from __future__ import annotations

import numpy as np


def sinusoidal_position_encoding(coords: np.ndarray, dim: int = 16, base: float = 10000.0) -> np.ndarray:
    if dim <= 0:
        raise ValueError("dim must be positive")
    c = np.asarray(coords, dtype=float)
    if c.ndim != 2 or c.shape[1] != 2:
        raise ValueError("coords must be [N, 2]")

    n = c.shape[0]
    out = np.zeros((n, dim), dtype=float)
    half = dim // 2

    for axis in range(2):
        for i in range(half // 2):
            denom = base ** (2.0 * i / max(1, half))
            idx = axis * (half // 2) * 2 + i * 2
            if idx + 1 >= dim:
                break
            out[:, idx] = np.sin(c[:, axis] / denom)
            out[:, idx + 1] = np.cos(c[:, axis] / denom)

    if dim % 2 == 1:
        out[:, -1] = np.linalg.norm(c, axis=1)
    return out


def relative_position_encoding(query_coords: np.ndarray, context_coords: np.ndarray) -> np.ndarray:
    q = np.asarray(query_coords, dtype=float)
    c = np.asarray(context_coords, dtype=float)
    diff = q[:, None, :] - c[None, :, :]
    dist = np.sqrt((diff * diff).sum(axis=-1, keepdims=True) + 1e-12)
    return np.concatenate([diff, dist], axis=-1)


class LearnablePositionEncoding:
    """Simple trainable linear position embedding."""

    def __init__(self, dim: int = 16, seed: int = 42) -> None:
        self.dim = max(1, int(dim))
        rng = np.random.default_rng(seed)
        self.weight = rng.normal(0.0, 0.08, size=(2, self.dim))
        self.bias = np.zeros(self.dim, dtype=float)

    def encode(self, coords: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be [N, 2]")
        return c @ self.weight + self.bias
