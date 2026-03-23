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
