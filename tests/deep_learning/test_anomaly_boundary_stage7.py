from __future__ import annotations

import numpy as np
import pytest

from services.backend.app.dl_services.explain_service import SpatiotemporalExplainTaskService
from services.backend.app.dl_services.service import DeepLearningService


MODELS = ("vae", "gcae", "gan", "contrastive")


class _DummySettings:
    REDIS_URL = None
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = 6379
    REDIS_DB = 0
    WORKFLOW_REDIS_POOL_SIZE = 20
    WORKFLOW_REDIS_TIMEOUT_SECONDS = 5
    WORKFLOW_REDIS_RETRY_TIMES = 1
    WORKFLOW_REDIS_STRICT = False
    WORKFLOW_REDIS_CLUSTER_ENABLED = False
    WORKFLOW_REDIS_CLUSTER_NODES: list[str] = []

    EXPLAIN_MAX_CONCURRENT_TASKS = 2
    EXPLAIN_TASK_TIMEOUT_SECONDS = 120
    EXPLAIN_TASK_TTL_SECONDS = 180
    EXPLAIN_RESULT_TTL_SECONDS = 360
    EXPLAIN_RESULT_COMPRESSION_THRESHOLD = 4096
    EXPLAIN_DEFAULT_PRIORITY = 5
    EXPLAIN_MAX_BATCH_SIZE = 128
    EXPLAIN_RATE_LIMIT_PER_MINUTE = 60
    EXPLAIN_ALLOWED_CREATORS: list[str] = []
    EXPLAIN_CELERY_ENABLED = False


class _DummyDLService:
    def explain_spatiotemporal(self, **kwargs):
        return {"ok": True, "payload": kwargs}


class _RaisingConnection:
    def ensure_connection(self, max_retries: int = 1) -> None:
        _ = max_retries
        raise ConnectionError("simulated network outage")

    def release(self) -> None:
        return None


class _RaisingCeleryApp:
    def connection(self) -> _RaisingConnection:
        return _RaisingConnection()


def _make_extreme_data(n: int = 96, seed: int = 719) -> tuple[list[list[float]], list[float]]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(-1.0e4, 1.0e4, size=(n, 2))
    values = (
        np.sin(coords[:, 0] * 1.0e-3) * 8.0e5
        + np.cos(coords[:, 1] * 8.0e-4) * 7.0e5
        + rng.normal(0.0, 2.0e4, size=n)
    )
    values[::17] += 6.0e5
    values[5::23] -= 4.8e5
    return coords.tolist(), values.tolist()


def _make_large_data(n: int = 1400, seed: int = 733) -> tuple[list[list[float]], list[float]]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 6.3) + np.cos(coords[:, 1] * 4.1) + rng.normal(0.0, 0.05, size=n)
    values[::31] += 1.1
    values[8::37] -= 0.8
    return coords.tolist(), values.tolist()


def test_stage7_extreme_input_data_processing() -> None:
    service = DeepLearningService()

    for model_name in MODELS:
        coords, values = _make_extreme_data(seed=719 + len(model_name))
        out = service.predict_anomaly(
            model_name=model_name,
            coords=coords,
            values=values,
            threshold_method="percentile",
            percentile=97.0,
            k=2.8,
        )

        prediction = out["prediction"]
        assert len(prediction["anomaly_scores"]) == len(values)
        assert len(prediction["anomaly_indices"]) <= len(values)
        assert np.isfinite(np.asarray(prediction["anomaly_scores"], dtype=float)).all()


def test_stage7_empty_input_and_short_input_handling() -> None:
    service = DeepLearningService()

    with pytest.raises(ValueError, match="coords must be"):
        service.predict_anomaly(model_name="vae", coords=[], values=[])

    with pytest.raises(ValueError, match="at least 5 points"):
        service.explain_anomaly(model_name="gcae", coords=[[0.1, 0.2]], values=[1.0], method="hybrid")


def test_stage7_large_volume_input_processing() -> None:
    service = DeepLearningService()
    coords, values = _make_large_data()

    out = service.predict_anomaly(
        model_name="vae",
        coords=coords,
        values=values,
        threshold_method="percentile",
        percentile=95.0,
        k=2.5,
    )

    prediction = out["prediction"]
    assert len(prediction["anomaly_scores"]) == len(values)
    assert len(prediction["anomaly_indices"]) <= len(values)
    assert len(out["score_preview"]) <= 10


def test_stage7_abnormal_model_state_auto_recovery() -> None:
    service = DeepLearningService()
    coords, values = _make_extreme_data(seed=811)

    service.train_anomaly_model("vae", coords, values, epochs=10)
    service.anomaly_models["vae"] = {"broken": True}

    out = service.predict_anomaly(
        model_name="vae",
        coords=coords,
        values=values,
        threshold_method="percentile",
        percentile=95.0,
        k=2.5,
    )

    assert out["model_name"] == "vae"
    assert len(out["prediction"]["anomaly_scores"]) == len(values)
    assert hasattr(service.anomaly_models["vae"], "predict")


def test_stage7_network_exception_handling_for_celery_verify() -> None:
    explain_service = SpatiotemporalExplainTaskService(settings=_DummySettings(), dl_service=_DummyDLService())
    explain_service._celery_available = True
    explain_service._celery_app = _RaisingCeleryApp()

    status = explain_service.verify_celery_connection()

    assert status["celery_enabled"] is True
    assert status["broker_ok"] is False
    assert "simulated network outage" in status["reason"]

    explain_service._running = False
    explain_service._executor.shutdown(wait=False, cancel_futures=True)
