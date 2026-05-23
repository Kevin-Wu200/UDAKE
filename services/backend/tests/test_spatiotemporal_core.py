from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

import numpy as np

services_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(services_root))

from backend.app.services.spatiotemporal_core import (
    IncrementalSTKrigingEngine,
    SpatiotemporalKrigingSolver,
    SpatiotemporalModelAutoSelector,
    SpatiotemporalPredictionEngine,
    SpatiotemporalVariogramModeler,
    STDataset,
)


def _dataset(n: int = 20) -> STDataset:
    x = np.linspace(120.0, 120.5, n)
    y = np.linspace(30.0, 30.5, n)
    z = np.linspace(10.0, 12.0, n)
    t = np.linspace(1711929600, 1711929600 + 86400 * (n - 1), n)
    value = 50 + 3 * np.sin(np.linspace(0, np.pi, n))
    return STDataset(x=x, y=y, z=z, t=t, value=value)


def test_variogram_modeler_fit():
    modeler = SpatiotemporalVariogramModeler()
    fitted = modeler.fit(_dataset(24), "nonseparable")

    assert "parameters" in fitted
    assert fitted["fitting_report"]["converged"] is True
    assert len(fitted["charts"]["spatial_variogram"]["lags"]) >= 1
    assert len(fitted["charts"]["temporal_variogram"]["lags"]) >= 1


def test_kriging_solver_predict():
    data = _dataset(28)
    modeler = SpatiotemporalVariogramModeler()
    params = modeler.fit(data, "product")["parameters"]

    solver = SpatiotemporalKrigingSolver(block_size=10, temporal_window_size=8, low_rank=12)
    result = solver.predict(
        train_data=data,
        targets={"x": [120.1, 120.2], "y": [30.1, 30.2], "z": [10.5, 10.8]},
        target_times=[1712016000, 1712102400],
        params=params,
        model_type="product",
        covariance_builder=modeler.build_covariance_function,
    )

    assert len(result["predictions"]) == 4
    assert len(result["weights"]) == 4
    assert "low_rank_used" in result["solver_info"]
    assert "target_rank" in result["solver_info"]


def test_auto_selector_metrics_and_report():
    selector = SpatiotemporalModelAutoSelector()
    y_true = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    y_pred_good = np.array([1.1, 2.0, 3.0, 3.9], dtype=np.float64)
    y_pred_bad = np.array([2.0, 3.5, 1.0, 0.5], dtype=np.float64)
    variance = np.array([0.2, 0.2, 0.2, 0.2], dtype=np.float64)

    eval_good = selector.evaluate(y_true, y_pred_good, variance)
    eval_bad = selector.evaluate(y_true, y_pred_bad, variance)

    best = selector.select_best({"good": eval_good, "bad": eval_bad})
    report = selector.generate_report(best, {"good": eval_good, "bad": eval_bad})

    assert eval_good["score"] < eval_bad["score"]
    assert best == "good"
    assert report["best_model"] == "good"
    assert len(report["ranked_models"]) == 2


def test_prediction_engine_cache_and_mode_switch():
    engine = SpatiotemporalPredictionEngine()

    async def _run_once():
        payload = {"model_id": "m1", "target": [1, 2, 3], "nonce": uuid.uuid4().hex}

        def online_predictor():
            return {"model_id": "m1", "predictions": [{"value": 1}], "summary": {"total_predictions": 1}}

        def offline_predictor():
            return {"model_id": "m1", "predictions": [{"value": 2}], "summary": {"total_predictions": 1}}

        first, mode1, cache1 = await engine.predict(
            model_id="m1",
            payload=payload,
            online_predictor=online_predictor,
            offline_predictor=offline_predictor,
            use_cache=True,
            online_preferred=True,
            backend_available=False,
        )
        second, mode2, cache2 = await engine.predict(
            model_id="m1",
            payload=payload,
            online_predictor=online_predictor,
            offline_predictor=offline_predictor,
            use_cache=True,
            online_preferred=True,
            backend_available=False,
        )

        assert mode1 == "offline"
        assert first["summary"]["cache_hit"] is False
        assert mode2 == "cache"
        assert second["summary"]["cache_hit"] is True
        assert cache1 is False and cache2 is True

    asyncio.run(_run_once())


def test_incremental_engine_update():
    engine = IncrementalSTKrigingEngine()
    base = _dataset(10)
    new = _dataset(3)
    params = {
        "spatial_sill": 1.0,
        "spatial_range": 0.5,
        "spatial_nugget": 0.01,
        "temporal_sill": 0.8,
        "temporal_range": 0.4,
        "temporal_nugget": 0.01,
        "coupling": 0.6,
        "beta": 1.5,
    }

    updated = engine.incremental_update(base, new, params)
    assert len(updated["dataset"].x) == 13
    assert updated["update_report"]["new_samples"] == 3
    assert updated["parameters"]["spatial_sill"] > 0

    inv_a = np.eye(3)
    u = np.array([0.1, 0.2, 0.3], dtype=np.float64)
    v = np.array([0.2, 0.1, 0.4], dtype=np.float64)
    updated_inv = engine.sherman_morrison_update(inv_a, u, v)
    assert updated_inv.shape == (3, 3)

    u_batch = np.array([[0.2, 0.1], [0.1, 0.3], [0.0, 0.2]], dtype=np.float64)
    c_batch = np.eye(2, dtype=np.float64)
    v_batch = u_batch.T
    woodbury_inv = engine.woodbury_batch_update(inv_a, u_batch, c_batch, v_batch)
    assert woodbury_inv.shape == (3, 3)


def test_solver_rank_and_windows_utilities():
    solver = SpatiotemporalKrigingSolver(block_size=6, temporal_window_size=4, low_rank=5)
    matrix = np.eye(10, dtype=np.float64) * 2.0
    landmarks = solver.sample_landmarks(matrix, rank=4)
    assert len(landmarks) == 4

    rank = solver.adaptive_rank(n_samples=1000, target_accuracy=0.95, memory_limit_mb=2000)
    assert 20 <= rank <= 300

    t = np.array([10, 20, 30, 40, 50, 60], dtype=np.float64)
    windows = solver.temporal_windows(t, step=2, overlap=1)
    assert len(windows) >= 2

    merged = solver.merge_window_predictions([np.array([1, 2, 3]), np.array([2, 3, 4])])
    assert merged.tolist() == [1.5, 2.5, 3.5]
