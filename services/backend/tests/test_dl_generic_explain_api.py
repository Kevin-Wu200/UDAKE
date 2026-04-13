"""通用 explain 端点扩展测试。"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dl_services import api as dl_api


def _wait_task(client: TestClient, path: str, headers: dict[str, str], timeout: float = 3.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body.get("status") in {"completed", "failed", "cancelled"}:
            return body
        time.sleep(0.05)
    raise TimeoutError(f"任务在 {timeout}s 内未完成: {path}")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(dl_api.router, prefix="/api")
    monkeypatch.setattr(dl_api.settings, "EXPLAIN_API_TOKENS", [])
    monkeypatch.setattr(dl_api.settings, "EXPLAIN_REQUIRE_AUTH", False)
    monkeypatch.setattr(dl_api.settings, "EXPLAIN_ALLOWED_CREATORS", [])
    dl_api.explain_task_service.reset_for_testing()
    with TestClient(app) as test_client:
        yield test_client
    dl_api.explain_task_service.reset_for_testing()


def test_sync_new_explain_endpoints(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dl_api.service, "explain_interpolation", lambda **kwargs: {"scope": "interpolation", "echo": kwargs})
    monkeypatch.setattr(dl_api.service, "explain_uncertainty", lambda **kwargs: {"scope": "uncertainty", "echo": kwargs})
    monkeypatch.setattr(dl_api.service, "explain_sampling_rl", lambda **kwargs: {"scope": "rl", "echo": kwargs})

    interpolation_resp = client.post(
        "/api/dl/interpolation/explain",
        json={
            "model_type": "gnn",
            "samples": [[0.0, 0.0, 1.0], [1.0, 0.0, 1.2], [0.0, 1.0, 0.8], [1.0, 1.0, 1.1], [0.5, 0.5, 1.0]],
            "queries": [[0.2, 0.3]],
            "method": "hybrid",
            "top_k": 3,
        },
    )
    assert interpolation_resp.status_code == 200, interpolation_resp.text
    assert interpolation_resp.json()["scope"] == "interpolation"

    uncertainty_resp = client.post(
        "/api/dl/uncertainty/explain",
        json={
            "model_name": "bnn",
            "features": [[0.1, 0.2], [0.2, 0.1], [0.3, 0.4], [0.4, 0.3]],
            "method": "hybrid",
            "top_k": 2,
        },
    )
    assert uncertainty_resp.status_code == 200, uncertainty_resp.text
    assert uncertainty_resp.json()["scope"] == "uncertainty"

    rl_resp = client.post(
        "/api/dl/rl/explain",
        json={
            "model_name": "ppo",
            "uncertainty_map": [[0.2, 0.3, 0.4, 0.3], [0.3, 0.5, 0.6, 0.4], [0.2, 0.4, 0.7, 0.5], [0.1, 0.2, 0.3, 0.4]],
            "existing_points": [[0.1, 0.1], [0.8, 0.8]],
            "method": "hybrid",
            "top_k": 3,
        },
    )
    assert rl_resp.status_code == 200, rl_resp.text
    assert rl_resp.json()["scope"] == "rl"


def test_anomaly_and_fusion_async_task_flow(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dl_api.explain_task_service, "_execute_explanation", lambda payload: {"scope": payload.get("scope")})
    headers = {"x-user-id": "alice"}

    anomaly_created = client.post(
        "/api/dl/anomaly/explain",
        headers=headers,
        json={
            "model_name": "vae",
            "coords": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.5, 0.5]],
            "values": [1.0, 1.1, 0.9, 1.2, 1.0],
            "async_mode": True,
        },
    )
    assert anomaly_created.status_code == 200, anomaly_created.text
    anomaly_task_id = anomaly_created.json()["task_id"]
    anomaly_final = _wait_task(client, f"/api/dl/anomaly/explain/{anomaly_task_id}", headers=headers)
    assert anomaly_final["status"] == "completed"
    assert anomaly_final["result"]["scope"] == "anomaly"

    fusion_created = client.post(
        "/api/dl/fusion/explain",
        headers=headers,
        json={
            "models": [{"model_id": "m1", "predictions": [1.0, 1.1, 1.2]}],
            "async_mode": True,
        },
    )
    assert fusion_created.status_code == 200, fusion_created.text
    fusion_task_id = fusion_created.json()["task_id"]
    fusion_final = _wait_task(client, f"/api/dl/fusion/explain/{fusion_task_id}", headers=headers)
    assert fusion_final["status"] == "completed"
    assert fusion_final["result"]["scope"] == "fusion"
