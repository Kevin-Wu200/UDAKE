"""分布式计算 API 集成测试。"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api import 分布式计算接口 as distributed_api  # noqa: E402
from app.schemas.分布式计算模型 import (  # noqa: E402
    DistributedFramework,
    DistributedTaskStatus,
)
from app.services.分布式计算服务 import DistributedComputeService  # noqa: E402


def _wait_task_status(
    client: TestClient,
    task_id: str,
    expected: set[str],
    timeout: float = 8.0,
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/distributed/tasks/{task_id}")
        assert response.status_code == 200
        task = response.json()
        if task["status"] in expected:
            return task
        time.sleep(0.05)
    raise TimeoutError(f"任务超时未结束: {task_id}")


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    service = DistributedComputeService(
        preferred_framework=DistributedFramework.RAY,
        heartbeat_timeout_seconds=1,
        max_workers=4,
    )

    original_service = distributed_api.distributed_compute_service
    distributed_api.distributed_compute_service = service
    app.include_router(distributed_api.router, prefix="/api")

    with TestClient(app) as api_client:
        yield api_client

    service.stop()
    distributed_api.distributed_compute_service = original_service


def test_submit_list_and_metrics(client: TestClient) -> None:
    submit = client.post(
        "/api/distributed/tasks",
        json={
            "task_type": "map_reduce_sum",
            "payload": {"values": list(range(1, 51)), "chunk_size": 8},
            "priority": 1,
            "max_retries": 1,
            "retry_delay_seconds": 0,
        },
    )
    assert submit.status_code == 200
    task_id = submit.json()["task_id"]

    task = _wait_task_status(
        client,
        task_id,
        {
            DistributedTaskStatus.COMPLETED.value,
            DistributedTaskStatus.FAILED.value,
            DistributedTaskStatus.CANCELLED.value,
        },
    )
    assert task["status"] == DistributedTaskStatus.COMPLETED.value
    assert task["result"]["sum"] == pytest.approx(sum(range(1, 51)))

    listed = client.get(
        "/api/distributed/tasks",
        params={"status": DistributedTaskStatus.COMPLETED.value, "limit": 20},
    )
    assert listed.status_code == 200
    listed_ids = {item["task_id"] for item in listed.json()["tasks"]}
    assert task_id in listed_ids

    metrics = client.get("/api/distributed/metrics")
    assert metrics.status_code == 200
    body = metrics.json()
    assert 0.0 <= body["task_success_rate"] <= 1.0
    assert body["estimated_acceleration_ratio"] > 0.0


def test_node_management_and_overview(client: TestClient) -> None:
    register = client.post(
        "/api/distributed/nodes/register",
        json={
            "node_id": "integration-worker",
            "cpu_capacity": 6,
            "memory_capacity_mb": 8192,
            "labels": {"zone": "api-test"},
        },
    )
    assert register.status_code == 200
    assert register.json()["node_id"] == "integration-worker"

    heartbeat = client.post(
        "/api/distributed/nodes/heartbeat",
        json={
            "node_id": "integration-worker",
            "cpu_used": 0.3,
            "memory_used": 0.4,
        },
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "online"

    nodes = client.get("/api/distributed/nodes")
    assert nodes.status_code == 200
    node_ids = {item["node_id"] for item in nodes.json()}
    assert "integration-worker" in node_ids

    overview = client.get("/api/distributed/overview")
    assert overview.status_code == 200
    assert overview.json()["total_nodes"] >= 2


def test_checkpoint_recover_backup_restore_and_events(client: TestClient) -> None:
    submit = client.post(
        "/api/distributed/tasks",
        json={
            "task_type": "failing_demo",
            "payload": {"fail_until_attempt": 1, "estimated_sequential_seconds": 0.2},
            "priority": 1,
            "max_retries": 0,
            "retry_delay_seconds": 0,
        },
    )
    assert submit.status_code == 200
    task_id = submit.json()["task_id"]

    failed = _wait_task_status(client, task_id, {DistributedTaskStatus.FAILED.value})
    assert failed["status"] == DistributedTaskStatus.FAILED.value

    checkpoint = client.post(f"/api/distributed/tasks/{task_id}/checkpoint")
    assert checkpoint.status_code == 200
    checkpoint_id = checkpoint.json()["checkpoint_id"]

    recovered = client.post(
        f"/api/distributed/tasks/{task_id}/recover",
        params={"checkpoint_id": checkpoint_id},
    )
    assert recovered.status_code == 200
    assert recovered.json()["recovered"] is True

    completed = _wait_task_status(client, task_id, {DistributedTaskStatus.COMPLETED.value})
    assert completed["attempt"] >= 2

    backup = client.post("/api/distributed/backup")
    assert backup.status_code == 200
    assert backup.json()["path"]

    restore = client.post("/api/distributed/restore")
    assert restore.status_code == 200

    events = client.get("/api/distributed/events", params={"limit": 200})
    assert events.status_code == 200
    event_names = {item["event"] for item in events.json()["events"]}
    assert "task_recovered" in event_names


def test_cancel_invalid_task_returns_400(client: TestClient) -> None:
    response = client.delete("/api/distributed/tasks/not-exists")
    assert response.status_code == 400
