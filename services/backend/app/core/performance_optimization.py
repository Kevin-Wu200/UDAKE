"""通用框架性能优化组件（阶段一）。"""

from __future__ import annotations

from collections import OrderedDict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import threading
import time
from typing import Any, Callable, Optional

import numpy as np


def _stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class _CacheRecord:
    value: dict[str, Any]
    created_at: float


class ModelPerformanceCache:
    """模型级缓存：预测/解释分命名空间，支持预热、失效、容量控制与命中统计。"""

    _NAMESPACES = ("prediction", "explanation")

    def __init__(self, *, max_size: int = 256) -> None:
        self.max_size = max(1, int(max_size))
        self._lock = threading.Lock()
        self._store: dict[str, "OrderedDict[str, _CacheRecord]"] = {
            ns: OrderedDict() for ns in self._NAMESPACES
        }
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
            "invalidations": 0,
            "warmups": 0,
        }

    def build_cache_key(self, *, model_name: str, model_version: str, payload: dict[str, Any], namespace: str) -> str:
        ns = self._normalize_namespace(namespace)
        normalized = {
            "namespace": ns,
            "model": str(model_name),
            "version": str(model_version),
            "payload": payload,
        }
        digest = hashlib.sha256(_stable_json_dumps(normalized).encode("utf-8")).hexdigest()
        return f"{ns}:{model_name}:{model_version}:{digest}"

    def _normalize_namespace(self, namespace: str) -> str:
        ns = str(namespace).strip().lower()
        if ns not in self._NAMESPACES:
            raise ValueError(f"unsupported namespace: {namespace}")
        return ns

    def _set(self, namespace: str, key: str, value: dict[str, Any], *, warmup: bool = False) -> None:
        with self._lock:
            bucket = self._store[namespace]
            bucket[key] = _CacheRecord(value=json.loads(_stable_json_dumps(value)), created_at=time.time())
            bucket.move_to_end(key)
            self._metrics["sets"] += 1
            if warmup:
                self._metrics["warmups"] += 1
            while len(bucket) > self.max_size:
                bucket.popitem(last=False)
                self._metrics["evictions"] += 1

    def _get(self, namespace: str, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            bucket = self._store[namespace]
            cached = bucket.get(key)
            if cached is None:
                self._metrics["misses"] += 1
                return None
            bucket.move_to_end(key)
            self._metrics["hits"] += 1
            return json.loads(_stable_json_dumps(cached.value))

    def set_prediction(self, key: str, value: dict[str, Any]) -> None:
        self._set("prediction", key, value)

    def set_explanation(self, key: str, value: dict[str, Any]) -> None:
        self._set("explanation", key, value)

    def get_prediction(self, key: str) -> Optional[dict[str, Any]]:
        return self._get("prediction", key)

    def get_explanation(self, key: str) -> Optional[dict[str, Any]]:
        return self._get("explanation", key)

    def warmup(self, entries: list[dict[str, Any]]) -> dict[str, int]:
        ok = 0
        failed = 0
        for item in entries:
            try:
                ns = self._normalize_namespace(str(item.get("namespace", "")))
                key = str(item.get("key", ""))
                value = item.get("value")
                if not key or not isinstance(value, dict):
                    raise ValueError("invalid warmup item")
                self._set(ns, key, value, warmup=True)
                ok += 1
            except Exception:
                failed += 1
        return {"succeeded": ok, "failed": failed}

    def invalidate(self, *, namespace: str | None = None, key_prefix: str | None = None) -> dict[str, int]:
        with self._lock:
            targets = [self._normalize_namespace(namespace)] if namespace else list(self._NAMESPACES)
            prefix = str(key_prefix or "")
            removed: dict[str, int] = {}
            for ns in targets:
                bucket = self._store[ns]
                count = 0
                if not prefix:
                    count = len(bucket)
                    bucket.clear()
                else:
                    for key in [k for k in bucket.keys() if k.startswith(prefix)]:
                        bucket.pop(key, None)
                        count += 1
                removed[ns] = count
                self._metrics["invalidations"] += count
            return removed

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = int(self._metrics["hits"] + self._metrics["misses"])
            return {
                **self._metrics,
                "requests": total,
                "hit_rate": float(self._metrics["hits"] / max(1, total)),
                "namespaces": {ns: len(bucket) for ns, bucket in self._store.items()},
                "max_size": int(self.max_size),
            }


class BatchExplanationOptimizer:
    """批量解释执行器：并行调度、进度跟踪、瓶颈分析与结果聚合。"""

    @staticmethod
    def analyze_bottleneck(tasks: list[dict[str, Any]]) -> dict[str, Any]:
        costs = []
        for task in tasks:
            payload = task.get("payload", {})
            explain_nodes = int(payload.get("max_explain_nodes", 1))
            samples = int(payload.get("num_samples", payload.get("nsamples", 1)))
            costs.append(max(1, explain_nodes) * max(1, samples))
        total = int(sum(costs))
        return {
            "task_count": len(tasks),
            "estimated_total_cost": total,
            "estimated_avg_cost": float(total / max(1, len(costs))),
            "bottleneck": "sampling" if total >= 1000 else "overhead",
        }

    def run(
        self,
        tasks: list[dict[str, Any]],
        worker: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        max_workers: int = 4,
    ) -> dict[str, Any]:
        if not tasks:
            return {
                "summary": {"total": 0, "succeeded": 0, "failed": 0, "progress": 1.0},
                "results": [],
                "progress_trace": [],
                "aggregation": {"avg_latency_ms": 0.0, "success_rate": 1.0},
            }

        queue = sorted(tasks, key=lambda item: int(item.get("priority", 0)), reverse=True)
        total = len(queue)
        done = 0
        success = 0
        rows: list[dict[str, Any]] = []
        progress_trace: list[dict[str, Any]] = []
        latencies = []

        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
            futures = {}
            for task in queue:
                task_id = str(task.get("task_id", f"task_{len(futures)}"))
                futures[executor.submit(self._run_single, worker, task)] = task_id

            for future in as_completed(futures):
                task_id = futures[future]
                started = time.perf_counter()
                try:
                    result = future.result()
                    ok = True
                except Exception as exc:  # pragma: no cover
                    result = {"error": str(exc)}
                    ok = False
                elapsed_ms = float((time.perf_counter() - started) * 1000.0)
                latencies.append(elapsed_ms)
                done += 1
                success += int(ok)
                rows.append({"task_id": task_id, "ok": ok, "result": result, "latency_ms": elapsed_ms})
                progress_trace.append(
                    {
                        "task_id": task_id,
                        "done": done,
                        "total": total,
                        "progress": float(done / total),
                    }
                )

        rows.sort(key=lambda item: str(item["task_id"]))
        aggregation = {
            "avg_latency_ms": float(np.mean(latencies)) if latencies else 0.0,
            "max_latency_ms": float(np.max(latencies)) if latencies else 0.0,
            "success_rate": float(success / total),
        }
        return {
            "summary": {
                "total": total,
                "succeeded": success,
                "failed": total - success,
                "progress": 1.0,
            },
            "results": rows,
            "progress_trace": progress_trace,
            "aggregation": aggregation,
        }

    @staticmethod
    def _run_single(worker: Callable[[dict[str, Any]], dict[str, Any]], task: dict[str, Any]) -> dict[str, Any]:
        return worker(task)


class PredictionReuseManager:
    """预测结果复用：索引、检索、一致性检查、版本管理与复用统计。"""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._versions: dict[str, set[str]] = {}
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()

    @staticmethod
    def _signature(prediction: Any) -> str:
        return hashlib.sha256(_stable_json_dumps(prediction).encode("utf-8")).hexdigest()

    @staticmethod
    def _index_key(model_name: str, model_version: str, query_fingerprint: str) -> str:
        return f"{model_name}:{model_version}:{query_fingerprint}"

    def index_prediction(
        self,
        *,
        model_name: str,
        model_version: str,
        query_fingerprint: str,
        prediction: Any,
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        key = self._index_key(model_name, model_version, query_fingerprint)
        payload = {
            "prediction": json.loads(_stable_json_dumps(prediction)),
            "signature": self._signature(prediction),
            "metadata": dict(metadata or {}),
            "created_at": time.time(),
        }
        with self._lock:
            self._store[key] = payload
            self._versions.setdefault(str(model_name), set()).add(str(model_version))
        return key

    def retrieve_prediction(
        self,
        *,
        model_name: str,
        model_version: str,
        query_fingerprint: str,
        expected_signature: str | None = None,
    ) -> Optional[dict[str, Any]]:
        key = self._index_key(model_name, model_version, query_fingerprint)
        with self._lock:
            cached = self._store.get(key)
            if cached is None:
                self._misses += 1
                return None
            signature = str(cached.get("signature", ""))
            if expected_signature is not None and signature != expected_signature:
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(_stable_json_dumps(cached))

    def optimize_reuse_strategy(self) -> dict[str, Any]:
        stats = self.stats()
        hit_rate = float(stats["hit_rate"])
        strategy = "reuse_first" if hit_rate >= 0.5 else "compute_first"
        return {
            "strategy": strategy,
            "hit_rate": hit_rate,
            "total_versions": int(sum(len(v) for v in self._versions.values())),
            "version_map": {k: sorted(list(v)) for k, v in self._versions.items()},
        }

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "hits": int(self._hits),
                "misses": int(self._misses),
                "requests": int(total),
                "hit_rate": float(self._hits / max(1, total)),
                "entries": int(len(self._store)),
            }


class MemoryOptimizationManager:
    """内存优化：模式分析、内存池、监控、回收与轻量泄漏检测。"""

    def __init__(self, *, monitor_window: int = 16) -> None:
        self._pool: dict[str, list[np.ndarray]] = {}
        self._pool_timestamps: dict[str, deque[float]] = {}
        self._reuse_hits = 0
        self._reuse_misses = 0
        self._history = deque(maxlen=max(4, int(monitor_window)))

    @staticmethod
    def _size_bytes(obj: Any) -> int:
        if isinstance(obj, np.ndarray):
            return int(obj.nbytes)
        if isinstance(obj, (bytes, bytearray)):
            return int(len(obj))
        if isinstance(obj, dict):
            return int(sum(MemoryOptimizationManager._size_bytes(k) + MemoryOptimizationManager._size_bytes(v) for k, v in obj.items()))
        if isinstance(obj, (list, tuple, set)):
            return int(sum(MemoryOptimizationManager._size_bytes(v) for v in obj))
        return int(len(str(obj).encode("utf-8")))

    def analyze_memory_usage(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = []
        total = 0
        for key, value in payload.items():
            size = self._size_bytes(value)
            rows.append({"field": str(key), "bytes": int(size)})
            total += size
        rows.sort(key=lambda item: int(item["bytes"]), reverse=True)
        return {
            "total_bytes": int(total),
            "top_fields": rows[:5],
            "field_count": int(len(rows)),
        }

    @staticmethod
    def _pool_key(shape: tuple[int, ...], dtype: np.dtype) -> str:
        return f"{tuple(shape)}:{np.dtype(dtype).name}"

    def acquire_buffer(self, shape: tuple[int, ...], dtype: np.dtype = np.float32) -> np.ndarray:
        key = self._pool_key(shape, np.dtype(dtype))
        bucket = self._pool.get(key, [])
        if bucket:
            self._reuse_hits += 1
            arr = bucket.pop()
            if self._pool_timestamps.get(key):
                self._pool_timestamps[key].pop()
            return arr
        self._reuse_misses += 1
        return np.zeros(shape, dtype=dtype)

    def release_buffer(self, arr: np.ndarray) -> None:
        key = self._pool_key(tuple(arr.shape), arr.dtype)
        self._pool.setdefault(key, []).append(arr)
        self._pool_timestamps.setdefault(key, deque()).append(time.time())

    def recycle_pool(self, *, max_idle_seconds: float = 30.0) -> int:
        now = time.time()
        removed = 0
        for key in list(self._pool.keys()):
            bucket = self._pool.get(key, [])
            ts_bucket = self._pool_timestamps.get(key, deque())
            kept_arrays = []
            kept_ts = deque()
            while bucket and ts_bucket:
                arr = bucket.pop(0)
                ts = ts_bucket.popleft()
                if (now - ts) > float(max_idle_seconds):
                    removed += 1
                else:
                    kept_arrays.append(arr)
                    kept_ts.append(ts)
            if kept_arrays:
                self._pool[key] = kept_arrays
                self._pool_timestamps[key] = kept_ts
            else:
                self._pool.pop(key, None)
                self._pool_timestamps.pop(key, None)
        return removed

    def optimize_large_object(self, arr: np.ndarray, *, target_dtype: np.dtype = np.float32) -> np.ndarray:
        if not isinstance(arr, np.ndarray):
            raise TypeError("arr must be numpy array")
        dst = np.dtype(target_dtype)
        if arr.dtype == dst:
            return arr
        return arr.astype(dst, copy=False)

    def monitor(self, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        memory_bytes = self.analyze_memory_usage(payload or {}).get("total_bytes", 0)
        snapshot = {
            "ts": time.time(),
            "memory_bytes": int(memory_bytes),
            "pool_entries": int(sum(len(v) for v in self._pool.values())),
            "reuse_hits": int(self._reuse_hits),
            "reuse_misses": int(self._reuse_misses),
        }
        self._history.append(snapshot)
        return snapshot

    def detect_memory_leak(self, *, min_growth_bytes: int = 1024) -> dict[str, Any]:
        if len(self._history) < 3:
            return {"suspected": False, "growth_bytes": 0}
        seq = np.asarray([int(item["memory_bytes"]) for item in self._history], dtype=float)
        growth = float(seq[-1] - seq[0])
        monotonic = bool(np.all(np.diff(seq) >= 0))
        suspected = bool(monotonic and growth >= float(min_growth_bytes))
        return {
            "suspected": suspected,
            "growth_bytes": int(max(0, growth)),
            "samples": int(len(seq)),
        }


class AdaptiveSamplingOptimizer:
    """自适应采样：采样密度调整、质量评估、采样点优化、历史与参数自适应。"""

    def __init__(self, *, base_density: float = 1.0) -> None:
        self.base_density = max(0.1, float(base_density))
        self._history: list[dict[str, Any]] = []
        self._adaptive = {
            "explore_weight": 0.6,
            "quality_target": 0.8,
        }

    def adjust_density(self, quality_score: float) -> float:
        q = float(np.clip(quality_score, 0.0, 1.0))
        target = float(self._adaptive["quality_target"])
        delta = (target - q) * 0.5
        density = float(np.clip(self.base_density * (1.0 + delta), 0.2, 3.0))
        return density

    @staticmethod
    def evaluate_quality(points: np.ndarray, uncertainties: np.ndarray) -> dict[str, Any]:
        pts = np.asarray(points, dtype=float)
        unc = np.asarray(uncertainties, dtype=float).reshape(-1)
        if pts.ndim != 2 or pts.shape[0] == 0:
            return {"quality": 0.0, "coverage": 0.0, "uncertainty_capture": 0.0}
        spread = float(np.mean(np.std(pts, axis=0)))
        coverage = float(np.clip(spread, 0.0, 1.0))
        capture = float(np.clip(np.mean(unc) / max(1e-12, np.max(unc)), 0.0, 1.0)) if unc.size else 0.0
        quality = float(np.clip(0.55 * capture + 0.45 * coverage, 0.0, 1.0))
        return {
            "quality": quality,
            "coverage": coverage,
            "uncertainty_capture": capture,
        }

    def optimize_points(
        self,
        candidates: np.ndarray,
        uncertainties: np.ndarray,
        *,
        target_count: int,
    ) -> dict[str, Any]:
        pts = np.asarray(candidates, dtype=float)
        unc = np.asarray(uncertainties, dtype=float).reshape(-1)
        if pts.ndim != 2 or pts.shape[0] == 0:
            return {"points": np.zeros((0, 2), dtype=float), "indices": [], "score": 0.0}
        n = min(max(1, int(target_count)), int(pts.shape[0]))
        order = np.argsort(unc)[::-1]
        selected: list[int] = []
        explore_w = float(self._adaptive["explore_weight"])

        for idx in order.tolist():
            if len(selected) >= n:
                break
            if not selected:
                selected.append(int(idx))
                continue
            dist = np.linalg.norm(pts[selected] - pts[int(idx)], axis=1)
            novelty = float(np.min(dist)) if dist.size else 0.0
            norm_unc = float(unc[int(idx)] / max(1e-12, float(np.max(unc))))
            score = explore_w * norm_unc + (1.0 - explore_w) * float(np.clip(novelty, 0.0, 1.0))
            if score >= 0.25 or len(selected) < n // 2:
                selected.append(int(idx))

        selected = selected[:n]
        out_points = pts[selected]
        quality = self.evaluate_quality(out_points, unc[selected])
        return {
            "points": out_points,
            "indices": selected,
            "score": float(quality["quality"]),
            "quality": quality,
        }

    def adapt_parameters(self, *, window: int = 5) -> dict[str, float]:
        if not self._history:
            return dict(self._adaptive)
        recent = self._history[-max(1, int(window)) :]
        mean_q = float(np.mean([float(item.get("quality", 0.0)) for item in recent]))
        target = float(self._adaptive["quality_target"])
        if mean_q < target:
            self._adaptive["explore_weight"] = float(np.clip(self._adaptive["explore_weight"] + 0.05, 0.2, 0.9))
        else:
            self._adaptive["explore_weight"] = float(np.clip(self._adaptive["explore_weight"] - 0.05, 0.2, 0.9))
        return dict(self._adaptive)

    def sample(
        self,
        *,
        candidates: np.ndarray,
        uncertainties: np.ndarray,
        target_count: int,
    ) -> dict[str, Any]:
        plan = self.optimize_points(candidates, uncertainties, target_count=target_count)
        quality = float(plan.get("score", 0.0))
        density = self.adjust_density(quality)
        self._history.append(
            {
                "ts": time.time(),
                "quality": quality,
                "density": density,
                "count": int(len(plan.get("indices", []))),
            }
        )
        plan["density"] = density
        plan["history_size"] = len(self._history)
        return plan

    def history(self) -> list[dict[str, Any]]:
        return list(self._history)
