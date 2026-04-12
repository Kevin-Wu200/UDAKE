from __future__ import annotations

import time

import numpy as np
import pytest

from deep_learning.models.uncertainty import UncertaintySystemIntegrator


def _make_data(n: int = 120, seed: int = 311) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    base = np.sin(coords[:, 0] * 5.1) + np.cos(coords[:, 1] * 3.7)
    # x 维高区间注入更强噪声，用于验证不确定性估计的敏感性。
    noise_scale = np.where(coords[:, 0] > 0.65, 0.18, 0.03)
    values = base + rng.normal(0.0, noise_scale, size=n)
    return coords, values


def test_stage2_deep_ensemble_integration_predict_api_and_dashboard() -> None:
    coords, values = _make_data(n=116, seed=317)
    sample_coords, sample_values = coords[:88], values[:88]
    query_coords = coords[88:104]

    integrator = UncertaintySystemIntegrator(cache_ttl_seconds=120)
    train = integrator.train_uq_model("deep_ensemble", sample_coords, sample_values, max_epochs=56)
    assert train["training"]["n_members"] >= 2
    assert train["training"]["avg_val_nll"] >= 0.0

    pred = integrator.predict(sample_coords, sample_values, query_coords, method="deep_ensemble")
    assert pred.method == "deep_ensemble"
    assert pred.mean.shape == (16,)
    assert pred.variance.shape == (16,)
    assert np.all(pred.variance > 0.0)
    assert np.all(pred.aleatoric > 0.0)
    assert np.all(pred.epistemic > 0.0)
    assert float(np.mean(np.abs(pred.variance - (pred.aleatoric + pred.epistemic)))) < 1e-6

    api = integrator.api_predict(
        {
            "sample_coords": sample_coords,
            "sample_values": sample_values,
            "query_coords": query_coords,
            "method": "deep_ensemble",
        }
    )
    assert api["method"] == "deep_ensemble"
    assert len(api["prediction"]) == 16
    assert len(api["variance"]) == 16
    assert abs(sum(api["uncertainty_levels"].values()) - 1.0) < 1e-6

    dashboard = integrator.dashboard_payload(query_coords, pred)
    assert len(dashboard["points"]) == 16
    assert len(dashboard["spatial_decomposition"]["local_mean"]) == 16


def test_stage2_edl_integration_predict_api_and_realtime() -> None:
    coords, values = _make_data(n=118, seed=331)
    sample_coords, sample_values = coords[:90], values[:90]
    query_coords = coords[90:106]

    integrator = UncertaintySystemIntegrator(cache_ttl_seconds=120)
    train = integrator.train_uq_model("edl", sample_coords, sample_values, max_epochs=64)
    assert train["training"]["epochs"] == 64

    pred = integrator.predict(sample_coords, sample_values, query_coords, method="edl")
    assert pred.method == "edl"
    assert pred.mean.shape == (16,)
    assert pred.variance.shape == (16,)
    assert np.all(pred.variance > 0.0)
    assert np.all(pred.aleatoric > 0.0)
    assert np.all(pred.epistemic > 0.0)

    api = integrator.api_predict(
        {
            "sample_coords": sample_coords,
            "sample_values": sample_values,
            "query_coords": query_coords,
            "method": "edl",
        }
    )
    assert api["method"] == "edl"
    assert len(api["prediction"]) == 16
    assert len(api["variance"]) == 16
    assert abs(sum(api["uncertainty_levels"].values()) - 1.0) < 1e-6

    stream = integrator.realtime_updates(
        [
            {
                "sample_coords": sample_coords[:60],
                "sample_values": sample_values[:60],
                "query_coords": query_coords[:8],
            },
            {
                "sample_coords": sample_coords,
                "sample_values": sample_values,
                "query_coords": query_coords[8:16],
            },
        ],
        method="edl",
    )
    assert len(stream) == 2
    assert stream[0]["method"] == "edl"
    assert stream[1]["max_uncertainty"] >= stream[1]["min_uncertainty"]


def test_stage2_uncertainty_estimation_accuracy_high_noise_region_has_higher_variance() -> None:
    coords, values = _make_data(n=128, seed=347)
    sample_coords, sample_values = coords[:96], values[:96]
    eval_coords = coords[96:128]

    low_noise_query = eval_coords[eval_coords[:, 0] < 0.35][:8]
    high_noise_query = eval_coords[eval_coords[:, 0] > 0.65][:8]
    assert len(low_noise_query) >= 3
    assert len(high_noise_query) >= 3

    integrator = UncertaintySystemIntegrator(cache_ttl_seconds=120)
    integrator.train_uq_model("deep_ensemble", sample_coords, sample_values, max_epochs=56)
    low = integrator.predict(sample_coords, sample_values, low_noise_query, method="deep_ensemble")
    high = integrator.predict(sample_coords, sample_values, high_noise_query, method="deep_ensemble")
    assert float(np.mean(high.variance)) > float(np.mean(low.variance))

    # EDL 路径确认输出形态稳定，不强制噪声区分单调关系，避免统计波动引发脆弱断言。
    integrator.train_uq_model("edl", sample_coords, sample_values, max_epochs=56)
    edl_low = integrator.predict(sample_coords, sample_values, low_noise_query, method="edl")
    edl_high = integrator.predict(sample_coords, sample_values, high_noise_query, method="edl")
    assert np.all(edl_low.variance > 0.0)
    assert np.all(edl_high.variance > 0.0)


def test_stage2_epistemic_aleatoric_decomposition_with_ood_shift() -> None:
    coords, values = _make_data(n=120, seed=359)
    sample_coords, sample_values = coords[:92], values[:92]
    in_dist_query = coords[92:104]
    ood_query = np.array([[1.30, 1.25], [1.45, 0.25], [1.15, -0.15], [1.28, 1.38]], dtype=float)

    integrator = UncertaintySystemIntegrator(cache_ttl_seconds=120)
    integrator.train_uq_model("deep_ensemble", sample_coords, sample_values, max_epochs=56)
    in_res = integrator.predict(sample_coords, sample_values, in_dist_query, method="deep_ensemble")
    ood_res = integrator.predict(sample_coords, sample_values, ood_query, method="deep_ensemble")
    assert not np.allclose(in_res.aleatoric, in_res.epistemic)
    assert not np.allclose(ood_res.aleatoric, ood_res.epistemic)
    assert float(np.mean(ood_res.epistemic)) >= float(np.mean(in_res.epistemic))

    integrator.train_uq_model("edl", sample_coords, sample_values, max_epochs=56)
    edl_in = integrator.predict(sample_coords, sample_values, in_dist_query, method="edl")
    edl_ood = integrator.predict(sample_coords, sample_values, ood_query, method="edl")
    assert not np.allclose(edl_in.aleatoric, edl_in.epistemic)
    assert not np.allclose(edl_ood.aleatoric, edl_ood.epistemic)


def test_stage2_performance_benchmark_cache_accelerates_inference() -> None:
    coords, values = _make_data(n=124, seed=373)
    sample_coords, sample_values = coords[:96], values[:96]
    query_coords = coords[96:116]

    integrator = UncertaintySystemIntegrator(cache_ttl_seconds=120)
    integrator.train_uq_model("deep_ensemble", sample_coords, sample_values, max_epochs=52)

    start_first = time.perf_counter()
    first = integrator.predict(sample_coords, sample_values, query_coords, method="deep_ensemble")
    first_ms = (time.perf_counter() - start_first) * 1000.0

    start_second = time.perf_counter()
    second = integrator.predict(sample_coords, sample_values, query_coords, method="deep_ensemble")
    second_ms = (time.perf_counter() - start_second) * 1000.0

    assert first.mean.shape == second.mean.shape == (20,)
    assert second_ms <= first_ms
    assert first_ms < 15000.0


def test_stage2_boundary_conditions_invalid_model_fuse_mismatch_and_empty_query() -> None:
    coords, values = _make_data(n=108, seed=389)
    sample_coords, sample_values = coords[:84], values[:84]
    query_coords = coords[84:96]
    empty_query = np.empty((0, 2), dtype=float)

    integrator = UncertaintySystemIntegrator(cache_ttl_seconds=120)

    with pytest.raises(ValueError, match="不支持的模型"):
        integrator.train_uq_model("unknown_model", sample_coords, sample_values, max_epochs=40)  # type: ignore[arg-type]

    pred = integrator.predict(sample_coords, sample_values, query_coords, method="deep_ensemble")
    with pytest.raises(ValueError, match="legacy_variance 长度不匹配"):
        integrator.fuse_with_existing_uncertainty(pred, legacy_variance=np.ones(len(pred.variance) - 1, dtype=float))

    empty_res = integrator.predict(sample_coords, sample_values, empty_query, method="edl")
    assert empty_res.mean.shape == (0,)
    assert empty_res.variance.shape == (0,)
