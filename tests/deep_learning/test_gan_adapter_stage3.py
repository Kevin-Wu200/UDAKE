from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import GANAnomalyDetector
from services.backend.app.dl_services.gan_anomaly_explainer import GANAnomalyLimeAdapter, GANAnomalySHAPAdapter, GANExplanationConfig


def _make_data(n: int = 88, seed: int = 23) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.0) + np.cos(coords[:, 1] * 3.4) + rng.normal(0.0, 0.06, size=n)
    values[::12] += 0.95
    values[5::19] -= 0.65
    return coords, values


def _assert_discriminator_payload(payload: dict) -> None:
    assert "decision_analysis" in payload
    assert "confidence_scores" in payload
    assert "decision_boundary" in payload
    assert "key_discriminator_features" in payload
    assert "adversarial_detection" in payload

    decision = payload["decision_analysis"]
    assert "threshold" in decision
    assert "node_decisions" in decision
    assert len(decision["node_decisions"]) >= 1
    assert "decision_counts" in decision

    confidence = payload["confidence_scores"]
    assert "mean_confidence" in confidence
    assert "node_confidence" in confidence
    assert len(confidence["node_confidence"]) == len(decision["node_decisions"])

    boundary = payload["decision_boundary"]
    assert "boundary_sample_ratio" in boundary
    assert "boundary_sharpness" in boundary
    assert "samples" in boundary

    key_features = payload["key_discriminator_features"]
    assert len(key_features) >= 1
    first = key_features[0]
    assert "feature_name" in first
    assert "corr_with_discriminator" in first
    assert "importance" in first

    adv = payload["adversarial_detection"]
    assert "risk_ratio" in adv
    assert "risk_threshold" in adv
    assert "candidates" in adv


def test_gan_lime_stage3_discriminator_analysis() -> None:
    coords, values = _make_data()
    model = GANAnomalyDetector()
    model.fit(coords, values)

    adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(parallel_workers=2, lime_num_samples=180))
    out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, num_samples=140)

    assert out["summary"]["method"] == "lime"
    assert "generator_analysis" in out
    assert "discriminator_analysis" in out
    _assert_discriminator_payload(out["discriminator_analysis"])

    first = out["batch_explanations"][0]
    assert "decomposition" in first
    assert "reason" in first


def test_gan_shap_stage3_discriminator_analysis_and_cache() -> None:
    coords, values = _make_data(seed=31)
    model = GANAnomalyDetector()
    model.fit(coords, values)

    adapter = GANAnomalySHAPAdapter(config=GANExplanationConfig(parallel_workers=2, shap_nsamples=120, shap_feature_cap=6))
    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=5, nsamples=120)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=5, nsamples=120)

    assert out1["summary"]["method"] == "shap"
    assert out1["summary"]["nsamples"] <= 120
    assert "generator_analysis" in out1
    assert "discriminator_analysis" in out1
    _assert_discriminator_payload(out1["discriminator_analysis"])
    assert out2["performance"]["cache_hit"] is True
