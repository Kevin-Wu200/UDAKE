"""异常检测数据准备、增强、图构建与标注工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal

import numpy as np

from .common import knn_graph, pairwise_distance, radius_graph

AnomalyType = Literal["point", "contextual", "collective"]


@dataclass
class AnomalyDataset:
    coords: np.ndarray
    values: np.ndarray
    labels: np.ndarray
    types: list[str]


class AnomalyGenerator:
    """异常生成器：高值/低值/梯度/模式。"""

    def __init__(self, random_state: int = 42) -> None:
        self.rng = np.random.default_rng(random_state)

    def high_value(self, values: np.ndarray, ratio: float = 0.05, intensity: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
        v = np.asarray(values, dtype=float).reshape(-1).copy()
        count = max(1, int(len(v) * max(ratio, 0.0))) if len(v) else 0
        idx = self.rng.choice(len(v), size=count, replace=False) if count > 0 else np.array([], dtype=int)
        v[idx] += intensity * (v.std() + 1e-6)
        return v, idx

    def low_value(self, values: np.ndarray, ratio: float = 0.05, intensity: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
        v = np.asarray(values, dtype=float).reshape(-1).copy()
        count = max(1, int(len(v) * max(ratio, 0.0))) if len(v) else 0
        idx = self.rng.choice(len(v), size=count, replace=False) if count > 0 else np.array([], dtype=int)
        v[idx] -= intensity * (v.std() + 1e-6)
        return v, idx

    def gradient_anomaly(self, coords: np.ndarray, values: np.ndarray, center_ratio: float = 0.1, slope: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1).copy()
        if len(v) == 0:
            return v, np.array([], dtype=int)
        center_idx = self.rng.integers(0, len(v))
        dist = np.linalg.norm(c - c[center_idx], axis=1)
        count = max(1, int(len(v) * max(center_ratio, 0.01)))
        idx = np.argsort(dist)[:count]
        v[idx] += slope * (dist[idx] - dist[idx].mean())
        return v, idx

    def pattern_anomaly(self, values: np.ndarray, segment_ratio: float = 0.15) -> tuple[np.ndarray, np.ndarray]:
        v = np.asarray(values, dtype=float).reshape(-1).copy()
        n = len(v)
        if n == 0:
            return v, np.array([], dtype=int)
        seg = max(2, int(n * max(segment_ratio, 0.05)))
        start = int(self.rng.integers(0, max(1, n - seg + 1)))
        idx = np.arange(start, min(n, start + seg))
        pattern = np.sin(np.linspace(0.0, 3.0 * np.pi, len(idx))) * (v.std() + 1e-6)
        v[idx] += pattern
        return v, idx


class DataAugmentor:
    """数据增强：空间变换、值扰动、掩码、混合增强。"""

    def __init__(self, random_state: int = 42) -> None:
        self.rng = np.random.default_rng(random_state)

    def spatial_transform(self, coords: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        theta = float(self.rng.uniform(-0.35, 0.35))
        scale = float(self.rng.uniform(0.85, 1.15))
        shift = self.rng.normal(0.0, 0.02, size=(1, c.shape[1]))
        rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]], dtype=float)
        return c @ rot.T * scale + shift

    def value_perturb(self, values: np.ndarray, strength: float = 0.05) -> np.ndarray:
        v = np.asarray(values, dtype=float).reshape(-1)
        noise = self.rng.normal(0.0, strength * (v.std() + 1e-6), size=len(v))
        return v + noise

    def mask_strategy(self, values: np.ndarray, mask_ratio: float = 0.1) -> np.ndarray:
        v = np.asarray(values, dtype=float).reshape(-1).copy()
        if len(v) == 0:
            return v
        count = max(1, int(len(v) * np.clip(mask_ratio, 0.0, 0.95)))
        idx = self.rng.choice(len(v), size=count, replace=False)
        v[idx] = np.median(v)
        return v

    def mixed_augment(self, coords: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        c = self.spatial_transform(coords)
        v = self.value_perturb(values)
        v = self.mask_strategy(v)
        return c, v


class AnomalyFeatureExtractor:
    """特征提取：空间特征、统计特征、拓扑特征。"""

    def spatial_features(self, coords: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        radius = np.linalg.norm(c, axis=1, keepdims=True)
        angle = np.arctan2(c[:, 1], c[:, 0]).reshape(-1, 1)
        return np.concatenate([c, radius, angle], axis=1)

    def statistical_features(self, values: np.ndarray) -> np.ndarray:
        v = np.asarray(values, dtype=float).reshape(-1)
        z = (v - v.mean()) / (v.std() + 1e-6)
        centered = v - np.median(v)
        iqr = np.percentile(v, 75) - np.percentile(v, 25)
        if iqr < 1e-6:
            iqr = 1.0
        robust = centered / iqr
        return np.stack([v, z, robust], axis=1)

    def topological_features(self, coords: np.ndarray, values: np.ndarray, k: int = 8) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        adj = knn_graph(c, k=k)
        deg = adj.sum(axis=1)
        dist = pairwise_distance(c)
        local_dist = np.zeros(len(c), dtype=float)
        local_mean = np.zeros(len(c), dtype=float)
        for i in range(len(c)):
            nbr = np.where(adj[i] > 0)[0]
            if len(nbr) == 0:
                continue
            local_dist[i] = float(dist[i, nbr].mean())
            local_mean[i] = float(v[nbr].mean())
        return np.stack([deg, local_dist, local_mean], axis=1)


class GraphBuilder:
    """图构建：空间邻接图、K近邻图、半径图。"""

    def spatial_adjacency_graph(self, coords: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        dist = pairwise_distance(c)
        sigma = np.median(dist[dist > 0]) if np.any(dist > 0) else 1.0
        weights = np.exp(-(dist ** 2) / (2 * sigma * sigma + 1e-9))
        np.fill_diagonal(weights, 0.0)
        return weights

    def knn_graph(self, coords: np.ndarray, k: int = 8) -> np.ndarray:
        return knn_graph(coords, k=k)

    def radius_graph(self, coords: np.ndarray, radius: float = 0.2) -> np.ndarray:
        return radius_graph(coords, radius=radius)


class AnomalyLabelingTool:
    """异常类型定义与标注工具。"""

    def __init__(self, context_window: int = 6) -> None:
        self.context_window = max(2, int(context_window))

    def label(self, values: np.ndarray) -> tuple[np.ndarray, list[str]]:
        v = np.asarray(values, dtype=float).reshape(-1)
        n = len(v)
        labels = np.zeros(n, dtype=int)
        types = ["normal" for _ in range(n)]

        if n == 0:
            return labels, types

        mean = float(v.mean())
        std = float(v.std() + 1e-6)
        z = np.abs((v - mean) / std)

        point_hits = np.where(z >= 3.0)[0]
        for idx in point_hits:
            labels[idx] = 1
            types[idx] = "point"

        for i in range(n):
            left = max(0, i - self.context_window)
            right = min(n, i + self.context_window + 1)
            local = v[left:right]
            local_std = float(local.std() + 1e-6)
            local_mean = float(local.mean())
            local_z = abs(v[i] - local_mean) / local_std
            if local_z >= 2.8 and labels[i] == 0:
                labels[i] = 1
                types[i] = "contextual"

        window = max(3, self.context_window)
        for i in range(0, n - window + 1):
            seg = v[i : i + window]
            seg_z = np.abs((seg - mean) / std)
            if np.mean(seg_z >= 2.0) >= 0.65:
                for j in range(i, i + window):
                    labels[j] = 1
                    if types[j] == "normal":
                        types[j] = "collective"

        return labels, types


class AnomalyDatasetBuilder:
    """创建异常检测数据集。"""

    def __init__(self, random_state: int = 42) -> None:
        self.generator = AnomalyGenerator(random_state=random_state)
        self.augmentor = DataAugmentor(random_state=random_state)
        self.labeler = AnomalyLabelingTool()

    def build(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        include_synthetic: bool = True,
    ) -> AnomalyDataset:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        v_aug = v.copy()

        if include_synthetic:
            v_aug, idx1 = self.generator.high_value(v_aug, ratio=0.04)
            v_aug, idx2 = self.generator.low_value(v_aug, ratio=0.04)
            v_aug, idx3 = self.generator.gradient_anomaly(c, v_aug, center_ratio=0.08)
            v_aug, idx4 = self.generator.pattern_anomaly(v_aug, segment_ratio=0.1)
            synth_idx = np.unique(np.concatenate([idx1, idx2, idx3, idx4])) if len(v) else np.array([], dtype=int)
        else:
            synth_idx = np.array([], dtype=int)

        labels, types = self.labeler.label(v_aug)
        if len(synth_idx) > 0:
            labels[synth_idx] = 1
            for idx in synth_idx:
                if types[idx] == "normal":
                    types[idx] = "point"

        return AnomalyDataset(coords=c, values=v_aug, labels=labels, types=types)


class SimpleAnomalyDataLoader:
    """轻量数据加载器。"""

    def __init__(self, batch_size: int = 32, shuffle: bool = True, random_state: int = 42) -> None:
        self.batch_size = max(1, int(batch_size))
        self.shuffle = shuffle
        self.rng = np.random.default_rng(random_state)

    def iterate(self, dataset: AnomalyDataset) -> Iterator[dict[str, np.ndarray]]:
        n = len(dataset.values)
        indices = np.arange(n)
        if self.shuffle:
            self.rng.shuffle(indices)

        for start in range(0, n, self.batch_size):
            idx = indices[start : start + self.batch_size]
            yield {
                "coords": dataset.coords[idx],
                "values": dataset.values[idx],
                "labels": dataset.labels[idx],
                "types": np.array([dataset.types[i] for i in idx]),
            }
