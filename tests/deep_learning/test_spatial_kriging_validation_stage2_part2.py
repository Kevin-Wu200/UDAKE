from __future__ import annotations

import time

import numpy as np

from deep_learning.models.spatial_interpolation import AttentionKrigingModel, GNNKrigingModel, ResidualKrigingModel
from deep_learning.utils.spatial_interpolation_data import SyntheticSpatialDataset
from services.backend.app.dl_services.attention_kriging_explainer import (
    AttentionKrigingExplanationConfig,
    AttentionKrigingLIMEAdapter,
)
from services.backend.app.dl_services.gnn_kriging_explainer import GNNKrigingExplanationConfig, GNNKrigingLIMEAdapter
from services.backend.app.dl_services.residual_kriging_explainer import (
    ResidualKrigingExplanationConfig,
    ResidualKrigingLIMEAdapter,
)


def _make_data(seed: int = 202, n_points: int = 64) -> tuple[np.ndarray, np.ndarray]:
    payload = SyntheticSpatialDataset(seed=seed).generate(n_points=n_points, noise_std=0.02)
    return np.asarray(payload["coords"], dtype=float), np.asarray(payload["values"], dtype=float)


def test_stage2_reasonableness_uncertainty_and_contribution_order() -> None:
    coords, values = _make_data(seed=211, n_points=68)
    queries = coords[:16]
    top_k = 4

    gnn = GNNKrigingLIMEAdapter(config=GNNKrigingExplanationConfig(max_explain_nodes=1))
    gnn_out = gnn.explain(
        model=GNNKrigingModel(hidden_dim=12),
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=top_k,
        num_samples=90,
    )
    gnn_target = int(np.argmax(np.asarray(gnn_out["score_components"]["uncertainty"], dtype=float)))
    assert gnn_out["batch_explanations"][0]["node_index"] == gnn_target
    gnn_weights = [item["abs_weight"] for item in gnn_out["batch_explanations"][0]["top_contributions"]]
    assert np.all(np.diff(np.asarray(gnn_weights, dtype=float)) <= 1e-12)

    attention = AttentionKrigingLIMEAdapter(config=AttentionKrigingExplanationConfig(max_explain_nodes=1))
    attention_out = attention.explain(
        model=AttentionKrigingModel(dim=24),
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=top_k,
        num_samples=90,
    )
    attention_target = int(np.argmax(np.asarray(attention_out["score_components"]["uncertainty"], dtype=float)))
    assert attention_out["batch_explanations"][0]["node_index"] == attention_target
    attn_weights = [item["abs_weight"] for item in attention_out["batch_explanations"][0]["top_contributions"]]
    assert np.all(np.diff(np.asarray(attn_weights, dtype=float)) <= 1e-12)

    residual = ResidualKrigingLIMEAdapter(config=ResidualKrigingExplanationConfig(max_explain_nodes=1))
    residual_out = residual.explain(
        model=ResidualKrigingModel(architecture="hybrid", baseline="universal"),
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=top_k,
        num_samples=90,
    )
    residual_target = int(np.argmax(np.asarray(residual_out["score_components"]["uncertainty"], dtype=float)))
    assert residual_out["batch_explanations"][0]["node_index"] == residual_target
    res_weights = [item["abs_weight"] for item in residual_out["batch_explanations"][0]["top_contributions"]]
    assert np.all(np.diff(np.asarray(res_weights, dtype=float)) <= 1e-12)


def test_stage2_single_sample_latency_under_8s() -> None:
    coords, values = _make_data(seed=221, n_points=72)
    query = coords[:1]

    cases = [
        (
            GNNKrigingLIMEAdapter(config=GNNKrigingExplanationConfig(max_explain_nodes=1)),
            GNNKrigingModel(hidden_dim=12),
        ),
        (
            AttentionKrigingLIMEAdapter(config=AttentionKrigingExplanationConfig(max_explain_nodes=1)),
            AttentionKrigingModel(dim=24),
        ),
        (
            ResidualKrigingLIMEAdapter(config=ResidualKrigingExplanationConfig(max_explain_nodes=1)),
            ResidualKrigingModel(architecture="hybrid", baseline="ordinary"),
        ),
    ]
    for adapter, model in cases:
        started = time.perf_counter()
        out = adapter.explain(
            model=model,
            sample_coords=coords,
            sample_values=values,
            query_coords=query,
            top_k=4,
            num_samples=80,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        assert elapsed_ms < 8000.0
        assert out["performance"]["duration_ms"] < 8000.0
        assert out["performance"]["meets_latency_target"] is True


def test_stage2_boundary_empty_query_coords_fallback_to_samples() -> None:
    coords, values = _make_data(seed=231, n_points=60)
    empty_queries = np.empty((0, 2), dtype=float)

    gnn_out = GNNKrigingLIMEAdapter().explain(
        model=GNNKrigingModel(hidden_dim=12),
        sample_coords=coords,
        sample_values=values,
        query_coords=empty_queries,
        top_k=4,
        num_samples=80,
    )
    assert gnn_out["graph_structure_analysis"]["node_count"] == int(coords.shape[0])
    assert gnn_out["summary"]["explained_nodes"] >= 1

    attention_out = AttentionKrigingLIMEAdapter().explain(
        model=AttentionKrigingModel(dim=24),
        sample_coords=coords,
        sample_values=values,
        query_coords=empty_queries,
        top_k=4,
        num_samples=80,
    )
    assert attention_out["attention_visualization"]["shape"][0] == int(coords.shape[0])
    assert attention_out["summary"]["explained_nodes"] >= 1

    residual_out = ResidualKrigingLIMEAdapter().explain(
        model=ResidualKrigingModel(architecture="hybrid", baseline="universal"),
        sample_coords=coords,
        sample_values=values,
        query_coords=empty_queries,
        top_k=4,
        num_samples=80,
    )
    assert residual_out["baseline_model_comparison"]["query_count"] == int(coords.shape[0])
    assert residual_out["summary"]["explained_nodes"] >= 1


def test_stage2_spatial_distribution_consistency() -> None:
    coords, values = _make_data(seed=241, n_points=70)
    queries = coords[:20]

    attention_out = AttentionKrigingLIMEAdapter().explain(
        model=AttentionKrigingModel(dim=24),
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=4,
        num_samples=80,
    )
    spatial_dist = attention_out["spatial_weight_distribution"]
    assert int(sum(spatial_dist["histogram"]["counts"])) == int(queries.shape[0])
    assert int(sum(item["query_count"] for item in spatial_dist["spatial_bins"])) == int(queries.shape[0])

    residual_out = ResidualKrigingLIMEAdapter().explain(
        model=ResidualKrigingModel(architecture="hybrid", baseline="ordinary"),
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=4,
        num_samples=80,
    )
    residual_spatial = residual_out["residual_spatial_distribution"]
    assert int(sum(residual_spatial["histogram"]["counts"])) == int(queries.shape[0])
    assert int(sum(item["query_count"] for item in residual_spatial["spatial_bins"])) == int(queries.shape[0])
    hotspot_abs = [item["abs_residual"] for item in residual_spatial["hotspots"]]
    assert np.all(np.diff(np.asarray(hotspot_abs, dtype=float)) <= 1e-12)
