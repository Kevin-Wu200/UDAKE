from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import DeepEnsembleRegressor
from services.backend.app.dl_services.deep_ensemble_explainer import (
    DeepEnsembleExplanationConfig,
    DeepEnsembleLIMEAdapter,
    DeepEnsembleSHAPAdapter,
)


def _make_features(n: int = 56, seed: int = 173) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    signal = np.sin(coords[:, 0] * 4.8) + np.cos(coords[:, 1] * 3.4)
    values = signal + rng.normal(0.0, 0.05, size=n)
    return np.concatenate([coords, values.reshape(-1, 1)], axis=1)


def _build_model(seed: int = 191) -> tuple[DeepEnsembleRegressor, np.ndarray]:
    x = _make_features(n=56, seed=seed)
    y = np.asarray(x[:, 2], dtype=float) + 0.19 * np.asarray(x[:, 0], dtype=float) - 0.08 * np.asarray(x[:, 1], dtype=float)
    model = DeepEnsembleRegressor(in_dim=3, n_members=5, seed=seed + 11)
    model.fit(x, y, epochs=74)
    return model, x


def _assert_stage2_payload(payload: dict) -> None:
    assert "member_contribution_analysis" in payload
    assert "ensemble_weight_explanation" in payload
    assert "model_diversity_analysis" in payload

    contribution = payload["member_contribution_analysis"]
    assert contribution["summary"]["member_count"] >= 2
    assert contribution["summary"]["sample_count"] >= 1
    assert len(contribution["member_summaries"]) >= 2
    assert len(contribution["top_contributing_members"]) >= 1

    weight = payload["ensemble_weight_explanation"]
    assert weight["summary"]["member_count"] >= 2
    assert weight["summary"]["effective_member_count"] >= 1.0
    assert len(weight["weight_distribution"]) >= 2

    diversity = payload["model_diversity_analysis"]
    assert diversity["summary"]["member_count"] >= 2
    assert diversity["summary"]["sample_count"] >= 1
    assert len(diversity["pairwise_diversity"]) >= 1
    assert len(diversity["top_diverse_pairs"]) >= 1

    perf = payload["performance"]
    assert perf["sample_count"] >= 1
    assert perf["feature_dim"] == 3
    assert perf["context_build_ms"] >= 0.0
    assert perf["context_memory_bytes"] > 0
    assert perf["result_memory_bytes"] >= 0


def test_deep_ensemble_lime_stage2_contribution_weight_diversity_and_performance() -> None:
    model, x = _build_model(seed=211)
    adapter = DeepEnsembleLIMEAdapter(config=DeepEnsembleExplanationConfig(lime_num_samples=100, max_explain_nodes=5))
    out = adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=5, num_samples=90)

    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 5
    _assert_stage2_payload(out)


def test_deep_ensemble_shap_stage2_contribution_weight_diversity_and_performance() -> None:
    model, x = _build_model(seed=223)
    adapter = DeepEnsembleSHAPAdapter(config=DeepEnsembleExplanationConfig(shap_nsamples=84, max_explain_nodes=5))
    out = adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=5, nsamples=76)

    assert out["summary"]["method"] == "shap"
    assert out["summary"]["explained_nodes"] == 5
    assert out["summary"]["nsamples"] == 76
    _assert_stage2_payload(out)


def test_deep_ensemble_lime_stage2_context_cache_hit_when_result_cache_miss() -> None:
    model, x = _build_model(seed=239)
    adapter = DeepEnsembleLIMEAdapter(config=DeepEnsembleExplanationConfig(lime_num_samples=90, max_explain_nodes=4, cache_size=6))

    first = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=4, num_samples=80)
    second = adapter.explain(model=model, features=x, top_k=5, max_explain_nodes=4, num_samples=80)

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is False
    assert second["performance"]["context_cache_hit"] is True
    assert second["performance"]["context_cache_hits"] >= 1
