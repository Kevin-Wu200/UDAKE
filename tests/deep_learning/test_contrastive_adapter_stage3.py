from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import ContrastiveAnomalyDetector
from services.backend.app.dl_services.contrastive_anomaly_explainer import (
    ContrastiveExplanationConfig,
    ContrastiveLimeAdapter,
    ContrastiveShapAdapter,
    _safe_float,
)


def _make_data(n: int = 86, seed: int = 41) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.1) + np.cos(coords[:, 1] * 3.4) + rng.normal(0.0, 0.05, size=n)
    values[::15] += 0.92
    values[6::23] -= 0.58
    return coords, values


def _fit_model(coords: np.ndarray, values: np.ndarray) -> ContrastiveAnomalyDetector:
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=12)
    return model


def test_contrastive_base_adapter_edge_branches() -> None:
    adapter = ContrastiveLimeAdapter(config=ContrastiveExplanationConfig(cache_size=1, parallel_workers=1))

    assert _safe_float(object(), default=3.5) == 3.5
    assert adapter._cache_get("missing-key") is None
    assert adapter._context_get("missing-key") is None

    adapter._cache_set("k1", {"v": 1})
    adapter._cache_set("k2", {"v": 2})
    assert adapter._cache_get("k1") is None
    assert adapter._cache_get("k2") == {"v": 2}

    adapter._context_set("c1", {"v": 1})
    adapter._context_set("c2", {"v": 2})
    assert adapter._context_get("c1") is None
    assert adapter._context_get("c2") == {"v": 2}

    assert adapter._feature_display("unknown_feature") == "unknown_feature"

    minmax_scaled, minmax_stats = adapter._standardize_column(np.array([7.0, 7.0, 7.0]), "minmax")
    robust_scaled, robust_stats = adapter._standardize_column(np.array([2.0, 2.0, 2.0]), "robust_zscore")
    assert np.allclose(minmax_scaled, np.zeros(3))
    assert minmax_stats["strategy"] == 2.0
    assert np.allclose(robust_scaled, np.zeros(3))
    assert robust_stats["strategy"] == 1.0

    class _DummyModel:
        def encode(self, coords: np.ndarray, values: np.ndarray) -> np.ndarray:
            return np.array([1.0, 2.0, 3.0], dtype=float)

    encoder_bundle = adapter._predict_encoder_response(
        model=_DummyModel(),
        coords=np.zeros((3, 2), dtype=float),
        values=np.zeros((3,), dtype=float),
    )
    assert encoder_bundle["embedding"].shape == (0, 0)

    assert adapter._select_explained_nodes(np.array([]), max_explain_nodes=4) == ([], 0.0)
    assert adapter._anomaly_profile(np.array([]), []).get("node_labels") == []

    assert adapter._embedding_similarity_analysis(np.array([]))["node_mean_similarity"] == []
    empty_similarity = adapter._sample_similarity_calculation(np.array([]))
    assert empty_similarity["matrix_shape"] == [0, 0]
    assert adapter._similarity_distribution_analysis({"pair_similarity_scores": []})["histogram"]["counts"] == []
    bounds = adapter._similarity_threshold_boundaries({}, np.array([]))
    assert bounds["score_high_threshold_p95"] == 0.0
    patterns = adapter._similarity_anomaly_patterns(
        similarity_bundle={},
        scores=np.array([]),
        explained_nodes=[],
        boundaries={},
    )
    assert patterns["isolated_nodes"] == []
    heatmap = adapter._similarity_heatmap(
        {"similarity_matrix": [[1.0, 0.1], [0.1, 1.0]]},
        np.array([0.5]),
    )
    assert len(heatmap["labels"]) == 2

    assert adapter._embedding_distribution_analysis(np.array([]), np.array([]))["embedding_dim"] == 0
    assert adapter._embedding_anomaly_patterns(
        scores=np.array([]),
        explained_nodes=[],
        similarity={},
        distribution={},
    )["pattern_name"] == "none"
    viz = adapter._embedding_visualization(np.array([[0.1], [0.2]]), np.array([0.2, 0.4]))
    assert viz["method"] == "pca_svd"
    assert len(viz["points"]) == 2

    assert adapter._score_decomposition(
        feature_distance=np.array([]),
        density=np.array([]),
        nearest_neighbor=np.array([]),
        bank_similarity=np.array([]),
        combined=np.array([]),
    )["decomposition"] == []
    assert adapter._component_contribution_analysis(decomposition=[], explained_nodes=[])["encoder_ratio"] == 0.0
    assert adapter._extract_key_anomaly_features(batch_explanations=[], top_k=3) == []

    reason = adapter._explanation_reason(node_idx=3, decomposition_row={}, top_contributions=[])
    assert "节点3异常" in reason

    assert adapter._validate_explanation_consistency(
        decomposition=[],
        combined_scores=np.array([]),
        explained_nodes=[],
    )["is_reasonable"] is False
    mismatch = adapter._validate_explanation_consistency(
        decomposition=[{"decomposed_score": 1.0}, {"decomposed_score": 2.0}],
        combined_scores=np.array([1.0]),
        explained_nodes=[0],
    )
    assert mismatch["coverage"] == 1.0


def test_contrastive_lime_stage3_serial_and_fallback_paths(monkeypatch) -> None:
    coords, values = _make_data(seed=43)
    model = _fit_model(coords, values)

    adapter = ContrastiveLimeAdapter(config=ContrastiveExplanationConfig(parallel_workers=1, lime_num_samples=140))

    class _BadLimeModule:
        class LimeTabularExplainer:
            def __init__(self, *args, **kwargs) -> None:
                raise RuntimeError("force fallback")

    monkeypatch.setattr(adapter, "_load_lime_tabular", lambda: _BadLimeModule)

    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=120)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=120)

    assert out1["summary"]["method"] == "lime"
    assert out1["performance"]["parallel_workers"] == 1
    assert out1["performance"]["post_parallel_workers"] == 1
    assert all(item["backend"] == "surrogate_linear" for item in out1["batch_explanations"])
    assert out2["performance"]["cache_hit"] is True


def test_contrastive_shap_stage3_serial_kernel_list_and_fallback(monkeypatch) -> None:
    coords, values = _make_data(seed=59)
    model = _fit_model(coords, values)

    adapter_kernel = ContrastiveShapAdapter(
        config=ContrastiveExplanationConfig(parallel_workers=1, shap_nsamples=100, shap_feature_cap=5)
    )

    class _FakeKernelExplainer:
        def __init__(self, predict_fn, background) -> None:
            self.expected_value = [0.123]

        def shap_values(self, x, nsamples, l1_reg):
            arr = np.asarray(x, dtype=float)
            return [np.full((1, arr.shape[1]), 0.01, dtype=float)]

    class _FakeShapModule:
        KernelExplainer = _FakeKernelExplainer

    monkeypatch.setattr(adapter_kernel, "_load_shap", lambda: _FakeShapModule)
    out_kernel = adapter_kernel.explain(
        model=model,
        coords=coords,
        values=values,
        top_k=4,
        max_explain_nodes=5,
        nsamples=90,
    )

    assert out_kernel["summary"]["method"] == "shap"
    assert out_kernel["performance"]["parallel_workers"] == 1
    assert out_kernel["performance"]["post_parallel_workers"] == 1
    assert all(item["backend"] == "shap_kernel" for item in out_kernel["batch_explanations"])

    adapter_fallback = ContrastiveShapAdapter(
        config=ContrastiveExplanationConfig(parallel_workers=1, shap_nsamples=100, shap_feature_cap=5)
    )

    class _BrokenKernelExplainer:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("force fallback")

    class _BrokenShapModule:
        KernelExplainer = _BrokenKernelExplainer

    monkeypatch.setattr(adapter_fallback, "_load_shap", lambda: _BrokenShapModule)
    out_fallback = adapter_fallback.explain(
        model=model,
        coords=coords,
        values=values,
        top_k=4,
        max_explain_nodes=5,
        nsamples=90,
    )

    assert out_fallback["summary"]["method"] == "shap"
    assert all(item["backend"] == "surrogate_linear" for item in out_fallback["batch_explanations"])
