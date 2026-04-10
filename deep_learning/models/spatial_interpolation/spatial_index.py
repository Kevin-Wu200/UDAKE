"""Lightweight spatial index for fast neighborhood queries.

Priority:
1) scipy.spatial.cKDTree when available
2) numpy vectorized fallback
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class SpatialNeighborResult:
    indices: np.ndarray
    distances: np.ndarray


class SpatialIndex:
    """Spatial index wrapper with scipy-backed and numpy fallback paths."""

    def __init__(self, coords: np.ndarray) -> None:
        c = np.asarray(coords, dtype=float)
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be [N, 2]")
        self.coords = c
        self.size = int(c.shape[0])

        self._tree: Any = None
        try:
            from scipy.spatial import cKDTree  # type: ignore

            self._tree = cKDTree(c)
        except Exception:
            self._tree = None

    def query_knn(
        self,
        query_coords: np.ndarray,
        k: int,
        *,
        exclude_self: bool = False,
        self_tolerance: float = 1e-12,
    ) -> SpatialNeighborResult:
        q = np.asarray(query_coords, dtype=float)
        if q.ndim != 2 or q.shape[1] != 2:
            raise ValueError("query_coords must be [M, 2]")
        if self.size == 0:
            return SpatialNeighborResult(indices=np.zeros((len(q), 0), dtype=int), distances=np.zeros((len(q), 0), dtype=float))

        target_k = max(1, int(k))
        raw_k = min(self.size, target_k + (1 if exclude_self else 0))

        if self._tree is not None:
            distances, indices = self._tree.query(q, k=raw_k)
            distances = np.asarray(distances, dtype=float)
            indices = np.asarray(indices, dtype=int)
            if distances.ndim == 1:
                distances = distances[:, None]
                indices = indices[:, None]
        else:
            diff = q[:, None, :] - self.coords[None, :, :]
            all_dist = np.sqrt(np.sum(diff * diff, axis=2) + 1e-12)
            order = np.argsort(all_dist, axis=1)
            indices = order[:, :raw_k].astype(int)
            distances = np.take_along_axis(all_dist, indices, axis=1).astype(float)

        if exclude_self:
            keep_indices = np.zeros((len(q), target_k), dtype=int)
            keep_distances = np.zeros((len(q), target_k), dtype=float)
            for row in range(len(q)):
                idx_row = indices[row]
                dist_row = distances[row]
                mask = dist_row > float(self_tolerance)
                selected_idx = idx_row[mask]
                selected_dist = dist_row[mask]
                if selected_idx.size < target_k:
                    fill = idx_row[: max(0, target_k - selected_idx.size)]
                    fill_dist = dist_row[: max(0, target_k - selected_dist.size)]
                    selected_idx = np.concatenate([selected_idx, fill], axis=0)
                    selected_dist = np.concatenate([selected_dist, fill_dist], axis=0)
                keep_indices[row] = selected_idx[:target_k]
                keep_distances[row] = selected_dist[:target_k]
            return SpatialNeighborResult(indices=keep_indices, distances=keep_distances)

        return SpatialNeighborResult(indices=indices[:, :target_k], distances=distances[:, :target_k])

    def query_radius(
        self,
        query_coords: np.ndarray,
        radius: float,
        *,
        exclude_self: bool = False,
        self_tolerance: float = 1e-12,
    ) -> list[np.ndarray]:
        q = np.asarray(query_coords, dtype=float)
        if q.ndim != 2 or q.shape[1] != 2:
            raise ValueError("query_coords must be [M, 2]")

        r = float(max(radius, 0.0))
        if self._tree is not None:
            neighbors = self._tree.query_ball_point(q, r=r)
            out: list[np.ndarray] = []
            if exclude_self:
                for row, ids in enumerate(neighbors):
                    ids_arr = np.asarray(ids, dtype=int)
                    if ids_arr.size == 0:
                        out.append(ids_arr)
                        continue
                    diff = self.coords[ids_arr] - q[row][None, :]
                    d = np.sqrt(np.sum(diff * diff, axis=1) + 1e-12)
                    out.append(ids_arr[d > float(self_tolerance)])
            else:
                out = [np.asarray(ids, dtype=int) for ids in neighbors]
            return out

        diff = q[:, None, :] - self.coords[None, :, :]
        all_dist = np.sqrt(np.sum(diff * diff, axis=2) + 1e-12)
        out = []
        for row in range(len(q)):
            mask = all_dist[row] <= r
            if exclude_self:
                mask = mask & (all_dist[row] > float(self_tolerance))
            out.append(np.where(mask)[0].astype(int))
        return out
