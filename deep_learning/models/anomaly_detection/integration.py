"""异常检测系统集成、融合推理、实时告警。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import ThresholdMethod, compute_threshold, safe_minmax


@dataclass
class AlertConfig:
    threshold: float = 0.85
    min_count: int = 1


class AnomalyAlertSystem:
    def __init__(self, config: AlertConfig | None = None) -> None:
        self.config = config or AlertConfig()

    def evaluate(self, scores: np.ndarray, indices: list[int]) -> dict[str, Any]:
        s = np.asarray(scores, dtype=float).reshape(-1)
        if len(s) == 0:
            return {"triggered": False, "level": "none", "count": 0}
        max_score = float(s.max())
        count = len(indices)
        triggered = count >= self.config.min_count and max_score >= self.config.threshold
        level = "high" if max_score >= max(0.95, self.config.threshold) else ("medium" if triggered else "low")
        return {
            "triggered": bool(triggered),
            "level": level,
            "count": int(count),
            "max_score": max_score,
        }


class AnomalyEnsembleIntegrator:
    """与现有方法融合，支持实时检测。"""

    def __init__(self, detectors: dict[str, Any], alert_system: AnomalyAlertSystem | None = None) -> None:
        if not detectors:
            raise ValueError("detectors 不能为空")
        self.detectors = detectors
        self.alert_system = alert_system or AnomalyAlertSystem()

    def detect(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        threshold_method: ThresholdMethod = "percentile",
        percentile: float = 95.0,
        k: float = 2.5,
        weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        component_scores: dict[str, np.ndarray] = {}
        component_outputs: dict[str, Any] = {}

        if weights is None:
            weights = {name: 1.0 / len(self.detectors) for name in self.detectors.keys()}

        for name, detector in self.detectors.items():
            pred = detector.predict(
                coords,
                values,
                threshold_method=threshold_method,
                percentile=percentile,
                k=k,
            )
            scores = np.asarray(pred.get("scores") or pred.get("node_scores") or [], dtype=float)
            if len(scores) == 0 and "score_components" in pred:
                parts = pred["score_components"]
                if "reconstruction" in parts:
                    scores = np.asarray(parts["reconstruction"], dtype=float)
                elif "feature_distance" in parts:
                    scores = np.asarray(parts["feature_distance"], dtype=float)
            if len(scores) == 0:
                scores = np.zeros(len(values), dtype=float)
            component_scores[name] = safe_minmax(scores)
            component_outputs[name] = pred

        fused = np.zeros(len(values), dtype=float)
        weight_sum = sum(float(weights.get(name, 0.0)) for name in component_scores.keys()) + 1e-9
        for name, scores in component_scores.items():
            fused += float(weights.get(name, 0.0)) / weight_sum * scores

        threshold = compute_threshold(fused, method=threshold_method, percentile=percentile, k=k)
        anomaly_idx = np.where(fused >= threshold.value)[0].tolist()
        alert = self.alert_system.evaluate(fused, anomaly_idx)

        return {
            "anomaly_indices": anomaly_idx,
            "anomaly_count": len(anomaly_idx),
            "fused_scores": fused.tolist(),
            "threshold": threshold.value,
            "threshold_method": threshold.method,
            "component_outputs": component_outputs,
            "component_weights": {k: float(v) for k, v in weights.items()},
            "alert": alert,
        }

    def detect_realtime(
        self,
        stream_batches: list[dict[str, np.ndarray]],
        threshold_method: ThresholdMethod = "adaptive",
        percentile: float = 95.0,
        k: float = 2.5,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for idx, batch in enumerate(stream_batches):
            coords = np.asarray(batch["coords"], dtype=float)
            values = np.asarray(batch["values"], dtype=float)
            res = self.detect(
                coords,
                values,
                threshold_method=threshold_method,
                percentile=percentile,
                k=k,
            )
            res["batch_index"] = idx
            results.append(res)
        return results
