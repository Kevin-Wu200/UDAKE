"""GPU计算引擎。"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Dict, Tuple

import numpy as np

from .data_structures import ComputeBackend
from .device_manager import DeviceManager
from .memory_manager import GPUMemoryManager
from .performance_monitor import PerformanceMonitor

try:  # pragma: no cover
    import cupy as cp  # type: ignore
except Exception:  # pragma: no cover
    cp = None


@dataclass
class ComputeResult:
    """单次计算结果。"""

    backend: ComputeBackend
    elapsed_ms: float
    payload: Dict[str, np.ndarray | float | list]

    def to_dict(self) -> dict:
        return {
            "backend": self.backend.value,
            "elapsed_ms": round(self.elapsed_ms, 4),
            "payload": self.payload,
        }


class GPUComputeEngine:
    """统一矩阵与向量计算接口，支持GPU回退。"""

    def __init__(
        self,
        device_manager: DeviceManager | None = None,
        memory_manager: GPUMemoryManager | None = None,
        performance_monitor: PerformanceMonitor | None = None,
        min_size_for_gpu: int = 25_000,
        max_workers: int = 4,
    ) -> None:
        self.device_manager = device_manager or DeviceManager()
        self.memory_manager = memory_manager or GPUMemoryManager()
        self.performance_monitor = performance_monitor or PerformanceMonitor()
        self.min_size_for_gpu = min_size_for_gpu
        self._executor = ThreadPoolExecutor(max_workers=max(1, int(max_workers)))

    def _select_backend(self, prefer_gpu: bool, problem_size: int) -> ComputeBackend:
        if not prefer_gpu:
            return ComputeBackend.CPU
        return self.device_manager.auto_select_backend(problem_size, self.min_size_for_gpu)

    def _run_binary_matrix_op(self, operation: str, a: np.ndarray, b: np.ndarray, prefer_gpu: bool, func_name: str) -> ComputeResult:
        backend = self._select_backend(prefer_gpu, int(a.size + b.size))
        start = perf_counter()

        da, _ = self.memory_manager.to_device(a, backend)
        db, _ = self.memory_manager.to_device(b, backend)
        if backend == ComputeBackend.GPU and cp is not None:
            op_func = getattr(cp, func_name)
            output = op_func(da, db)
        else:
            op_func = getattr(np, func_name)
            output = op_func(da, db)

        output_host, _ = self.memory_manager.to_host(output, backend)
        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record(operation, backend, elapsed_ms, int(a.size + b.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": output_host})

    def matrix_multiply(self, a: np.ndarray, b: np.ndarray, prefer_gpu: bool = True) -> ComputeResult:
        if a.ndim != 2 or b.ndim != 2:
            raise ValueError("矩阵乘法需要二维数组")
        if a.shape[1] != b.shape[0]:
            raise ValueError("矩阵维度不匹配，无法相乘")
        return self._run_binary_matrix_op("matrix_multiply", a, b, prefer_gpu, "matmul")

    def matrix_inverse(self, matrix: np.ndarray, prefer_gpu: bool = True) -> ComputeResult:
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError("矩阵求逆需要方阵")

        backend = self._select_backend(prefer_gpu, int(matrix.size))
        start = perf_counter()
        d_matrix, _ = self.memory_manager.to_device(matrix, backend)

        if backend == ComputeBackend.GPU and cp is not None:
            inv = cp.linalg.inv(d_matrix)
        else:
            inv = np.linalg.inv(d_matrix)

        inv_host, _ = self.memory_manager.to_host(inv, backend)
        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record("matrix_inverse", backend, elapsed_ms, int(matrix.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": inv_host})

    def solve_linear_system(self, a: np.ndarray, b: np.ndarray, prefer_gpu: bool = True) -> ComputeResult:
        if a.ndim != 2 or a.shape[0] != a.shape[1]:
            raise ValueError("线性方程组系数矩阵必须是方阵")
        if b.ndim not in (1, 2):
            raise ValueError("右侧向量/矩阵维度不合法")

        backend = self._select_backend(prefer_gpu, int(a.size + b.size))
        start = perf_counter()
        da, _ = self.memory_manager.to_device(a, backend)
        db, _ = self.memory_manager.to_device(b, backend)

        if backend == ComputeBackend.GPU and cp is not None:
            x = cp.linalg.solve(da, db)
        else:
            x = np.linalg.solve(da, db)

        x_host, _ = self.memory_manager.to_host(x, backend)
        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record("linear_solve", backend, elapsed_ms, int(a.size + b.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": x_host})

    def eigenvalues(self, matrix: np.ndarray, prefer_gpu: bool = True) -> ComputeResult:
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError("特征值计算需要方阵")

        backend = self._select_backend(prefer_gpu, int(matrix.size))
        start = perf_counter()
        d_matrix, _ = self.memory_manager.to_device(matrix, backend)
        if backend == ComputeBackend.GPU and cp is not None:
            eig_vals = cp.linalg.eigvals(d_matrix)
        else:
            eig_vals = np.linalg.eigvals(d_matrix)
        eig_vals_host, _ = self.memory_manager.to_host(eig_vals, backend)

        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record("eigenvalues", backend, elapsed_ms, int(matrix.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": eig_vals_host})

    def cholesky_decomposition(self, matrix: np.ndarray, prefer_gpu: bool = True) -> ComputeResult:
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError("Cholesky分解需要方阵")

        backend = self._select_backend(prefer_gpu, int(matrix.size))
        start = perf_counter()
        d_matrix, _ = self.memory_manager.to_device(matrix, backend)

        if backend == ComputeBackend.GPU and cp is not None:
            lower = cp.linalg.cholesky(d_matrix)
        else:
            lower = np.linalg.cholesky(d_matrix)

        lower_host, _ = self.memory_manager.to_host(lower, backend)
        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record("cholesky", backend, elapsed_ms, int(matrix.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": lower_host})

    def lu_decomposition(self, matrix: np.ndarray, prefer_gpu: bool = True) -> ComputeResult:
        """LU分解采用CPU实现，保证在无SciPy时可用。"""
        del prefer_gpu

        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError("LU分解需要方阵")

        a = np.array(matrix, dtype=float, copy=True)
        n = a.shape[0]
        l = np.eye(n)
        u = np.zeros_like(a)
        p = np.eye(n)

        start = perf_counter()
        for i in range(n):
            pivot = np.argmax(np.abs(a[i:, i])) + i
            if pivot != i:
                a[[i, pivot]] = a[[pivot, i]]
                p[[i, pivot]] = p[[pivot, i]]
                if i > 0:
                    l[[i, pivot], :i] = l[[pivot, i], :i]

            if np.isclose(a[i, i], 0.0):
                raise np.linalg.LinAlgError("矩阵奇异，无法进行LU分解")

            u[i, i:] = a[i, i:]
            for j in range(i + 1, n):
                l[j, i] = a[j, i] / u[i, i]
                a[j, i:] = a[j, i:] - l[j, i] * u[i, i:]

        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record("lu_decomposition", ComputeBackend.CPU, elapsed_ms, int(matrix.size))
        return ComputeResult(
            backend=ComputeBackend.CPU,
            elapsed_ms=elapsed_ms,
            payload={"l": l, "u": u, "p": p},
        )

    def vector_dot(self, a: np.ndarray, b: np.ndarray, prefer_gpu: bool = True) -> ComputeResult:
        if a.shape != b.shape:
            raise ValueError("向量点积要求输入形状一致")

        backend = self._select_backend(prefer_gpu, int(a.size + b.size))
        start = perf_counter()
        da, _ = self.memory_manager.to_device(a, backend)
        db, _ = self.memory_manager.to_device(b, backend)

        if backend == ComputeBackend.GPU and cp is not None:
            result = cp.dot(da, db)
        else:
            result = np.dot(da, db)

        host, _ = self.memory_manager.to_host(result, backend)
        scalar = float(np.asarray(host).reshape(-1)[0])

        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record("vector_dot", backend, elapsed_ms, int(a.size + b.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": scalar})

    def vector_norm(self, a: np.ndarray, prefer_gpu: bool = True) -> ComputeResult:
        backend = self._select_backend(prefer_gpu, int(a.size))
        start = perf_counter()
        da, _ = self.memory_manager.to_device(a, backend)

        if backend == ComputeBackend.GPU and cp is not None:
            result = cp.linalg.norm(da)
        else:
            result = np.linalg.norm(da)

        host, _ = self.memory_manager.to_host(result, backend)
        scalar = float(np.asarray(host).reshape(-1)[0])

        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record("vector_norm", backend, elapsed_ms, int(a.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": scalar})

    def vector_sort(self, a: np.ndarray, prefer_gpu: bool = True) -> ComputeResult:
        backend = self._select_backend(prefer_gpu, int(a.size))
        start = perf_counter()
        da, _ = self.memory_manager.to_device(a, backend)

        if backend == ComputeBackend.GPU and cp is not None:
            result = cp.sort(da)
        else:
            result = np.sort(da)

        host, _ = self.memory_manager.to_host(result, backend)
        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record("vector_sort", backend, elapsed_ms, int(a.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": host})

    def run_kernel(
        self,
        kernel_name: str,
        array: np.ndarray,
        *,
        alpha: float = 1.0,
        beta: float = 0.0,
        prefer_gpu: bool = True,
    ) -> ComputeResult:
        """执行通用Kernel函数（element-wise）。"""
        arr = np.asarray(array, dtype=float)
        backend = self._select_backend(prefer_gpu, int(arr.size))
        start = perf_counter()
        d_arr, _ = self.memory_manager.to_device(arr, backend)

        if backend == ComputeBackend.GPU and cp is not None:
            output = self._run_kernel_gpu(kernel_name, d_arr, alpha=alpha, beta=beta)
        else:
            output = self._run_kernel_cpu(kernel_name, d_arr, alpha=alpha, beta=beta)

        host, _ = self.memory_manager.to_host(output, backend)
        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record(f"kernel_{kernel_name}", backend, elapsed_ms, int(arr.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": host})

    def _run_kernel_gpu(self, kernel_name: str, arr: Any, *, alpha: float, beta: float) -> Any:
        # CuPy环境下优先使用GPU向量化内核。
        if kernel_name == "square":
            return arr * arr
        if kernel_name == "affine":
            return arr * alpha + beta
        if kernel_name == "relu":
            return cp.maximum(arr, 0)
        if kernel_name == "sigmoid":
            return 1.0 / (1.0 + cp.exp(-arr))
        raise ValueError(f"不支持的kernel: {kernel_name}")

    def _run_kernel_cpu(self, kernel_name: str, arr: np.ndarray, *, alpha: float, beta: float) -> np.ndarray:
        if kernel_name == "square":
            return arr * arr
        if kernel_name == "affine":
            return arr * alpha + beta
        if kernel_name == "relu":
            return np.maximum(arr, 0.0)
        if kernel_name == "sigmoid":
            return 1.0 / (1.0 + np.exp(-arr))
        raise ValueError(f"不支持的kernel: {kernel_name}")

    def sparse_matrix_multiply(
        self,
        values: np.ndarray,
        col_indices: np.ndarray,
        row_ptr: np.ndarray,
        dense_b: np.ndarray,
        shape: tuple[int, int],
        prefer_gpu: bool = True,
    ) -> ComputeResult:
        """CSR稀疏矩阵与稠密矩阵乘法。"""
        rows, cols = shape
        if row_ptr.shape[0] != rows + 1:
            raise ValueError("CSR row_ptr 长度与矩阵行数不匹配")
        if dense_b.ndim != 2 or dense_b.shape[0] != cols:
            raise ValueError("稠密矩阵维度不匹配")

        backend = self._select_backend(prefer_gpu, int(values.size + dense_b.size))
        start = perf_counter()
        out = np.zeros((rows, dense_b.shape[1]), dtype=float)

        for row in range(rows):
            begin = int(row_ptr[row])
            end = int(row_ptr[row + 1])
            if begin >= end:
                continue
            cids = col_indices[begin:end].astype(int)
            coeff = values[begin:end].reshape(-1, 1)
            out[row] = np.sum(coeff * dense_b[cids], axis=0)

        elapsed_ms = (perf_counter() - start) * 1000
        self.performance_monitor.record("sparse_matrix_multiply", backend, elapsed_ms, int(values.size + dense_b.size))
        return ComputeResult(backend=backend, elapsed_ms=elapsed_ms, payload={"result": out})

    def sparse_linear_solve(
        self,
        values: np.ndarray,
        col_indices: np.ndarray,
        row_ptr: np.ndarray,
        rhs: np.ndarray,
        shape: tuple[int, int],
        prefer_gpu: bool = True,
    ) -> ComputeResult:
        """CSR稀疏矩阵线性求解（转稠密回退实现）。"""
        rows, cols = shape
        if rows != cols:
            raise ValueError("稀疏求解仅支持方阵")
        dense = np.zeros((rows, cols), dtype=float)
        for row in range(rows):
            begin = int(row_ptr[row])
            end = int(row_ptr[row + 1])
            if begin >= end:
                continue
            dense[row, col_indices[begin:end].astype(int)] = values[begin:end]
        return self.solve_linear_system(dense, rhs, prefer_gpu=prefer_gpu)

    def split_workload(self, total_size: int, chunk_size: int) -> list[tuple[int, int]]:
        """按块切分任务范围。"""
        total = max(0, int(total_size))
        chunk = max(1, int(chunk_size))
        segments: list[tuple[int, int]] = []
        start = 0
        while start < total:
            end = min(start + chunk, total)
            segments.append((start, end))
            start = end
        return segments

    def submit_async(self, func: Callable[..., ComputeResult], *args: Any, **kwargs: Any) -> Future[ComputeResult]:
        """异步提交计算任务。"""
        return self._executor.submit(func, *args, **kwargs)

    def get_runtime_metrics(self) -> dict:
        """返回性能与内存统计。"""
        return {
            "backend": self.device_manager.get_backend().value,
            "gpu_available": self.device_manager.is_gpu_available(),
            "devices": [item.to_dict() for item in self.device_manager.get_devices()],
            "memory_stats": self.memory_manager.stats.to_dict(),
            "performance": {
                "overall": self.performance_monitor.get_overall_stats(),
                "operations": self.performance_monitor.get_operation_stats(),
                "recent": self.performance_monitor.get_recent(20),
            },
        }
