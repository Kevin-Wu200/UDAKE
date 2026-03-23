from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.backend.app.dl_services.api import router
from services.backend.app.dl_services.service import DeepLearningService


def test_service_core() -> None:
    service = DeepLearningService()
    health = service.health()
    assert health["status"] == "healthy"
    assert "dummy_regressor" in health["registered_models"]

    train = service.train_demo_model([[0.1, 1.0], [0.2, 0.9]])
    assert train["training"]["epochs_ran"] >= 1

    pred = service.predict([[1.0, 2.0], [3.0, 4.0]], bias=0.5)
    assert pred["predictions"] == [0.5, 0.5]


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
