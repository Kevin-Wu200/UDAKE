"""GPU计算性能监控。"""

from __future__ import annotations

from collections import defaultdict, deque
from statistics import mean
from typing import Deque, Dict, List

from .data_structures import ComputeBackend, PerformanceSnapshot


class PerformanceMonitor:
    """维护GPU/CPU计算性能指标。"""

    def __init__(self, max_snapshots: int = 1000):
        self._snapshots: Deque[PerformanceSnapshot] = deque(maxlen=max_snapshots)

    def record(self, operation: str, backend: ComputeBackend, elapsed_ms: float, input_size: int) -> None:
        self._snapshots.append(
            PerformanceSnapshot(
                operation=operation,
                backend=backend,
                elapsed_ms=max(0.0, float(elapsed_ms)),
                input_size=max(0, int(input_size)),
            )
        )

    def clear(self) -> None:
        self._snapshots.clear()

    def get_recent(self, limit: int = 50) -> List[dict]:
        if limit <= 0:
            return []
        snapshots = list(self._snapshots)[-limit:]
        return [item.to_dict() for item in snapshots]

    def get_operation_stats(self) -> Dict[str, dict]:
        grouped: Dict[str, List[PerformanceSnapshot]] = defaultdict(list)
        for snapshot in self._snapshots:
            key = f"{snapshot.operation}:{snapshot.backend.value}"
            grouped[key].append(snapshot)

        result: Dict[str, dict] = {}
        for key, values in grouped.items():
            elapsed_list = [v.elapsed_ms for v in values]
            result[key] = {
                "count": len(values),
                "avg_elapsed_ms": round(mean(elapsed_list), 4),
                "min_elapsed_ms": round(min(elapsed_list), 4),
                "max_elapsed_ms": round(max(elapsed_list), 4),
            }
        return result

    def get_overall_stats(self) -> dict:
        if not self._snapshots:
            return {
                "total_runs": 0,
                "gpu_runs": 0,
                "cpu_runs": 0,
                "avg_gpu_speedup": 1.0,
            }

        cpu_costs = defaultdict(list)
        gpu_costs = defaultdict(list)
        for s in self._snapshots:
            bucket_key = (s.operation, s.input_size)
            if s.backend == ComputeBackend.CPU:
                cpu_costs[bucket_key].append(s.elapsed_ms)
            else:
                gpu_costs[bucket_key].append(s.elapsed_ms)

        speedups: List[float] = []
        for key, gpu_values in gpu_costs.items():
            if key not in cpu_costs:
                continue
            cpu_avg = mean(cpu_costs[key])
            gpu_avg = mean(gpu_values)
            if gpu_avg > 0:
                speedups.append(cpu_avg / gpu_avg)

        total_runs = len(self._snapshots)
        gpu_runs = sum(1 for s in self._snapshots if s.backend == ComputeBackend.GPU)
        cpu_runs = total_runs - gpu_runs

        return {
            "total_runs": total_runs,
            "gpu_runs": gpu_runs,
            "cpu_runs": cpu_runs,
            "avg_gpu_speedup": round(mean(speedups), 4) if speedups else 1.0,
        }
