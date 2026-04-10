from __future__ import annotations

import numpy as np

from deep_learning.models.spatial_interpolation import ResidualKrigingModel
from deep_learning.utils.spatial_interpolation_data import SyntheticSpatialDataset
from services.backend.app.dl_services.residual_kriging_explainer import (
    ResidualKrigingExplanationConfig,
    ResidualKrigingLIMEAdapter,
    ResidualKrigingSHAPAdapter,
)


def _make_data(seed: int = 151, n_points: int = 84) -> tuple[np.ndarray, np.ndarray]:
    payload = SyntheticSpatialDataset(seed=seed).generate(n_points=n_points, noise_std=0.02)
    return np.asarray(payload["coords"], dtype=float), np.asarray(payload["values"], dtype=float)


def _assert_common_stage2_payload(payload: dict) -> None:
    residual_analysis = payload["residual_analysis"]
    assert residual_analysis["residual_stats"]["mae"] >= 0.0
    assert residual_analysis["residual_stats"]["rmse"] >= 0.0
    assert len(residual_analysis["top_residual_nodes"]) >= 1
    assert residual_analysis["diagnosis"]["bias_type"] in {"under_prediction_bias", "over_prediction_bias", "balanced"}

    baseline_cmp = payload["baseline_model_comparison"]
    assert baseline_cmp["active_baseline"] in {"ordinary", "universal"}
    assert baseline_cmp["query_count"] >= 1
    assert baseline_cmp["active_baseline_consistency"]["mae"] >= 0.0
    assert len(baseline_cmp["candidate_baselines"]) == 2
    names = [item["name"] for item in baseline_cmp["candidate_baselines"]]
    assert set(names) == {"ordinary", "universal"}

    spatial = payload["residual_spatial_distribution"]
    assert len(spatial["histogram"]["edges"]) >= 5
    assert len(spatial["histogram"]["counts"]) >= 4
    assert len(spatial["spatial_bins"]) == 4
    assert len(spatial["hotspots"]) >= 1

    perf = payload["performance"]
    assert perf["duration_ms"] < 8000.0
    assert perf["latency_target_ms"] == 8000.0
    assert perf["meets_latency_target"] is True
    assert perf["context_memory_bytes"] > 0


def test_residual_kriging_lime_stage2_residual_baseline_spatial_and_performance() -> None:
    coords, values = _make_data(seed=161)
    model = ResidualKrigingModel(architecture="hybrid", baseline="universal")
    queries = coords[:24]
    adapter = ResidualKrigingLIMEAdapter(
        config=ResidualKrigingExplanationConfig(lime_num_samples=120, max_explain_nodes=5)
    )

    out = adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=5,
        num_samples=100,
    )

    _assert_common_stage2_payload(out)
    assert out["performance"]["lime_training_size"] >= len(out["batch_explanations"])
    assert out["performance"]["lime_sampling_budget"] >= 80

    active = out["baseline_model_comparison"]["active_baseline_consistency"]
    assert active["mae"] <= 1e-6


def test_residual_kriging_shap_stage2_residual_baseline_spatial_and_performance() -> None:
    coords, values = _make_data(seed=171)
    model = ResidualKrigingModel(architecture="hybrid", baseline="ordinary")
    queries = coords[:22]
    adapter = ResidualKrigingSHAPAdapter(
        config=ResidualKrigingExplanationConfig(shap_nsamples=90, max_explain_nodes=4)
    )

    out = adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=4,
        nsamples=80,
    )

    _assert_common_stage2_payload(out)
    assert out["performance"]["backend"] in {"shap", "surrogate_linear"}
    assert out["performance"]["shap_background_size"] <= 32
    assert out["performance"]["shap_sampling_budget"] >= 40


def test_residual_kriging_shap_stage2_batch_explain_with_cache() -> None:
    coords, values = _make_data(seed=181)
    model = ResidualKrigingModel(architecture="hybrid", baseline="ordinary")
    adapter = ResidualKrigingSHAPAdapter(
        config=ResidualKrigingExplanationConfig(shap_nsamples=70, max_explain_nodes=3)
    )

    batches = [coords[:10], coords[10:20], coords[:10]]
    out = adapter.explain_batch(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords_batch=batches,
        top_k=3,
        nsamples=60,
    )

    assert out["summary"]["method"] == "shap"
    assert out["summary"]["batch_size"] == 3
    assert out["summary"]["cache_hit_count"] >= 1
    assert out["summary"]["cache_hit_ratio"] > 0.0
    assert out["performance"]["avg_duration_ms"] > 0.0
