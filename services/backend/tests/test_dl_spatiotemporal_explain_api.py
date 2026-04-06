"""深度学习时空解释 API 测试。"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dl_services import api as dl_api


def _payload() -> dict:
    return {
        "model_type": "st_transformer",
        "coords": [[0.0, 0.0], [1.0, 1.0]],
        "series": [
            [[0.1], [0.2], [0.3], [0.4], [0.5], [0.6]],
            [[0.2], [0.3], [0.4], [0.5], [0.6], [0.7]],
        ],
        "pred_horizon": 2,
        "method": "hybrid",
        "top_k": 1,
        "include_prediction": True,
        "batch_size": 32,
        "max_retries": 1,
    }


def _wait_completed(client: TestClient, task_id: str, headers: dict[str, str], timeout: float = 3.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/dl/spatiotemporal/explain/{task_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["status"] in {"completed", "failed"}:
            return body
        time.sleep(0.05)
    raise TimeoutError(f"任务在 {timeout}s 内未完成: {task_id}")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    app.include_router(dl_api.router, prefix="/api")

    def _fake_explain(payload: dict) -> dict:
        return {
            "model_type": payload["model_type"],
            "summary": {"method": payload["method"], "top_features": [{"feature_index": 0, "importance": 0.9}]},
            "prediction": [[0.11, 0.12], [0.21, 0.22]],
            "variance": [[0.01, 0.01], [0.02, 0.02]],
        }

    monkeypatch.setattr(dl_api.explain_task_service, "_execute_explanation", _fake_explain)
    monkeypatch.setattr(dl_api.settings, "EXPLAIN_API_TOKENS", [])
    monkeypatch.setattr(dl_api.settings, "EXPLAIN_REQUIRE_AUTH", False)
    monkeypatch.setattr(dl_api.settings, "EXPLAIN_ALLOWED_CREATORS", [])
    dl_api.explain_task_service.reset_for_testing()
    with TestClient(app) as test_client:
        yield test_client
    dl_api.explain_task_service.reset_for_testing()


def test_create_and_query_explain_task(client: TestClient) -> None:
    headers = {"x-user-id": "alice"}
    created = client.post("/api/dl/spatiotemporal/explain", json=_payload(), headers=headers)
    assert created.status_code == 200, created.text
    task_id = created.json()["task_id"]
    assert created.json()["status"] == "queued"

    final = _wait_completed(client, task_id, headers=headers)
    assert final["status"] == "completed"
    assert final["result"]["summary"]["method"] == "hybrid"
    assert final["result"]["prediction"][0][0] == pytest.approx(0.11)


def test_access_control_on_explain_task(client: TestClient) -> None:
    owner_headers = {"x-user-id": "owner"}
    created = client.post("/api/dl/spatiotemporal/explain", json=_payload(), headers=owner_headers)
    assert created.status_code == 200, created.text
    task_id = created.json()["task_id"]
    _ = _wait_completed(client, task_id, headers=owner_headers)

    forbidden = client.get(f"/api/dl/spatiotemporal/explain/{task_id}", headers={"x-user-id": "other"})
    assert forbidden.status_code == 403

    allowed_admin = client.get(
        f"/api/dl/spatiotemporal/explain/{task_id}",
        headers={"x-user-id": "other", "x-explain-admin": "true"},
    )
    assert allowed_admin.status_code == 200


def test_delete_explain_task(client: TestClient) -> None:
    headers = {"x-user-id": "alice"}
    created = client.post("/api/dl/spatiotemporal/explain", json=_payload(), headers=headers)
    assert created.status_code == 200, created.text
    task_id = created.json()["task_id"]

    deleted = client.delete(f"/api/dl/spatiotemporal/explain/{task_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/api/dl/spatiotemporal/explain/{task_id}", headers=headers)
    assert missing.status_code == 404


def test_cancel_explain_task(client: TestClient) -> None:
    headers = {"x-user-id": "alice"}
    created = client.post("/api/dl/spatiotemporal/explain", json=_payload(), headers=headers)
    assert created.status_code == 200, created.text
    task_id = created.json()["task_id"]

    cancelled = client.post(f"/api/dl/spatiotemporal/explain/{task_id}/cancel", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["cancelled"] is True

    task = client.get(f"/api/dl/spatiotemporal/explain/{task_id}", headers=headers)
    assert task.status_code == 200, task.text
    assert task.json()["status"] in {"cancelled", "completed"}


def test_invalid_explain_request_returns_422(client: TestClient) -> None:
    payload = _payload()
    payload["top_k"] = 0
    response = client.post("/api/dl/spatiotemporal/explain", json=payload, headers={"x-user-id": "alice"})
    assert response.status_code == 422


def test_explain_monitor_and_verify_api(client: TestClient) -> None:
    headers = {"x-user-id": "alice"}
    _ = client.post("/api/dl/spatiotemporal/explain", json=_payload(), headers=headers)

    monitor = client.get("/api/dl/spatiotemporal/explain/monitor", headers=headers)
    assert monitor.status_code == 200, monitor.text
    monitor_body = monitor.json()
    assert "queue_size" in monitor_body
    assert "success_rate" in monitor_body
    assert "error_rate" in monitor_body

    verify = client.get("/api/dl/spatiotemporal/explain/verify", headers=headers)
    assert verify.status_code == 200, verify.text
    verify_body = verify.json()
    assert "celery_enabled" in verify_body
    assert "redis_backend_ok" in verify_body


def test_explain_cleanup_admin_only(client: TestClient) -> None:
    headers = {"x-user-id": "alice"}
    forbidden = client.post("/api/dl/spatiotemporal/explain/cleanup", headers=headers)
    assert forbidden.status_code == 403

    allowed = client.post(
        "/api/dl/spatiotemporal/explain/cleanup",
        headers={"x-user-id": "alice", "x-explain-admin": "true"},
    )
    assert allowed.status_code == 200, allowed.text
    assert "deleted_tasks" in allowed.json()
