from __future__ import annotations

import numpy as np

from deep_learning.models.spatial_interpolation import AttentionKrigingModel
from deep_learning.utils.spatial_interpolation_data import SyntheticSpatialDataset
from services.backend.app.dl_services.attention_kriging_explainer import (
    AttentionKrigingExplanationConfig,
    AttentionKrigingLIMEAdapter,
    AttentionKrigingSHAPAdapter,
)


def _make_data(seed: int = 71, n_points: int = 72) -> tuple[np.ndarray, np.ndarray]:
    payload = SyntheticSpatialDataset(seed=seed).generate(n_points=n_points, noise_std=0.02)
    return np.asarray(payload["coords"], dtype=float), np.asarray(payload["values"], dtype=float)


def _assert_common_stage2_payload(payload: dict, query_count: int, sample_count: int) -> None:
    attention_viz = payload["attention_visualization"]
    assert attention_viz["type"] == "query_sample_heatmap"
    assert attention_viz["shape"] == [query_count, sample_count]
    assert len(attention_viz["heatmap"]) == query_count
    assert len(attention_viz["top_attention_links"]) == query_count

    neighborhood = payload["neighborhood_impact_analysis"]
    assert neighborhood["top_neighbors"] >= 1
    assert len(neighborhood["per_query"]) == query_count
    assert "mean_dominant_weight" in neighborhood["global_summary"]

    distribution = payload["spatial_weight_distribution"]
    assert len(distribution["histogram"]["edges"]) >= 5
    assert len(distribution["histogram"]["counts"]) >= 4
    assert len(distribution["spatial_bins"]) == 4
    assert "p50" in distribution["quantiles"]

    perf = payload["performance"]
    assert perf["duration_ms"] < 8000.0
    assert perf["latency_target_ms"] == 8000.0
    assert perf["meets_latency_target"] is True


def test_attention_kriging_lime_stage2_visualization_and_neighborhood() -> None:
    coords, values = _make_data(seed=81)
    model = AttentionKrigingModel(dim=24)
    queries = coords[:20]
    adapter = AttentionKrigingLIMEAdapter(
        config=AttentionKrigingExplanationConfig(lime_num_samples=100, max_explain_nodes=5)
    )

    out = adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=5,
        num_samples=90,
    )

    _assert_common_stage2_payload(out, query_count=20, sample_count=coords.shape[0])
    # 邻域影响中的主导邻居权重应与可视化热力图该行最大值一致。
    heatmap = np.asarray(out["attention_visualization"]["heatmap"], dtype=float)
    dominant = [row["dominant_neighbor"]["weight"] for row in out["neighborhood_impact_analysis"]["per_query"]]
    assert np.allclose(np.max(heatmap, axis=1), np.asarray(dominant, dtype=float), atol=1e-8)


def test_attention_kriging_shap_stage2_distribution_and_performance() -> None:
    coords, values = _make_data(seed=91)
    model = AttentionKrigingModel(dim=24)
    queries = coords[:18]
    adapter = AttentionKrigingSHAPAdapter(
        config=AttentionKrigingExplanationConfig(shap_nsamples=70, max_explain_nodes=4)
    )

    out = adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=4,
        nsamples=60,
    )

    _assert_common_stage2_payload(out, query_count=18, sample_count=coords.shape[0])
    assert out["performance"]["backend"] in {"shap", "surrogate_linear"}
