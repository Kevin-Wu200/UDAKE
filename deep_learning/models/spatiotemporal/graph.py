"""Graph utilities for spatiotemporal models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SpatioTemporalGraph:
    adjacency: np.ndarray
    edge_index: np.ndarray
    edge_weight: np.ndarray


def _pairwise_distance(coords: np.ndarray) -> np.ndarray:
    c = np.asarray(coords, dtype=float)
    diff = c[:, None, :] - c[None, :, :]
    return np.sqrt(np.sum(diff ** 2, axis=-1) + 1e-12)


def build_knn_graph(coords: np.ndarray, k: int = 6) -> SpatioTemporalGraph:
    c = np.asarray(coords, dtype=float)
    n = len(c)
    if n == 0:
        return SpatioTemporalGraph(adjacency=np.zeros((0, 0)), edge_index=np.zeros((2, 0), dtype=int), edge_weight=np.zeros((0,)))

    dist = _pairwise_distance(c)
    np.fill_diagonal(dist, np.inf)
    kk = int(max(1, min(k, n - 1))) if n > 1 else 0

    adj = np.zeros((n, n), dtype=float)
    edges: list[tuple[int, int]] = []
    weights: list[float] = []

    for i in range(n):
        if kk == 0:
            continue
        ids = np.argpartition(dist[i], kk)[:kk]
        for j in ids:
            w = float(np.exp(-dist[i, j]))
            adj[i, j] = max(adj[i, j], w)
            adj[j, i] = max(adj[j, i], w)

    rows, cols = np.where(adj > 0)
    for i, j in zip(rows.tolist(), cols.tolist()):
        edges.append((i, j))
        weights.append(float(adj[i, j]))

    edge_index = np.asarray(edges, dtype=int).T if edges else np.zeros((2, 0), dtype=int)
    edge_weight = np.asarray(weights, dtype=float) if weights else np.zeros((0,), dtype=float)
    return SpatioTemporalGraph(adjacency=adj, edge_index=edge_index, edge_weight=edge_weight)


def update_dynamic_graph(
    coords: np.ndarray,
    signal: np.ndarray,
    base_adjacency: np.ndarray | None = None,
    alpha: float = 0.7,
) -> SpatioTemporalGraph:
    """Build dynamic graph using spatial distance + signal similarity."""
    c = np.asarray(coords, dtype=float)
    sig = np.asarray(signal, dtype=float)
    if sig.ndim == 3:
        sig = sig[:, :, 0]
    if sig.ndim == 2:
        feat = sig
    else:
        feat = sig.reshape(len(c), -1)

    dist = _pairwise_distance(c)
    sim = np.corrcoef(feat)
    sim = np.nan_to_num(sim, nan=0.0)
    spatial = np.exp(-dist)
    adj = alpha * spatial + (1.0 - alpha) * np.maximum(sim, 0.0)

    if base_adjacency is not None:
        base = np.asarray(base_adjacency, dtype=float)
        if base.shape == adj.shape:
            adj = 0.5 * adj + 0.5 * base

    np.fill_diagonal(adj, 0.0)
    rows, cols = np.where(adj > np.percentile(adj, 70))
    edges = np.stack([rows, cols], axis=0) if len(rows) else np.zeros((2, 0), dtype=int)
    weights = adj[rows, cols] if len(rows) else np.zeros((0,), dtype=float)
    return SpatioTemporalGraph(adjacency=adj, edge_index=edges, edge_weight=weights)
