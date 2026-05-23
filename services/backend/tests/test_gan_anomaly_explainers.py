"""GAN 异常解释适配器测试。"""

from __future__ import annotations

import numpy as np
from app.dl_services.gan_anomaly_explainer import (
    GANAnomalyLimeAdapter,
    GANAnomalySHAPAdapter,
)

from deep_learning.models.anomaly_detection import GANAnomalyDetector


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
            [120.22, 30.32],
            [120.16, 30.24],
        ],
        dtype=float,
    )
    values = np.asarray([1.0, 1.1, 0.95, 1.3, 1.18, 2.2, 1.05, 0.98, 1.12, 1.25], dtype=float)
    return coords, values


def _build_trained_model() -> tuple[GANAnomalyDetector, np.ndarray, np.ndarray]:
    coords, values = _build_data()
    model = GANAnomalyDetector()
    model.fit(coords, values)
    return model, coords, values


def test_gan_lime_adapter_generates_explanations() -> None:
    model, coords, values = _build_trained_model()
    adapter = GANAnomalyLimeAdapter()

    result = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=3)

    assert result["summary"]["method"] == "lime"
    assert result["summary"]["explained_nodes"] == 3
    assert len(result["batch_explanations"]) == 3
    assert "generator_analysis" in result
    assert len(result["score_components"]["combined"]) == len(values)
    assert "anomaly_score_explanation" in result
    assert "output_analysis" in result["generator_analysis"]
    assert "quality_metrics" in result["generator_analysis"]
    assert "latent_space_distribution" in result["generator_analysis"]
    assert "anomaly_patterns" in result["generator_analysis"]
    assert "sample_comparison" in result["generator_analysis"]
    assert len(result["anomaly_score_explanation"]["decomposition"]) == len(values)
    assert len(result["anomaly_score_explanation"]["key_anomaly_nodes"]) >= 1
    assert len(result["anomaly_score_explanation"]["key_anomaly_features"]) >= 1
    assert len(result["anomaly_score_explanation"]["anomaly_reasons"]) == 3

    component = result["anomaly_score_explanation"]["component_contribution"]
    assert component["discriminator_total"] >= 0.0
    assert component["generator_total"] >= 0.0
    assert 0.0 <= component["discriminator_ratio"] <= 1.0
    assert 0.0 <= component["generator_ratio"] <= 1.0
    assert len(component["explained_node_breakdown"]) == 3

    first = result["batch_explanations"][0]
    assert "decomposition" in first
    assert "reason" in first
    assert first["reason"].startswith("节点")

    consistency = result["anomaly_score_explanation"]["consistency_validation"]
    assert "is_reasonable" in consistency
    assert "score_corr" in consistency


def test_gan_shap_adapter_generates_explanations_and_cache() -> None:
    model, coords, values = _build_trained_model()
    adapter = GANAnomalySHAPAdapter()

    first = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=2)
    second = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=2)

    assert first["summary"]["method"] == "shap"
    assert first["summary"]["explained_nodes"] == 2
    assert len(first["batch_explanations"]) == 2
    assert "component_contribution" in first["anomaly_score_explanation"]
    assert len(first["anomaly_score_explanation"]["anomaly_reasons"]) == 2
    assert second["performance"]["cache_hit"] is True


def test_gan_generator_analysis_contains_stage2_sections() -> None:
    model, coords, values = _build_trained_model()
    adapter = GANAnomalyLimeAdapter()

    result = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=4)
    generator = result["generator_analysis"]

    output = generator["output_analysis"]
    quality = generator["quality_metrics"]
    latent = generator["latent_space_distribution"]
    patterns = generator["anomaly_patterns"]
    comparison = generator["sample_comparison"]

    assert output["distribution_match"]["pearson_corr"] <= 1.0
    assert output["distribution_match"]["pearson_corr"] >= -1.0
    assert quality["mae"] >= 0.0
    assert quality["rmse"] >= 0.0
    assert quality["mape"] >= 0.0

    assert "stats" in latent
    assert "quantiles" in latent
    assert "distribution_health" in latent
    assert isinstance(latent["histogram"], list)
    assert "mode_collapse_risk" in latent["distribution_health"]

    assert "pattern_counts" in patterns
    assert "detected_patterns" in patterns
    assert isinstance(patterns["detected_patterns"], list)
    assert sum(patterns["pattern_counts"].values()) == len(patterns["detected_patterns"])

    assert "anomalous_samples" in comparison
    assert "reference_samples" in comparison
    assert isinstance(comparison["anomalous_samples"], list)
    assert isinstance(comparison["reference_samples"], list)
    assert len(generator["node_analysis"]) == len(values)
