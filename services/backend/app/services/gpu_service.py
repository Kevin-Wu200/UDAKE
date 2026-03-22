"""GPU加速计算服务。"""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import TimeoutError as FutureTimeoutError
from hashlib import md5
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from ..gpu_acceleration import (
    ComputeBackend,
    DeviceManager,
    GPUComputeEngine,
    GPUMemoryManager,
    GPUTaskScheduler,
    KrigingGPUAccelerator,
    PerformanceMonitor,
)


class GPUService:
    """对外提供GPU计算与监控能力。"""

    def __init__(self, force_cpu: bool = False):
        self.device_manager = DeviceManager(force_cpu=force_cpu)
        self.memory_manager = GPUMemoryManager()
        self.performance_monitor = PerformanceMonitor()
        self.compute_engine = GPUComputeEngine(
            device_manager=self.device_manager,
            memory_manager=self.memory_manager,
            performance_monitor=self.performance_monitor,
        )
        self.scheduler = GPUTaskScheduler()
        self.kriging_accelerator = KrigingGPUAccelerator(self.compute_engine)
        self.config: Dict[str, Any] = {
            "enable_gpu": not force_cpu,
            "auto_switch": True,
            "min_size_for_gpu": self.compute_engine.min_size_for_gpu,
            "timeout_ms": 5000,
            "load_balance": True,
            "cache_enabled": True,
            "cache_limit": 256,
        }
        self._result_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._device_rr_index = 0

    def _normalize_prefer_gpu(self, prefer_gpu: bool) -> bool:
        if not self.config.get("enable_gpu", True):
            return False
        if not self.config.get("auto_switch", True):
            return bool(prefer_gpu and self.device_manager.is_gpu_available())
        return bool(prefer_gpu)

    def _make_cache_key(self, op: str, payload: Dict[str, Any]) -> str:
        raw = f"{op}:{self._serialize(payload)}"
        return md5(raw.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.config.get("cache_enabled", True):
            return None
        item = self._result_cache.get(key)
        if item is None:
            return None
        self._result_cache.move_to_end(key)
        return item

    def _cache_set(self, key: str, value: Dict[str, Any]) -> None:
        if not self.config.get("cache_enabled", True):
            return
        self._result_cache[key] = value
        self._result_cache.move_to_end(key)
        limit = max(1, int(self.config.get("cache_limit", 256)))
        while len(self._result_cache) > limit:
            self._result_cache.popitem(last=False)

    def _choose_device(self) -> Optional[int]:
        if not self.config.get("load_balance", True):
            return None
        devices = self.device_manager.get_devices()
        if not devices:
            return None
        idx = self._device_rr_index % len(devices)
        self._device_rr_index += 1
        return int(devices[idx].device_id)

    def _to_numpy(self, data: List[List[float]] | List[float] | np.ndarray) -> np.ndarray:
        return np.asarray(data, dtype=float)

    def _serialize(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._serialize(v) for v in value]
        return value

    def _build_response(self, task_id: str, backend: ComputeBackend, elapsed_ms: float, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "task_id": task_id,
            "backend": backend.value,
            "elapsed_ms": round(elapsed_ms, 4),
            "result": self._serialize(payload),
        }

    def get_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "gpu_available": self.device_manager.is_gpu_available(),
            "backend": self.device_manager.get_backend().value,
            "device_count": len(self.device_manager.get_devices()),
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "health": self.get_health(),
            "config": dict(self.config),
            "runtime": self.compute_engine.get_runtime_metrics(),
            "task_count": len(self.scheduler.list_tasks(1000)),
        }

    def list_devices(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self.device_manager.get_devices()]

    def update_config(self, *, enable_gpu: Optional[bool] = None, auto_switch: Optional[bool] = None, min_size_for_gpu: Optional[int] = None) -> Dict[str, Any]:
        if enable_gpu is not None:
            self.config["enable_gpu"] = bool(enable_gpu)
        if auto_switch is not None:
            self.config["auto_switch"] = bool(auto_switch)
        if min_size_for_gpu is not None:
            self.compute_engine.min_size_for_gpu = max(1, int(min_size_for_gpu))
            self.config["min_size_for_gpu"] = self.compute_engine.min_size_for_gpu
        timeout_ms = self.config.get("timeout_ms")
        if timeout_ms is not None:
            self.config["timeout_ms"] = max(100, int(timeout_ms))
        return dict(self.config)

    def get_metrics(self) -> Dict[str, Any]:
        return self.compute_engine.get_runtime_metrics()

    def clear_metrics(self) -> Dict[str, Any]:
        self.performance_monitor.clear()
        self.memory_manager.reset_stats()
        self._result_cache.clear()
        return {"message": "性能指标已清空"}

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.scheduler.get_task(task_id)
        return task.to_dict() if task else None

    def list_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.scheduler.list_tasks(limit)

    def _prepare_task(self, task_type: str, payload: Dict[str, Any], problem_size: int, prefer_gpu: bool) -> str:
        selected_device = self._choose_device()
        if selected_device is not None:
            payload = dict(payload)
            payload["device_id"] = selected_device
        selected = self.compute_engine._select_backend(self._normalize_prefer_gpu(prefer_gpu), problem_size)
        task = self.scheduler.create_task(task_type, payload, selected)
        self.scheduler.start_task(task.task_id)
        return task.task_id

    def _finalize_task_success(self, task_id: str) -> None:
        self.scheduler.complete_task(task_id)

    def _finalize_task_fail(self, task_id: str, exc: Exception) -> None:
        self.scheduler.fail_task(task_id, str(exc))

    def _execute_with_recovery(
        self,
        op_name: str,
        task_id: str,
        payload_for_cache: Dict[str, Any],
        prefer_gpu: bool,
        fn: Callable[[bool], Dict[str, Any]],
    ) -> Dict[str, Any]:
        cache_key = self._make_cache_key(op_name, payload_for_cache)
        cached = self._cache_get(cache_key)
        if cached is not None:
            self._finalize_task_success(task_id)
            cached_resp = dict(cached)
            cached_resp["task_id"] = task_id
            cached_resp["cached"] = True
            return cached_resp

        timeout_sec = max(0.1, float(self.config.get("timeout_ms", 5000)) / 1000.0)
        use_gpu = self._normalize_prefer_gpu(prefer_gpu)
        future = self.compute_engine.submit_async(fn, use_gpu)
        try:
            response = future.result(timeout=timeout_sec)
            self._cache_set(cache_key, dict(response))
            self._finalize_task_success(task_id)
            return response
        except FutureTimeoutError as exc:
            future.cancel()
            if use_gpu:
                try:
                    response = fn(False)
                    response["recovered_from"] = "timeout_gpu_to_cpu"
                    self._cache_set(cache_key, dict(response))
                    self._finalize_task_success(task_id)
                    return response
                except Exception as recovery_exc:
                    self._finalize_task_fail(task_id, recovery_exc)
                    raise recovery_exc
            self._finalize_task_fail(task_id, exc)
            raise TimeoutError(f"{op_name}执行超时({self.config.get('timeout_ms')}ms)") from exc
        except Exception as exc:
            if use_gpu:
                try:
                    response = fn(False)
                    response["recovered_from"] = "error_gpu_to_cpu"
                    self._cache_set(cache_key, dict(response))
                    self._finalize_task_success(task_id)
                    return response
                except Exception:
                    self._finalize_task_fail(task_id, exc)
                    raise
            self._finalize_task_fail(task_id, exc)
            raise

    def matrix_multiply(self, a: Any, b: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        a_np = self._to_numpy(a)
        b_np = self._to_numpy(b)
        task_id = self._prepare_task("matrix_multiply", {"shape_a": list(a_np.shape), "shape_b": list(b_np.shape)}, int(a_np.size + b_np.size), prefer_gpu)
        payload = {"a": a_np, "b": b_np}

        def _run(use_gpu: bool) -> Dict[str, Any]:
            result = self.compute_engine.matrix_multiply(a_np, b_np, prefer_gpu=use_gpu)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)

        return self._execute_with_recovery("matrix_multiply", task_id, payload, prefer_gpu, _run)

    def matrix_inverse(self, matrix: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        matrix_np = self._to_numpy(matrix)
        task_id = self._prepare_task("matrix_inverse", {"shape": list(matrix_np.shape)}, int(matrix_np.size), prefer_gpu)
        payload = {"matrix": matrix_np}

        def _run(use_gpu: bool) -> Dict[str, Any]:
            result = self.compute_engine.matrix_inverse(matrix_np, prefer_gpu=use_gpu)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)

        return self._execute_with_recovery("matrix_inverse", task_id, payload, prefer_gpu, _run)

    def matrix_eigenvalues(self, matrix: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        matrix_np = self._to_numpy(matrix)
        task_id = self._prepare_task("matrix_eigenvalues", {"shape": list(matrix_np.shape)}, int(matrix_np.size), prefer_gpu)
        try:
            result = self.compute_engine.eigenvalues(matrix_np, prefer_gpu=self._normalize_prefer_gpu(prefer_gpu))
            self._finalize_task_success(task_id)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

    def matrix_cholesky(self, matrix: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        matrix_np = self._to_numpy(matrix)
        task_id = self._prepare_task("matrix_cholesky", {"shape": list(matrix_np.shape)}, int(matrix_np.size), prefer_gpu)
        try:
            result = self.compute_engine.cholesky_decomposition(matrix_np, prefer_gpu=self._normalize_prefer_gpu(prefer_gpu))
            self._finalize_task_success(task_id)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

    def matrix_lu(self, matrix: Any) -> Dict[str, Any]:
        matrix_np = self._to_numpy(matrix)
        task_id = self._prepare_task("matrix_lu", {"shape": list(matrix_np.shape)}, int(matrix_np.size), False)
        try:
            result = self.compute_engine.lu_decomposition(matrix_np, prefer_gpu=False)
            self._finalize_task_success(task_id)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

    def solve_linear(self, a: Any, b: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        a_np = self._to_numpy(a)
        b_np = self._to_numpy(b)
        task_id = self._prepare_task("linear_solve", {"shape_a": list(a_np.shape), "shape_b": list(b_np.shape)}, int(a_np.size + b_np.size), prefer_gpu)
        payload = {"a": a_np, "b": b_np}

        def _run(use_gpu: bool) -> Dict[str, Any]:
            result = self.compute_engine.solve_linear_system(a_np, b_np, prefer_gpu=use_gpu)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)

        return self._execute_with_recovery("linear_solve", task_id, payload, prefer_gpu, _run)

    def vector_dot(self, a: Any, b: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        a_np = self._to_numpy(a)
        b_np = self._to_numpy(b)
        task_id = self._prepare_task("vector_dot", {"length": int(a_np.size)}, int(a_np.size + b_np.size), prefer_gpu)
        try:
            result = self.compute_engine.vector_dot(a_np, b_np, prefer_gpu=self._normalize_prefer_gpu(prefer_gpu))
            self._finalize_task_success(task_id)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

    def vector_norm(self, a: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        a_np = self._to_numpy(a)
        task_id = self._prepare_task("vector_norm", {"length": int(a_np.size)}, int(a_np.size), prefer_gpu)
        try:
            result = self.compute_engine.vector_norm(a_np, prefer_gpu=self._normalize_prefer_gpu(prefer_gpu))
            self._finalize_task_success(task_id)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

    def vector_sort(self, a: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        a_np = self._to_numpy(a)
        task_id = self._prepare_task("vector_sort", {"length": int(a_np.size)}, int(a_np.size), prefer_gpu)
        try:
            result = self.compute_engine.vector_sort(a_np, prefer_gpu=self._normalize_prefer_gpu(prefer_gpu))
            self._finalize_task_success(task_id)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

    def kriging_semivariogram(
        self,
        points: Any,
        values: Any,
        bins: int = 12,
        max_range: Optional[float] = None,
        prefer_gpu: bool = True,
    ) -> Dict[str, Any]:
        points_np = self._to_numpy(points)
        values_np = self._to_numpy(values)
        task_id = self._prepare_task("kriging_semivariogram", {"point_count": int(points_np.shape[0])}, int(points_np.size + values_np.size), prefer_gpu)
        try:
            result = self.kriging_accelerator.semivariogram(
                points_np,
                values_np,
                bins=bins,
                max_range=max_range,
                prefer_gpu=self._normalize_prefer_gpu(prefer_gpu),
            )
            self._finalize_task_success(task_id)
            return {
                "task_id": task_id,
                "backend": result["backend"],
                "elapsed_ms": result["elapsed_ms"],
                "result": self._serialize(result),
            }
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

    def kriging_predict(
        self,
        sample_points: Any,
        sample_values: Any,
        target_points: Any,
        sill: float,
        range_: float,
        nugget: float = 0.0,
        prefer_gpu: bool = True,
    ) -> Dict[str, Any]:
        sample_points_np = self._to_numpy(sample_points)
        sample_values_np = self._to_numpy(sample_values)
        target_points_np = self._to_numpy(target_points)

        total_size = int(sample_points_np.size + sample_values_np.size + target_points_np.size)
        task_id = self._prepare_task("kriging_predict", {"sample_count": int(sample_points_np.shape[0]), "target_count": int(target_points_np.shape[0])}, total_size, prefer_gpu)
        payload = {
            "sample_points": sample_points_np,
            "sample_values": sample_values_np,
            "target_points": target_points_np,
            "sill": sill,
            "range": range_,
            "nugget": nugget,
        }

        def _run(use_gpu: bool) -> Dict[str, Any]:
            result = self.kriging_accelerator.block_predict(
                sample_points=sample_points_np,
                sample_values=sample_values_np,
                target_points=target_points_np,
                sill=sill,
                range_=range_,
                nugget=nugget,
                block_size=1024,
                prefer_gpu=use_gpu,
            )
            return {
                "task_id": task_id,
                "backend": result["backend"],
                "elapsed_ms": 0.0,
                "result": self._serialize(result),
            }

        return self._execute_with_recovery("kriging_predict", task_id, payload, prefer_gpu, _run)

    def run_kernel(
        self,
        kernel_name: str,
        array: Any,
        *,
        alpha: float = 1.0,
        beta: float = 0.0,
        prefer_gpu: bool = True,
    ) -> Dict[str, Any]:
        arr = self._to_numpy(array)
        task_id = self._prepare_task("kernel_run", {"kernel": kernel_name, "size": int(arr.size)}, int(arr.size), prefer_gpu)

        def _run(use_gpu: bool) -> Dict[str, Any]:
            result = self.compute_engine.run_kernel(kernel_name, arr, alpha=alpha, beta=beta, prefer_gpu=use_gpu)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)

        return self._execute_with_recovery("kernel_run", task_id, {"kernel": kernel_name, "array": arr, "alpha": alpha, "beta": beta}, prefer_gpu, _run)

    def sparse_matrix_multiply(
        self,
        values: Any,
        col_indices: Any,
        row_ptr: Any,
        dense_b: Any,
        shape: tuple[int, int],
        prefer_gpu: bool = True,
    ) -> Dict[str, Any]:
        v = self._to_numpy(values)
        c = self._to_numpy(col_indices).astype(int)
        r = self._to_numpy(row_ptr).astype(int)
        b = self._to_numpy(dense_b)
        task_id = self._prepare_task("sparse_matrix_multiply", {"shape": list(shape)}, int(v.size + b.size), prefer_gpu)

        def _run(use_gpu: bool) -> Dict[str, Any]:
            result = self.compute_engine.sparse_matrix_multiply(v, c, r, b, shape, prefer_gpu=use_gpu)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)

        return self._execute_with_recovery("sparse_matrix_multiply", task_id, {"values": v, "col_indices": c, "row_ptr": r, "dense_b": b, "shape": shape}, prefer_gpu, _run)

    def fit_variogram(self, points: Any, values: Any, bins: int = 12, prefer_gpu: bool = True) -> Dict[str, Any]:
        points_np = self._to_numpy(points)
        values_np = self._to_numpy(values)
        task_id = self._prepare_task("fit_variogram", {"point_count": int(points_np.shape[0]), "bins": bins}, int(points_np.size + values_np.size), prefer_gpu)

        def _run(use_gpu: bool) -> Dict[str, Any]:
            result = self.kriging_accelerator.fit_variogram_parameters(points_np, values_np, bins=bins, prefer_gpu=use_gpu)
            return {
                "task_id": task_id,
                "backend": result["backend"],
                "elapsed_ms": 0.0,
                "result": self._serialize(result),
            }

        return self._execute_with_recovery("fit_variogram", task_id, {"points": points_np, "values": values_np, "bins": bins}, prefer_gpu, _run)

    def parallel_sampling(self, values: Any, sample_count: int = 256) -> Dict[str, Any]:
        arr = self._to_numpy(values)
        result = self.kriging_accelerator.parallel_sampling(arr, sample_count=sample_count)
        return {"result": self._serialize(result)}

    def parallel_validation(self, truth: Any, pred: Any) -> Dict[str, Any]:
        y_true = self._to_numpy(truth)
        y_pred = self._to_numpy(pred)
        result = self.kriging_accelerator.parallel_validation(y_true, y_pred)
        return {"result": self._serialize(result)}

    def preload_cache(self, warm_items: Optional[List[str]] = None) -> Dict[str, Any]:
        items = warm_items or ["identity_4", "demo_variogram"]
        warmed = 0
        for item in items:
            if item == "identity_4":
                _ = self.matrix_inverse(np.eye(4), prefer_gpu=False)
                warmed += 1
            elif item == "demo_variogram":
                pts = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
                vals = np.array([1.0, 2.0, 2.0, 3.0])
                _ = self.fit_variogram(pts, vals, bins=6, prefer_gpu=False)
                warmed += 1
        return {"warmed_items": warmed, "cache_size": len(self._result_cache)}


gpu_service = GPUService()
