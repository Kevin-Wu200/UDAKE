from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


def _payload(nodes: int = 8, seq_len: int = 20, horizon: int = 4) -> dict:
    rng = np.random.default_rng(123)
    coords = rng.uniform(0.0, 1.0, size=(nodes, 2))
    t = np.linspace(0.0, 2.0 * np.pi, seq_len, endpoint=False)
    base = np.sin(t)[None, :] + rng.normal(0.0, 0.02, size=(nodes, seq_len))
    aux = np.cos(t)[None, :] + rng.normal(0.0, 0.02, size=(nodes, seq_len))
    series = np.stack([base, aux], axis=-1)
    targets = np.repeat(base[:, -1:], horizon, axis=1)
    return {
        "coords": coords.tolist(),
        "series": series.tolist(),
        "targets": targets.tolist(),
        "pred_horizon": horizon,
    }


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_realtime_spatiotemporal_train_api(client):
    payload = _payload()
    resp = client.post(
        "/api/realtime/spatiotemporal/train",
        json={
            "model_type": "st_transformer",
            "coords": payload["coords"],
            "series": payload["series"],
            "targets": payload["targets"],
            "epochs": 6,
            "pred_horizon": payload["pred_horizon"],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["model_type"] == "st_transformer"
    assert data["training"]["epochs_ran"] >= 1


def test_realtime_spatiotemporal_predict_api(client):
    payload = _payload()
    resp = client.post(
        "/api/realtime/spatiotemporal/predict",
        json={
            "model_type": "st_transformer",
            "coords": payload["coords"],
            "series": payload["series"],
            "pred_horizon": payload["pred_horizon"],
            "fusion_strategy": "gating",
            "uncertainty_method": "mc_dropout",
            "enable_memory_optimization": True,
            "enable_inference_acceleration": True,
            "enable_long_sequence_optimization": False,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["prediction"]) == len(payload["coords"])
    assert len(data["variance"]) == len(payload["coords"])
    assert data["uncertainty_method"].startswith("mc_dropout")
    assert data["optimization"]["memory"]["enabled"] is True
