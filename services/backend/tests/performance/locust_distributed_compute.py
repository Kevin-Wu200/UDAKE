"""分布式计算 API 压力测试脚本。"""

from __future__ import annotations

import random
import time

from locust import HttpUser, between, task


class DistributedComputeUser(HttpUser):
    """模拟分布式计算 API 的典型请求流量。"""

    wait_time = between(1, 3)

    @task(3)
    def get_overview(self):
        self.client.get("/api/distributed/overview", name="GET /api/distributed/overview")

    @task(2)
    def submit_and_poll_task(self):
        values = [random.randint(1, 1000) for _ in range(1000)]
        response = self.client.post(
            "/api/distributed/tasks",
            json={
                "task_type": "map_reduce_sum",
                "payload": {"values": values, "chunk_size": 64},
                "priority": random.randint(0, 4),
                "max_retries": 1,
                "retry_delay_seconds": 0,
            },
            name="POST /api/distributed/tasks",
        )

        if response.status_code != 200:
            return

        task_id = response.json().get("task_id")
        if not task_id:
            return

        for _ in range(6):
            status_resp = self.client.get(
                f"/api/distributed/tasks/{task_id}",
                name="GET /api/distributed/tasks/:task_id",
            )
            if status_resp.status_code != 200:
                return
            status = status_resp.json().get("status")
            if status in {"completed", "failed", "cancelled"}:
                return
            time.sleep(0.2)
