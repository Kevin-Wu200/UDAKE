"""GPU加速计算服务。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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
        }

    def _normalize_prefer_gpu(self, prefer_gpu: bool) -> bool:
        if not self.config.get("enable_gpu", True):
            return False
        if not self.config.get("auto_switch", True):
            return bool(prefer_gpu and self.device_manager.is_gpu_available())
        return bool(prefer_gpu)

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
        return dict(self.config)

    def get_metrics(self) -> Dict[str, Any]:
        return self.compute_engine.get_runtime_metrics()

    def clear_metrics(self) -> Dict[str, Any]:
        self.performance_monitor.clear()
        self.memory_manager.reset_stats()
        return {"message": "性能指标已清空"}

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.scheduler.get_task(task_id)
        return task.to_dict() if task else None

    def list_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.scheduler.list_tasks(limit)

    def _prepare_task(self, task_type: str, payload: Dict[str, Any], problem_size: int, prefer_gpu: bool) -> str:
        selected = self.compute_engine._select_backend(self._normalize_prefer_gpu(prefer_gpu), problem_size)
        task = self.scheduler.create_task(task_type, payload, selected)
        self.scheduler.start_task(task.task_id)
        return task.task_id

    def _finalize_task_success(self, task_id: str) -> None:
        self.scheduler.complete_task(task_id)

    def _finalize_task_fail(self, task_id: str, exc: Exception) -> None:
        self.scheduler.fail_task(task_id, str(exc))

    def matrix_multiply(self, a: Any, b: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        a_np = self._to_numpy(a)
        b_np = self._to_numpy(b)
        task_id = self._prepare_task("matrix_multiply", {"shape_a": list(a_np.shape), "shape_b": list(b_np.shape)}, int(a_np.size + b_np.size), prefer_gpu)
        try:
            result = self.compute_engine.matrix_multiply(a_np, b_np, prefer_gpu=self._normalize_prefer_gpu(prefer_gpu))
            self._finalize_task_success(task_id)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

    def matrix_inverse(self, matrix: Any, prefer_gpu: bool = True) -> Dict[str, Any]:
        matrix_np = self._to_numpy(matrix)
        task_id = self._prepare_task("matrix_inverse", {"shape": list(matrix_np.shape)}, int(matrix_np.size), prefer_gpu)
        try:
            result = self.compute_engine.matrix_inverse(matrix_np, prefer_gpu=self._normalize_prefer_gpu(prefer_gpu))
            self._finalize_task_success(task_id)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

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
        try:
            result = self.compute_engine.solve_linear_system(a_np, b_np, prefer_gpu=self._normalize_prefer_gpu(prefer_gpu))
            self._finalize_task_success(task_id)
            return self._build_response(task_id, result.backend, result.elapsed_ms, result.payload)
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise

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
        try:
            result = self.kriging_accelerator.batch_predict(
                sample_points=sample_points_np,
                sample_values=sample_values_np,
                target_points=target_points_np,
                sill=sill,
                range_=range_,
                nugget=nugget,
                prefer_gpu=self._normalize_prefer_gpu(prefer_gpu),
            )
            self._finalize_task_success(task_id)
            return {
                "task_id": task_id,
                "backend": result["backend"],
                "elapsed_ms": 0.0,
                "result": self._serialize(result),
            }
        except Exception as exc:
            self._finalize_task_fail(task_id, exc)
            raise


gpu_service = GPUService()
