"""MC Dropout 不确定性量化实现。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import copy
import hashlib
import json
import threading
from typing import Any, Sequence

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
        self.feature_names: list[str] = [f"feature_{i}" for i in range(int(config.in_dim))]
        self._runtime_feature_mean = np.zeros(int(config.in_dim), dtype=float)
        self._runtime_feature_std = np.ones(int(config.in_dim), dtype=float)
        self._has_runtime_stats = False
        self._predict_cache_lock = threading.Lock()
        self._predict_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._predict_cache_size = 24
        self._predict_cache_hits = 0
        self._predict_cache_misses = 0
        self._batch_cache_lock = threading.Lock()
        self._batch_result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._batch_cache_size = 16
        self._batch_cache_hits = 0
        self._batch_cache_misses = 0

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
        conf = float(confidence)
        cache_key = self._predict_cache_key(features, steps=steps, confidence=conf)
        cached = self._predict_cache_get(cache_key)
        if cached is not None:
            result = dict(cached)
            result["performance"] = {
                **dict(result.get("performance", {})),
                "cache_hit": True,
                "sampling_strategy": "vectorized",
                "cache_metrics": self._predict_cache_metrics(),
            }
            return result

        means, vars_ = self._sample_forward_passes(features, steps=steps)
        moments: PredictiveMoments = decompose_uncertainty(means, vars_)
        lower, upper = confidence_interval(moments.mean, moments.variance, confidence=conf)
        result = {
            "mean": moments.mean,
            "variance": moments.variance,
            "aleatoric": moments.aleatoric,
            "epistemic": moments.epistemic,
            "lower": lower,
            "upper": upper,
            "t": steps,
            "confidence": conf,
            "performance": {
                "cache_hit": False,
                "sampling_strategy": "vectorized",
                "cache_metrics": self._predict_cache_metrics(),
            },
        }
        self._predict_cache_set(cache_key, result)
        return result

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

    def preprocess_mc_dropout_data(
        self,
        features: np.ndarray | list[list[float]],
        *,
        feature_names: list[str] | None = None,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        x_raw = ensure_2d(np.asarray(features, dtype=float))
        expected_dim = int(self.config.in_dim)
        if x_raw.shape[1] != expected_dim:
            raise ValueError(f"输入维度不匹配：期望 {expected_dim}，实际 {x_raw.shape[1]}")

        names = list(feature_names) if feature_names is not None else [f"feature_{i}" for i in range(x_raw.shape[1])]
        if len(names) != x_raw.shape[1]:
            raise ValueError("feature_names 长度与特征维度不一致")

        if use_training_stats and self._has_runtime_stats:
            mean = np.asarray(self._runtime_feature_mean, dtype=float)
            std = np.asarray(self._runtime_feature_std, dtype=float)
            stats_source = "runtime"
        else:
            mean = np.mean(x_raw, axis=0)
            std = np.std(x_raw, axis=0)
            std = np.where(std > 1e-8, std, 1.0)
            self._runtime_feature_mean = mean.astype(float)
            self._runtime_feature_std = std.astype(float)
            self._has_runtime_stats = True
            stats_source = "batch"

        x_scaled = (x_raw - mean.reshape(1, -1)) / std.reshape(1, -1)
        self.feature_names = list(names)
        return {
            "raw_features": x_raw,
            "processed_features": x_scaled,
            "feature_names": list(names),
            "scaler": {
                "mean": [float(v) for v in mean.tolist()],
                "std": [float(v) for v in std.tolist()],
                "source": stats_source,
            },
            "validation": {
                "is_valid": True,
                "sample_count": int(x_raw.shape[0]),
                "feature_dim": int(x_raw.shape[1]),
                "stats_source": stats_source,
            },
        }

    def predict_mc_dropout(
        self,
        features: np.ndarray | list[list[float]],
        *,
        t: int = 50,
        confidence: float = 0.95,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_mc_dropout_data(features, use_training_stats=use_training_stats)
        pred = self.predict(
            np.asarray(pre["processed_features"], dtype=float),
            t=t,
            confidence=confidence,
        )
        pred["preprocess"] = {
            "scaler": dict(pre["scaler"]),
            "validation": dict(pre["validation"]),
            "feature_names": list(pre["feature_names"]),
        }
        return pred

    def predict_mc_dropout_batch(
        self,
        features: np.ndarray | list[list[float]],
        *,
        t: int = 50,
        confidence: float = 0.95,
        batch_size: int = 128,
        use_training_stats: bool = True,
        optimize_memory: bool = True,
        use_result_cache: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_mc_dropout_data(features, use_training_stats=use_training_stats)
        pred = self.predict_batch(
            np.asarray(pre["processed_features"], dtype=float),
            t=t,
            confidence=confidence,
            batch_size=batch_size,
            optimize_memory=optimize_memory,
            use_result_cache=use_result_cache,
        )
        pred["preprocess"] = {
            "scaler": dict(pre["scaler"]),
            "validation": dict(pre["validation"]),
            "feature_names": list(pre["feature_names"]),
        }
        return pred

    def predict_batch(
        self,
        x: np.ndarray,
        *,
        t: int = 50,
        confidence: float = 0.95,
        batch_size: int = 128,
        optimize_memory: bool = True,
        use_result_cache: bool = True,
    ) -> dict[str, Any]:
        features = ensure_2d(x)
        steps = int(max(2, t))
        conf = float(confidence)
        chunk_size = int(max(1, batch_size))
        compact = bool(optimize_memory)
        cache_key = self._batch_cache_key(
            features=features,
            steps=steps,
            confidence=conf,
            batch_size=chunk_size,
            optimize_memory=compact,
        )
        if use_result_cache:
            cached = self._batch_cache_get(cache_key)
            if cached is not None:
                result = dict(cached)
                result["performance"] = {
                    **dict(result.get("performance", {})),
                    "cache_hit": True,
                    "batch_cache_metrics": self._batch_cache_metrics(),
                }
                return result

        mean_list: list[np.ndarray] = []
        var_list: list[np.ndarray] = []
        ale_list: list[np.ndarray] = []
        epi_list: list[np.ndarray] = []
        low_list: list[np.ndarray] = []
        up_list: list[np.ndarray] = []
        input_memory_bytes = 0

        for start in range(0, features.shape[0], chunk_size):
            end = min(start + chunk_size, features.shape[0])
            x_batch = np.asarray(features[start:end], dtype=np.float32 if compact else float)
            input_memory_bytes += int(x_batch.nbytes)
            pred = self.predict(np.asarray(x_batch, dtype=float), t=steps, confidence=conf)
            mean_list.append(np.asarray(pred["mean"], dtype=np.float32 if compact else float))
            var_list.append(np.asarray(pred["variance"], dtype=np.float32 if compact else float))
            ale_list.append(np.asarray(pred["aleatoric"], dtype=np.float32 if compact else float))
            epi_list.append(np.asarray(pred["epistemic"], dtype=np.float32 if compact else float))
            low_list.append(np.asarray(pred["lower"], dtype=np.float32 if compact else float))
            up_list.append(np.asarray(pred["upper"], dtype=np.float32 if compact else float))

        result = {
            "mean": np.concatenate(mean_list, axis=0) if mean_list else np.zeros((0,), dtype=np.float32),
            "variance": np.concatenate(var_list, axis=0) if var_list else np.zeros((0,), dtype=np.float32),
            "aleatoric": np.concatenate(ale_list, axis=0) if ale_list else np.zeros((0,), dtype=np.float32),
            "epistemic": np.concatenate(epi_list, axis=0) if epi_list else np.zeros((0,), dtype=np.float32),
            "lower": np.concatenate(low_list, axis=0) if low_list else np.zeros((0,), dtype=np.float32),
            "upper": np.concatenate(up_list, axis=0) if up_list else np.zeros((0,), dtype=np.float32),
            "t": steps,
            "confidence": conf,
            "performance": {
                "cache_hit": False,
                "sampling_strategy": "vectorized_batched",
                "batch_size": int(chunk_size),
                "batch_count": int((features.shape[0] + chunk_size - 1) // chunk_size),
                "sample_count": int(features.shape[0]),
                "optimize_memory": compact,
                "input_memory_bytes": int(input_memory_bytes),
                "result_memory_bytes": 0,
                "predict_cache_metrics": self._predict_cache_metrics(),
                "batch_cache_metrics": self._batch_cache_metrics(),
            },
        }
        result["performance"]["result_memory_bytes"] = int(
            np.asarray(result["mean"]).nbytes
            + np.asarray(result["variance"]).nbytes
            + np.asarray(result["aleatoric"]).nbytes
            + np.asarray(result["epistemic"]).nbytes
            + np.asarray(result["lower"]).nbytes
            + np.asarray(result["upper"]).nbytes
        )
        if use_result_cache:
            self._batch_cache_set(cache_key, result)
        return result

    def _named_parameter_arrays(self) -> list[tuple[str, np.ndarray]]:
        return [
            ("hidden.weight", np.asarray(self.w1, dtype=float)),
            ("hidden.bias", np.asarray(self.b1, dtype=float)),
            ("mean_head.weight", np.asarray(self.w_mean, dtype=float)),
            ("mean_head.bias", np.asarray(self.b_mean, dtype=float)),
            ("logvar_head.weight", np.asarray(self.w_logvar, dtype=float)),
            ("logvar_head.bias", np.asarray(self.b_logvar, dtype=float)),
        ]

    def explain_dropout_weights(self, top_k: int = 8) -> dict[str, Any]:
        """输出 Dropout 相关权重统计，用于权重解释。"""
        keep_prob = float(max(1e-8, 1.0 - float(self.config.dropout_rate)))
        summaries: list[dict[str, Any]] = []
        important_pool: list[tuple[float, str, int, float, float]] = []
        weak_pool: list[tuple[float, str, int, float, float]] = []

        for name, arr in self._named_parameter_arrays():
            flat = np.asarray(arr, dtype=float).reshape(-1)
            abs_flat = np.abs(flat)
            adjusted = abs_flat * keep_prob
            sparsity = float(np.mean(abs_flat < 1e-3)) if flat.size else 0.0
            summaries.append(
                {
                    "parameter": name,
                    "count": int(flat.size),
                    "shape": [int(v) for v in np.asarray(arr).shape],
                    "value_stats": {
                        "mean": float(np.mean(flat)) if flat.size else 0.0,
                        "std": float(np.std(flat)) if flat.size else 0.0,
                        "abs_mean": float(np.mean(abs_flat)) if flat.size else 0.0,
                        "p90_abs": float(np.quantile(abs_flat, 0.9)) if flat.size else 0.0,
                        "min": float(np.min(flat)) if flat.size else 0.0,
                        "max": float(np.max(flat)) if flat.size else 0.0,
                    },
                    "dropout_effect": {
                        "dropout_rate": float(self.config.dropout_rate),
                        "keep_probability": keep_prob,
                        "adjusted_abs_mean": float(np.mean(adjusted)) if flat.size else 0.0,
                        "sparsity_ratio": sparsity,
                    },
                }
            )
            for idx, value in enumerate(flat.tolist()):
                score = float(abs(value) * keep_prob)
                important_pool.append((score, name, int(idx), float(value), keep_prob))
                weak_pool.append((score, name, int(idx), float(value), keep_prob))

        k = max(1, int(top_k))
        important_pool.sort(key=lambda item: item[0], reverse=True)
        weak_pool.sort(key=lambda item: item[0])
        return {
            "summary": {
                "parameter_groups": int(len(summaries)),
                "total_parameter_count": int(sum(item["count"] for item in summaries)),
                "dropout_type": str(self.config.dropout_type),
                "dropout_rate": float(self.config.dropout_rate),
                "keep_probability": keep_prob,
            },
            "parameter_summaries": summaries,
            "top_important_parameters": [
                {
                    "parameter": str(name),
                    "flat_index": int(idx),
                    "value": float(value),
                    "adjusted_importance": float(score),
                    "keep_probability": float(kp),
                }
                for score, name, idx, value, kp in important_pool[:k]
            ],
            "top_weak_parameters": [
                {
                    "parameter": str(name),
                    "flat_index": int(idx),
                    "value": float(value),
                    "adjusted_importance": float(score),
                    "keep_probability": float(kp),
                }
                for score, name, idx, value, kp in weak_pool[:k]
            ],
        }

    def analyze_multiple_forward_passes(
        self,
        features: np.ndarray | list[list[float]],
        *,
        t: int = 80,
        top_k: int = 8,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        """输出多次前向传播统计，用于稳定性分析。"""
        pre = self.preprocess_mc_dropout_data(features, use_training_stats=use_training_stats)
        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        steps = int(max(2, t))
        sampled_means, sampled_vars = self._sample_forward_passes(x_scaled, steps=steps)

        pred_mean = np.mean(sampled_means, axis=0)
        pred_std = np.std(sampled_means, axis=0)
        epistemic = np.var(sampled_means, axis=0)
        aleatoric = np.mean(sampled_vars, axis=0)
        total = np.maximum(epistemic + aleatoric, 1e-8)
        cv = pred_std / (np.abs(pred_mean) + 1e-8)
        stability = 1.0 / (1.0 + cv)

        n = int(pred_mean.size)
        k = min(max(1, int(top_k)), max(1, n))
        top_idx = np.argsort(pred_std)[::-1][:k] if n > 0 else np.asarray([], dtype=int)
        corr = float(np.corrcoef(pred_std, epistemic)[0, 1]) if n >= 2 else 0.0
        if not np.isfinite(corr):
            corr = 0.0

        return {
            "summary": {
                "sample_count": int(n),
                "forward_passes": int(steps),
                "mean_prediction_std": float(np.mean(pred_std)) if n > 0 else 0.0,
                "p90_prediction_std": float(np.quantile(pred_std, 0.9)) if n > 0 else 0.0,
                "mean_epistemic": float(np.mean(epistemic)) if n > 0 else 0.0,
                "mean_aleatoric": float(np.mean(aleatoric)) if n > 0 else 0.0,
                "mean_stability": float(np.mean(stability)) if n > 0 else 0.0,
                "corr_prediction_std_epistemic": corr,
            },
            "top_unstable_samples": [
                {
                    "sample_index": int(i),
                    "prediction_mean": float(pred_mean[int(i)]),
                    "prediction_std": float(pred_std[int(i)]),
                    "epistemic": float(epistemic[int(i)]),
                    "aleatoric": float(aleatoric[int(i)]),
                    "total_variance": float(total[int(i)]),
                    "stability_score": float(stability[int(i)]),
                }
                for i in top_idx.tolist()
            ],
            "forward_pass_metrics": {
                "per_pass_mean_prediction": [float(v) for v in np.mean(sampled_means, axis=1).tolist()],
                "per_pass_mean_aleatoric": [float(v) for v in np.mean(sampled_vars, axis=1).tolist()],
                "sampling_strategy": "vectorized",
            },
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
                "feature_names": list(pre["feature_names"]),
            },
        }

    @staticmethod
    def _moment_skew_kurt(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        arr = np.asarray(values, dtype=float)
        mean = np.mean(arr, axis=0)
        centered = arr - mean.reshape(1, -1)
        std = np.std(arr, axis=0)
        denom3 = np.maximum(std, 1e-8) ** 3
        denom4 = np.maximum(std, 1e-8) ** 4
        skew = np.mean(centered ** 3, axis=0) / denom3
        kurt = np.mean(centered ** 4, axis=0) / denom4 - 3.0
        skew = np.where(np.isfinite(skew), skew, 0.0)
        kurt = np.where(np.isfinite(kurt), kurt, 0.0)
        return skew.astype(float), kurt.astype(float)

    def analyze_prediction_distribution(
        self,
        features: np.ndarray | list[list[float]],
        *,
        t: int = 80,
        top_k: int = 8,
        quantiles: Sequence[float] = (0.05, 0.25, 0.5, 0.75, 0.95),
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        """输出预测分布统计（分位区间/形态）。"""
        pre = self.preprocess_mc_dropout_data(features, use_training_stats=use_training_stats)
        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        steps = int(max(2, t))
        sampled_means, _ = self._sample_forward_passes(x_scaled, steps=steps)

        q = np.asarray(list(quantiles), dtype=float)
        q = np.clip(q, 0.0, 1.0)
        if q.size == 0:
            q = np.asarray([0.5], dtype=float)

        q_values = np.quantile(sampled_means, q, axis=0)
        pred_mean = np.mean(sampled_means, axis=0)
        pred_std = np.std(sampled_means, axis=0)
        skew, kurt = self._moment_skew_kurt(sampled_means)
        q05 = np.quantile(sampled_means, 0.05, axis=0)
        q95 = np.quantile(sampled_means, 0.95, axis=0)
        interval_width = q95 - q05

        n = int(pred_mean.size)
        k = min(max(1, int(top_k)), max(1, n))
        top_idx = np.argsort(interval_width)[::-1][:k] if n > 0 else np.asarray([], dtype=int)

        return {
            "summary": {
                "sample_count": int(n),
                "forward_passes": int(steps),
                "mean_predictive_std": float(np.mean(pred_std)) if n > 0 else 0.0,
                "mean_interval_width_p05_p95": float(np.mean(interval_width)) if n > 0 else 0.0,
                "p90_interval_width_p05_p95": float(np.quantile(interval_width, 0.9)) if n > 0 else 0.0,
                "mean_abs_skewness": float(np.mean(np.abs(skew))) if n > 0 else 0.0,
                "mean_excess_kurtosis": float(np.mean(kurt)) if n > 0 else 0.0,
            },
            "quantiles": {
                f"q{int(v * 100):02d}": [float(x) for x in q_values[i].tolist()]
                for i, v in enumerate(q.tolist())
            },
            "distribution_overview": {
                f"q{int(v * 100):02d}_mean": float(np.mean(q_values[i])) if q_values.shape[1] > 0 else 0.0
                for i, v in enumerate(q.tolist())
            },
            "top_wide_interval_samples": [
                {
                    "sample_index": int(i),
                    "prediction_mean": float(pred_mean[int(i)]),
                    "prediction_std": float(pred_std[int(i)]),
                    "interval_p05_p95": [float(q05[int(i)]), float(q95[int(i)])],
                    "interval_width_p05_p95": float(interval_width[int(i)]),
                    "skewness": float(skew[int(i)]),
                    "excess_kurtosis": float(kurt[int(i)]),
                }
                for i in top_idx.tolist()
            ],
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
                "feature_names": list(pre["feature_names"]),
            },
        }

    def _model_signature(self) -> str:
        stats: list[float] = [float(len(self.history))]
        for arr in (self.w1, self.b1, self.w_mean, self.b_mean, self.w_logvar, self.b_logvar):
            flat = np.asarray(arr, dtype=float).reshape(-1)
            if flat.size == 0:
                continue
            stats.extend([float(np.mean(flat)), float(np.std(flat)), float(np.mean(np.abs(flat)))])
        normalized = ",".join(f"{v:.8f}" for v in stats)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _feature_fingerprint(self, x: np.ndarray) -> str:
        arr = np.ascontiguousarray(np.asarray(x, dtype=float))
        h = hashlib.sha256()
        h.update(str(tuple(int(v) for v in arr.shape)).encode("utf-8"))
        h.update(arr.tobytes())
        return h.hexdigest()

    def _predict_cache_key(self, features: np.ndarray, *, steps: int, confidence: float) -> str:
        payload = {
            "feature_hash": self._feature_fingerprint(features),
            "shape": [int(features.shape[0]), int(features.shape[1]) if features.ndim == 2 else 0],
            "steps": int(steps),
            "confidence": float(confidence),
            "model_hash": self._model_signature(),
            "dropout_type": str(self.config.dropout_type),
            "dropout_rate": float(self.config.dropout_rate),
        }
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _predict_cache_get(self, key: str) -> dict[str, Any] | None:
        with self._predict_cache_lock:
            cached = self._predict_cache.get(key)
            if cached is None:
                self._predict_cache_misses += 1
                return None
            self._predict_cache_hits += 1
            self._predict_cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _predict_cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._predict_cache_lock:
            cached = copy.deepcopy(value)
            perf = dict(cached.get("performance", {}))
            perf.pop("cache_hit", None)
            cached["performance"] = perf
            self._predict_cache[key] = cached
            self._predict_cache.move_to_end(key)
            while len(self._predict_cache) > self._predict_cache_size:
                self._predict_cache.popitem(last=False)

    def _predict_cache_metrics(self) -> dict[str, float | int]:
        with self._predict_cache_lock:
            total = self._predict_cache_hits + self._predict_cache_misses
            return {
                "hits": int(self._predict_cache_hits),
                "misses": int(self._predict_cache_misses),
                "hit_rate": float(self._predict_cache_hits / max(1, total)),
            }

    def _batch_cache_key(
        self,
        *,
        features: np.ndarray,
        steps: int,
        confidence: float,
        batch_size: int,
        optimize_memory: bool,
    ) -> str:
        payload = {
            "feature_hash": self._feature_fingerprint(features),
            "shape": [int(features.shape[0]), int(features.shape[1]) if features.ndim == 2 else 0],
            "t": int(steps),
            "confidence": float(confidence),
            "batch_size": int(batch_size),
            "optimize_memory": bool(optimize_memory),
            "model_hash": self._model_signature(),
        }
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _batch_cache_get(self, key: str) -> dict[str, Any] | None:
        with self._batch_cache_lock:
            cached = self._batch_result_cache.get(key)
            if cached is None:
                self._batch_cache_misses += 1
                return None
            self._batch_cache_hits += 1
            self._batch_result_cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _batch_cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._batch_cache_lock:
            cached = copy.deepcopy(value)
            perf = dict(cached.get("performance", {}))
            perf.pop("cache_hit", None)
            cached["performance"] = perf
            self._batch_result_cache[key] = cached
            self._batch_result_cache.move_to_end(key)
            while len(self._batch_result_cache) > self._batch_cache_size:
                self._batch_result_cache.popitem(last=False)

    def _batch_cache_metrics(self) -> dict[str, float | int]:
        with self._batch_cache_lock:
            total = self._batch_cache_hits + self._batch_cache_misses
            return {
                "hits": int(self._batch_cache_hits),
                "misses": int(self._batch_cache_misses),
                "hit_rate": float(self._batch_cache_hits / max(1, total)),
            }

    def _sample_forward_passes(self, x: np.ndarray, *, steps: int) -> tuple[np.ndarray, np.ndarray]:
        features = ensure_2d(x)
        z1 = features @ self.w1 + self.b1
        h = np.tanh(z1)
        keep = float(max(1e-8, 1.0 - float(self.config.dropout_rate)))
        n_samples, hidden_dim = h.shape

        if self.config.dropout_type == "variational":
            if self.dropout._variational_mask is None or self.dropout._variational_mask.shape != h.shape:
                self.dropout._variational_mask = (
                    (self.dropout.rng.uniform(0.0, 1.0, size=h.shape) < keep).astype(float) / keep
                )
            base_mask = np.asarray(self.dropout._variational_mask, dtype=float)
            masks = np.repeat(base_mask.reshape(1, n_samples, hidden_dim), steps, axis=0)
        elif self.config.dropout_type == "spatial":
            base = (self.dropout.rng.uniform(0.0, 1.0, size=(steps, 1, hidden_dim)) < keep).astype(float)
            masks = np.repeat(base, n_samples, axis=1) / keep
        else:
            masks = (self.dropout.rng.uniform(0.0, 1.0, size=(steps, n_samples, hidden_dim)) < keep).astype(float) / keep

        h_drop = h.reshape(1, n_samples, hidden_dim) * masks
        means = np.einsum("tnh,hk->tnk", h_drop, self.w_mean, optimize=True)[..., 0] + float(self.b_mean[0])
        logvar = np.einsum("tnh,hk->tnk", h_drop, self.w_logvar, optimize=True)[..., 0] + float(self.b_logvar[0])
        vars_ = np.exp(np.clip(logvar, -8.0, 5.0)) + 1e-6
        return np.asarray(means, dtype=float), np.asarray(vars_, dtype=float)
