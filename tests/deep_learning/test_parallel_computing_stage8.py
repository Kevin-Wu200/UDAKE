from __future__ import annotations

import time
from typing import Any

import numpy as np

from services.backend.app.dl_services.lime_explainer import LIMEConfig, SpatiotemporalLIMEExplainer
from services.backend.app.dl_services.parallel_runtime import ParallelExecutionManager, ParallelTask
from services.backend.app.dl_services.service import DeepLearningService
from services.backend.app.dl_services.shap_explainer import SHAPConfig, SpatiotemporalSHAPExplainer


def _build_case(n_nodes: int = 36, seq_len: int = 8, n_features: int = 3, seed: int = 20260410) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n_nodes, 2)).astype(float)
    series = rng.normal(0.0, 0.05, size=(n_nodes, seq_len, n_features)).astype(float)
    trend = np.linspace(0.0, 0.6, seq_len, dtype=float).reshape(1, seq_len, 1)
    series = series + trend
    series[::8, :, 0] += 0.7
    series[3::10, :, 1] -= 0.55
    weights = np.zeros((n_features,), dtype=float)
    preset = np.asarray([0.5, 0.3, 0.2], dtype=float)
    weights[: min(n_features, preset.shape[0])] = preset[: min(n_features, preset.shape[0])]
    if float(np.sum(weights)) <= 1e-8:
        weights[:] = 1.0 / max(1, n_features)
    else:
        weights = weights / np.sum(weights)
    pred = np.sum(np.mean(series, axis=1) * weights.reshape(1, -1), axis=1)
    pred_mean = np.stack((pred, pred * 0.99 + 0.005), axis=1)
    return coords, series, pred_mean


def test_parallel_runtime_queue_and_monitor_stage8() -> None:
    runtime = ParallelExecutionManager(name="parallel-test", max_workers=4, min_workers=1)
    tasks = [ParallelTask(task_id=f"t{i}", priority=i % 2, payload=i) for i in range(12)]

    out, report = runtime.run_tasks(
        tasks=tasks,
        task_type="cpu",
        worker_fn=lambda value: value * value,
    )

    assert out == [i * i for i in range(12)]
    assert report.task_count == 12
    assert report.workers >= 1
    snapshot = runtime.snapshot()
    assert snapshot["submitted_tasks"] >= 12
    assert snapshot["completed_tasks"] >= 12
    assert snapshot["peak_queue_size"] >= 1


def test_lime_parallel_metrics_stage8() -> None:
    coords, series, pred_mean = _build_case()
    explainer = SpatiotemporalLIMEExplainer(config=LIMEConfig(max_workers=4, num_samples=120, min_samples=80, max_samples=280))
    out = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=5,
        max_explain_nodes=8,
    )
    perf = out["performance"]
    assert int(perf["parallel_workers"]) >= 1
    assert "parallel_report" in perf
    assert int(perf["parallel_report"]["task_count"]) == 8
    assert "parallel_monitor" in perf


def test_shap_parallel_metrics_stage8() -> None:
    coords, series, pred_mean = _build_case()
    explainer = SpatiotemporalSHAPExplainer(config=SHAPConfig(max_workers=4, nsamples=70))
    explainer._load_shap = lambda: None
    out = explainer.explain(
        model_type="spatiotemporal",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=5,
        max_explain_nodes=7,
    )
    perf = out["performance"]
    assert int(perf["parallel_workers"]) >= 1
    assert int(perf["parallel_report"]["task_count"]) == 7
    assert "parallel_monitor" in perf


class _MockPredictResult:
    def __init__(self, mean: np.ndarray, variance: np.ndarray) -> None:
        self.mean = mean
        self.variance = variance


class _MockIntegrator:
    def __init__(self, delay_seconds: float = 0.03) -> None:
        self.delay_seconds = delay_seconds

    def predict(self, **kwargs: Any) -> _MockPredictResult:
        coords = np.asarray(kwargs["coords"], dtype=float)
        pred_horizon = int(kwargs["pred_horizon"])
        n = int(coords.shape[0])
        time.sleep(self.delay_seconds)
        mean = np.full((n, pred_horizon), fill_value=0.8, dtype=float)
        variance = np.full((n, pred_horizon), fill_value=0.1, dtype=float)
        return _MockPredictResult(mean=mean, variance=variance)


def test_batched_parallel_speedup_stage8() -> None:
    coords, series, _ = _build_case(n_nodes=64, seq_len=6, n_features=2)
    service = DeepLearningService()
    service.spatiotemporal_integrator = _MockIntegrator(delay_seconds=0.03)

    service.batch_parallel = ParallelExecutionManager(name="batch-serial", max_workers=1, min_workers=1)
    started_serial = time.perf_counter()
    serial_mean, serial_var = service._predict_spatiotemporal_batched(
        model_type="st_transformer",
        coords=coords,
        series=series,
        pred_horizon=4,
        batch_size=16,
    )
    serial_duration = time.perf_counter() - started_serial

    service.batch_parallel = ParallelExecutionManager(name="batch-parallel", max_workers=4, min_workers=1)
    started_parallel = time.perf_counter()
    parallel_mean, parallel_var = service._predict_spatiotemporal_batched(
        model_type="st_transformer",
        coords=coords,
        series=series,
        pred_horizon=4,
        batch_size=16,
    )
    parallel_duration = time.perf_counter() - started_parallel

    assert serial_mean.shape == parallel_mean.shape
    assert serial_var.shape == parallel_var.shape
    assert parallel_duration < serial_duration * 0.8
