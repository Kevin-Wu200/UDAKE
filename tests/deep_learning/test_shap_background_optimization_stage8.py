from __future__ import annotations

import numpy as np

from services.backend.app.dl_services.shap_explainer import (
    SHAPConfig,
    SpatiotemporalSHAPExplainer,
)


def _build_case(n_nodes: int = 48, seq_len: int = 8, n_features: int = 3, seed: int = 20260409) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n_nodes, 2)).astype(float)

    base = rng.normal(0.0, 0.08, size=(n_nodes, seq_len, n_features)).astype(float)
    trend = np.linspace(0.0, 0.7, seq_len, dtype=float).reshape(1, seq_len, 1)
    series = base + trend
    series[::9, :, 0] += 0.85
    series[5::11, :, 1] -= 0.65

    base_weights = np.asarray([0.5, 0.3, 0.2], dtype=float)
    weights = np.zeros((n_features,), dtype=float)
    weights[: min(n_features, base_weights.shape[0])] = base_weights[: min(n_features, base_weights.shape[0])]
    if np.sum(weights) <= 1e-8:
        weights[:] = 1.0 / max(1, n_features)
    else:
        weights = weights / np.sum(weights)
    pred = np.sum(np.mean(series, axis=1) * weights.reshape(1, -1), axis=1)
    pred_mean = np.stack((pred, pred * 0.98 + 0.01), axis=1)
    return coords, series, pred_mean


def test_shap_background_optimization_outputs_stage8() -> None:
    coords, series, pred_mean = _build_case()
    explainer = SpatiotemporalSHAPExplainer(
        config=SHAPConfig(background_size=24, min_background_size=12, max_background_size=40, nsamples=80)
    )
    explainer._load_shap = lambda: None

    out = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=5,
        max_explain_nodes=6,
    )

    summary = out["summary"]
    performance = out["performance"]

    assert 12 <= int(summary["background_size"]) <= 40
    assert int(summary["background_recommended_size"]) >= 8
    assert 0.0 <= float(summary["background_quality_score"]) <= 1.0

    quality = performance["background_quality"]
    assert set(quality.keys()) == {"coverage", "diversity", "target_balance", "local_focus", "overall"}
    assert all(0.0 <= float(v) <= 1.0 for v in quality.values())

    impact = performance["background_size_impact"]
    assert len(impact) >= 2
    assert all("size" in item and "quality_score" in item for item in impact)


def test_shap_background_cache_and_update_strategy_stage8() -> None:
    coords, series, pred_mean = _build_case(n_nodes=44)
    explainer = SpatiotemporalSHAPExplainer(
        config=SHAPConfig(
            background_size=20,
            min_background_size=10,
            max_background_size=36,
            background_update_interval_seconds=3600,
            background_drift_threshold=0.2,
            nsamples=70,
        )
    )
    explainer._load_shap = lambda: None

    out1 = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=4,
        nsamples=90,
        max_explain_nodes=5,
    )
    out2 = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=4,
        nsamples=110,
        max_explain_nodes=5,
    )

    assert out1["performance"]["background_cache_hit"] is False
    assert out2["performance"]["cache_hit"] is False
    assert out2["performance"]["background_cache_hit"] is True

    shifted = pred_mean + 1.2
    out3 = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=shifted,
        top_k=4,
        nsamples=130,
        max_explain_nodes=5,
    )

    assert out3["performance"]["cache_hit"] is False
    assert out3["performance"]["background_cache_hit"] is False
    assert out3["performance"]["background_update_reason"] == "new_or_refreshed"


def test_shap_fallback_accuracy_stage8() -> None:
    coords, series, pred_mean = _build_case(n_nodes=30, seq_len=7, n_features=2)
    explainer = SpatiotemporalSHAPExplainer(config=SHAPConfig(background_size=16, min_background_size=8, max_background_size=24))
    explainer._load_shap = lambda: None

    out = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=4,
        max_explain_nodes=6,
    )

    node_indices = [int(item["node_index"]) for item in out["batch_explanations"]]
    context = explainer._build_context(
        model_type="spatiotemporal",
        coords=np.asarray(coords, dtype=float),
        series=np.asarray(series, dtype=float),
        pred_mean=np.asarray(pred_mean, dtype=float),
        node_indices=node_indices,
    )
    coef = np.asarray(context["surrogate"].coef_, dtype=float)
    baseline = np.mean(np.asarray(context["background"], dtype=float), axis=0)

    mae_list: list[float] = []
    for item in out["batch_explanations"]:
        idx = int(item["node_index"])
        instance = np.asarray(context["scaled_x"][idx], dtype=float)
        expected = coef * (instance - baseline)
        actual = np.asarray(item["raw_shap_values"], dtype=float)
        mae_list.append(float(np.mean(np.abs(expected - actual))))
        assert item["backend"] == "surrogate_linear"
        assert abs(float(np.sum(actual)) + float(item["expected_value"]) - float(item["prediction"])) < 1e-6

    assert float(np.mean(mae_list)) < 1e-10
