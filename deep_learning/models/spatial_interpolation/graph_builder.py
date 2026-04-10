"""Spatial graph construction utilities for interpolation models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .spatial_index import SpatialIndex


@dataclass
class GraphData:
    """Container for graph representation used by numpy-based models."""

    coords: np.ndarray
    values: np.ndarray
    edge_index: np.ndarray
    edge_weight: np.ndarray
    adjacency: np.ndarray


class SpatialGraphBuilder:
    """Build graph topology from 2D coordinates with multiple strategies."""

    def __init__(self, default_k: int = 8, default_radius: float = 0.25, covariance_range: float = 0.2) -> None:
        self.default_k = max(1, int(default_k))
        self.default_radius = float(default_radius)
        self.covariance_range = max(float(covariance_range), 1e-6)

    def build(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        strategy: Literal["knn", "radius", "voronoi", "delaunay"] = "knn",
        k: int | None = None,
        radius: float | None = None,
        weight_mode: Literal["distance", "covariance", "hybrid"] = "hybrid",
    ) -> GraphData:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be of shape [N, 2]")
        if len(c) != len(v):
            raise ValueError("coords and values must have same length")

        if strategy == "knn":
            edge_index = self.build_knn_graph(c, k=k)
        elif strategy == "radius":
            edge_index = self.build_radius_graph(c, radius=radius)
        elif strategy == "voronoi":
            edge_index = self.build_voronoi_graph(c)
        elif strategy == "delaunay":
            edge_index = self.build_delaunay_graph(c)
        else:
            raise ValueError(f"unsupported graph strategy: {strategy}")

        edge_weight = self.compute_edge_weights(c, edge_index, values=v, mode=weight_mode)
        adjacency = self.to_adjacency(len(c), edge_index, edge_weight)
        return GraphData(coords=c, values=v, edge_index=edge_index, edge_weight=edge_weight, adjacency=adjacency)

    def pairwise_distance(self, coords: np.ndarray) -> np.ndarray:
        diff = coords[:, None, :] - coords[None, :, :]
        return np.sqrt((diff * diff).sum(axis=-1) + 1e-12)

    def build_knn_graph(self, coords: np.ndarray, k: int | None = None) -> np.ndarray:
        n = len(coords)
        if n <= 1:
            return np.zeros((2, 0), dtype=int)

        k_val = min(max(1, int(k or self.default_k)), max(1, n - 1))
        index = SpatialIndex(coords)
        knn = index.query_knn(coords, k=k_val, exclude_self=True)
        edges: set[tuple[int, int]] = set()

        for i in range(n):
            nearest = knn.indices[i]
            for j in nearest:
                a, b = (i, int(j)) if i < int(j) else (int(j), i)
                edges.add((a, b))

        return self._edges_to_undirected_index(edges)

    def build_radius_graph(self, coords: np.ndarray, radius: float | None = None) -> np.ndarray:
        n = len(coords)
        if n <= 1:
            return np.zeros((2, 0), dtype=int)

        r = float(radius if radius is not None else self.default_radius)
        index = SpatialIndex(coords)
        neighbors = index.query_radius(coords, radius=r, exclude_self=True)
        edges: set[tuple[int, int]] = set()

        for i in range(n):
            row = neighbors[i]
            if row.size == 0:
                continue
            for j in row.tolist():
                j_idx = int(j)
                if j_idx > i:
                    edges.add((i, j_idx))

        if not edges:
            return self.build_knn_graph(coords, k=1)
        return self._edges_to_undirected_index(edges)

    def build_voronoi_graph(self, coords: np.ndarray) -> np.ndarray:
        n = len(coords)
        if n <= 3:
            return self.build_knn_graph(coords, k=1)

        try:
            from scipy.spatial import Voronoi

            vor = Voronoi(coords)
            edges: set[tuple[int, int]] = set()
            for i, j in vor.ridge_points:
                a, b = (int(i), int(j)) if i < j else (int(j), int(i))
                edges.add((a, b))
            if not edges:
                return self.build_knn_graph(coords, k=2)
            return self._edges_to_undirected_index(edges)
        except Exception:
            return self.build_knn_graph(coords, k=2)

    def build_delaunay_graph(self, coords: np.ndarray) -> np.ndarray:
        n = len(coords)
        if n <= 2:
            return self.build_knn_graph(coords, k=1)

        try:
            from scipy.spatial import Delaunay

            tri = Delaunay(coords)
            edges: set[tuple[int, int]] = set()
            for simplex in tri.simplices:
                ids = [int(x) for x in simplex]
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        a, b = (ids[i], ids[j]) if ids[i] < ids[j] else (ids[j], ids[i])
                        edges.add((a, b))
            if not edges:
                return self.build_knn_graph(coords, k=2)
            return self._edges_to_undirected_index(edges)
        except Exception:
            return self.build_knn_graph(coords, k=2)

    def compute_edge_weights(
        self,
        coords: np.ndarray,
        edge_index: np.ndarray,
        values: np.ndarray,
        mode: Literal["distance", "covariance", "hybrid"] = "hybrid",
    ) -> np.ndarray:
        if edge_index.shape[1] == 0:
            return np.zeros(0, dtype=float)

        src = edge_index[0]
        dst = edge_index[1]
        dist = np.sqrt(((coords[src] - coords[dst]) ** 2).sum(axis=1) + 1e-12)
        distance_w = 1.0 / (1.0 + dist)

        value_diff = np.abs(values[src] - values[dst])
        covariance_w = np.exp(-dist / self.covariance_range) / (1.0 + value_diff)

        if mode == "distance":
            w = distance_w
        elif mode == "covariance":
            w = covariance_w
        elif mode == "hybrid":
            w = 0.5 * distance_w + 0.5 * covariance_w
        else:
            raise ValueError(f"unsupported weight mode: {mode}")

        return np.clip(w, 1e-6, None)

    def to_adjacency(self, n_nodes: int, edge_index: np.ndarray, edge_weight: np.ndarray) -> np.ndarray:
        adjacency = np.zeros((n_nodes, n_nodes), dtype=float)
        if edge_index.shape[1] == 0:
            return adjacency
        src = np.asarray(edge_index[0], dtype=int)
        dst = np.asarray(edge_index[1], dtype=int)
        np.add.at(adjacency, (src, dst), np.asarray(edge_weight, dtype=float))
        return adjacency

    def _edges_to_undirected_index(self, edges: set[tuple[int, int]]) -> np.ndarray:
        directed: list[tuple[int, int]] = []
        for i, j in sorted(edges):
            directed.append((i, j))
            directed.append((j, i))
        if not directed:
            return np.zeros((2, 0), dtype=int)
        return np.asarray(directed, dtype=int).T
