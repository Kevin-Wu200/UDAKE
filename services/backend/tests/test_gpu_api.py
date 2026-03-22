"""GPU API集成测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api import GPU加速接口 as gpu_api
from app.services.gpu_service import GPUService


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    gpu_api.gpu_service = GPUService(force_cpu=True)
    app.include_router(gpu_api.router, prefix="/api")
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/api/gpu/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["backend"] == "cpu"


def test_config_update(client: TestClient) -> None:
    resp = client.put(
        "/api/gpu/config",
        json={
            "enable_gpu": False,
            "auto_switch": False,
            "min_size_for_gpu": 8,
        },
    )
    assert resp.status_code == 200
    cfg = resp.json()["config"]
    assert cfg["enable_gpu"] is False
    assert cfg["auto_switch"] is False
    assert cfg["min_size_for_gpu"] == 8


def test_matrix_multiply_and_task(client: TestClient) -> None:
    multiply_resp = client.post(
        "/api/gpu/compute/matrix/multiply",
        json={
            "matrix_a": [[1, 2], [3, 4]],
            "matrix_b": [[1], [2]],
            "prefer_gpu": True,
        },
    )
    assert multiply_resp.status_code == 200
    body = multiply_resp.json()
    assert body["result"]["result"] == [[5.0], [11.0]]

    task_resp = client.get(f"/api/gpu/tasks/{body['task_id']}")
    assert task_resp.status_code == 200
    assert task_resp.json()["status"] == "completed"


def test_vector_norm_and_metrics(client: TestClient) -> None:
    norm_resp = client.post(
        "/api/gpu/compute/vector/norm",
        json={"vector": [6, 8], "prefer_gpu": True},
    )
    assert norm_resp.status_code == 200
    assert norm_resp.json()["result"]["result"] == pytest.approx(10.0)

    metrics_resp = client.get("/api/gpu/metrics")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert "performance" in metrics


def test_kriging_semivariogram(client: TestClient) -> None:
    resp = client.post(
        "/api/gpu/kriging/semivariogram",
        json={
            "points": [[0, 0], [1, 0], [0, 1], [1, 1]],
            "values": [1.0, 2.0, 2.0, 3.0],
            "bins": 5,
            "prefer_gpu": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["result"]["lags"]) == 5
    assert len(body["result"]["pair_counts"]) == 5
