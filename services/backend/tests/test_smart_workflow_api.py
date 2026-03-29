"""智能工作流 API 测试。"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import 智能工作流接口 as workflow_api
from app.services.智能工作流服务 import SmartWorkflowService


def _basic_workflow_definition() -> dict:
    return {
        "name": "api-basic-workflow",
        "nodes": [
            {
                "node_id": "input",
                "kind": "input",
                "node_type": "input.constant",
                "params": {"value": [1, 2, 3, 4]},
            },
            {
                "node_id": "sample",
                "kind": "process",
                "node_type": "process.sample",
                "params": {"step": 2},
            },
            {
                "node_id": "sum",
                "kind": "process",
                "node_type": "process.transform",
                "params": {"operation": "sum", "source": "{{nodes.sample}}"},
            },
            {
                "node_id": "output",
                "kind": "output",
                "node_type": "output.collect",
                "params": {"fields": ["sample", "sum"]},
            },
        ],
        "edges": [
            {"source": "input", "target": "sample"},
            {"source": "sample", "target": "sum"},
            {"source": "sum", "target": "output"},
        ],
    }


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    service = SmartWorkflowService(auto_start_scheduler=False)
    workflow_api.smart_workflow_service = service
    app.include_router(workflow_api.router, prefix="/api")

    with TestClient(app) as test_client:
        yield test_client

    service.stop_scheduler()


def _wait_run_completed(client: TestClient, run_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/workflow/runs/{run_id}")
        assert resp.status_code == 200
        run = resp.json()
        if run["status"] in {"completed", "failed"}:
            return run
        time.sleep(0.05)
    raise TimeoutError(f"run timeout: {run_id}")


def test_workflow_health_and_template_library(client: TestClient) -> None:
    health = client.get("/api/workflow/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    templates = client.get("/api/workflow/templates")
    assert templates.status_code == 200
    assert templates.json()["count"] >= 20

    marketplace = client.get("/api/workflow/marketplace?limit=5")
    assert marketplace.status_code == 200
    assert 1 <= marketplace.json()["count"] <= 5


def test_create_validate_execute_and_logs(client: TestClient) -> None:
    definition = _basic_workflow_definition()

    validate_resp = client.post("/api/workflow/validate", json={"definition": definition})
    assert validate_resp.status_code == 200
    assert validate_resp.json()["valid"] is True

    create_resp = client.post("/api/workflow", json={"definition": definition})
    assert create_resp.status_code == 200
    workflow = create_resp.json()["workflow"]
    workflow_id = workflow["workflow_id"]

    execute_resp = client.post(
        f"/api/workflow/{workflow_id}/execute",
        json={"async": True, "input_variables": {"tenant": "test"}},
    )
    assert execute_resp.status_code == 200
    run_id = execute_resp.json()["run_id"]

    run = _wait_run_completed(client, run_id)
    assert run["status"] == "completed"
    assert run["node_outputs"]["sum"] == 4

    logs_resp = client.get(f"/api/workflow/runs/{run_id}/logs")
    assert logs_resp.status_code == 200
    assert logs_resp.json()["count"] >= 1

    list_runs = client.get(f"/api/workflow/{workflow_id}/runs")
    assert list_runs.status_code == 200
    assert list_runs.json()["count"] >= 1


def test_version_rollback_schedule_and_recommendation(client: TestClient) -> None:
    create_resp = client.post("/api/workflow", json={"definition": _basic_workflow_definition()})
    assert create_resp.status_code == 200
    workflow_id = create_resp.json()["workflow"]["workflow_id"]

    update_resp = client.put(
        f"/api/workflow/{workflow_id}",
        json={
            "updates": {"description": "new-version"},
            "note": "for-test",
        },
    )
    assert update_resp.status_code == 200

    versions_resp = client.get(f"/api/workflow/{workflow_id}/versions")
    assert versions_resp.status_code == 200
    versions = versions_resp.json()["versions"]
    assert len(versions) >= 2

    rollback_resp = client.post(f"/api/workflow/{workflow_id}/rollback/1")
    assert rollback_resp.status_code == 200

    recommend_resp = client.get("/api/workflow/templates/recommend?tags=采样,插值&limit=3")
    assert recommend_resp.status_code == 200
    assert 1 <= recommend_resp.json()["count"] <= 3

    schedule_resp = client.post(
        f"/api/workflow/{workflow_id}/schedules",
        json={"interval_seconds": 60, "trigger_payload": {"source": "schedule"}},
    )
    assert schedule_resp.status_code == 200
    schedule_id = schedule_resp.json()["schedule"]["schedule_id"]

    trigger_resp = client.post(f"/api/workflow/schedules/{schedule_id}/trigger")
    assert trigger_resp.status_code == 200
    run_id = trigger_resp.json()["run"]["run_id"]

    run = _wait_run_completed(client, run_id)
    assert run["status"] == "completed"

    perf_resp = client.get("/api/workflow/performance")
    assert perf_resp.status_code == 200
    assert perf_resp.json()["total_runs"] >= 1
