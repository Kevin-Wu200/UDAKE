"""GeoJSON 到数据集的转换。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


def _to_feature_row(feature: dict[str, Any], target_key: str) -> tuple[list[float], float]:
    geom = feature.get("geometry", {})
    if geom.get("type") != "Point":
        raise ValueError("当前仅支持 Point 几何")
    coordinates = geom.get("coordinates", [])
    props = feature.get("properties", {})
    target = props.get(target_key)
    if target is None:
        raise ValueError(f"缺少目标字段: {target_key}")

    extra_features = [float(v) for k, v in props.items() if k != target_key and isinstance(v, (int, float))]
    row = [float(c) for c in coordinates] + extra_features
    return row, float(target)


@dataclass
class GeoJSONSamples:
    features: np.ndarray
    targets: np.ndarray


class GeoJSONDataset:
    """简易数据集，兼容 torch Dataset 访问接口。"""

    def __init__(self, samples: GeoJSONSamples) -> None:
        self.features = samples.features
        self.targets = samples.targets

    def __len__(self) -> int:
        return int(len(self.features))

    def __getitem__(self, index: int) -> tuple[np.ndarray, np.ndarray]:
        return self.features[index], np.asarray(self.targets[index])


def geojson_to_dataset(payload: dict[str, Any], target_key: str = "value") -> GeoJSONDataset:
    if payload.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON 必须为 FeatureCollection")
    features = payload.get("features", [])

    rows: list[list[float]] = []
    labels: list[float] = []
    for feature in features:
        row, target = _to_feature_row(feature, target_key)
        rows.append(row)
        labels.append(target)

    samples = GeoJSONSamples(features=np.asarray(rows, dtype=float), targets=np.asarray(labels, dtype=float))
    return GeoJSONDataset(samples)
