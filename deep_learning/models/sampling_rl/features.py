"""强化学习采样特征工程。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class TopologyFeatures:
    adjacency: np.ndarray
    degree: np.ndarray
    connected_components: int
    clustering: np.ndarray


class SamplingFeatureEngineer:
    """提供空间、不确定性、采样、拓扑特征。"""

    def position_features(self, coords: np.ndarray, boundary: tuple[float, float, float, float]) -> np.ndarray:
        arr = np.asarray(coords, dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 2:
            raise ValueError("coords 必须为 [N, 2]")

        min_x, max_x, min_y, max_y = boundary
        width = max(max_x - min_x, 1e-8)
        height = max(max_y - min_y, 1e-8)

        x_norm = (arr[:, 0] - min_x) / width
        y_norm = (arr[:, 1] - min_y) / height
        radius = np.sqrt((x_norm - 0.5) ** 2 + (y_norm - 0.5) ** 2)
        angle = np.arctan2(y_norm - 0.5, x_norm - 0.5)
        return np.stack([x_norm, y_norm, radius, angle], axis=1)

    def distance_features(self, coords: np.ndarray, reference_points: np.ndarray | None = None) -> np.ndarray:
        arr = np.asarray(coords, dtype=float)
        ref = arr if reference_points is None else np.asarray(reference_points, dtype=float)
        if len(arr) == 0:
            return np.zeros((0, 2), dtype=float)
        if len(ref) == 0:
            return np.zeros((len(arr), 2), dtype=float)

        diff = arr[:, None, :] - ref[None, :, :]
        dist = np.linalg.norm(diff, axis=2)
        if reference_points is None:
            # 自身距离矩阵，排除对角线。
            dist = dist + np.eye(len(arr)) * 1e6

        min_dist = dist.min(axis=1)
        mean_dist = dist.mean(axis=1)
        return np.stack([min_dist, mean_dist], axis=1)

    def density_features(self, coords: np.ndarray, k: int = 5) -> np.ndarray:
        arr = np.asarray(coords, dtype=float)
        if len(arr) == 0:
            return np.zeros((0, 1), dtype=float)

        diff = arr[:, None, :] - arr[None, :, :]
        dist = np.linalg.norm(diff, axis=2) + np.eye(len(arr)) * 1e6
        kk = int(max(1, min(k, max(1, len(arr) - 1))))
        nearest = np.partition(dist, kk, axis=1)[:, :kk]
        density = 1.0 / (nearest.mean(axis=1) + 1e-8)
        return density.reshape(-1, 1)

    def spatial_features(self, coords: np.ndarray, boundary: tuple[float, float, float, float]) -> np.ndarray:
        pos = self.position_features(coords, boundary)
        dist = self.distance_features(coords)
        density = self.density_features(coords)
        return np.concatenate([pos, dist, density], axis=1)

    def uncertainty_features(self, uncertainty_map: np.ndarray) -> np.ndarray:
        umap = np.asarray(uncertainty_map, dtype=float)
        if umap.ndim != 2:
            raise ValueError("uncertainty_map 必须为二维")

        grad_y, grad_x = np.gradient(umap)
        local_grad = np.sqrt(grad_x ** 2 + grad_y ** 2)

        flat = umap.reshape(-1)
        mean = np.mean(flat)
        std = np.std(flat) + 1e-8
        z = (flat - mean) / std

        confidence_width = 1.96 * np.sqrt(np.maximum(flat, 1e-8))
        return np.stack([flat, z, local_grad.reshape(-1), confidence_width], axis=1)

    def sampling_features(
        self,
        sampled_points: np.ndarray,
        boundary: tuple[float, float, float, float],
        grid_shape: tuple[int, int],
    ) -> np.ndarray:
        points = np.asarray(sampled_points, dtype=float)
        h, w = int(grid_shape[0]), int(grid_shape[1])
        density_map = np.zeros((h, w), dtype=float)

        min_x, max_x, min_y, max_y = boundary
        width = max(max_x - min_x, 1e-8)
        height = max(max_y - min_y, 1e-8)

        for x, y in points:
            col = int(np.clip(round((x - min_x) / width * (w - 1)), 0, w - 1))
            row = int(np.clip(round((y - min_y) / height * (h - 1)), 0, h - 1))
            density_map[row, col] += 1.0

        total = float(np.sum(density_map))
        if total > 0:
            distribution = density_map / total
            entropy = -np.sum(distribution * np.log(distribution + 1e-8))
            entropy_norm = entropy / np.log(h * w + 1e-8)
        else:
            entropy_norm = 0.0

        sampled_ratio = float(np.count_nonzero(density_map) / (h * w))
        return np.array([sampled_ratio, float(total), float(entropy_norm)], dtype=float)

    def topology_features(self, coords: np.ndarray, k: int = 4) -> TopologyFeatures:
        points = np.asarray(coords, dtype=float)
        n = len(points)
        if n == 0:
            return TopologyFeatures(
                adjacency=np.zeros((0, 0), dtype=float),
                degree=np.zeros((0,), dtype=float),
                connected_components=0,
                clustering=np.zeros((0,), dtype=float),
            )

        diff = points[:, None, :] - points[None, :, :]
        dist = np.linalg.norm(diff, axis=2) + np.eye(n) * 1e6
        kk = int(max(1, min(k, max(1, n - 1))))
        nn_idx = np.argpartition(dist, kk, axis=1)[:, :kk]

        adjacency = np.zeros((n, n), dtype=float)
        for i in range(n):
            adjacency[i, nn_idx[i]] = 1.0
        adjacency = np.maximum(adjacency, adjacency.T)
        np.fill_diagonal(adjacency, 0.0)

        degree = adjacency.sum(axis=1)
        components = self._count_components(adjacency)
        clustering = self._clustering_coeff(adjacency)

        return TopologyFeatures(
            adjacency=adjacency,
            degree=degree,
            connected_components=components,
            clustering=clustering,
        )

    def _count_components(self, adjacency: np.ndarray) -> int:
        n = len(adjacency)
        if n == 0:
            return 0

        visited = np.zeros(n, dtype=bool)
        components = 0
        for i in range(n):
            if visited[i]:
                continue
            components += 1
            stack = [i]
            visited[i] = True
            while stack:
                cur = stack.pop()
                neighbors = np.where(adjacency[cur] > 0)[0]
                for nb in neighbors:
                    if not visited[nb]:
                        visited[nb] = True
                        stack.append(nb)
        return int(components)

    def _clustering_coeff(self, adjacency: np.ndarray) -> np.ndarray:
        n = len(adjacency)
        coeff = np.zeros(n, dtype=float)
        for i in range(n):
            neighbors = np.where(adjacency[i] > 0)[0]
            if len(neighbors) < 2:
                coeff[i] = 0.0
                continue
            sub = adjacency[np.ix_(neighbors, neighbors)]
            links = np.sum(sub) / 2.0
            possible = len(neighbors) * (len(neighbors) - 1) / 2.0
            coeff[i] = float(links / max(possible, 1e-8))
        return coeff
