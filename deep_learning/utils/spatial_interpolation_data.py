"""Data preparation and preprocessing for spatial interpolation models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

import numpy as np

from deep_learning.models.spatial_interpolation.feature_extractors import (
    SpatialFeatureExtractor,
)
from deep_learning.models.spatial_interpolation.graph_builder import SpatialGraphBuilder


class SyntheticSpatialDataset:
    """Synthetic dataset generation for interpolation experiments."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)

    def generate(self, n_points: int = 64, noise_std: float = 0.02) -> dict[str, np.ndarray]:
        coords = self.rng.uniform(0.0, 1.0, size=(n_points, 2))
        values = np.sin(2.0 * np.pi * coords[:, 0]) + np.cos(2.0 * np.pi * coords[:, 1])
        values += self.rng.normal(0.0, noise_std, size=n_points)
        return {
            "coords": coords,
            "values": values,
            "targets": values.copy(),
        }


class RealSpatialDataLoader:
    """Load real data from CSV or GeoJSON into [coords, values]."""

    def load_csv(self, path: str) -> dict[str, np.ndarray]:
        rows = Path(path).read_text(encoding="utf-8").strip().splitlines()
        if len(rows) < 2:
            raise ValueError("csv file is empty")
        header = [x.strip() for x in rows[0].split(",")]
        x_idx = header.index("x")
        y_idx = header.index("y")
        v_idx = header.index("value")

        coords: list[list[float]] = []
        values: list[float] = []
        for row in rows[1:]:
            parts = [x.strip() for x in row.split(",")]
            coords.append([float(parts[x_idx]), float(parts[y_idx])])
            values.append(float(parts[v_idx]))

        arr_coords = np.asarray(coords, dtype=float)
        arr_values = np.asarray(values, dtype=float)
        return {"coords": arr_coords, "values": arr_values, "targets": arr_values.copy()}

    def load_geojson(self, path: str) -> dict[str, np.ndarray]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        features = payload.get("features", [])
        coords: list[list[float]] = []
        values: list[float] = []
        for feat in features:
            geom = feat.get("geometry", {})
            props = feat.get("properties", {})
            if geom.get("type") != "Point":
                continue
            x, y = geom.get("coordinates", [None, None])
            v = props.get("value")
            if x is None or y is None or v is None:
                continue
            coords.append([float(x), float(y)])
            values.append(float(v))

        arr_coords = np.asarray(coords, dtype=float)
        arr_values = np.asarray(values, dtype=float)
        return {"coords": arr_coords, "values": arr_values, "targets": arr_values.copy()}


class SpatialDataAugmentation:
    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)

    def apply(self, coords: np.ndarray, values: np.ndarray, noise_std: float = 0.01, shift: float = 0.01) -> tuple[np.ndarray, np.ndarray]:
        noisy_values = values + self.rng.normal(0.0, noise_std, size=len(values))
        jitter = self.rng.uniform(-shift, shift, size=coords.shape)
        return coords + jitter, noisy_values


class GraphConstructionTools:
    def __init__(self) -> None:
        self.builder = SpatialGraphBuilder(default_k=8, default_radius=0.25)

    def knn_graph(self, coords: np.ndarray, values: np.ndarray, k: int = 8):
        return self.builder.build(coords=coords, values=values, strategy="knn", k=k)

    def radius_graph(self, coords: np.ndarray, values: np.ndarray, radius: float = 0.2):
        return self.builder.build(coords=coords, values=values, strategy="radius", radius=radius)

    def delaunay_graph(self, coords: np.ndarray, values: np.ndarray):
        return self.builder.build(coords=coords, values=values, strategy="delaunay")


class FeatureExtractionTools:
    def __init__(self) -> None:
        self.spatial = SpatialFeatureExtractor()

    def spatial_features(self, coords: np.ndarray) -> np.ndarray:
        return self.spatial.extract(coords)

    def statistical_features(self, values: np.ndarray) -> np.ndarray:
        v = np.asarray(values, dtype=float).reshape(-1)
        mean = np.full_like(v, np.mean(v), dtype=float)
        std = np.full_like(v, np.std(v), dtype=float)
        centered = v - mean
        skew = centered ** 3
        return np.stack([mean, std, skew], axis=1)

    def topology_features(self, graph_adj: np.ndarray) -> np.ndarray:
        adj = np.asarray(graph_adj, dtype=float)
        degree = adj.sum(axis=1)
        clustering = np.zeros(len(adj), dtype=float)

        for i in range(len(adj)):
            neighbors = np.where(adj[i] > 0)[0]
            if len(neighbors) < 2:
                clustering[i] = 0.0
                continue
            subgraph = adj[np.ix_(neighbors, neighbors)]
            possible = len(neighbors) * (len(neighbors) - 1)
            clustering[i] = subgraph.sum() / max(1.0, possible)

        return np.stack([degree, clustering], axis=1)


@dataclass
class NormalizationStats:
    mean: np.ndarray
    std: np.ndarray


class ValueNormalizer:
    def __init__(self) -> None:
        self.stats: NormalizationStats | None = None

    def fit(self, values: np.ndarray) -> "ValueNormalizer":
        v = np.asarray(values, dtype=float).reshape(-1, 1)
        self.stats = NormalizationStats(mean=v.mean(axis=0), std=np.maximum(v.std(axis=0), 1e-6))
        return self

    def transform(self, values: np.ndarray) -> np.ndarray:
        if self.stats is None:
            raise ValueError("normalizer is not fitted")
        v = np.asarray(values, dtype=float).reshape(-1, 1)
        return ((v - self.stats.mean) / self.stats.std).reshape(-1)

    def inverse_transform(self, values: np.ndarray) -> np.ndarray:
        if self.stats is None:
            raise ValueError("normalizer is not fitted")
        v = np.asarray(values, dtype=float).reshape(-1, 1)
        return (v * self.stats.std + self.stats.mean).reshape(-1)


class CoordNormalizer:
    def __init__(self) -> None:
        self.min_: np.ndarray | None = None
        self.max_: np.ndarray | None = None

    def fit(self, coords: np.ndarray) -> "CoordNormalizer":
        c = np.asarray(coords, dtype=float)
        self.min_ = c.min(axis=0)
        self.max_ = c.max(axis=0)
        return self

    def transform(self, coords: np.ndarray) -> np.ndarray:
        if self.min_ is None or self.max_ is None:
            raise ValueError("normalizer is not fitted")
        c = np.asarray(coords, dtype=float)
        scale = np.where((self.max_ - self.min_) == 0, 1.0, self.max_ - self.min_)
        return (c - self.min_) / scale


class VarianceNormalizer(ValueNormalizer):
    pass


class SpatialInterpolationDataLoader:
    """Data loader with single/batch/grid prediction modes."""

    def __init__(self, dataset: dict[str, np.ndarray], batch_size: int = 16, shuffle: bool = True, seed: int = 42) -> None:
        self.coords = np.asarray(dataset["coords"], dtype=float)
        self.values = np.asarray(dataset["values"], dtype=float).reshape(-1)
        self.targets = np.asarray(dataset.get("targets", self.values), dtype=float).reshape(-1)
        self.batch_size = max(1, int(batch_size))
        self.shuffle = shuffle
        self.seed = seed

    def single_point_mode(self) -> Iterator[dict[str, np.ndarray]]:
        for i in range(len(self.coords)):
            yield {
                "coords": self.coords[i : i + 1],
                "values": self.values[i : i + 1],
                "targets": self.targets[i : i + 1],
            }

    def batch_mode(self) -> Iterator[list[dict[str, np.ndarray]]]:
        indices = np.arange(len(self.coords))
        if self.shuffle:
            rng = np.random.default_rng(self.seed)
            rng.shuffle(indices)

        for start in range(0, len(indices), self.batch_size):
            ids = indices[start : start + self.batch_size]
            batch: list[dict[str, np.ndarray]] = []
            for idx in ids:
                batch.append(
                    {
                        "coords": self.coords,
                        "values": self.values,
                        "targets": self.targets,
                        "query": self.coords[idx : idx + 1],
                    }
                )
            yield batch

    def grid_mode(
        self,
        x_bounds: tuple[float, float] | None = None,
        y_bounds: tuple[float, float] | None = None,
        grid_size: int = 20,
    ) -> dict[str, np.ndarray]:
        x_min, x_max = x_bounds if x_bounds is not None else (float(self.coords[:, 0].min()), float(self.coords[:, 0].max()))
        y_min, y_max = y_bounds if y_bounds is not None else (float(self.coords[:, 1].min()), float(self.coords[:, 1].max()))

        xs = np.linspace(x_min, x_max, grid_size)
        ys = np.linspace(y_min, y_max, grid_size)
        mesh_x, mesh_y = np.meshgrid(xs, ys)
        query = np.stack([mesh_x.reshape(-1), mesh_y.reshape(-1)], axis=1)

        return {
            "coords": self.coords,
            "values": self.values,
            "targets": self.targets,
            "grid_query": query,
            "grid_shape": np.array([grid_size, grid_size], dtype=int),
        }


def build_spatial_dataset(
    mode: Literal["synthetic", "csv", "geojson"],
    source: str | None = None,
    n_points: int = 64,
) -> dict[str, np.ndarray]:
    if mode == "synthetic":
        return SyntheticSpatialDataset().generate(n_points=n_points)

    loader = RealSpatialDataLoader()
    if source is None:
        raise ValueError("source path is required for csv/geojson modes")
    if mode == "csv":
        return loader.load_csv(source)
    if mode == "geojson":
        return loader.load_geojson(source)
    raise ValueError(f"unsupported mode: {mode}")
