from __future__ import annotations

import numpy as np
import pytest

from deep_learning.models.anomaly_detection import GANAnomalyDetector
from services.backend.app.dl_services.gan_anomaly_explainer import (
    GANAnomalyLimeAdapter,
    GANAnomalySHAPAdapter,
    GANExplanationConfig,
    _safe_float,
)


def _make_data(n: int = 80, seed: int = 41) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.9) + np.cos(coords[:, 1] * 3.6) + rng.normal(0.0, 0.06, size=n)
    values[::13] += 0.85
    values[5::19] -= 0.58
    return coords, values


def _fit_model(coords: np.ndarray, values: np.ndarray) -> GANAnomalyDetector:
    model = GANAnomalyDetector()
    model.fit(coords, values)
    return model


def test_gan_preprocess_and_standard_predict() -> None:
    coords, values = _make_data()
    model = GANAnomalyDetector()

    with pytest.raises(ValueError):
        model.predict_standard(coords, values)

    model.fit(coords, values)
    pre = model.preprocess_gan_data(coords, values, batch_size=16, use_training_stats=True)

    processed = np.asarray(pre["processed_features"], dtype=float)
    assert processed.shape == (len(values), 9)
    assert len(pre["feature_names"]) == 9
    assert len(pre["batch_slices"]) == 5
    assert pre["batch_slices"][-1] == [64, 80]

    validation = pre["validation"]
    assert validation["is_valid"] is True
    assert validation["n_points"] == len(values)
    assert validation["batch_size"] == 16
    assert pre["scaler"]["source"] == "trained"

    pred = model.predict_standard(coords, values, threshold_method="percentile", percentile=92.0)
    assert len(pred["scores"]) == len(values)
    assert len(pred["labels"]) == len(values)
    assert pred["anomaly_count"] == len(pred["anomaly_indices"])
    assert 0.0 <= pred["threshold"] <= 1.0


def test_gan_lime_and_shap_adapters() -> None:
    coords, values = _make_data()
    model = _fit_model(coords, values)

    lime_adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(parallel_workers=2, lime_num_samples=180))
    lime = lime_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=120)
    assert lime["summary"]["method"] == "lime"
    assert lime["summary"]["explained_nodes"] == 5
    assert len(lime["global_feature_importance"]) >= 1
    assert "batch_slices" in lime["preprocess"]
    assert "validation" in lime["preprocess"]

    shap_adapter = GANAnomalySHAPAdapter(config=GANExplanationConfig(parallel_workers=2, shap_nsamples=120, shap_feature_cap=6))
    shap = shap_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, nsamples=100)
    assert shap["summary"]["method"] == "shap"
    assert shap["summary"]["explained_nodes"] == 5
    assert shap["summary"]["nsamples"] <= 100
    assert len(shap["global_feature_importance"]) >= 1


def test_gan_anomaly_score_explanation_and_generator_discriminator_analysis() -> None:
    coords, values = _make_data(seed=53)
    model = _fit_model(coords, values)

    adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(parallel_workers=2, lime_num_samples=180))
    out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, num_samples=130)

    anomaly = out["anomaly_score_explanation"]
    assert len(anomaly["decomposition"]) == len(values)
    assert len(anomaly["key_anomaly_nodes"]) >= 1
    assert len(anomaly["key_anomaly_features"]) >= 1
    assert len(anomaly["anomaly_reasons"]) == 6

    component = anomaly["component_contribution"]
    assert component["discriminator_total"] >= 0.0
    assert component["generator_total"] >= 0.0
    assert 0.0 <= component["discriminator_ratio"] <= 1.0
    assert 0.0 <= component["generator_ratio"] <= 1.0
    assert len(component["explained_node_breakdown"]) == 6

    consistency = anomaly["consistency_validation"]
    assert set(consistency.keys()) == {"is_reasonable", "score_corr", "coverage"}

    generator = out["generator_analysis"]
    assert "output_analysis" in generator
    assert "quality_metrics" in generator
    assert "latent_space_distribution" in generator
    assert "anomaly_patterns" in generator
    assert "sample_comparison" in generator
    assert len(generator["node_analysis"]) == len(values)

    discriminator = out["discriminator_analysis"]
    assert "decision_analysis" in discriminator
    assert "confidence_scores" in discriminator
    assert "decision_boundary" in discriminator
    assert "key_discriminator_features" in discriminator
    assert "adversarial_detection" in discriminator
    assert len(discriminator["decision_analysis"]["node_decisions"]) == len(values)
    assert len(discriminator["key_discriminator_features"]) >= 1


def test_gan_shap_cache_hit() -> None:
    coords, values = _make_data(seed=67)
    model = _fit_model(coords, values)

    adapter = GANAnomalySHAPAdapter(config=GANExplanationConfig(parallel_workers=2, shap_nsamples=110, shap_feature_cap=6))
    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, nsamples=90)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, nsamples=90)

    assert out1["performance"]["cache_hit"] is False
    assert out2["performance"]["cache_hit"] is True


def test_gan_base_adapter_edge_branches() -> None:
    coords, values = _make_data(n=48, seed=73)
    model = _fit_model(coords, values)
    adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(parallel_workers=1, lime_num_samples=120))

    assert _safe_float(object(), default=3.2) == 3.2
    assert adapter._cache_get("missing-key") is None
    assert adapter._context_get("missing-key") is None

    minmax_scaled, minmax_stats = adapter._standardize_column(np.array([5.0, 5.0, 5.0]), "minmax")
    robust_scaled, robust_stats = adapter._standardize_column(np.array([2.0, 2.0, 2.0, 2.0]), "robust_zscore")
    assert np.allclose(minmax_scaled, np.zeros(3))
    assert minmax_stats["strategy"] == 2.0
    assert np.allclose(robust_scaled, np.zeros(4))
    assert robust_stats["strategy"] == 1.0

    x = np.ones((4, 3), dtype=np.float32)
    bg = adapter._select_background(x, np.zeros(4), size=64)
    assert bg.shape == x.shape
    assert adapter._to_float32(x).dtype == np.float32
    assert adapter._feature_display("unknown_feature") == "unknown_feature"
    assert adapter._dynamic_lime_samples(n_features=2, n_points=3) >= 80
    assert adapter._dynamic_shap_samples(selected_nsamples=10, n_features=300, n_points=300) >= 40

    assert adapter._anomaly_profile(np.array([]), [])["node_labels"] == []
    assert adapter._component_contribution_analysis(decomposition=[], explained_nodes=[])["generator_total"] == 0.0
    assert adapter._extract_key_anomaly_features(batch_explanations=[], top_k=3) == []
    assert adapter._validate_explanation_consistency(decomposition=[], combined_scores=np.array([]), explained_nodes=[])["is_reasonable"] is False
    assert "GAN判别器分数触发" in adapter._explanation_reason(
        node_idx=2,
        decomposition_row={"discriminator_component": 0.1, "reconstruction_component": 0.2, "gradient_component": 0.3},
        top_contributions=[],
    )

    context = adapter._build_context(model=model, coords=coords, values=values)
    fallback_pairs, fallback_pred = adapter._fallback_local_pairs(context, node_index=0)
    assert len(fallback_pairs) == len(context["feature_names"])
    assert isinstance(fallback_pred, float)

    lime_out1 = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=4, num_samples=100)
    lime_out2 = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=4, num_samples=100)
    assert lime_out2["performance"]["cache_hit"] is True
    assert lime_out1["performance"]["post_parallel_workers"] == 1

    generator_fallback = adapter._generator_analysis(
        model=model,
        coords=coords,
        values=values,
        score_bundle=context["score_bundle"],
        generator_artifacts={"generated_values": np.array([0.0]), "latent_projection": np.array([0.0])},
    )
    assert "latent_space_distribution" in generator_fallback

    empty_discriminator = adapter._discriminator_analysis(
        model=model,
        coords=np.zeros((0, 2), dtype=float),
        values=np.array([], dtype=float),
        feature_names=[],
        feature_matrix=np.zeros((0, 0), dtype=float),
        score_bundle={"discriminator": np.array([]), "reconstruction": np.array([]), "gradient": np.array([]), "combined": np.array([])},
        batch_explanations=[],
        top_k=3,
    )
    assert empty_discriminator["decision_analysis"]["node_decisions"] == []

    shap_adapter = GANAnomalySHAPAdapter(config=GANExplanationConfig(parallel_workers=1, shap_nsamples=80, shap_feature_cap=5))
    shap_out = shap_adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=4, nsamples=80)
    assert shap_out["performance"]["post_parallel_workers"] == 1
