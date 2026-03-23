"""强化学习采样性能优化。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np


@dataclass
class BatchOptimizationResult:
    batch_size: int
    estimated_memory_mb: float
    throughput_score: float


class BatchOptimizer:
    def suggest(self, sample_count: int, feature_dim: int, memory_budget_mb: float = 128.0) -> BatchOptimizationResult:
        bytes_per_sample = max(1, int(feature_dim)) * 4 * 6  # 状态、动作、奖励等近似缓存
        max_samples = int((memory_budget_mb * 1024 * 1024) / max(bytes_per_sample, 1))
        batch_size = int(max(8, min(sample_count, max_samples, 512)))
        estimated = batch_size * bytes_per_sample / (1024 * 1024)
        throughput = float(batch_size / max(1.0, np.log(batch_size + 1.0)))
        return BatchOptimizationResult(batch_size=batch_size, estimated_memory_mb=float(estimated), throughput_score=throughput)


class MemoryOptimizer:
    def compress(self, array: np.ndarray, dtype: np.dtype = np.float32) -> np.ndarray:
        arr = np.asarray(array)
        return arr.astype(dtype, copy=False)

    def deduplicate_points(self, points: np.ndarray, decimals: int = 4) -> np.ndarray:
        arr = np.asarray(points, dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 2:
            return arr
        rounded = np.round(arr, decimals=decimals)
        unique, _ = np.unique(rounded, axis=0, return_index=True)
        return unique


class GPUAccelerator:
    """可选 GPU 加速，缺少 cupy 时自动回退 CPU。"""

    def __init__(self) -> None:
        try:
            import cupy as cp  # type: ignore

            self.cp = cp
            self.available = True
        except Exception:
            self.cp = None
            self.available = False

    def accelerate_matrix(self, matrix: np.ndarray) -> np.ndarray:
        arr = np.asarray(matrix, dtype=float)
        if not self.available or self.cp is None:
            return arr
        dev = self.cp.asarray(arr)
        return self.cp.asnumpy(dev)

    def info(self) -> dict[str, Any]:
        return {
            "gpu_available": bool(self.available),
            "backend": "cupy" if self.available else "numpy",
        }


class InferenceAccelerator:
    """推理加速：缓存最近状态到动作映射。"""

    def __init__(self, cache_size: int = 256) -> None:
        self.cache_size = int(max(8, cache_size))
        self.cache: dict[int, Any] = {}
        self.order: list[int] = []

    def _put(self, key: int, value: Any) -> None:
        if key in self.cache:
            self.order.remove(key)
        self.cache[key] = value
        self.order.append(key)
        if len(self.order) > self.cache_size:
            old = self.order.pop(0)
            self.cache.pop(old, None)

    def predict(self, state: np.ndarray, predictor: Callable[[np.ndarray], Any]) -> Any:
        arr = np.asarray(state, dtype=float)
        key = hash(arr.tobytes())
        if key in self.cache:
            return self.cache[key]
        value = predictor(arr)
        self._put(key, value)
        return value


class ParallelSampler:
    """并行采样：并发评估候选动作收益。"""

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = int(max(1, max_workers))

    def evaluate_candidates(
        self,
        candidates: list[Any],
        scorer: Callable[[Any], float],
    ) -> list[tuple[Any, float]]:
        if not candidates:
            return []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            scores = list(executor.map(scorer, candidates))
        return list(zip(candidates, [float(s) for s in scores]))

    def best_k(
        self,
        candidates: list[Any],
        scorer: Callable[[Any], float],
        k: int = 10,
    ) -> list[tuple[Any, float]]:
        pairs = self.evaluate_candidates(candidates, scorer)
        pairs.sort(key=lambda x: x[1], reverse=True)
        return pairs[: max(1, int(k))]
