"""分布式计算服务单元测试。"""

from __future__ import annotations

import sys
import time
from datetime import timedelta
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.schemas.分布式计算模型 import (  # noqa: E402
    DistributedFramework,
    DistributedTaskStatus,
    DistributedTaskSubmitRequest,
    NodeRegisterRequest,
    NodeStatus,
)
from app.services.分布式计算服务 import DistributedComputeService  # noqa: E402


def _wait_task_status(service: DistributedComputeService, task_id: str, timeout: float = 8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = service.get_task(task_id)
        if task and task.status in {
            DistributedTaskStatus.COMPLETED,
            DistributedTaskStatus.FAILED,
            DistributedTaskStatus.CANCELLED,
        }:
            return task
        time.sleep(0.05)
    raise TimeoutError(f"任务超时未结束: {task_id}")


@pytest.fixture
def service() -> DistributedComputeService:
    svc = DistributedComputeService(
        preferred_framework=DistributedFramework.RAY,
        heartbeat_timeout_seconds=1,
        max_workers=4,
    )
    svc.start()
    yield svc
    svc.stop()


def test_framework_selection_with_fallback(service: DistributedComputeService):
    assert service.active_framework in {
        DistributedFramework.RAY,
        DistributedFramework.DASK,
        DistributedFramework.LOCAL,
    }


def test_submit_and_complete_map_reduce_task(service: DistributedComputeService):
    task_id = service.submit_task(
        DistributedTaskSubmitRequest(
            task_type="map_reduce_sum",
            payload={"values": list(range(1, 101)), "chunk_size": 16},
            priority=1,
            max_retries=1,
            retry_delay_seconds=0,
        )
    )

    task = _wait_task_status(service, task_id)
    assert task.status == DistributedTaskStatus.COMPLETED
    assert task.result is not None
    assert task.result["sum"] == pytest.approx(sum(range(1, 101)))


def test_retry_checkpoint_and_recover(service: DistributedComputeService):
    task_id = service.submit_task(
        DistributedTaskSubmitRequest(
            task_type="failing_demo",
            payload={"fail_until_attempt": 1, "estimated_sequential_seconds": 0.2},
            priority=2,
            max_retries=0,
            retry_delay_seconds=0,
        )
    )

    first = _wait_task_status(service, task_id)
    assert first.status == DistributedTaskStatus.FAILED

    checkpoint = service.create_checkpoint(task_id)
    assert checkpoint.task_id == task_id

    recover = service.recover_task(task_id, checkpoint.checkpoint_id)
    assert recover.recovered is True

    second = _wait_task_status(service, task_id)
    assert second.status == DistributedTaskStatus.COMPLETED
    assert second.attempt >= 2


def test_heartbeat_failure_detection_and_metrics(service: DistributedComputeService):
    service.register_node(
        NodeRegisterRequest(
            node_id="worker-a",
            cpu_capacity=4,
            memory_capacity_mb=8192,
            labels={"zone": "test"},
        )
    )

    # 手动将最后心跳设置为超时，验证心跳线程会标记离线。
    with service._lock:  # pylint: disable=protected-access
        service._nodes["worker-a"].last_heartbeat = service._nodes["worker-a"].last_heartbeat - timedelta(seconds=5)

    time.sleep(1.3)
    nodes = {node.node_id: node for node in service.list_nodes()}
    assert nodes["worker-a"].status == NodeStatus.OFFLINE

    task_id = service.submit_task(
        DistributedTaskSubmitRequest(
            task_type="map_reduce_sum",
            payload={"values": list(range(500)), "chunk_size": 32},
            priority=3,
            max_retries=1,
            retry_delay_seconds=0,
        )
    )
    task = _wait_task_status(service, task_id)
    assert task.status == DistributedTaskStatus.COMPLETED

    metrics = service.get_metrics()
    assert 0.0 <= metrics.task_success_rate <= 1.0
    assert metrics.queue_depth >= 0
    assert metrics.estimated_acceleration_ratio > 0.0


def test_backup_and_restore_cluster_state(service: DistributedComputeService):
    task_id = service.submit_task(
        DistributedTaskSubmitRequest(
            task_type="map_reduce_sum",
            payload={"values": [1, 2, 3, 4]},
            priority=1,
            max_retries=0,
            retry_delay_seconds=0,
        )
    )
    done = _wait_task_status(service, task_id)
    assert done.status == DistributedTaskStatus.COMPLETED

    backup_path = service.backup_cluster_state()
    assert Path(backup_path).exists()

    with service._lock:  # pylint: disable=protected-access
        service._tasks.clear()
        service._nodes.clear()

    restored = service.restore_cluster_state()
    assert restored is True
    overview = service.get_cluster_overview()
    assert overview.total_nodes >= 1
    assert overview.completed_tasks >= 1
