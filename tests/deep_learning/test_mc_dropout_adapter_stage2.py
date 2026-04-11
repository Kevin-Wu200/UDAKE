from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import MCDropoutConfig, MCDropoutRegressor
from services.backend.app.dl_services.mc_dropout_explainer import (
    MCDropoutExplanationConfig,
    MCDropoutLIMEAdapter,
    MCDropoutSHAPAdapter,
)


def _make_features(n: int = 52, seed: int = 109) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.4) + np.cos(coords[:, 1] * 3.3) + rng.normal(0.0, 0.05, size=n)
    return np.concatenate([coords, values.reshape(-1, 1)], axis=1)


def _build_model(seed: int = 137) -> tuple[MCDropoutRegressor, np.ndarray]:
    x = _make_features(n=52, seed=seed)
    y = np.asarray(x[:, 2], dtype=float) + 0.17 * np.asarray(x[:, 0], dtype=float) - 0.09 * np.asarray(x[:, 1], dtype=float)
    model = MCDropoutRegressor(
        MCDropoutConfig(in_dim=3, hidden_dim=18, dropout_rate=0.25, dropout_type="variational", seed=seed + 5)
    )
    model.fit(x, y, epochs=72, lr=7e-3)
    return model, x


def _assert_stage2_payload(payload: dict) -> None:
    assert "dropout_weight_analysis" in payload
    assert "forward_pass_analysis" in payload
    assert "prediction_distribution_analysis" in payload

    weight = payload["dropout_weight_analysis"]
    assert weight["summary"]["parameter_groups"] >= 3
    assert weight["summary"]["total_parameter_count"] > 0
    assert len(weight["parameter_summaries"]) >= 3
    assert len(weight["top_important_parameters"]) >= 1

    forward = payload["forward_pass_analysis"]
    assert forward["summary"]["sample_count"] >= 1
    assert forward["summary"]["forward_passes"] >= 24
    assert forward["summary"]["mean_epistemic"] >= 0.0
    assert len(forward["top_unstable_samples"]) >= 1

    dist = payload["prediction_distribution_analysis"]
    assert dist["summary"]["sample_count"] >= 1
    assert dist["summary"]["forward_passes"] >= 24
    assert dist["summary"]["mean_predictive_std"] >= 0.0
    assert len(dist["top_wide_interval_samples"]) >= 1

    perf = payload["performance"]
    assert perf["sample_count"] >= 1
    assert perf["feature_dim"] == 3
    assert perf["context_build_ms"] >= 0.0
    assert perf["context_memory_bytes"] > 0
    assert perf["result_memory_bytes"] >= 0


def test_mc_dropout_lime_stage2_weight_forward_distribution_analysis() -> None:
    model, x = _build_model(seed=149)
    adapter = MCDropoutLIMEAdapter(config=MCDropoutExplanationConfig(lime_num_samples=100, max_explain_nodes=5))
    out = adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=5, num_samples=90)

    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 5
    _assert_stage2_payload(out)


def test_mc_dropout_shap_stage2_weight_forward_distribution_analysis() -> None:
    model, x = _build_model(seed=157)
    adapter = MCDropoutSHAPAdapter(config=MCDropoutExplanationConfig(shap_nsamples=84, max_explain_nodes=5))
    out = adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=5, nsamples=76)

    assert out["summary"]["method"] == "shap"
    assert out["summary"]["explained_nodes"] == 5
    assert out["summary"]["nsamples"] == 76
    _assert_stage2_payload(out)


def test_mc_dropout_lime_stage2_context_cache_hit_when_result_cache_miss() -> None:
    model, x = _build_model(seed=173)
    adapter = MCDropoutLIMEAdapter(config=MCDropoutExplanationConfig(lime_num_samples=90, max_explain_nodes=4, cache_size=6))

    first = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=4, num_samples=80)
    second = adapter.explain(model=model, features=x, top_k=5, max_explain_nodes=4, num_samples=80)

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is False
    assert second["performance"]["context_cache_hit"] is True
    assert second["performance"]["context_cache_hits"] >= 1
