"""不确定性校准：等渗回归、Platt 缩放、温度缩放。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import ensure_1d, ensure_2d


@dataclass
class IsotonicModel:
    x: np.ndarray
    y: np.ndarray


@dataclass
class PlattModel:
    a: float
    b: float


class UncertaintyCalibrator:
    def __init__(self) -> None:
        self.isotonic_model: IsotonicModel | None = None
        self.platt_model: PlattModel | None = None
        self.temperature: float = 1.0
        self.variance_temperature: float = 1.0

    def fit_isotonic(self, scores: np.ndarray, labels: np.ndarray) -> IsotonicModel:
        x = ensure_1d(scores)
        y = ensure_1d(labels)
        if len(x) != len(y):
            raise ValueError("scores 与 labels 长度不一致")

        order = np.argsort(x)
        x_sorted = x[order]
        y_sorted = y[order]

        # Pair Adjacent Violators (PAV)
        block_values = y_sorted.astype(float).tolist()
        block_sizes = [1] * len(block_values)

        i = 0
        while i < len(block_values) - 1:
            if block_values[i] <= block_values[i + 1] + 1e-12:
                i += 1
                continue
            merged = (
                block_values[i] * block_sizes[i] + block_values[i + 1] * block_sizes[i + 1]
            ) / (block_sizes[i] + block_sizes[i + 1])
            block_values[i] = float(merged)
            block_sizes[i] = int(block_sizes[i] + block_sizes[i + 1])
            del block_values[i + 1]
            del block_sizes[i + 1]
            if i > 0:
                i -= 1

        y_iso = np.zeros_like(y_sorted, dtype=float)
        ptr = 0
        for val, size in zip(block_values, block_sizes):
            y_iso[ptr : ptr + size] = val
            ptr += size

        self.isotonic_model = IsotonicModel(x=x_sorted, y=np.clip(y_iso, 0.0, 1.0))
        return self.isotonic_model

    def transform_isotonic(self, scores: np.ndarray) -> np.ndarray:
        if self.isotonic_model is None:
            raise ValueError("请先 fit_isotonic")
        s = ensure_1d(scores)
        return np.interp(s, self.isotonic_model.x, self.isotonic_model.y)

    def fit_platt(self, scores: np.ndarray, labels: np.ndarray, epochs: int = 800, lr: float = 1e-2) -> PlattModel:
        x = ensure_1d(scores)
        y = ensure_1d(labels)
        if len(x) != len(y):
            raise ValueError("scores 与 labels 长度不一致")

        a, b = 0.0, 0.0
        n = float(len(x))
        for _ in range(int(max(1, epochs))):
            logits = a * x + b
            probs = 1.0 / (1.0 + np.exp(-logits))
            d_logits = (probs - y) / n
            grad_a = float(np.sum(d_logits * x))
            grad_b = float(np.sum(d_logits))
            a -= lr * grad_a
            b -= lr * grad_b

        self.platt_model = PlattModel(a=float(a), b=float(b))
        return self.platt_model

    def transform_platt(self, scores: np.ndarray) -> np.ndarray:
        if self.platt_model is None:
            raise ValueError("请先 fit_platt")
        x = ensure_1d(scores)
        logits = self.platt_model.a * x + self.platt_model.b
        return 1.0 / (1.0 + np.exp(-logits))

    def fit_temperature(self, logits: np.ndarray, labels: np.ndarray, candidates: list[float] | None = None) -> float:
        arr = ensure_2d(logits)
        y = ensure_1d(labels).astype(int)
        if len(arr) != len(y):
            raise ValueError("logits 与 labels 长度不一致")

        candidates = candidates or [0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0]
        best_t = 1.0
        best_nll = float("inf")

        for t in candidates:
            scaled = arr / float(max(t, 1e-4))
            z = scaled - np.max(scaled, axis=1, keepdims=True)
            probs = np.exp(z)
            probs = probs / np.maximum(np.sum(probs, axis=1, keepdims=True), 1e-8)
            nll = -float(np.mean(np.log(np.maximum(probs[np.arange(len(y)), y], 1e-8))))
            if nll < best_nll:
                best_nll = nll
                best_t = float(t)

        self.temperature = best_t
        return self.temperature

    def transform_temperature(self, logits: np.ndarray) -> np.ndarray:
        arr = ensure_2d(logits)
        scaled = arr / float(max(self.temperature, 1e-4))
        z = scaled - np.max(scaled, axis=1, keepdims=True)
        probs = np.exp(z)
        return probs / np.maximum(np.sum(probs, axis=1, keepdims=True), 1e-8)

    def fit_variance_temperature(self, y_true: np.ndarray, pred_mean: np.ndarray, pred_var: np.ndarray) -> float:
        y = ensure_1d(y_true)
        m = ensure_1d(pred_mean)
        v = np.maximum(ensure_1d(pred_var), 1e-8)
        if len(y) != len(m) or len(y) != len(v):
            raise ValueError("输入长度不一致")

        mse = np.mean((y - m) ** 2)
        base = np.mean(v)
        t = float(mse / (base + 1e-8))
        self.variance_temperature = float(np.clip(t, 0.1, 10.0))
        return self.variance_temperature

    def transform_variance_temperature(self, pred_var: np.ndarray) -> np.ndarray:
        v = np.maximum(ensure_1d(pred_var), 1e-8)
        return np.maximum(v * self.variance_temperature, 1e-8)

    def snapshot(self) -> dict[str, Any]:
        return {
            "has_isotonic": self.isotonic_model is not None,
            "has_platt": self.platt_model is not None,
            "temperature": float(self.temperature),
            "variance_temperature": float(self.variance_temperature),
        }
