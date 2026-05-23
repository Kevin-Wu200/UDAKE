"""Anomaly detection utilities for data quality evaluation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

import numpy as np

from .models import AnomalyRecord


class DataQualityAnomalyDetector:
    """Detect statistical and spatial anomalies."""

    def detect_from_records(
        self,
        records: List[Dict[str, Any]],
        value_field: str = "value",
        x_field: str = "x",
        y_field: str = "y",
        z_threshold: float = 3.0,
    ) -> List[AnomalyRecord]:
        if not records:
            return []

        value_hits = self.detect_value_anomalies(records, value_field=value_field, z_threshold=z_threshold)
        spatial_hits = self.detect_spatial_anomalies(records, x_field=x_field, y_field=y_field, z_threshold=z_threshold)

        merged: Dict[int, Dict[str, Any]] = defaultdict(lambda: {"methods": set(), "field": value_field, "value": None, "score": 0.0})

        for item in value_hits:
            slot = merged[item.row_index]
            slot["field"] = item.field
            slot["value"] = item.value
            slot["methods"].update(item.methods)
            slot["score"] = max(slot["score"], item.score)

        for item in spatial_hits:
            slot = merged[item.row_index]
            slot["field"] = item.field
            slot["value"] = item.value
            slot["methods"].update(item.methods)
            slot["score"] = max(slot["score"], item.score)

        result = [
            AnomalyRecord(
                row_index=index,
                field=payload["field"],
                value=payload["value"],
                methods=sorted(payload["methods"]),
                score=round(float(payload["score"]), 4),
            )
            for index, payload in merged.items()
        ]
        result.sort(key=lambda item: item.score, reverse=True)
        return result

    def detect_value_anomalies(
        self,
        records: List[Dict[str, Any]],
        value_field: str = "value",
        z_threshold: float = 3.0,
    ) -> List[AnomalyRecord]:
        indices, values = _extract_numeric(records, value_field)
        if len(values) < 5:
            return []

        arr = np.array(values, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr))
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = float(q3 - q1)

        method_hits: Dict[int, set[str]] = defaultdict(set)
        score_map: Dict[int, float] = defaultdict(float)

        if std > 0:
            z_scores = np.abs((arr - mean) / std)
            for local_idx, z_val in enumerate(z_scores):
                if z_val > 3:
                    method_hits[local_idx].add("3sigma")
                if z_val > z_threshold:
                    method_hits[local_idx].add("zscore")
                score_map[local_idx] = max(score_map[local_idx], float(z_val))

        if iqr > 0:
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            for local_idx, value in enumerate(arr):
                if value < lower or value > upper:
                    method_hits[local_idx].add("iqr")
                    score_map[local_idx] = max(score_map[local_idx], float(abs(value - mean) / (std + 1e-9)))

        anomalies: List[AnomalyRecord] = []
        for local_idx, methods in method_hits.items():
            global_idx = indices[local_idx]
            anomalies.append(
                AnomalyRecord(
                    row_index=global_idx,
                    field=value_field,
                    value=records[global_idx].get(value_field),
                    methods=sorted(methods),
                    score=round(score_map.get(local_idx, 0.0), 4),
                )
            )

        return anomalies

    def detect_spatial_anomalies(
        self,
        records: List[Dict[str, Any]],
        x_field: str = "x",
        y_field: str = "y",
        z_threshold: float = 3.0,
    ) -> List[AnomalyRecord]:
        idx_x, x_values = _extract_numeric(records, x_field)
        idx_y, y_values = _extract_numeric(records, y_field)

        common = sorted(set(idx_x) & set(idx_y))
        if len(common) < 5:
            return []

        points = np.array([
            [float(records[index][x_field]), float(records[index][y_field])] for index in common
        ])

        center = points.mean(axis=0)
        dists = np.linalg.norm(points - center, axis=1)
        dist_std = float(np.std(dists))
        if dist_std <= 0:
            return []

        dist_mean = float(np.mean(dists))
        z_scores = np.abs((dists - dist_mean) / dist_std)

        anomalies: List[AnomalyRecord] = []
        for local_idx, z_val in enumerate(z_scores):
            if z_val <= z_threshold:
                continue
            row_index = common[local_idx]
            anomalies.append(
                AnomalyRecord(
                    row_index=row_index,
                    field=f"{x_field},{y_field}",
                    value={"x": records[row_index][x_field], "y": records[row_index][y_field]},
                    methods=["spatial_zscore"],
                    score=round(float(z_val), 4),
                )
            )

        return anomalies


def _extract_numeric(records: List[Dict[str, Any]], field: str) -> Tuple[List[int], List[float]]:
    indices: List[int] = []
    values: List[float] = []

    for idx, row in enumerate(records):
        value = row.get(field)
        if value is None or value == "":
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if np.isnan(numeric):
            continue
        indices.append(idx)
        values.append(numeric)

    return indices, values
