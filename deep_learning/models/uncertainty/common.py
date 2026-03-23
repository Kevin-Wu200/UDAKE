"""不确定性量化模块通用工具。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

DropoutType = Literal["standard", "spatial", "variational"]
ActivationType = Literal["relu", "softplus"]


@dataclass
class PredictiveMoments:
    mean: np.ndarray
    variance: np.ndarray
    aleatoric: np.ndarray
    epistemic: np.ndarray


def ensure_2d(array: np.ndarray | list[float] | list[list[float]]) -> np.ndarray:
    arr = np.asarray(array, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError("输入必须是一维或二维数组")
    return arr


def ensure_1d(array: np.ndarray | list[float]) -> np.ndarray:
    arr = np.asarray(array, dtype=float).reshape(-1)
    return arr


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def softplus(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    return np.log1p(np.exp(-np.abs(arr))) + np.maximum(arr, 0.0)


def confidence_interval(
    mean: np.ndarray,
    variance: np.ndarray,
    confidence: float = 0.95,
) -> tuple[np.ndarray, np.ndarray]:
    mu = ensure_1d(mean)
    var = np.maximum(ensure_1d(variance), 1e-8)
    conf = float(np.clip(confidence, 0.5, 0.9999))
    alpha = 0.5 * (1.0 + conf)
    z_value = abs(float(np.sqrt(2.0) * math.erfinv(2.0 * alpha - 1.0))) if hasattr(math, "erfinv") else 1.96
    delta = z_value * np.sqrt(var)
    return mu - delta, mu + delta


def decompose_uncertainty(sample_means: np.ndarray, sample_vars: np.ndarray) -> PredictiveMoments:
    means = np.asarray(sample_means, dtype=float)
    vars_ = np.maximum(np.asarray(sample_vars, dtype=float), 1e-8)
    if means.ndim != 2 or vars_.ndim != 2:
        raise ValueError("sample_means/sample_vars 必须为二维 [T, N]")
    if means.shape != vars_.shape:
        raise ValueError("sample_means 与 sample_vars 形状不一致")

    pred_mean = means.mean(axis=0)
    aleatoric = vars_.mean(axis=0)
    epistemic = means.var(axis=0)
    total = np.maximum(aleatoric + epistemic, 1e-8)
    return PredictiveMoments(mean=pred_mean, variance=total, aleatoric=aleatoric, epistemic=epistemic)


def gaussian_nll(y_true: np.ndarray, mean: np.ndarray, variance: np.ndarray) -> float:
    y = ensure_1d(y_true)
    mu = ensure_1d(mean)
    var = np.maximum(ensure_1d(variance), 1e-8)
    nll = 0.5 * np.log(2.0 * np.pi * var) + 0.5 * ((y - mu) ** 2) / var
    return float(np.mean(nll))


def kl_diag_gaussian(mu: np.ndarray, sigma: np.ndarray, prior_sigma: float = 1.0) -> float:
    m = np.asarray(mu, dtype=float)
    s = np.maximum(np.asarray(sigma, dtype=float), 1e-8)
    p2 = float(max(prior_sigma, 1e-8)) ** 2
    kl = np.log(np.sqrt(p2) / s) + (s ** 2 + m ** 2) / (2.0 * p2) - 0.5
    return float(np.sum(kl))


def adaptive_t_value(curve: list[float], tolerance: float = 0.02, window: int = 4, min_t: int = 10) -> int:
    if not curve:
        return min_t
    if len(curve) <= max(window, min_t):
        return len(curve)

    start = max(min_t, window + 1)
    for t in range(start, len(curve) + 1):
        now = np.mean(curve[t - window : t])
        prev = np.mean(curve[t - window - 1 : t - 1])
        denom = abs(prev) + 1e-8
        if abs(now - prev) / denom <= tolerance:
            return t
    return len(curve)


def temperature_scale_variance(variance: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    t = float(max(temperature, 1e-4))
    return np.maximum(np.asarray(variance, dtype=float) * t, 1e-8)
