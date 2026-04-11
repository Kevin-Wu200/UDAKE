from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import BayesianNeuralRegressor, GaussianMixturePrior
from services.backend.app.dl_services.bnn_explainer import BNNExplanationConfig, BNNLIMEAdapter, BNNSHAPAdapter


def _make_features(n: int = 52, seed: int = 101) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    signal = np.sin(coords[:, 0] * 4.6) + np.cos(coords[:, 1] * 3.2)
    noise = rng.normal(0.0, 0.05, size=n)
    values = signal + noise
    return np.concatenate([coords, values.reshape(-1, 1)], axis=1)


def _build_model(seed: int = 131) -> tuple[BayesianNeuralRegressor, np.ndarray]:
    x = _make_features(n=52, seed=seed)
    y = np.asarray(x[:, 2], dtype=float) + 0.18 * np.asarray(x[:, 0], dtype=float) - 0.11 * np.asarray(x[:, 1], dtype=float)
    model = BayesianNeuralRegressor(in_dim=3, hidden_dim=18, prior=GaussianMixturePrior(), seed=seed + 7)
    model.fit(x, y, epochs=72, lr=7e-3)
    return model, x


def _assert_stage2_payload(payload: dict) -> None:
    assert "bayesian_weight_explanation" in payload
    assert "posterior_distribution_analysis" in payload
    assert "epistemic_uncertainty_analysis" in payload

    weight_expl = payload["bayesian_weight_explanation"]
    assert weight_expl["summary"]["parameter_groups"] >= 3
    assert weight_expl["summary"]["total_parameter_count"] > 0
    assert len(weight_expl["parameter_summaries"]) >= 3
    assert len(weight_expl["top_uncertain_parameters"]) >= 1

    posterior = payload["posterior_distribution_analysis"]
    assert posterior["summary"]["parameter_groups"] >= 3
    assert posterior["summary"]["global_sigma_mean"] > 0.0
    assert len(posterior["layers"]) >= 3

    epistemic = payload["epistemic_uncertainty_analysis"]
    assert epistemic["summary"]["sample_count"] >= 1
    assert epistemic["summary"]["monte_carlo_samples"] >= 24
    assert epistemic["summary"]["mean_epistemic"] >= 0.0
    assert len(epistemic["top_epistemic_samples"]) >= 1

    perf = payload["performance"]
    assert perf["sample_count"] >= 1
    assert perf["feature_dim"] == 3
    assert perf["context_build_ms"] >= 0.0
    assert perf["context_memory_bytes"] > 0
    assert perf["result_memory_bytes"] >= 0


def test_bnn_lime_stage2_weight_posterior_and_epistemic_analysis() -> None:
    model, x = _build_model(seed=143)
    adapter = BNNLIMEAdapter(config=BNNExplanationConfig(lime_num_samples=100, max_explain_nodes=5))
    out = adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=5, num_samples=90)

    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 5
    _assert_stage2_payload(out)


def test_bnn_shap_stage2_weight_posterior_and_epistemic_analysis() -> None:
    model, x = _build_model(seed=151)
    adapter = BNNSHAPAdapter(config=BNNExplanationConfig(shap_nsamples=84, max_explain_nodes=5))
    out = adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=5, nsamples=76)

    assert out["summary"]["method"] == "shap"
    assert out["summary"]["explained_nodes"] == 5
    assert out["summary"]["nsamples"] == 76
    _assert_stage2_payload(out)


def test_bnn_lime_stage2_context_cache_hit_when_result_cache_miss() -> None:
    model, x = _build_model(seed=167)
    adapter = BNNLIMEAdapter(config=BNNExplanationConfig(lime_num_samples=90, max_explain_nodes=4, cache_size=6))

    first = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=4, num_samples=80)
    second = adapter.explain(model=model, features=x, top_k=5, max_explain_nodes=4, num_samples=80)

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is False
    assert second["performance"]["context_cache_hit"] is True
    assert second["performance"]["context_cache_hits"] >= 1
