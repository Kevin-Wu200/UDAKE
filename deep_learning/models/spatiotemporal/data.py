"""Data preparation pipeline for spatiotemporal forecasting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np

from .graph import SpatioTemporalGraph, build_knn_graph, update_dynamic_graph


@dataclass
class SpatioTemporalSample:
    coords: np.ndarray
    series: np.ndarray
    targets: np.ndarray
    adjacency: np.ndarray


class SyntheticSpatioTemporalDataset:
    """Synthetic sensor-network time series generator."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)

    def generate(
        self,
        n_nodes: int = 24,
        seq_len: int = 36,
        pred_horizon: int = 6,
        n_features: int = 2,
        noise_std: float = 0.03,
    ) -> SpatioTemporalSample:
        coords = self.rng.uniform(0.0, 1.0, size=(n_nodes, 2))
        total = seq_len + pred_horizon
        t = np.linspace(0.0, 4.0 * np.pi, total)

        series = np.zeros((n_nodes, seq_len, n_features), dtype=float)
        future = np.zeros((n_nodes, pred_horizon), dtype=float)

        for i in range(n_nodes):
            x, y = coords[i]
            phase = 2.0 * np.pi * (0.3 * x + 0.7 * y)
            base = np.sin(t + phase) + 0.6 * np.cos(0.5 * t + 2.2 * x)
            trend = 0.05 * t * (x - 0.5)
            signal = base + trend + self.rng.normal(0.0, noise_std, size=total)

            series[i, :, 0] = signal[:seq_len]
            if n_features > 1:
                derivative = np.gradient(signal[:seq_len])
                series[i, :, 1] = derivative
            for f in range(2, n_features):
                series[i, :, f] = np.roll(signal[:seq_len], f)

            future[i] = signal[seq_len : seq_len + pred_horizon]

        graph = build_knn_graph(coords, k=min(6, max(1, n_nodes - 1)))
        return SpatioTemporalSample(coords=coords, series=series, targets=future, adjacency=graph.adjacency)


class SpatioTemporalDataAugmentation:
    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)

    def time_warp(self, series: np.ndarray, strength: float = 0.08) -> np.ndarray:
        s = np.asarray(series, dtype=float)
        n, t, f = s.shape
        base_idx = np.arange(t, dtype=float)
        jitter = self.rng.normal(0.0, strength * t, size=t)
        warped_idx = np.clip(np.sort(base_idx + jitter), 0.0, t - 1.0)

        out = np.zeros_like(s)
        for i in range(n):
            for k in range(f):
                out[i, :, k] = np.interp(base_idx, warped_idx, s[i, :, k])
        return out

    def spatial_transform(self, coords: np.ndarray, rotate_rad: float = 0.15, scale: float = 1.03) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        rot = np.array(
            [
                [np.cos(rotate_rad), -np.sin(rotate_rad)],
                [np.sin(rotate_rad), np.cos(rotate_rad)],
            ],
            dtype=float,
        )
        centered = c - np.mean(c, axis=0, keepdims=True)
        transformed = centered @ rot.T * float(scale)
        transformed += np.mean(c, axis=0, keepdims=True)
        return transformed

    def noise_injection(self, series: np.ndarray, std: float = 0.02) -> np.ndarray:
        s = np.asarray(series, dtype=float)
        return s + self.rng.normal(0.0, std, size=s.shape)


class SpatioTemporalFeatureEngineer:
    """Feature engineering for temporal/spatial/spatiotemporal features."""

    def temporal_features(self, series: np.ndarray) -> np.ndarray:
        s = np.asarray(series, dtype=float)
        n, t, _ = s.shape
        idx = np.arange(t, dtype=float)
        seasonal = np.stack([np.sin(2.0 * np.pi * idx / max(2, t)), np.cos(2.0 * np.pi * idx / max(2, t))], axis=1)
        seasonal = np.repeat(seasonal[None, :, :], n, axis=0)

        trend = np.linspace(0.0, 1.0, t, dtype=float)
        trend = np.repeat(trend[None, :, None], n, axis=0)
        return np.concatenate([s, seasonal, trend], axis=-1)

    def spatial_features(self, coords: np.ndarray, adjacency: np.ndarray | None = None) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        center = np.mean(c, axis=0, keepdims=True)
        rel = c - center
        radius = np.sqrt(np.sum(rel ** 2, axis=1, keepdims=True))

        if adjacency is None:
            degree = np.zeros((len(c), 1), dtype=float)
        else:
            adj = np.asarray(adjacency, dtype=float)
            degree = np.sum(adj > 0, axis=1, keepdims=True)
        return np.concatenate([c, rel, radius, degree], axis=1)

    def spatiotemporal_interaction_features(self, coords: np.ndarray, series: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        s = np.asarray(series, dtype=float)
        # Use the most recent signal and local coordinate magnitude interaction.
        latest = s[:, -1, 0:1]
        spatial_mag = np.linalg.norm(c, axis=1, keepdims=True)
        interaction = latest * spatial_mag
        return np.concatenate([latest, spatial_mag, interaction], axis=1)


@dataclass
class NormalizationState:
    mean: np.ndarray
    std: np.ndarray


class TemporalNormalizer:
    def __init__(self) -> None:
        self.state: NormalizationState | None = None

    def fit(self, series: np.ndarray) -> "TemporalNormalizer":
        s = np.asarray(series, dtype=float)
        mean = np.mean(s, axis=(0, 1), keepdims=True)
        std = np.maximum(np.std(s, axis=(0, 1), keepdims=True), 1e-6)
        self.state = NormalizationState(mean=mean, std=std)
        return self

    def transform(self, series: np.ndarray) -> np.ndarray:
        if self.state is None:
            raise ValueError("TemporalNormalizer not fitted")
        s = np.asarray(series, dtype=float)
        return (s - self.state.mean) / self.state.std

    def inverse_transform(self, series: np.ndarray) -> np.ndarray:
        if self.state is None:
            raise ValueError("TemporalNormalizer not fitted")
        s = np.asarray(series, dtype=float)
        return s * self.state.std + self.state.mean


class SpatialNormalizer:
    def __init__(self) -> None:
        self.min_: np.ndarray | None = None
        self.max_: np.ndarray | None = None

    def fit(self, coords: np.ndarray) -> "SpatialNormalizer":
        c = np.asarray(coords, dtype=float)
        self.min_ = np.min(c, axis=0, keepdims=True)
        self.max_ = np.max(c, axis=0, keepdims=True)
        return self

    def transform(self, coords: np.ndarray) -> np.ndarray:
        if self.min_ is None or self.max_ is None:
            raise ValueError("SpatialNormalizer not fitted")
        c = np.asarray(coords, dtype=float)
        scale = np.where((self.max_ - self.min_) < 1e-8, 1.0, self.max_ - self.min_)
        return (c - self.min_) / scale


class SpatioTemporalGraphBuilder:
    def build(self, coords: np.ndarray, k: int = 6) -> SpatioTemporalGraph:
        return build_knn_graph(coords, k=k)

    def update(self, coords: np.ndarray, series: np.ndarray, base_adjacency: np.ndarray | None = None) -> SpatioTemporalGraph:
        return update_dynamic_graph(coords=coords, signal=series, base_adjacency=base_adjacency)


class SlidingWindowDataLoader:
    """Sliding-window + batching for spatiotemporal series.

    Input long-series shape: [n_nodes, total_steps, n_features].
    """

    def __init__(
        self,
        coords: np.ndarray,
        long_series: np.ndarray,
        seq_len: int = 24,
        pred_horizon: int = 6,
        batch_size: int = 8,
        shuffle: bool = True,
        seed: int = 42,
    ) -> None:
        self.coords = np.asarray(coords, dtype=float)
        self.series = np.asarray(long_series, dtype=float)
        self.seq_len = int(max(2, seq_len))
        self.pred_horizon = int(max(1, pred_horizon))
        self.batch_size = int(max(1, batch_size))
        self.shuffle = bool(shuffle)
        self.seed = seed

        if self.series.ndim != 3:
            raise ValueError("long_series must be [n_nodes, total_steps, n_features]")
        self.n_nodes, self.total_steps, _ = self.series.shape
        if self.total_steps < self.seq_len + self.pred_horizon:
            raise ValueError("insufficient total_steps for sliding windows")

        self._graph = build_knn_graph(self.coords, k=min(6, max(1, self.n_nodes - 1)))

    def _windows(self) -> list[SpatioTemporalSample]:
        samples: list[SpatioTemporalSample] = []
        for start in range(0, self.total_steps - self.seq_len - self.pred_horizon + 1):
            mid = start + self.seq_len
            end = mid + self.pred_horizon
            seq = self.series[:, start:mid, :]
            tgt = self.series[:, mid:end, 0]
            samples.append(SpatioTemporalSample(self.coords, seq, tgt, self._graph.adjacency))
        return samples

    def split(self, train_ratio: float = 0.7, val_ratio: float = 0.2) -> tuple[list[SpatioTemporalSample], list[SpatioTemporalSample], list[SpatioTemporalSample]]:
        windows = self._windows()
        n = len(windows)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        train = windows[:n_train]
        val = windows[n_train : n_train + n_val]
        test = windows[n_train + n_val :]
        return train, val, test

    def batch_iter(self) -> Iterator[list[dict[str, np.ndarray]]]:
        windows = self._windows()
        idx = np.arange(len(windows))
        if self.shuffle:
            rng = np.random.default_rng(self.seed)
            rng.shuffle(idx)

        for start in range(0, len(idx), self.batch_size):
            ids = idx[start : start + self.batch_size]
            batch: list[dict[str, np.ndarray]] = []
            for i in ids:
                item = windows[int(i)]
                batch.append(
                    {
                        "coords": item.coords,
                        "series": item.series,
                        "targets": item.targets,
                        "adjacency": item.adjacency,
                    }
                )
            yield batch
