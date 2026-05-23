from __future__ import annotations

import numpy as np

from services.backend.app.dl_services.lime_explainer import (
    LIMEConfig,
    SpatiotemporalLIMEExplainer,
)


def _build_case(n_nodes: int = 40, seq_len: int = 8, n_features: int = 3) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20260409)
    coords = rng.uniform(0.0, 1.0, size=(n_nodes, 2)).astype(float)

    base = rng.normal(0.0, 0.08, size=(n_nodes, seq_len, n_features)).astype(float)
    trend = np.linspace(0.0, 0.6, seq_len, dtype=float).reshape(1, seq_len, 1)
    series = base + trend
    series[::9, :, 0] += 0.9
    series[5::11, :, 1] -= 0.7

    pred = (
        0.45 * np.mean(series[:, :, 0], axis=1)
        + 0.35 * np.mean(series[:, :, 1], axis=1)
        + 0.2 * np.mean(series[:, :, 2], axis=1)
    )
    pred_mean = np.stack((pred, pred * 0.97 + 0.01), axis=1)
    return coords, series, pred_mean


def test_lime_adaptive_sampling_plan_and_range_stage8() -> None:
    coords, series, pred_mean = _build_case()
    explainer = SpatiotemporalLIMEExplainer(
        config=LIMEConfig(num_samples=160, max_workers=1, neighborhood_size=24, min_samples=80, max_samples=420)
    )

    out = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=5,
        max_explain_nodes=6,
    )

    perf = out["performance"]
    summary = out["summary"]
    plan = perf["sampling_plan"]

    assert len(plan) == 6
    values = [int(v) for v in plan.values()]
    assert min(values) >= 80
    assert max(values) <= 420
    assert summary["sampling_range"][0] == min(values)
    assert summary["sampling_range"][1] == max(values)


def test_lime_weighted_neighborhood_definition_stage8() -> None:
    coords, series, pred_mean = _build_case(n_nodes=24)
    explainer = SpatiotemporalLIMEExplainer(config=LIMEConfig(neighborhood_size=20, max_workers=1))
    context = explainer._build_context(model_type="spatiotemporal", coords=coords, series=series, pred_mean=pred_mean)

    node_index = 3
    neighborhood = explainer._build_node_neighborhood(context, node_index=node_index, node_score=0.8)
    instance = np.asarray(context["scaled_x"][node_index], dtype=float)

    assert 16 <= neighborhood.shape[0] <= 24
    assert neighborhood.shape[1] == context["scaled_x"].shape[1]
    assert np.any(np.all(np.isclose(neighborhood, instance.reshape(1, -1)), axis=1))


def test_lime_sampling_convergence_and_cache_key_stage8() -> None:
    coords, series, pred_mean = _build_case(n_nodes=28)
    explainer = SpatiotemporalLIMEExplainer(config=LIMEConfig(num_samples=150, max_workers=1, convergence_rounds=2))

    out1 = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=4,
        max_explain_nodes=5,
        num_samples=120,
    )
    out2 = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=4,
        max_explain_nodes=5,
        num_samples=160,
    )

    assert out1["performance"]["cache_hit"] is False
    assert out2["performance"]["cache_hit"] is False
    assert "convergence_rate" in out1["summary"]
    assert "convergence_rounds_mean" in out1["performance"]

    first_item = out1["batch_explanations"][0]
    assert "sampling" in first_item
    assert "convergence" in first_item["sampling"]
    assert first_item["sampling"]["neighborhood_size"] >= 16
