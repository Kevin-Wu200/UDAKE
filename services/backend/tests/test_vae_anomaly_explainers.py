"""VAE 异常解释适配器测试。"""

from __future__ import annotations

import numpy as np

from app.dl_services.vae_anomaly_explainer import VAEAnomalyLIMEAdapter, VAEAnomalySHAPAdapter
from deep_learning.models.anomaly_detection import VAEAnomalyDetector


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


def _build_trained_model() -> tuple[VAEAnomalyDetector, np.ndarray, np.ndarray]:
    coords, values = _build_data()
    model = VAEAnomalyDetector()
    model.fit(coords, values)
    return model, coords, values


def test_vae_lime_adapter_generates_explanations() -> None:
    model, coords, values = _build_trained_model()
    adapter = VAEAnomalyLIMEAdapter()
    result = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=3)

    assert result["summary"]["method"] == "lime"
    assert result["summary"]["explained_nodes"] == 3
    assert len(result["batch_explanations"]) == 3
    assert "reconstruction_analysis" in result
    assert len(result["score_components"]["combined"]) == len(values)


def test_vae_shap_adapter_generates_explanations_and_cache() -> None:
    model, coords, values = _build_trained_model()
    adapter = VAEAnomalySHAPAdapter()
    first = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=2)
    second = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=2)

    assert first["summary"]["method"] == "shap"
    assert len(first["batch_explanations"]) == 2
    assert second["performance"]["cache_hit"] is True
