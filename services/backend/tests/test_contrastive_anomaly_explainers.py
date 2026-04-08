"""Contrastive 异常解释适配器测试。"""

from __future__ import annotations

import numpy as np

from app.dl_services.contrastive_anomaly_explainer import ContrastiveLimeAdapter
from deep_learning.models.anomaly_detection import ContrastiveAnomalyDetector


def _build_data() -> tuple[np.ndarray, np.ndarray]:
    coords = np.asarray(
        [
            [120.10, 30.20],
            [120.20, 30.25],
            [120.18, 30.30],
            [120.24, 30.28],
            [120.15, 30.35],
            [120.28, 30.22],
            [120.30, 30.26],
            [120.12, 30.18],
        ],
        dtype=float,
    )
    values = np.asarray([1.0, 1.1, 0.95, 1.3, 1.18, 2.2, 1.05, 0.98], dtype=float)
    return coords, values


def _build_trained_model() -> tuple[ContrastiveAnomalyDetector, np.ndarray, np.ndarray]:
    coords, values = _build_data()
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=12)
    return model, coords, values


def test_contrastive_lime_adapter_generates_explanations_and_cache() -> None:
    model, coords, values = _build_trained_model()
    adapter = ContrastiveLimeAdapter()
    first = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=3)
    second = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=3)

    assert first["summary"]["method"] == "lime"
    assert first["summary"]["explained_nodes"] == 3
    assert len(first["batch_explanations"]) == 3
    assert len(first["score_components"]["combined"]) == len(values)
    assert "encoder_components" in first
    assert second["performance"]["cache_hit"] is True
