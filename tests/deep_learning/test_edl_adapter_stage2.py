from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import EDLClassifier, EDLConfig
from services.backend.app.dl_services.edl_explainer import (
    EDLExplanationConfig,
    EDLLIMEAdapter,
    EDLSHAPAdapter,
)


def _make_features(n: int = 60, seed: int = 241) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    signal = np.sin(coords[:, 0] * 4.5) + np.cos(coords[:, 1] * 3.9)
    values = signal + rng.normal(0.0, 0.06, size=n)
    return np.concatenate([coords, values.reshape(-1, 1)], axis=1)


def _make_labels(values: np.ndarray, classes: int = 3) -> np.ndarray:
    bins = np.percentile(values, np.linspace(0.0, 100.0, classes + 1))
    y = np.zeros(len(values), dtype=int)
    for i in range(classes):
        left, right = bins[i], bins[i + 1]
        if i == classes - 1:
            mask = (values >= left) & (values <= right)
        else:
            mask = (values >= left) & (values < right)
        y[mask] = i
    return y


def _build_model(seed: int = 257) -> tuple[EDLClassifier, np.ndarray]:
    x = _make_features(n=60, seed=seed)
    y = _make_labels(x[:, 2], classes=3)
    model = EDLClassifier(EDLConfig(in_dim=3, num_classes=3, hidden_dim=20, evidence_activation="softplus", seed=seed + 9))
    model.fit(x, y, epochs=96, lr=7e-3)
    return model, x


def _assert_stage2_payload(payload: dict) -> None:
    assert "evidence_explanation" in payload
    assert "uncertainty_evidence_analysis" in payload
    assert "confidence_distribution_analysis" in payload

    evidence = payload["evidence_explanation"]
    assert evidence["summary"]["sample_count"] >= 1
    assert evidence["summary"]["num_classes"] == 3
    assert len(evidence["class_evidence_statistics"]) == 3
    assert len(evidence["top_high_evidence_samples"]) >= 1

    ue = payload["uncertainty_evidence_analysis"]
    assert ue["summary"]["sample_count"] >= 1
    assert len(ue["evidence_uncertainty_profile"]) == 3
    assert len(ue["top_high_uncertainty_samples"]) >= 1

    conf = payload["confidence_distribution_analysis"]
    assert conf["summary"]["sample_count"] >= 1
    assert "q50" in conf["quantiles"]
    assert len(conf["top_low_confidence_samples"]) >= 1

    perf = payload["performance"]
    assert perf["sample_count"] >= 1
    assert perf["feature_dim"] == 3
    assert perf["context_build_ms"] >= 0.0
    assert perf["context_memory_bytes"] > 0
    assert perf["result_memory_bytes"] >= 0


def test_edl_lime_stage2_evidence_uncertainty_confidence_and_performance() -> None:
    model, x = _build_model(seed=271)
    adapter = EDLLIMEAdapter(config=EDLExplanationConfig(lime_num_samples=96, max_explain_nodes=5))
    out = adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=5, num_samples=88)

    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 5
    _assert_stage2_payload(out)


def test_edl_shap_stage2_evidence_uncertainty_confidence_and_performance() -> None:
    model, x = _build_model(seed=283)
    adapter = EDLSHAPAdapter(config=EDLExplanationConfig(shap_nsamples=82, max_explain_nodes=5))
    out = adapter.explain(model=model, features=x, top_k=4, max_explain_nodes=5, nsamples=74)

    assert out["summary"]["method"] == "shap"
    assert out["summary"]["explained_nodes"] == 5
    assert out["summary"]["nsamples"] == 74
    _assert_stage2_payload(out)


def test_edl_lime_stage2_context_cache_hit_when_result_cache_miss() -> None:
    model, x = _build_model(seed=307)
    adapter = EDLLIMEAdapter(config=EDLExplanationConfig(lime_num_samples=90, max_explain_nodes=4, cache_size=6))

    first = adapter.explain(model=model, features=x, top_k=3, max_explain_nodes=4, num_samples=80)
    second = adapter.explain(model=model, features=x, top_k=5, max_explain_nodes=4, num_samples=80)

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is False
    assert second["performance"]["context_cache_hit"] is True
    assert second["performance"]["context_cache_hits"] >= 1


def test_edl_model_stage2_analysis_methods() -> None:
    model, x = _build_model(seed=331)

    evidence = model.explain_evidence(x, top_k=5, use_training_stats=True)
    assert evidence["summary"]["sample_count"] == 60
    assert len(evidence["class_evidence_statistics"]) == 3
    assert len(evidence["top_high_evidence_samples"]) == 5

    ue = model.analyze_uncertainty_evidence(x, top_k=5, use_training_stats=True)
    assert ue["summary"]["sample_count"] == 60
    assert len(ue["evidence_uncertainty_profile"]) == 3
    assert len(ue["top_high_uncertainty_samples"]) == 5

    conf = model.analyze_confidence_distribution(x, top_k=5, use_training_stats=True)
    assert conf["summary"]["sample_count"] == 60
    assert "q50" in conf["quantiles"]
    assert len(conf["top_low_confidence_samples"]) == 5
