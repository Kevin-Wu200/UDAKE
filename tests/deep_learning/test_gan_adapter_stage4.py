from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import GANAnomalyDetector
from services.backend.app.dl_services.gan_anomaly_explainer import GANAnomalyLimeAdapter, GANAnomalySHAPAdapter, GANExplanationConfig


def _make_data(n: int = 128, seed: int = 47) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 6.2) + np.cos(coords[:, 1] * 4.6) + rng.normal(0.0, 0.05, size=n)
    values[::17] += 1.1
    values[5::23] -= 0.75
    return coords, values


def test_gan_lime_stage4_performance_fields() -> None:
    coords, values = _make_data()
    model = GANAnomalyDetector()
    model.fit(coords, values)

    adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(parallel_workers=2, lime_num_samples=320))
    out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=8, num_samples=300)

    perf = out["performance"]
    assert perf["cache_hit"] is False
    assert perf["parallel_workers"] >= 1
    assert perf["post_parallel_workers"] >= 1
    assert perf["lime_sampling_budget"] <= 300
    assert 1 <= perf["lime_training_size"] <= len(values)
    assert perf["memory_bytes"] > 0


def test_gan_shap_stage4_reduction_and_cache() -> None:
    coords, values = _make_data(seed=61)
    model = GANAnomalyDetector()
    model.fit(coords, values)

    adapter = GANAnomalySHAPAdapter(config=GANExplanationConfig(parallel_workers=2, shap_nsamples=220, shap_feature_cap=6))
    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=7, nsamples=220)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=7, nsamples=220)

    perf = out1["performance"]
    assert perf["effective_feature_count"] <= 6
    assert 0.0 < perf["feature_reduction_ratio"] <= 1.0
    assert perf["memory_bytes"] > 0
    assert out2["performance"]["cache_hit"] is True
