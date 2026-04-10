from __future__ import annotations

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backend.app.dl_services.api import router


def build_payload(n: int = 60) -> tuple[list[list[float]], list[float]]:
    rng = np.random.default_rng(44)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.0) + np.cos(coords[:, 1] * 3.0) + rng.normal(0.0, 0.07, size=n)
    return coords.tolist(), values.tolist()


def test_anomaly_train_predict_and_realtime_endpoints() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    coords, values = build_payload()

    train_resp = client.post(
        "/api/dl/anomaly/train",
        json={
            "model_name": "vae",
            "coords": coords,
            "values": values,
            "epochs": 10,
        },
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["model_name"] == "vae"

    predict_resp = client.post(
        "/api/dl/anomaly/predict",
        json={
            "model_name": "vae",
            "coords": coords,
            "values": values,
            "threshold_method": "percentile",
            "percentile": 92.0,
        },
    )
    assert predict_resp.status_code == 200
    assert predict_resp.json()["model_name"] == "vae"
    assert "prediction" in predict_resp.json()

    fusion_resp = client.post(
        "/api/dl/anomaly/predict",
        json={
            "model_name": "fusion",
            "coords": coords,
            "values": values,
        },
    )
    assert fusion_resp.status_code == 200
    assert fusion_resp.json()["anomaly_count"] >= 0

    realtime_resp = client.post(
        "/api/dl/anomaly/realtime",
        json={
            "model_name": "vae",
            "stream_batches": [
                {"coords": coords[:30], "values": values[:30]},
                {"coords": coords[30:], "values": values[30:]},
            ],
            "threshold_method": "adaptive",
            "k": 2.0,
        },
    )
    assert realtime_resp.status_code == 200
    assert len(realtime_resp.json()["batches"]) == 2


def test_anomaly_cache_management_endpoints() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    coords, values = build_payload(48)
    first = client.post(
        "/api/dl/anomaly/predict",
        json={
            "model_name": "vae",
            "coords": coords,
            "values": values,
            "threshold_method": "adaptive",
            "k": 2.1,
        },
    )
    assert first.status_code == 200
    assert first.json()["cache"]["cache_hit"] is False

    second = client.post(
        "/api/dl/anomaly/predict",
        json={
            "model_name": "vae",
            "coords": coords,
            "values": values,
            "threshold_method": "adaptive",
            "k": 2.1,
        },
    )
    assert second.status_code == 200
    assert second.json()["cache"]["cache_hit"] is True

    metrics_resp = client.get("/api/dl/anomaly/cache/metrics")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert metrics["enabled"] is True
    assert "prediction" in metrics["namespaces"]

    cleanup_resp = client.post("/api/dl/anomaly/cache/cleanup", json={"namespace": "prediction"})
    assert cleanup_resp.status_code == 200
    assert "stats" in cleanup_resp.json()

    clear_resp = client.post("/api/dl/anomaly/cache/clear", json={"namespace": "prediction"})
    assert clear_resp.status_code == 200
    assert "removed" in clear_resp.json()


def test_anomaly_cache_warmup_invalidate_and_persist_endpoints() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    warmup_resp = client.post(
        "/api/dl/anomaly/cache/warmup",
        json={
            "items": [
                {"namespace": "prediction", "key": "prediction:vae:v0:api-k1", "value": {"x": 1}},
                {"namespace": "explanation", "key": "explanation:vae:v0:api-k2", "value": {"y": 2}},
            ]
        },
    )
    assert warmup_resp.status_code == 200
    assert warmup_resp.json()["warmup"]["succeeded"] == 2

    invalidate_resp = client.post(
        "/api/dl/anomaly/cache/invalidate",
        json={"namespace": "prediction", "key_prefix": "prediction:vae:v0:"},
    )
    assert invalidate_resp.status_code == 200
    assert invalidate_resp.json()["removed"]["prediction"] >= 1

    persist_resp = client.post("/api/dl/anomaly/cache/persist")
    assert persist_resp.status_code == 200
    assert "persist_enabled" in persist_resp.json()
