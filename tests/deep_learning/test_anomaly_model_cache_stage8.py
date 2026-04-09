from __future__ import annotations

import time

import numpy as np

from services.backend.app.dl_services.anomaly_cache import AnomalyModelCache
from services.backend.app.dl_services.service import DeepLearningService


def _build_payload(n: int = 48) -> tuple[list[list[float]], list[float]]:
    rng = np.random.default_rng(208)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.0) + np.cos(coords[:, 1] * 4.0) + rng.normal(0.0, 0.04, size=n)
    values[::11] += 0.55
    return coords.tolist(), values.tolist()


def test_anomaly_model_cache_ttl_and_cleanup() -> None:
    cache = AnomalyModelCache(cache_size=8, ttl_seconds=1)
    cache.set("prediction", "k1", {"value": 1})
    assert cache.get("prediction", "k1") == {"value": 1}
    assert cache.stats()["namespaces"]["prediction"]["hit_rate"] == 1.0

    time.sleep(1.2)
    assert cache.get("prediction", "k1") is None
    cleanup = cache.cleanup("prediction")
    assert cleanup["prediction"] >= 0
    stats = cache.stats()
    assert stats["namespaces"]["prediction"]["expirations"] >= 1


def test_service_predict_cache_hit_stage8() -> None:
    service = DeepLearningService()
    coords, values = _build_payload(44)

    out1 = service.predict_anomaly(
        model_name="vae",
        coords=coords,
        values=values,
        threshold_method="percentile",
        percentile=93.0,
        k=2.2,
    )
    out2 = service.predict_anomaly(
        model_name="vae",
        coords=coords,
        values=values,
        threshold_method="percentile",
        percentile=93.0,
        k=2.2,
    )

    assert out1["cache"]["namespace"] == "prediction"
    assert out1["cache"]["cache_hit"] is False
    assert out2["cache"]["cache_hit"] is True
    assert out2["prediction"]["anomaly_indices"] == out1["prediction"]["anomaly_indices"]


def test_service_explain_cache_hit_stage8() -> None:
    service = DeepLearningService()
    coords, values = _build_payload(42)

    out1 = service.explain_anomaly(
        model_name="vae",
        coords=coords,
        values=values,
        method="lime",
        top_k=4,
        include_prediction=False,
        max_explain_nodes=5,
        num_samples=100,
    )
    out2 = service.explain_anomaly(
        model_name="vae",
        coords=coords,
        values=values,
        method="lime",
        top_k=4,
        include_prediction=False,
        max_explain_nodes=5,
        num_samples=100,
    )

    assert out1["cache"]["namespace"] == "explanation"
    assert out1["cache"]["cache_hit"] is False
    assert out2["cache"]["cache_hit"] is True
    assert out2["summary"]["method"] == "lime"


def test_service_cache_expire_and_cleanup_stage8() -> None:
    service = DeepLearningService()
    service.anomaly_cache = AnomalyModelCache(cache_size=64, ttl_seconds=1)
    coords, values = _build_payload(40)

    out1 = service.predict_anomaly(
        model_name="vae",
        coords=coords,
        values=values,
        threshold_method="adaptive",
        percentile=95.0,
        k=2.0,
    )
    assert out1["cache"]["cache_hit"] is False

    time.sleep(1.2)
    cleanup = service.cleanup_anomaly_cache("prediction")
    assert cleanup["removed"]["prediction"] >= 0

    out2 = service.predict_anomaly(
        model_name="vae",
        coords=coords,
        values=values,
        threshold_method="adaptive",
        percentile=95.0,
        k=2.0,
    )
    assert out2["cache"]["cache_hit"] is False
