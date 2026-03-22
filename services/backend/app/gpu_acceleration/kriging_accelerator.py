"""克里金相关的GPU加速工具。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Dict, Tuple

import numpy as np

from .compute_engine import GPUComputeEngine
from .data_structures import ComputeBackend

try:  # pragma: no cover
    import cupy as cp  # type: ignore
except Exception:  # pragma: no cover
    cp = None


class KrigingGPUAccelerator:
    """提供克里金关键步骤的并行加速实现。"""

    def __init__(self, compute_engine: GPUComputeEngine):
        self.compute_engine = compute_engine

    def _select_array_module(self, backend: ComputeBackend):
        if backend == ComputeBackend.GPU and cp is not None:
            return cp
        return np

    def pairwise_distances(self, points: np.ndarray, prefer_gpu: bool = True) -> Tuple[np.ndarray, ComputeBackend, float]:
        points = np.asarray(points, dtype=float)
        backend = self.compute_engine._select_backend(prefer_gpu, int(points.size))
        xp = self._select_array_module(backend)
        start = perf_counter()

        d_points, _ = self.compute_engine.memory_manager.to_device(points, backend)
        diff = d_points[:, None, :] - d_points[None, :, :]
        dist = xp.sqrt(xp.sum(diff * diff, axis=2))
        host_dist, _ = self.compute_engine.memory_manager.to_host(dist, backend)

        elapsed_ms = (perf_counter() - start) * 1000
        self.compute_engine.performance_monitor.record("kriging_pairwise_distance", backend, elapsed_ms, int(points.size))
        return host_dist, backend, elapsed_ms

    def semivariogram(
        self,
        points: np.ndarray,
        values: np.ndarray,
        bins: int = 12,
        max_range: float | None = None,
        prefer_gpu: bool = True,
    ) -> Dict[str, object]:
        points = np.asarray(points, dtype=float)
        values = np.asarray(values, dtype=float)
        if points.shape[0] != values.shape[0]:
            raise ValueError("点数量与数值数量不一致")

        dist, backend, elapsed_ms = self.pairwise_distances(points, prefer_gpu=prefer_gpu)
        diff_val = values[:, None] - values[None, :]
        gamma = 0.5 * (diff_val ** 2)

        if max_range is None:
            max_range = float(np.max(dist)) * 0.6
        max_range = max(float(max_range), 1e-9)

        edges = np.linspace(0.0, max_range, bins + 1)
        lags = []
        semivariances = []
        counts = []

        for idx in range(bins):
            low = edges[idx]
            high = edges[idx + 1]
            mask = (dist >= low) & (dist < high)
            count = int(np.count_nonzero(mask))
            counts.append(count)
            lags.append(float((low + high) * 0.5))
            if count == 0:
                semivariances.append(0.0)
            else:
                semivariances.append(float(np.mean(gamma[mask])))

        return {
            "lags": lags,
            "semivariance": semivariances,
            "pair_counts": counts,
            "backend": backend.value,
            "elapsed_ms": round(elapsed_ms, 4),
            "max_range": max_range,
        }

    def fit_variogram_parameters(
        self,
        points: np.ndarray,
        values: np.ndarray,
        bins: int = 12,
        prefer_gpu: bool = True,
    ) -> Dict[str, object]:
        """基于经验变异函数进行参数拟合。"""
        variogram = self.semivariogram(points, values, bins=bins, prefer_gpu=prefer_gpu)
        lags = np.asarray(variogram["lags"], dtype=float)
        gamma = np.asarray(variogram["semivariance"], dtype=float)
        mask = gamma > 0
        if not np.any(mask):
            return {
                "sill": 1.0,
                "range": 1.0,
                "nugget": 0.0,
                "backend": variogram["backend"],
                "loss": 0.0,
            }

        lags_fit = lags[mask]
        gamma_fit = gamma[mask]
        sill = float(np.max(gamma_fit))
        range_ = float(max(np.median(lags_fit), 1e-6))
        nugget = float(max(np.min(gamma_fit), 0.0))

        model = nugget + sill * (1.0 - np.exp(-lags_fit / range_))
        loss = float(np.mean((model - gamma_fit) ** 2))
        return {
            "sill": sill,
            "range": range_,
            "nugget": nugget,
            "backend": variogram["backend"],
            "loss": round(loss, 6),
        }

    def covariance_matrix(
        self,
        points: np.ndarray,
        sill: float,
        range_: float,
        nugget: float = 0.0,
        prefer_gpu: bool = True,
    ) -> Dict[str, object]:
        points = np.asarray(points, dtype=float)
        dist, backend, elapsed_ms = self.pairwise_distances(points, prefer_gpu=prefer_gpu)

        range_safe = max(float(range_), 1e-9)
        cov = sill * np.exp(-dist / range_safe)
        np.fill_diagonal(cov, sill + nugget)

        self.compute_engine.performance_monitor.record("kriging_covariance", backend, elapsed_ms, int(points.size))
        return {
            "covariance": cov,
            "backend": backend.value,
            "elapsed_ms": round(elapsed_ms, 4),
        }

    def solve_weights(
        self,
        covariance_matrix: np.ndarray,
        covariance_vector: np.ndarray,
        prefer_gpu: bool = True,
    ) -> Dict[str, object]:
        a = np.asarray(covariance_matrix, dtype=float)
        b = np.asarray(covariance_vector, dtype=float)
        if b.ndim == 1:
            b = b.reshape(-1, 1)

        result = self.compute_engine.solve_linear_system(a, b, prefer_gpu=prefer_gpu)
        weights = np.asarray(result.payload["result"]).reshape(-1)
        return {
            "weights": weights,
            "backend": result.backend.value,
            "elapsed_ms": round(result.elapsed_ms, 4),
        }

    def batch_predict(
        self,
        sample_points: np.ndarray,
        sample_values: np.ndarray,
        target_points: np.ndarray,
        sill: float,
        range_: float,
        nugget: float = 0.0,
        prefer_gpu: bool = True,
    ) -> Dict[str, object]:
        sample_points = np.asarray(sample_points, dtype=float)
        sample_values = np.asarray(sample_values, dtype=float).reshape(-1)
        target_points = np.asarray(target_points, dtype=float)

        cov_data = self.covariance_matrix(sample_points, sill=sill, range_=range_, nugget=nugget, prefer_gpu=prefer_gpu)
        cov_mat = np.asarray(cov_data["covariance"], dtype=float)
        cov_inv = np.linalg.inv(cov_mat)

        predictions = []
        variances = []

        for point in target_points:
            d = np.sqrt(np.sum((sample_points - point) ** 2, axis=1))
            cov_vec = sill * np.exp(-d / max(float(range_), 1e-9))
            weights = cov_inv @ cov_vec
            pred = float(weights @ sample_values)
            var = float(max(sill + nugget - cov_vec @ weights, 0.0))
            predictions.append(pred)
            variances.append(var)

        backend = cov_data["backend"]
        return {
            "prediction": np.asarray(predictions, dtype=float),
            "variance": np.asarray(variances, dtype=float),
            "backend": backend,
            "target_count": int(target_points.shape[0]),
        }

    def block_predict(
        self,
        sample_points: np.ndarray,
        sample_values: np.ndarray,
        target_points: np.ndarray,
        sill: float,
        range_: float,
        nugget: float = 0.0,
        block_size: int = 4096,
        prefer_gpu: bool = True,
    ) -> Dict[str, object]:
        """大数据分块预测，降低单次显存/内存压力。"""
        target_points = np.asarray(target_points, dtype=float)
        blocks = self.compute_engine.split_workload(int(target_points.shape[0]), block_size)

        predictions: list[np.ndarray] = []
        variances: list[np.ndarray] = []
        backend = "cpu"
        for start, end in blocks:
            result = self.batch_predict(
                sample_points=sample_points,
                sample_values=sample_values,
                target_points=target_points[start:end],
                sill=sill,
                range_=range_,
                nugget=nugget,
                prefer_gpu=prefer_gpu,
            )
            backend = str(result["backend"])
            predictions.append(np.asarray(result["prediction"], dtype=float))
            variances.append(np.asarray(result["variance"], dtype=float))

        prediction_all = np.concatenate(predictions) if predictions else np.array([], dtype=float)
        variance_all = np.concatenate(variances) if variances else np.array([], dtype=float)
        return {
            "prediction": prediction_all,
            "variance": variance_all,
            "backend": backend,
            "target_count": int(target_points.shape[0]),
            "block_count": len(blocks),
            "block_size": int(max(1, block_size)),
        }

    def parallel_sampling(self, sample_values: np.ndarray, sample_count: int = 256) -> Dict[str, object]:
        """并行采样统计，用于批量不确定性估计。"""
        values = np.asarray(sample_values, dtype=float).reshape(-1)
        if values.size == 0:
            raise ValueError("样本值为空")
        sample_count = max(1, int(sample_count))
        rng = np.random.default_rng(42)

        def _one_sample(_: int) -> float:
            idx = rng.integers(0, values.size, size=max(2, values.size // 2))
            return float(np.mean(values[idx]))

        with ThreadPoolExecutor(max_workers=4) as pool:
            means = list(pool.map(_one_sample, range(sample_count)))

        arr = np.asarray(means, dtype=float)
        return {
            "sample_count": sample_count,
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "p05": float(np.quantile(arr, 0.05)),
            "p95": float(np.quantile(arr, 0.95)),
        }

    def parallel_validation(self, truth: np.ndarray, pred: np.ndarray) -> Dict[str, float]:
        """并行验证指标计算。"""
        y_true = np.asarray(truth, dtype=float).reshape(-1)
        y_pred = np.asarray(pred, dtype=float).reshape(-1)
        if y_true.shape != y_pred.shape:
            raise ValueError("真实值与预测值长度不一致")
        err = y_pred - y_true
        rmse = float(np.sqrt(np.mean(err ** 2)))
        mae = float(np.mean(np.abs(err)))
        mape = float(np.mean(np.abs(err / np.where(np.abs(y_true) < 1e-9, 1.0, y_true))) * 100.0)
        return {"rmse": rmse, "mae": mae, "mape": mape}
