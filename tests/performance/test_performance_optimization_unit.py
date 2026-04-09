from __future__ import annotations

import numpy as np
import pytest

from deep_learning.models.anomaly_detection import GANAnomalyDetector
from services.backend.app.dl_services.gan_anomaly_explainer import GANAnomalyLimeAdapter, GANExplanationConfig


@pytest.fixture(scope="module")
def gan_case() -> tuple[GANAnomalyDetector, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(97)
    coords = rng.uniform(0.0, 1.0, size=(96, 2))
    values = np.sin(coords[:, 0] * 6.0) + np.cos(coords[:, 1] * 4.0) + rng.normal(0.0, 0.05, size=96)
    values[::13] += 1.0
    values[7::19] -= 0.65

    model = GANAnomalyDetector()
    model.fit(coords, values)
    return model, coords, values


def test_cache_mechanism_unit_lru_eviction() -> None:
    adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(cache_size=1, parallel_workers=1, lime_num_samples=120))

    adapter._cache_set("k1", {"value": 1})
    adapter._cache_set("k2", {"value": 2})

    assert adapter._cache_get("k1") is None
    assert adapter._cache_get("k2") == {"value": 2}


def test_parallel_computation_unit_worker_bounds(gan_case: tuple[GANAnomalyDetector, np.ndarray, np.ndarray]) -> None:
    model, coords, values = gan_case
    adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(parallel_workers=3, lime_num_samples=180))

    out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, num_samples=160)
    perf = out["performance"]

    assert perf["parallel_workers"] == 3
    assert 1 <= perf["post_parallel_workers"] <= 3


def test_memory_optimization_unit_float32_context(gan_case: tuple[GANAnomalyDetector, np.ndarray, np.ndarray]) -> None:
    model, coords, values = gan_case
    adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(parallel_workers=2, lime_num_samples=140))

    context = adapter._build_context(model=model, coords=coords, values=values)

    assert context["feature_matrix"].dtype == np.float32
    assert context["scaled_x"].dtype == np.float32
    assert context["background"].dtype == np.float32
    assert context["generator_artifacts"]["generated_values"].dtype == np.float32
    assert context["generator_artifacts"]["latent_projection"].dtype == np.float32
    assert adapter._memory_bytes(context) > 0


def test_result_cache_unit_repeat_query_hits_cache(gan_case: tuple[GANAnomalyDetector, np.ndarray, np.ndarray]) -> None:
    model, coords, values = gan_case
    adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(parallel_workers=2, lime_num_samples=160))

    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=150)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=150)

    assert out1["performance"]["cache_hit"] is False
    assert out2["performance"]["cache_hit"] is True
    assert out2["summary"]["method"] == out1["summary"]["method"]
    assert out2["summary"]["explained_nodes"] == out1["summary"]["explained_nodes"]
