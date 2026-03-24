"""Spatiotemporal inference performance optimization utilities."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np


@dataclass
class LongSequenceOutput:
    mean: np.ndarray
    variance: np.ndarray
    windows: int
    chunk_size: int
    overlap: int


class SpatioTemporalPerformanceOptimizer:
    """轻量性能优化器：内存压缩、GPU探测、推理加速与长序列优化。"""

    def __init__(self, seed: int = 42) -> None:
        self.seed = int(seed)
        self._cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def optimize_memory(self, coords: np.ndarray, series: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
        c64 = np.asarray(coords, dtype=np.float64)
        s64 = np.asarray(series, dtype=np.float64)
        before = int(c64.nbytes + s64.nbytes)

        c32 = np.ascontiguousarray(c64.astype(np.float32, copy=False))
        s32 = np.ascontiguousarray(s64.astype(np.float32, copy=False))
        after = int(c32.nbytes + s32.nbytes)

        ratio = float(after / max(before, 1))
        return c32, s32, {
            "coords_dtype": str(c32.dtype),
            "series_dtype": str(s32.dtype),
            "bytes_before": before,
            "bytes_after": after,
            "compression_ratio": ratio,
            "memory_saved_pct": float((1.0 - ratio) * 100.0),
        }

    def detect_gpu(self) -> dict[str, Any]:
        # 默认路径：NumPy模型在CPU上执行。这里做可用性探测并回传给上层。
        result = {
            "enabled": False,
            "backend": "cpu",
            "device_name": "cpu",
        }
        try:
            import cupy as cp  # type: ignore

            if int(cp.cuda.runtime.getDeviceCount()) > 0:
                dev = cp.cuda.Device()
                props = cp.cuda.runtime.getDeviceProperties(dev.id)
                name = props.get("name", b"cuda").decode() if isinstance(props.get("name"), bytes) else str(props.get("name", "cuda"))
                result.update({"enabled": True, "backend": "cupy", "device_name": name})
                return result
        except Exception:
            pass

        try:
            import torch  # type: ignore

            if bool(torch.cuda.is_available()):
                result.update({"enabled": True, "backend": "torch-cuda", "device_name": str(torch.cuda.get_device_name(0))})
            elif bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available()):
                result.update({"enabled": True, "backend": "torch-mps", "device_name": "apple-mps"})
        except Exception:
            pass

        return result

    def accelerated_forward(
        self,
        model: Any,
        coords: np.ndarray,
        series: np.ndarray,
        fusion_strategy: str = "gating",
    ) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
        key = f"{hash(np.asarray(coords).tobytes())}:{hash(np.asarray(series).tobytes())}:{fusion_strategy}"
        if key in self._cache:
            mean, var = self._cache[key]
            return mean.copy(), var.copy(), {"cached": True, "latency_ms": 0.0}

        st = perf_counter()
        if getattr(model, "model_name", "") == "st_transformer":
            out = model.forward(coords, series, fusion_strategy=fusion_strategy)
        else:
            out = model.forward(coords, series)
        latency = float((perf_counter() - st) * 1000.0)

        mean = np.asarray(out.mean, dtype=float)
        var = np.asarray(out.variance, dtype=float)
        self._cache[key] = (mean.copy(), var.copy())
        return mean, var, {"cached": False, "latency_ms": latency}

    def long_sequence_predict(
        self,
        model: Any,
        coords: np.ndarray,
        long_series: np.ndarray,
        pred_horizon: int,
        chunk_size: int = 48,
        overlap: int = 12,
        fusion_strategy: str = "gating",
    ) -> LongSequenceOutput:
        c = np.asarray(coords, dtype=float)
        s = np.asarray(long_series, dtype=float)
        if s.ndim != 3:
            raise ValueError("long_series must be [n_nodes, seq_len, n_features]")

        seq_len = int(s.shape[1])
        chunk = int(max(8, chunk_size))
        ov = int(np.clip(overlap, 0, max(0, chunk - 4)))
        step = max(1, chunk - ov)

        if seq_len <= chunk:
            mean, var, _ = self.accelerated_forward(model, c, s, fusion_strategy=fusion_strategy)
            return LongSequenceOutput(mean=mean, variance=var, windows=1, chunk_size=chunk, overlap=ov)

        means: list[np.ndarray] = []
        vars_: list[np.ndarray] = []
        weights: list[float] = []
        horizon = int(max(1, pred_horizon))

        for start in range(0, seq_len - chunk + 1, step):
            window = s[:, start : start + chunk, :]
            mean, var, _ = self.accelerated_forward(model, c, window, fusion_strategy=fusion_strategy)
            if mean.shape[1] != horizon:
                if mean.shape[1] > horizon:
                    mean = mean[:, :horizon]
                    var = var[:, :horizon]
                else:
                    pad = horizon - mean.shape[1]
                    mean = np.concatenate([mean, np.repeat(mean[:, -1:], pad, axis=1)], axis=1)
                    var = np.concatenate([var, np.repeat(var[:, -1:], pad, axis=1)], axis=1)
            means.append(mean)
            vars_.append(var)
            weights.append(float(start + chunk))

        w = np.asarray(weights, dtype=float)
        w = w / np.maximum(np.sum(w), 1e-8)
        stacked_mean = np.stack(means, axis=0)
        stacked_var = np.stack(vars_, axis=0)

        final_mean = np.sum(stacked_mean * w[:, None, None], axis=0)
        final_var = np.sum(stacked_var * w[:, None, None], axis=0)
        return LongSequenceOutput(
            mean=final_mean,
            variance=np.maximum(final_var, 1e-6),
            windows=len(means),
            chunk_size=chunk,
            overlap=ov,
        )
