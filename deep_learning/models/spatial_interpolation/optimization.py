"""Performance optimization utilities for spatial interpolation models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from deep_learning.models.registry import ModelExporter


@dataclass
class BatchOptimizationResult:
    batch_size: int
    estimated_latency_ms: float


class BatchOptimizer:
    def suggest(self, sample_count: int, feature_dim: int, memory_budget_mb: float = 256.0) -> BatchOptimizationResult:
        per_sample_bytes = max(1, feature_dim) * 8
        max_batch = int((memory_budget_mb * 1024 * 1024) / per_sample_bytes)
        batch = max(1, min(sample_count, max_batch))
        latency = 0.05 * batch + 2.0
        return BatchOptimizationResult(batch_size=batch, estimated_latency_ms=latency)


class MemoryOptimizer:
    def optimize(self, array: np.ndarray, dtype: str = "float32") -> np.ndarray:
        if dtype not in {"float32", "float16"}:
            raise ValueError("dtype must be float32 or float16")
        return np.asarray(array, dtype=dtype)


class ComputeGraphOptimizer:
    def fuse_linear_relu(self, x: np.ndarray, weight: np.ndarray, bias: np.ndarray) -> np.ndarray:
        return np.maximum(0.0, x @ weight + bias)


class GPUAccelerator:
    def available(self) -> bool:
        try:
            import torch

            return bool(torch.cuda.is_available() or (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()))
        except Exception:
            return False

    def run(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)


class ModelCompressor:
    def prune(self, weights: np.ndarray, ratio: float = 0.2) -> np.ndarray:
        w = np.asarray(weights, dtype=float).copy()
        ratio = float(np.clip(ratio, 0.0, 1.0))
        threshold = np.quantile(np.abs(w), ratio)
        w[np.abs(w) < threshold] = 0.0
        return w

    def quantize(self, weights: np.ndarray, bits: int = 8) -> np.ndarray:
        w = np.asarray(weights, dtype=float)
        bits = max(2, int(bits))
        levels = 2**bits - 1
        mn, mx = float(np.min(w)), float(np.max(w))
        if abs(mx - mn) < 1e-12:
            return np.zeros_like(w)
        normalized = (w - mn) / (mx - mn)
        q = np.round(normalized * levels) / levels
        return q * (mx - mn) + mn

    def distill(self, teacher_pred: np.ndarray, alpha: float = 0.7) -> np.ndarray:
        t = np.asarray(teacher_pred, dtype=float)
        mean_t = float(np.mean(t))
        return alpha * t + (1.0 - alpha) * mean_t


class InferenceAccelerator:
    def __init__(self) -> None:
        self.exporter = ModelExporter()

    def export_onnx(self, model: Any, path: str) -> str:
        return self.exporter.export_onnx(model, path)

    def export_torchscript(self, model: Any, path: str) -> str:
        return self.exporter.export_torchscript(model, path)

    def export_tensorrt_hint(self) -> dict[str, str]:
        return {
            "status": "optional",
            "note": "TensorRT conversion is optional and environment dependent.",
        }
