"""分布式计算性能基准脚本。"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from app.schemas.分布式计算模型 import (  # noqa: E402
    DistributedFramework,
    DistributedTaskStatus,
    DistributedTaskSubmitRequest,
)
from app.services.分布式计算服务 import DistributedComputeService  # noqa: E402


@dataclass
class BenchmarkSummary:
    total_tasks: int
    durations: list[float]
    queue_wait: list[float]
    cache_hit_time: float
    cache_miss_time: float
    success_rate: float
    acceleration_ratio: float

    def to_dict(self) -> dict:
        return {
            "total_tasks": self.total_tasks,
            "avg_duration_seconds": round(statistics.mean(self.durations), 4) if self.durations else 0.0,
            "p95_duration_seconds": round(_percentile(self.durations, 95), 4) if self.durations else 0.0,
            "avg_queue_wait_seconds": round(statistics.mean(self.queue_wait), 4) if self.queue_wait else 0.0,
            "cache_miss_seconds": round(self.cache_miss_time, 4),
            "cache_hit_seconds": round(self.cache_hit_time, 4),
            "cache_speedup": round(self.cache_miss_time / max(self.cache_hit_time, 1e-6), 4),
            "task_success_rate": round(self.success_rate, 4),
            "estimated_acceleration_ratio": round(self.acceleration_ratio, 4),
        }


def _percentile(values: list[float], p: int) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, round((p / 100) * (len(ordered) - 1)))
    return ordered[index]


def _wait_task(service: DistributedComputeService, task_id: str, timeout: float = 20.0):
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


def run_benchmark(task_count: int, values_per_task: int, chunk_size: int) -> BenchmarkSummary:
    service = DistributedComputeService(
        preferred_framework=DistributedFramework.RAY,
        heartbeat_timeout_seconds=2,
        max_workers=8,
    )
    service.start()

    durations: list[float] = []
    queue_wait: list[float] = []

    try:
        for idx in range(task_count):
            payload = {
                "values": list(range(1, values_per_task + 1)),
                "chunk_size": chunk_size,
                "estimated_sequential_seconds": max(0.05, values_per_task * 0.0002),
            }
            task_id = service.submit_task(
                DistributedTaskSubmitRequest(
                    task_type="map_reduce_sum",
                    payload=payload,
                    priority=idx % 3,
                    max_retries=1,
                    retry_delay_seconds=0,
                )
            )

            task = _wait_task(service, task_id)
            if task.started_at and task.created_at and task.completed_at:
                queue_wait.append((task.started_at - task.created_at).total_seconds())
                durations.append((task.completed_at - task.started_at).total_seconds())

        # 测试缓存命中耗时
        cache_payload = {
            "values": list(range(1, values_per_task + 1)),
            "chunk_size": chunk_size,
            "estimated_sequential_seconds": max(0.05, values_per_task * 0.0002),
        }
        start = time.perf_counter()
        task_id = service.submit_task(
            DistributedTaskSubmitRequest(
                task_type="map_reduce_sum",
                payload=cache_payload,
                priority=1,
                max_retries=0,
                retry_delay_seconds=0,
            )
        )
        _wait_task(service, task_id)
        cache_miss_time = time.perf_counter() - start

        start = time.perf_counter()
        cache_hit_task_id = service.submit_task(
            DistributedTaskSubmitRequest(
                task_type="map_reduce_sum",
                payload=cache_payload,
                priority=1,
                max_retries=0,
                retry_delay_seconds=0,
            )
        )
        cache_hit_task = _wait_task(service, cache_hit_task_id)
        cache_hit_time = time.perf_counter() - start
        if not cache_hit_task.result or not cache_hit_task.result.get("from_cache"):
            raise RuntimeError("缓存命中验证失败：重复请求未命中缓存")

        metrics = service.get_metrics()
        return BenchmarkSummary(
            total_tasks=task_count + 2,
            durations=durations,
            queue_wait=queue_wait,
            cache_hit_time=cache_hit_time,
            cache_miss_time=cache_miss_time,
            success_rate=metrics.task_success_rate,
            acceleration_ratio=metrics.estimated_acceleration_ratio,
        )
    finally:
        service.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="分布式计算性能基准")
    parser.add_argument("--tasks", type=int, default=30, help="基准任务数量")
    parser.add_argument("--values-per-task", type=int, default=4000, help="每个任务的数据量")
    parser.add_argument("--chunk-size", type=int, default=128, help="MapReduce 分片大小")
    parser.add_argument("--json-out", type=str, default="", help="结果输出 JSON 路径")
    args = parser.parse_args()

    summary = run_benchmark(args.tasks, args.values_per_task, args.chunk_size)
    result = summary.to_dict()

    print("分布式计算性能基准结果")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 低优先级任务目标中的关键验收指标。
    if result["task_success_rate"] < 0.99:
        print("性能门禁失败: 任务成功率低于 99%")
        return 1
    if result["estimated_acceleration_ratio"] < 0.7:
        print("性能门禁失败: 加速比低于 0.7")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
