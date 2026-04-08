from __future__ import annotations

import numpy as np
import pytest

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
    assert "anomaly_score_explanation" in lime
    assert "consistency_validation" in lime["anomaly_score_explanation"]
    assert len(lime["anomaly_score_explanation"]["key_anomaly_features"]) >= 1
    assert len(lime["anomaly_score_explanation"]["anomaly_reasons"]) == 5
    assert "reason" in lime["batch_explanations"][0]
    assert "decomposition" in lime["batch_explanations"][0]

    shap_adapter = ContrastiveShapAdapter(config=ContrastiveExplanationConfig(shap_nsamples=120))
    shap = shap_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, nsamples=100)
    assert shap["summary"]["method"] == "shap"
    assert shap["summary"]["explained_nodes"] == 5
    assert shap["summary"]["nsamples"] == 100
    assert len(shap["global_feature_importance"]) >= 1
    assert "encoder_shap_analysis" in shap
    assert "contrastive_loss_shap_analysis" in shap
    assert "anomaly_score_explanation" in shap
    assert "component_contribution" in shap["anomaly_score_explanation"]
    assert len(shap["anomaly_score_explanation"]["anomaly_reasons"]) == 5
    assert "reason" in shap["batch_explanations"][0]
    assert "decomposition" in shap["batch_explanations"][0]


def test_contrastive_preprocess_validation_and_batch_support() -> None:
    coords, values = _make_data(n=50, seed=39)
    model = ContrastiveAnomalyDetector()

    pre = model.preprocess_contrastive_data(coords, values, batch_size=16, use_training_stats=False, augmentation=False)
    processed = np.asarray(pre["processed_features"], dtype=float)

    assert processed.shape == (len(values), 10)
    assert len(pre["feature_names"]) == 10
    assert len(pre["batch_slices"]) == 4
    assert pre["batch_slices"][-1] == [48, 50]
    assert len(pre["positive_pairs"]) == len(values)
    assert len(pre["negative_pairs"]) == len(values)

    validation = pre["validation"]
    assert validation["is_valid"] is True
    assert validation["n_points"] == len(values)
    assert validation["pair_count"] == len(values)
    assert validation["batch_size"] == 16
    assert validation["num_batches"] == 4
    assert validation["last_batch_size"] == 2
    assert validation["feature_dim"] == 10
    assert isinstance(validation["zero_variance_feature_indices"], list)

    assert abs(float(np.mean(processed))) < 0.5
    assert np.isfinite(processed).all()
    assert pre["scaler"]["source"] == "runtime"


def test_contrastive_preprocess_training_stats_and_fallback() -> None:
    coords, values = _make_data(n=64, seed=67)
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=10)

    trained = model.preprocess_contrastive_data(coords, values, batch_size=32, use_training_stats=True, augmentation=False)
    assert trained["scaler"]["source"] == "trained"

    model.feature_mean = np.zeros((1, 3), dtype=float)
    model.feature_std = np.ones((1, 3), dtype=float)
    fallback = model.preprocess_contrastive_data(coords, values, batch_size=32, use_training_stats=True, augmentation=False)
    assert fallback["scaler"]["source"] == "runtime_fallback"

    with pytest.raises(ValueError):
        model.preprocess_contrastive_data(coords, values, batch_size=0)


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


def test_contrastive_similarity_distribution_analysis() -> None:
    coords, values = _make_data(n=72, seed=91)
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=12)

    lime_adapter = ContrastiveLimeAdapter(config=ContrastiveExplanationConfig(lime_num_samples=160))
    lime = lime_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=100)
    analysis = lime["embedding_analysis"]["similarity_distribution_analysis"]

    assert "sample_similarity" in analysis
    assert "distribution" in analysis
    assert "anomaly_patterns" in analysis
    assert "threshold_boundaries" in analysis
    assert "heatmap" in analysis

    sim = analysis["sample_similarity"]
    assert sim["matrix_shape"][0] == sim["matrix_shape"][1]
    assert len(sim["similarity_matrix"]) == sim["matrix_shape"][0]
    assert len(sim["node_mean_similarity"]) == sim["matrix_shape"][0]

    dist = analysis["distribution"]
    assert "stats" in dist and "histogram" in dist
    assert len(dist["histogram"]["bin_edges"]) == 11
    assert len(dist["histogram"]["counts"]) == 10

    boundaries = analysis["threshold_boundaries"]
    assert boundaries["node_low_similarity_threshold_p10"] <= boundaries["node_high_similarity_threshold_p90"]
    assert boundaries["pair_low_similarity_threshold_p05"] <= boundaries["pair_high_similarity_threshold_p95"]

    heatmap = analysis["heatmap"]
    assert len(heatmap["labels"]) == sim["matrix_shape"][0]
    assert len(heatmap["matrix"]) == sim["matrix_shape"][0]
    assert len(heatmap["score_order_desc"]) == sim["matrix_shape"][0]

    shap_adapter = ContrastiveShapAdapter(config=ContrastiveExplanationConfig(shap_nsamples=100))
    shap = shap_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, nsamples=80)
    shap_analysis = shap["embedding_analysis"]["similarity_distribution_analysis"]
    assert "anomaly_patterns" in shap_analysis
    assert "high_score_low_similarity_nodes" in shap_analysis["anomaly_patterns"]


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
