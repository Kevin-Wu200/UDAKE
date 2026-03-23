"""Position encoding utilities for spatiotemporal models."""

from __future__ import annotations

import numpy as np


def _safe_div(num: np.ndarray, den: np.ndarray) -> np.ndarray:
    return num / np.where(np.abs(den) < 1e-8, 1.0, den)


def sinusoidal_spatial_position_encoding(coords: np.ndarray, dim: int = 16) -> np.ndarray:
    """Encode 2D coordinates with sinusoidal embedding."""
    c = np.asarray(coords, dtype=float)
    if c.ndim != 2 or c.shape[1] != 2:
        raise ValueError("coords must be [n_nodes, 2]")
    d = max(2, int(dim))
    half = d // 2
    scales = np.exp(-np.log(10000.0) * np.arange(half, dtype=float) / max(1, half - 1))

    x = c[:, 0:1] * scales[None, :]
    y = c[:, 1:2] * scales[None, :]
    out = np.concatenate([np.sin(x), np.cos(x), np.sin(y), np.cos(y)], axis=1)
    if out.shape[1] < d:
        out = np.pad(out, ((0, 0), (0, d - out.shape[1])), constant_values=0.0)
    return out[:, :d]


def sinusoidal_temporal_position_encoding(length: int, dim: int = 16) -> np.ndarray:
    """Encode time indices with sinusoidal embedding."""
    n = int(max(1, length))
    d = max(2, int(dim))
    pos = np.arange(n, dtype=float).reshape(-1, 1)
    half = d // 2
    scales = np.exp(-np.log(10000.0) * np.arange(half, dtype=float) / max(1, half - 1))
    scaled = pos * scales[None, :]
    out = np.concatenate([np.sin(scaled), np.cos(scaled)], axis=1)
    if out.shape[1] < d:
        out = np.pad(out, ((0, 0), (0, d - out.shape[1])), constant_values=0.0)
    return out[:, :d]


def relative_spatial_position_encoding(query_coords: np.ndarray, key_coords: np.ndarray) -> np.ndarray:
    """Return relative (dx, dy, distance)."""
    q = np.asarray(query_coords, dtype=float)
    k = np.asarray(key_coords, dtype=float)
    if q.ndim != 2 or k.ndim != 2 or q.shape[1] != 2 or k.shape[1] != 2:
        raise ValueError("query/key coords must be [n,2]")
    diff = q[:, None, :] - k[None, :, :]
    dist = np.sqrt(np.sum(diff ** 2, axis=-1, keepdims=True) + 1e-8)
    return np.concatenate([diff, dist], axis=-1)


def relative_temporal_position_encoding(query_index: np.ndarray, key_index: np.ndarray) -> np.ndarray:
    """Return relative time offset and normalized offset."""
    q = np.asarray(query_index, dtype=float).reshape(-1)
    k = np.asarray(key_index, dtype=float).reshape(-1)
    diff = q[:, None] - k[None, :]
    denom = float(np.max(np.abs(diff)) + 1e-6)
    norm = diff / denom
    return np.stack([diff, norm], axis=-1)


def normalize_spatial_positions(coords: np.ndarray) -> np.ndarray:
    c = np.asarray(coords, dtype=float)
    c_min = c.min(axis=0, keepdims=True)
    c_max = c.max(axis=0, keepdims=True)
    return _safe_div(c - c_min, c_max - c_min)


def normalize_temporal_positions(indices: np.ndarray) -> np.ndarray:
    idx = np.asarray(indices, dtype=float).reshape(-1, 1)
    return _safe_div(idx - idx.min(), idx.max() - idx.min())
