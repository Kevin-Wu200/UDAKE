from __future__ import annotations

import numpy as np

from deep_learning.models.spatial_interpolation import GNNKrigingModel
from deep_learning.utils.spatial_interpolation_data import SyntheticSpatialDataset
from services.backend.app.dl_services.gnn_kriging_explainer import (
    GNNKrigingExplanationConfig,
    GNNKrigingLIMEAdapter,
    GNNKrigingSHAPAdapter,
)


def _make_data(seed: int = 101, n_points: int = 80) -> tuple[np.ndarray, np.ndarray]:
    payload = SyntheticSpatialDataset(seed=seed).generate(n_points=n_points, noise_std=0.02)
    return np.asarray(payload["coords"], dtype=float), np.asarray(payload["values"], dtype=float)


def _assert_common_stage2_payload(payload: dict, query_count: int) -> None:
    graph = payload["graph_structure_analysis"]
    assert graph["node_count"] == query_count
    assert graph["edge_count"] > 0
    assert graph["connected_components"]["count"] >= 1
    assert graph["degree_stats"]["max"] >= graph["degree_stats"]["min"]

    node = payload["node_weight_explanation"]
    assert len(node["per_node"]) == query_count
    assert len(node["top_nodes"]) >= 1
    top_scores = [item["influence_score"] for item in node["top_nodes"]]
    assert np.all(np.diff(np.asarray(top_scores, dtype=float)) <= 1e-12)

    edge = payload["edge_weight_explanation"]
    assert edge["edge_count"] > 0
    assert len(edge["top_edges"]) >= 1
    assert edge["global_summary"]["max_weight"] >= edge["global_summary"]["mean_weight"]

    perf = payload["performance"]
    assert perf["duration_ms"] < 8000.0
    assert perf["latency_target_ms"] == 8000.0
    assert perf["meets_latency_target"] is True


def test_gnn_kriging_lime_stage2_graph_and_node_edge_weight_explanations() -> None:
    coords, values = _make_data(seed=111)
    model = GNNKrigingModel(hidden_dim=12)
    queries = coords[:22]
    adapter = GNNKrigingLIMEAdapter(
        config=GNNKrigingExplanationConfig(lime_num_samples=120, max_explain_nodes=5)
    )

    out = adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=5,
        num_samples=100,
    )

    _assert_common_stage2_payload(out, query_count=22)
    assert out["performance"]["lime_training_size"] >= len(out["batch_explanations"])
    assert out["performance"]["lime_sampling_budget"] >= 80


def test_gnn_kriging_shap_stage2_graph_and_node_edge_weight_explanations() -> None:
    coords, values = _make_data(seed=131)
    model = GNNKrigingModel(hidden_dim=12)
    queries = coords[:20]
    adapter = GNNKrigingSHAPAdapter(
        config=GNNKrigingExplanationConfig(shap_nsamples=90, max_explain_nodes=4)
    )

    out = adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=4,
        nsamples=80,
    )

    _assert_common_stage2_payload(out, query_count=20)
    assert out["performance"]["backend"] in {"shap", "surrogate_linear"}
    assert out["performance"]["shap_background_size"] <= 24
    assert out["performance"]["shap_sampling_budget"] >= 40
