from __future__ import annotations

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backend.app.dl_services.api import router
from services.backend.app.dl_services.service import DeepLearningService


def _spatial_samples() -> list[list[float]]:
    return [
        [0.10, 0.10, 1.20],
        [0.20, 0.15, 1.35],
        [0.35, 0.40, 1.10],
        [0.55, 0.60, 0.75],
        [0.75, 0.20, 1.60],
        [0.80, 0.75, 0.50],
    ]


def _uncertainty_map(size: int = 12) -> list[list[float]]:
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    arr = np.clip(0.45 + 0.25 * np.sin(xx * 3.0) + 0.2 * np.cos(yy * 4.0), 0.01, 1.0)
    return arr.tolist()


def test_service_core() -> None:
    service = DeepLearningService()
    health = service.health()
    assert health["status"] == "healthy"
    assert "dummy_regressor" in health["registered_models"]
    assert "gnn_kriging" in health["registered_models"]

    train = service.train_demo_model([[0.1, 1.0], [0.2, 0.9]])
    assert train["training"]["epochs_ran"] >= 1

    pred = service.predict([[1.0, 2.0], [3.0, 4.0]], bias=0.5)
    assert pred["predictions"] == [0.5, 0.5]


def test_service_spatial_train_and_predict() -> None:
    service = DeepLearningService()
    samples = _spatial_samples()

    train = service.train_spatial_model(model_type="gnn", samples=samples, epochs=6)
    assert train["model_type"] == "gnn"
    assert train["training"]["epochs_ran"] >= 1

    pred = service.predict_spatial(
        model_type="gnn",
        samples=samples,
        queries=[[0.15, 0.12], [0.6, 0.5]],
        blend_ratio=0.6,
    )
    assert pred["model_type"] == "gnn"
    assert len(pred["prediction"]) == 2
    assert len(pred["variance"]) == 2


def test_api_routes() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    health_resp = client.get("/api/dl/health")
    assert health_resp.status_code == 200

    predict_resp = client.post(
        "/api/dl/predict",
        json={"samples": [[1.0, 2.0], [2.0, 2.0]], "bias": 1.2},
    )
    assert predict_resp.status_code == 200
    assert predict_resp.json()["predictions"] == [1.2, 1.2]


def test_api_spatial_routes() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    samples = _spatial_samples()

    train_resp = client.post(
        "/api/dl/spatial/train",
        json={"model_type": "residual", "samples": samples, "epochs": 5},
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["model_type"] == "residual"

    pred_resp = client.post(
        "/api/dl/spatial/predict",
        json={
            "model_type": "attention",
            "samples": samples,
            "queries": [[0.1, 0.1], [0.5, 0.5], [0.8, 0.8]],
            "blend_ratio": 0.7,
        },
    )
    assert pred_resp.status_code == 200
    payload = pred_resp.json()
    assert len(payload["prediction"]) == 3
    assert len(payload["variance"]) == 3


def test_service_sampling_rl_train_and_recommend() -> None:
    service = DeepLearningService()
    uncertainty = _uncertainty_map(size=10)

    train = service.train_sampling_rl(
        model_name="ppo",
        uncertainty_map=uncertainty,
        existing_points=[[0.1, 0.1], [0.8, 0.7]],
        episodes=8,
        budget=12,
    )
    assert train["model_name"] == "ppo"
    assert train["training"]["summary"]["episodes"] >= 1

    rec = service.recommend_sampling_rl(
        model_name="ppo",
        uncertainty_map=uncertainty,
        existing_points=[[0.1, 0.1], [0.8, 0.7]],
        n_recommendations=6,
        fusion_strategy="hybrid",
        realtime=True,
    )
    assert rec["model_name"] == "ppo"
    assert len(rec["recommendation"]["recommendations"]) >= 1
    assert "optimization" in rec


def test_api_sampling_rl_routes() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)

    uncertainty = _uncertainty_map(size=10)

    train_resp = client.post(
        "/api/dl/sampling-rl/train",
        json={
            "model_name": "dqn",
            "uncertainty_map": uncertainty,
            "existing_points": [[0.2, 0.2], [0.7, 0.6]],
            "episodes": 8,
            "budget": 12,
        },
    )
    assert train_resp.status_code == 200
    assert train_resp.json()["model_name"] == "dqn"

    rec_resp = client.post(
        "/api/dl/sampling-rl/recommend",
        json={
            "model_name": "dqn",
            "uncertainty_map": uncertainty,
            "existing_points": [[0.2, 0.2], [0.7, 0.6]],
            "n_recommendations": 5,
            "fusion_strategy": "hybrid",
            "realtime": True,
        },
    )
    assert rec_resp.status_code == 200
    payload = rec_resp.json()
    assert payload["model_name"] == "dqn"
    assert len(payload["recommendation"]["recommendations"]) >= 1
