from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import ContrastiveAnomalyDetector
from services.backend.app.dl_services.contrastive_anomaly_explainer import (
    ContrastiveExplanationConfig,
    ContrastiveLimeAdapter,
    ContrastiveShapAdapter,
)


def _make_data(n: int = 92, seed: int = 19) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.6) + np.cos(coords[:, 1] * 3.9) + rng.normal(0.0, 0.05, size=n)
    values[::13] += 0.95
    values[7::27] -= 0.62
    return coords, values


def _fit_model(coords: np.ndarray, values: np.ndarray) -> ContrastiveAnomalyDetector:
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=14)
    return model


def test_contrastive_lime_stage2_prediction_and_embedding_analysis() -> None:
    coords, values = _make_data()
    model = _fit_model(coords, values)

    adapter = ContrastiveLimeAdapter(config=ContrastiveExplanationConfig(parallel_workers=2, lime_num_samples=180))
    out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, num_samples=140)

    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 6
    assert len(out["batch_explanations"]) == 6
    assert "anomaly_score_explanation" in out

    first = out["batch_explanations"][0]
    assert isinstance(first["prediction"], float)
    assert isinstance(first["target_prediction"], float)
    assert "top_contributions" in first and len(first["top_contributions"]) >= 1
    assert "decomposition" in first and "reason" in first

    anomaly = out["anomaly_score_explanation"]
    assert len(anomaly["decomposition"]) == len(values)
    assert len(anomaly["key_anomaly_nodes"]) >= 1
    assert len(anomaly["key_anomaly_features"]) >= 1
    assert len(anomaly["anomaly_reasons"]) == 6
    assert set(anomaly["consistency_validation"].keys()) == {"is_reasonable", "score_corr", "coverage"}

    embed = out["embedding_analysis"]
    assert embed["summary"]["embedding_count"] == len(values)
    assert embed["summary"]["embedding_dim"] > 0
    assert "similarity" in embed
    assert "distribution" in embed
    assert "anomaly_patterns" in embed
    assert "visualization" in embed


def test_contrastive_shap_stage2_prediction_and_similarity_distribution() -> None:
    coords, values = _make_data(seed=31)
    model = _fit_model(coords, values)

    adapter = ContrastiveShapAdapter(
        config=ContrastiveExplanationConfig(parallel_workers=2, shap_nsamples=130, shap_feature_cap=6)
    )
    out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, nsamples=110)

    assert out["summary"]["method"] == "shap"
    assert out["summary"]["explained_nodes"] == 6
    assert out["summary"]["nsamples"] == 110
    assert len(out["batch_explanations"]) == 6

    first = out["batch_explanations"][0]
    assert isinstance(first["prediction"], float)
    assert isinstance(first["expected_value"], float)
    assert isinstance(first["target_prediction"], float)
    assert len(first["raw_shap_values"]) == out["summary"]["num_features"]
    assert "decomposition" in first and "reason" in first

    assert "encoder_shap_analysis" in out
    assert "contrastive_loss_shap_analysis" in out
    assert "embedding_input" in out

    sim_dist = out["embedding_analysis"]["similarity_distribution_analysis"]
    assert "sample_similarity" in sim_dist
    assert "distribution" in sim_dist
    assert "threshold_boundaries" in sim_dist
    assert "anomaly_patterns" in sim_dist
    assert "heatmap" in sim_dist

    predict_fn = adapter._predict_surrogate(adapter._build_context(model=model, coords=coords, values=values))
    pred = predict_fn(np.asarray(out["feature_importance"], dtype=float).reshape(1, -1))
    assert pred.shape == (1,)
    assert np.isfinite(pred).all()
