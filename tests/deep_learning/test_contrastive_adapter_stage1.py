from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import ContrastiveAnomalyDetector
from services.backend.app.dl_services.contrastive_anomaly_explainer import (
    ContrastiveExplanationConfig,
    ContrastiveLimeAdapter,
    ContrastiveShapAdapter,
)
from services.backend.app.dl_services.service import DeepLearningService


def _make_data(n: int = 80, seed: int = 37) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.8) + np.cos(coords[:, 1] * 3.5) + rng.normal(0.0, 0.06, size=n)
    values[::12] += 0.9
    values[5::21] -= 0.55
    return coords, values


def test_contrastive_lime_and_shap_adapters() -> None:
    coords, values = _make_data()
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=16)

    lime_adapter = ContrastiveLimeAdapter(config=ContrastiveExplanationConfig(lime_num_samples=180))
    lime = lime_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=120)
    assert lime["summary"]["method"] == "lime"
    assert lime["summary"]["explained_nodes"] == 5
    assert len(lime["global_feature_importance"]) >= 1

    shap_adapter = ContrastiveShapAdapter(config=ContrastiveExplanationConfig(shap_nsamples=120))
    shap = shap_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, nsamples=100)
    assert shap["summary"]["method"] == "shap"
    assert shap["summary"]["explained_nodes"] == 5
    assert shap["summary"]["nsamples"] == 100
    assert len(shap["global_feature_importance"]) >= 1
    assert "encoder_shap_analysis" in shap
    assert "contrastive_loss_shap_analysis" in shap


def test_contrastive_shap_cache_and_validation_fields() -> None:
    coords, values = _make_data(seed=41)
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=14)

    adapter = ContrastiveShapAdapter(config=ContrastiveExplanationConfig(shap_nsamples=110))
    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, nsamples=90)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, nsamples=90)

    assert "validation" in out1
    assert "surrogate_fidelity" in out1["validation"]
    assert "additivity_mean_abs_error" in out1["validation"]
    assert "additivity_max_abs_error" in out1["validation"]
    assert "embedding_input" in out1
    assert "explainer_config" in out1["summary"]
    assert out1["summary"]["explainer_config"]["effective_nsamples"] >= out1["summary"]["nsamples"]
    assert out2["performance"]["cache_hit"] is True


def test_service_supports_contrastive_hybrid_explain() -> None:
    coords, values = _make_data(n=64, seed=53)
    service = DeepLearningService()

    out = service.explain_anomaly(
        model_name="contrastive",
        coords=coords.tolist(),
        values=values.tolist(),
        method="hybrid",
        top_k=4,
        max_explain_nodes=4,
        include_prediction=True,
        num_samples=120,
        nsamples=90,
    )
    assert out["model_name"] == "contrastive"
    assert out["summary"]["method"] == "hybrid"
    assert "lime" in out
    assert "shap" in out
    assert "prediction" in out
