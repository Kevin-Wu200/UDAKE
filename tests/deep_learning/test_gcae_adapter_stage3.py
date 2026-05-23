from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import GCAEAnomalyDetector
from services.backend.app.dl_services.gcae_anomaly_explainer import (
    GCAEExplanationConfig,
    GCAELimeAdapter,
    GCAEShapAdapter,
    _safe_float,
)


def _make_data(n: int = 96, seed: int = 37) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.8) + np.cos(coords[:, 1] * 3.7) + rng.normal(0.0, 0.05, size=n)
    values[::14] += 0.9
    values[5::21] -= 0.55
    return coords, values


def _fit_model(coords: np.ndarray, values: np.ndarray) -> GCAEAnomalyDetector:
    model = GCAEAnomalyDetector()
    model.fit(coords, values)
    return model


def test_gcae_lime_stage3_prediction_and_anomaly_score_explanation() -> None:
    coords, values = _make_data()
    model = _fit_model(coords, values)

    adapter = GCAELimeAdapter(config=GCAEExplanationConfig(parallel_workers=2, lime_num_samples=200))
    out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=7, num_samples=160)

    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 7
    assert len(out["batch_explanations"]) == 7

    first = out["batch_explanations"][0]
    assert isinstance(first["prediction"], float)
    assert isinstance(first["target_prediction"], float)
    assert "top_contributions" in first and len(first["top_contributions"]) >= 1
    assert "decomposition" in first and "reason" in first

    anomaly = out["anomaly_score_explanation"]
    assert len(anomaly["decomposition"]) == len(values)
    assert "key_anomaly_nodes" in anomaly and len(anomaly["key_anomaly_nodes"]) >= 1
    assert "propagation_paths" in anomaly
    assert set(anomaly["consistency_validation"].keys()) == {"is_reasonable", "score_corr", "coverage"}


def test_gcae_shap_stage3_prediction_and_cache() -> None:
    coords, values = _make_data(seed=43)
    model = _fit_model(coords, values)

    adapter = GCAEShapAdapter(config=GCAEExplanationConfig(parallel_workers=2, shap_nsamples=140, shap_feature_cap=6))
    out1 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, nsamples=140)
    out2 = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, nsamples=140)

    assert out1["summary"]["method"] == "shap"
    assert out1["summary"]["explained_nodes"] == 6
    assert len(out1["batch_explanations"]) == 6
    assert out1["summary"]["nsamples"] <= 140

    first = out1["batch_explanations"][0]
    assert isinstance(first["prediction"], float)
    assert isinstance(first["expected_value"], float)
    assert isinstance(first["target_prediction"], float)
    assert len(first["raw_shap_values"]) == out1["summary"]["num_features"]
    assert "decomposition" in first and "reason" in first

    assert out2["performance"]["cache_hit"] is True


def test_gcae_preprocess_strategy_and_predict_function_contract() -> None:
    coords, values = _make_data(seed=59)
    model = _fit_model(coords, values)

    adapter = GCAELimeAdapter(config=GCAEExplanationConfig())
    matrix, feature_names, _ = adapter._build_feature_matrix(model=model, coords=coords, values=values)
    scaled, stats = adapter._preprocess(matrix, feature_names)

    assert scaled.shape == matrix.shape
    idx_map = {name: idx for idx, name in enumerate(feature_names)}

    value_idx = idx_map["value"]  # noqa: F841
    node_degree_idx = idx_map["node_degree"]
    adj_density_idx = idx_map["adj_density"]

    assert stats["value"]["strategy"] == 1.0
    assert stats["node_degree"]["strategy"] == 2.0
    assert stats["adj_density"]["strategy"] == 2.0

    node_degree_col = scaled[:, node_degree_idx]
    adj_density_col = scaled[:, adj_density_idx]
    assert np.min(node_degree_col) >= -1e-6 and np.max(node_degree_col) <= 1.0 + 1e-6
    assert np.min(adj_density_col) >= -1e-6 and np.max(adj_density_col) <= 1.0 + 1e-6

    context = adapter._build_context(model=model, coords=coords, values=values)
    predict_fn = adapter._predict_surrogate(context)
    pred = predict_fn(np.asarray(context["scaled_x"], dtype=float))
    assert pred.shape == (len(values),)
    assert np.isfinite(pred).all()

    bundle = adapter._predict_scores(model=model, coords=coords, values=values)
    expected_combined = 0.65 * bundle["node"] + 0.35 * bundle["subgraph"]
    assert np.allclose(bundle["combined"], expected_combined)


def test_gcae_graph_structure_feature_analysis_payload() -> None:
    coords, values = _make_data(seed=71)
    model = _fit_model(coords, values)

    adapter = GCAELimeAdapter(config=GCAEExplanationConfig(parallel_workers=2, lime_num_samples=180))
    out = adapter.explain(model=model, coords=coords, values=values, top_k=4, max_explain_nodes=5, num_samples=140)

    analysis = out["graph_structure_analysis"]
    assert len(analysis["structure_importance"]) == len(values)
    assert len(analysis["edge_weight_contribution"]) == len(values)

    patterns = analysis["key_connection_patterns"]
    assert "high_degree_nodes" in patterns and len(patterns["high_degree_nodes"]) >= 1
    assert 0.0 <= patterns["edge_density"] <= 1.0
    assert 0.0 <= patterns["cluster_like_ratio"] <= 1.0

    subgraphs = analysis["subgraph_features"]
    assert len(subgraphs) == 5
    first = subgraphs[0]
    assert {"node_index", "size", "mean_edge_weight", "mean_node_score"}.issubset(first.keys())

    graph_level = analysis["graph_level_explanation"]
    assert "dominant_nodes" in graph_level
    assert "explained_nodes_overlap" in graph_level
    assert "graph_anomaly_tendency" in graph_level


def test_gcae_base_adapter_edge_branches() -> None:
    adapter = GCAELimeAdapter(config=GCAEExplanationConfig())

    assert _safe_float(object(), default=3.5) == 3.5
    assert adapter._cache_get("missing-key") is None
    assert adapter._context_get("missing-key") is None

    minmax_scaled, minmax_stats = adapter._standardize_column(np.array([7.0, 7.0, 7.0]), "minmax")
    assert np.allclose(minmax_scaled, np.zeros(3))
    assert minmax_stats["strategy"] == 2.0

    robust_scaled, robust_stats = adapter._standardize_column(np.array([2.0, 2.0, 2.0, 2.0]), "robust_zscore")
    assert np.allclose(robust_scaled, np.zeros(4))
    assert robust_stats["strategy"] == 1.0

    x = np.ones((4, 3), dtype=np.float32)
    background = adapter._select_background(x, np.zeros(4), size=64)
    assert background.shape == x.shape
    out32 = adapter._to_float32(x)
    assert out32.dtype == np.float32

    assert adapter._feature_display("unknown_feature") == "unknown_feature"
    assert adapter._dynamic_lime_samples(n_features=2, n_points=3) >= 80
    assert adapter._dynamic_shap_samples(selected_nsamples=10, n_features=300, n_points=300) >= 40

    empty_profile = adapter._anomaly_profile(np.array([]), [])
    assert empty_profile["stats"]["mean"] == 0.0
    assert empty_profile["node_labels"] == []

    reason = adapter._explanation_reason(
        node_idx=3,
        decomposition_row={"node_component": 0.1, "neighborhood_component": 0.2, "edge_component": 0.3},
        top_contributions=[],
    )
    assert "图结构扰动" in reason
