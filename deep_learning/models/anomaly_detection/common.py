"""异常检测模块通用工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

ThresholdMethod = Literal["statistical", "percentile", "adaptive"]


@dataclass
class ThresholdResult:
    value: float
    method: ThresholdMethod
    details: dict[str, float]


def ensure_2d(array: np.ndarray | list[list[float]] | list[float]) -> np.ndarray:
    arr = np.asarray(array, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError("输入必须是一维或二维数组")
    return arr


def standardize(array: np.ndarray, eps: float = 1e-8) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arr = ensure_2d(array)
    mean = arr.mean(axis=0, keepdims=True)
    std = arr.std(axis=0, keepdims=True)
    std = np.where(std < eps, 1.0, std)
    return (arr - mean) / std, mean, std


def safe_minmax(values: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    v_min = float(arr.min())
    v_max = float(arr.max())
    if abs(v_max - v_min) < eps:
        return np.zeros_like(arr, dtype=float)
    return (arr - v_min) / (v_max - v_min + eps)


def pairwise_distance(coords: np.ndarray) -> np.ndarray:
    c = ensure_2d(coords)
    diff = c[:, None, :] - c[None, :, :]
    return np.sqrt((diff * diff).sum(axis=-1) + 1e-12)


def knn_graph(coords: np.ndarray, k: int = 8, include_self: bool = False) -> np.ndarray:
    points = ensure_2d(coords)
    n = len(points)
    if n == 0:
        return np.zeros((0, 0), dtype=float)
    k = int(max(1, min(k, n - 1 if n > 1 else 1)))
    dist = pairwise_distance(points)
    order = np.argsort(dist, axis=1)
    adj = np.zeros((n, n), dtype=float)

    for i in range(n):
        neighbors = order[i, 1 : k + 1] if n > 1 else np.array([0])
        adj[i, neighbors] = 1.0
        if include_self:
            adj[i, i] = 1.0

    adj = np.maximum(adj, adj.T)
    return adj


def radius_graph(coords: np.ndarray, radius: float = 0.15, include_self: bool = False) -> np.ndarray:
    points = ensure_2d(coords)
    n = len(points)
    if n == 0:
        return np.zeros((0, 0), dtype=float)
    dist = pairwise_distance(points)
    adj = (dist <= float(max(radius, 1e-8))).astype(float)
    if not include_self:
        np.fill_diagonal(adj, 0.0)
    return adj


def normalize_adjacency(adj: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    a = ensure_2d(adj)
    if a.shape[0] != a.shape[1]:
        raise ValueError("邻接矩阵必须是方阵")
    a_hat = a + np.eye(a.shape[0], dtype=float)
    deg = a_hat.sum(axis=1)
    deg_inv_sqrt = 1.0 / np.sqrt(deg + eps)
    d = np.diag(deg_inv_sqrt)
    return d @ a_hat @ d


def multiscale_value_features(coords: np.ndarray, values: np.ndarray, scales: tuple[int, ...] = (3, 5, 9)) -> np.ndarray:
    points = ensure_2d(coords)
    v = np.asarray(values, dtype=float).reshape(-1)
    if len(points) != len(v):
        raise ValueError("coords 与 values 长度不一致")
    if len(points) == 0:
        return np.zeros((0, len(scales) * 2), dtype=float)

    dist = pairwise_distance(points)
    order = np.argsort(dist, axis=1)
    feats: list[np.ndarray] = []

    for scale in scales:
        k = int(max(1, min(scale, len(points) - 1 if len(points) > 1 else 1)))
        idx = order[:, 1 : k + 1] if len(points) > 1 else np.zeros((len(points), 1), dtype=int)
        local_values = v[idx]
        local_mean = local_values.mean(axis=1)
        local_std = local_values.std(axis=1)
        feats.append(local_mean.reshape(-1, 1))
        feats.append(local_std.reshape(-1, 1))

    return np.concatenate(feats, axis=1)


def compute_threshold(
    scores: np.ndarray,
    method: ThresholdMethod = "percentile",
    k: float = 2.5,
    percentile: float = 95.0,
    adapt_rate: float = 0.15,
) -> ThresholdResult:
    s = np.asarray(scores, dtype=float).reshape(-1)
    if len(s) == 0:
        return ThresholdResult(value=0.0, method=method, details={"count": 0.0})

    if method == "statistical":
        mean = float(s.mean())
        std = float(s.std())
        value = mean + float(k) * std
        return ThresholdResult(value=value, method=method, details={"mean": mean, "std": std, "k": float(k)})

    if method == "adaptive":
        baseline = float(np.median(s))
        mad = float(np.median(np.abs(s - baseline)))
        value = (1.0 - adapt_rate) * baseline + adapt_rate * (baseline + 1.4826 * mad * max(k, 1.0))
        return ThresholdResult(
            value=float(value),
            method=method,
            details={"median": baseline, "mad": mad, "adapt_rate": float(adapt_rate), "k": float(k)},
        )

    pct = float(np.clip(percentile, 0.0, 100.0))
    value = float(np.percentile(s, pct))
    return ThresholdResult(value=value, method="percentile", details={"percentile": pct})


def topk_indices(scores: np.ndarray, k: int) -> np.ndarray:
    s = np.asarray(scores, dtype=float).reshape(-1)
    if k <= 0 or len(s) == 0:
        return np.array([], dtype=int)
    k = min(k, len(s))
    return np.argsort(s)[-k:][::-1]


def robust_zscore(values: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    v = np.asarray(values, dtype=float).reshape(-1)
    median = float(np.median(v))
    mad = float(np.median(np.abs(v - median)))
    if mad < eps:
        mean = float(v.mean())
        std = float(v.std())
        if std < eps:
            return np.zeros_like(v)
        return (v - mean) / std
    return 0.6745 * (v - median) / (mad + eps)
