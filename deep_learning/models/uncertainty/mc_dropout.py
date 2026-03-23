"""MC Dropout 不确定性量化实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import (
    DropoutType,
    PredictiveMoments,
    adaptive_t_value,
    confidence_interval,
    decompose_uncertainty,
    ensure_1d,
    ensure_2d,
)


@dataclass
class MCDropoutConfig:
    in_dim: int
    hidden_dim: int = 32
    dropout_rate: float = 0.2
    dropout_type: DropoutType = "standard"
    seed: int = 42


class DropoutLayer:
    def __init__(self, rate: float = 0.2, kind: DropoutType = "standard", seed: int = 42) -> None:
        self.rate = float(np.clip(rate, 0.0, 0.8))
        self.kind = kind
        self.rng = np.random.default_rng(seed)
        self._variational_mask: np.ndarray | None = None

    def _make_mask(self, x: np.ndarray) -> np.ndarray:
        keep = 1.0 - self.rate
        if keep <= 1e-8:
            return np.zeros_like(x, dtype=float)

        if self.kind == "spatial":
            if x.ndim != 2:
                return (self.rng.uniform(0.0, 1.0, size=x.shape) < keep).astype(float) / keep
            base = (self.rng.uniform(0.0, 1.0, size=(1, x.shape[1])) < keep).astype(float)
            return np.repeat(base, x.shape[0], axis=0) / keep

        if self.kind == "variational":
            if self._variational_mask is None or self._variational_mask.shape != x.shape:
                self._variational_mask = (self.rng.uniform(0.0, 1.0, size=x.shape) < keep).astype(float) / keep
            return self._variational_mask

        return (self.rng.uniform(0.0, 1.0, size=x.shape) < keep).astype(float) / keep

    def forward(self, x: np.ndarray, training: bool = True, force_active: bool = False) -> np.ndarray:
        arr = np.asarray(x, dtype=float)
        if not training and not force_active:
            return arr
        mask = self._make_mask(arr)
        return arr * mask


class MCDropoutRegressor:
    """两层网络 + Dropout，训练后通过 T 次采样进行推理。"""

    def __init__(self, config: MCDropoutConfig) -> None:
        self.config = config
        self.rng = np.random.default_rng(config.seed)

        h = int(max(4, config.hidden_dim))
        d = int(config.in_dim)

        self.w1 = self.rng.normal(0.0, 0.12, size=(d, h))
        self.b1 = np.zeros(h, dtype=float)
        self.w_mean = self.rng.normal(0.0, 0.12, size=(h, 1))
        self.b_mean = np.zeros(1, dtype=float)
        self.w_logvar = self.rng.normal(0.0, 0.12, size=(h, 1))
        self.b_logvar = np.zeros(1, dtype=float)

        self.dropout = DropoutLayer(rate=config.dropout_rate, kind=config.dropout_type, seed=config.seed + 7)
        self.history: list[dict[str, float]] = []

    def _forward(self, x: np.ndarray, training: bool, keep_dropout: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        z1 = x @ self.w1 + self.b1
        h = np.tanh(z1)
        h_drop = self.dropout.forward(h, training=training, force_active=keep_dropout)
        mean = (h_drop @ self.w_mean + self.b_mean).reshape(-1)
        logvar = np.clip((h_drop @ self.w_logvar + self.b_logvar).reshape(-1), -8.0, 5.0)
        var = np.exp(logvar) + 1e-6
        return h, h_drop, mean, var

    def fit(self, x: np.ndarray, y: np.ndarray, epochs: int = 180, lr: float = 8e-3, nll_weight: float = 0.4) -> dict[str, Any]:
        features = ensure_2d(x)
        target = ensure_1d(y)
        n = float(len(target))
        weight = float(np.clip(nll_weight, 0.0, 1.0))

        for epoch in range(int(max(1, epochs))):
            h, h_drop, mean, var = self._forward(features, training=True, keep_dropout=False)
            err = mean - target

            d_mse_mean = 2.0 * err / n
            d_nll_mean = err / var / n
            d_mean = (1.0 - weight) * d_mse_mean + weight * d_nll_mean
            d_logvar = weight * 0.5 * (1.0 - (err ** 2) / var) / n

            grad_w_mean = h_drop.T @ d_mean[:, None]
            grad_b_mean = np.sum(d_mean)
            grad_w_logvar = h_drop.T @ d_logvar[:, None]
            grad_b_logvar = np.sum(d_logvar)

            d_hdrop = d_mean[:, None] @ self.w_mean.T + d_logvar[:, None] @ self.w_logvar.T
            keep = 1.0 - self.config.dropout_rate
            if keep <= 1e-8:
                keep = 1e-8
            d_h = d_hdrop * keep
            dz1 = d_h * (1.0 - h ** 2)

            grad_w1 = features.T @ dz1
            grad_b1 = np.sum(dz1, axis=0)

            self.w_mean -= lr * grad_w_mean
            self.b_mean -= lr * grad_b_mean
            self.w_logvar -= lr * grad_w_logvar
            self.b_logvar -= lr * grad_b_logvar
            self.w1 -= lr * grad_w1
            self.b1 -= lr * grad_b1

            mse = float(np.mean(err ** 2))
            nll = float(np.mean(0.5 * np.log(2.0 * np.pi * var) + 0.5 * (err ** 2) / var))
            total = (1.0 - weight) * mse + weight * nll
            self.history.append({"epoch": float(epoch + 1), "mse": mse, "nll": nll, "total": float(total)})

        return {
            "epochs": int(max(1, epochs)),
            "final_loss": float(self.history[-1]["total"]),
            "final_nll": float(self.history[-1]["nll"]),
            "best_total_loss": float(min(r["total"] for r in self.history)),
        }

    def predict(self, x: np.ndarray, t: int = 50, confidence: float = 0.95) -> dict[str, Any]:
        features = ensure_2d(x)
        steps = int(max(2, t))
        means = np.zeros((steps, len(features)), dtype=float)
        vars_ = np.zeros((steps, len(features)), dtype=float)

        for i in range(steps):
            _, _, mean_i, var_i = self._forward(features, training=False, keep_dropout=True)
            means[i] = mean_i
            vars_[i] = var_i

        moments: PredictiveMoments = decompose_uncertainty(means, vars_)
        lower, upper = confidence_interval(moments.mean, moments.variance, confidence=confidence)
        return {
            "mean": moments.mean,
            "variance": moments.variance,
            "aleatoric": moments.aleatoric,
            "epistemic": moments.epistemic,
            "lower": lower,
            "upper": upper,
            "t": steps,
            "confidence": float(confidence),
        }

    def t_sensitivity(self, x: np.ndarray, t_values: list[int]) -> list[dict[str, float]]:
        features = ensure_2d(x)
        result: list[dict[str, float]] = []
        for t in sorted(set(int(max(2, v)) for v in t_values)):
            pred = self.predict(features, t=t)
            result.append(
                {
                    "t": float(t),
                    "mean_epistemic": float(np.mean(pred["epistemic"])),
                    "mean_total_variance": float(np.mean(pred["variance"])),
                }
            )
        return result

    def adaptive_t(self, x: np.ndarray, max_t: int = 100, tolerance: float = 0.02, min_t: int = 10) -> dict[str, Any]:
        features = ensure_2d(x)
        max_t = int(max(max_t, min_t + 2))

        curve: list[float] = []
        for t in range(2, max_t + 1):
            pred = self.predict(features, t=t)
            curve.append(float(np.mean(pred["epistemic"])))

        best_t = adaptive_t_value(curve, tolerance=tolerance, min_t=min_t)
        return {
            "best_t": int(best_t),
            "curve": curve,
            "tolerance": float(tolerance),
            "min_t": int(min_t),
        }
