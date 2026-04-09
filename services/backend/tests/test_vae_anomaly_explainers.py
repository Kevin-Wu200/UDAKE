"""VAE 异常解释适配器测试。"""

from __future__ import annotations

import builtins
import numpy as np
import pytest

from app.dl_services.vae_anomaly_explainer import (
    VAEAnomalyLIMEAdapter,
    VAEAnomalySHAPAdapter,
    VAEExplanationConfig,
    _safe_float,
)
from deep_learning.models.anomaly_detection import VAEAnomalyDetector


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
        ],
        dtype=float,
    )
    values = np.asarray([1.0, 1.1, 0.95, 1.3, 1.18, 2.2, 1.05, 0.98], dtype=float)
    return coords, values


def _build_trained_model() -> tuple[VAEAnomalyDetector, np.ndarray, np.ndarray]:
    coords, values = _build_data()
    model = VAEAnomalyDetector()
    model.fit(coords, values)
    return model, coords, values


def test_vae_lime_adapter_generates_explanations() -> None:
    model, coords, values = _build_trained_model()
    adapter = VAEAnomalyLIMEAdapter()
    result = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=3)

    assert result["summary"]["method"] == "lime"
    assert result["summary"]["explained_nodes"] == 3
    assert len(result["batch_explanations"]) == 3
    assert "reconstruction_analysis" in result
    assert len(result["score_components"]["combined"]) == len(values)
    assert len(result["global_feature_importance"]) <= 3
    assert result["performance"]["cache_hit"] is False


def test_vae_shap_adapter_generates_explanations_and_cache() -> None:
    model, coords, values = _build_trained_model()
    adapter = VAEAnomalySHAPAdapter()
    first = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=2)
    second = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=2)

    assert first["summary"]["method"] == "shap"
    assert len(first["batch_explanations"]) == 2
    assert second["performance"]["cache_hit"] is True
    assert len(first["feature_importance"]) == len(first["batch_explanations"][0]["raw_shap_values"])


def test_vae_lime_adapter_cache_hit() -> None:
    model, coords, values = _build_trained_model()
    adapter = VAEAnomalyLIMEAdapter()
    first = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=2, num_samples=120)
    second = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=2, num_samples=120)

    assert first["summary"]["method"] == "lime"
    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is True


def test_vae_predict_scores_matches_detector_output() -> None:
    model, coords, values = _build_trained_model()
    adapter = VAEAnomalyLIMEAdapter()
    via_adapter = adapter._predict_scores(model=model, coords=coords, values=values)
    direct = model.anomaly_scores(coords, values)

    assert np.allclose(via_adapter["reconstruction"], direct["reconstruction"])
    assert np.allclose(via_adapter["latent_distance"], direct["latent_distance"])
    assert np.allclose(via_adapter["combined"], direct["combined"])


def test_vae_preprocess_applies_expected_standardization_plan() -> None:
    model, coords, values = _build_trained_model()
    adapter = VAEAnomalyLIMEAdapter()
    context = adapter._build_context(model=model, coords=coords, values=values)

    matrix = context["feature_matrix"]
    scaled = context["scaled_x"]
    names = context["feature_names"]
    stats = context["scaler_stats"]

    assert matrix.shape == scaled.shape
    assert len(names) == matrix.shape[1]
    assert set(stats.keys()) == set(names)
    assert stats["coord_x"]["strategy"] == 0.0
    assert stats["value"]["strategy"] == 1.0
    assert abs(float(np.mean(scaled[:, names.index("coord_x")]))) < 1e-6


def test_vae_explained_nodes_align_with_top_combined_scores() -> None:
    model, coords, values = _build_trained_model()
    adapter = VAEAnomalyLIMEAdapter()
    result = adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=3)

    combined = np.asarray(result["score_components"]["combined"], dtype=float)
    expected_top = np.argsort(-combined)[:3].astype(int).tolist()
    explained_nodes = [int(item["node_index"]) for item in result["batch_explanations"]]

    assert explained_nodes == expected_top
    for item in result["batch_explanations"]:
        assert 0.0 <= float(item["confidence"]) <= 1.0
        assert len(item["top_contributions"]) <= 3


def test_vae_reconstruction_analysis_matches_score_components() -> None:
    model, coords, values = _build_trained_model()
    adapter = VAEAnomalySHAPAdapter()
    result = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=3, nsamples=100)

    analysis = result["reconstruction_analysis"]
    reconstruction = np.asarray(result["score_components"]["reconstruction"], dtype=float)
    node_analysis = analysis["node_analysis"]

    assert analysis["stats"]["mean"] == float(np.mean(reconstruction))
    assert analysis["stats"]["p95"] == float(np.percentile(reconstruction, 95))
    assert len(node_analysis) == 3
    for item in node_analysis:
        idx = int(item["node_index"])
        assert item["reconstruction_error"] == float(reconstruction[idx])


def test_vae_internal_utils_cover_edge_paths() -> None:
    adapter = VAEAnomalyLIMEAdapter(config=VAEExplanationConfig(cache_size=1))

    assert _safe_float("1.25") == 1.25
    assert _safe_float(object(), default=9.0) == 9.0

    minmax_scaled, minmax_stats = adapter._standardize_column(np.asarray([3.0, 3.0, 3.0], dtype=float), "minmax")
    robust_scaled, robust_stats = adapter._standardize_column(np.asarray([2.0, 2.0, 2.0], dtype=float), "robust_zscore")

    assert np.allclose(minmax_scaled, np.zeros((3,), dtype=float))
    assert minmax_stats["strategy"] == 2.0
    assert robust_stats["strategy"] == 1.0
    assert np.allclose(robust_scaled, np.zeros((3,), dtype=float))

    adapter._cache_set("k1", {"v": 1})
    adapter._cache_set("k2", {"v": 2})
    assert adapter._cache_get("k1") is None
    assert adapter._cache_get("k2") == {"v": 2}
    assert adapter._context_get("missing") is None
    assert adapter._feature_category("unknown_feature") == "unknown"
    assert adapter._feature_display("unknown_feature") == "unknown_feature"

    small = np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=float)
    selected = adapter._select_background(small, np.asarray([0.1, 0.2], dtype=float), size=64)
    assert np.allclose(selected, small)


def test_vae_import_fallbacks_when_dependency_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name in {"lime", "shap"}:
            raise ImportError("simulated missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert VAEAnomalyLIMEAdapter._load_lime_tabular() is None
    assert VAEAnomalySHAPAdapter._load_shap() is None


def test_vae_lime_and_shap_adapter_exception_fallback_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    model, coords, values = _build_trained_model()

    class _BrokenLimeExplainer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def explain_instance(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("broken lime")

    class _BrokenLimeModule:
        LimeTabularExplainer = _BrokenLimeExplainer

    class _BrokenKernelExplainer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.expected_value = 0.0

        def shap_values(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("broken shap")

    class _BrokenShapModule:
        KernelExplainer = _BrokenKernelExplainer

    lime_adapter = VAEAnomalyLIMEAdapter()
    shap_adapter = VAEAnomalySHAPAdapter()
    monkeypatch.setattr(lime_adapter, "_load_lime_tabular", lambda: _BrokenLimeModule)
    monkeypatch.setattr(shap_adapter, "_load_shap", lambda: _BrokenShapModule)

    lime_result = lime_adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=2, num_samples=80)
    shap_result = shap_adapter.explain(model=model, coords=coords, values=values, top_k=3, max_explain_nodes=2, nsamples=60)

    assert lime_result["summary"]["method"] == "lime"
    assert len(lime_result["batch_explanations"]) == 2
    assert len(lime_result["batch_explanations"][0]["top_contributions"]) > 0
    assert shap_result["summary"]["method"] == "shap"
    assert shap_result["batch_explanations"][0]["backend"] == "surrogate_linear"
