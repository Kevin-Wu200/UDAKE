"""阶段7：融合权重计算。"""

from __future__ import annotations

import math
import threading
from collections import OrderedDict

import numpy as np

from .common import (
    EPS,
    AdaptiveLearningMode,
    ModelMetric,
    WeightMethod,
    normalize_weights,
)


class FusionWeightCalculator:
    """支持多种权重策略与自适应学习。"""

    def __init__(self, cache_size: int = 128) -> None:
        self._cache_size = max(8, int(cache_size))
        self._lock = threading.Lock()
        self._cache: "OrderedDict[tuple, dict[str, float]]" = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_cache_hit = False

    @property
    def last_cache_hit(self) -> bool:
        return bool(self._last_cache_hit)

    def cache_metrics(self) -> dict[str, float | int]:
        with self._lock:
            total = self._cache_hits + self._cache_misses
            return {
                "hits": int(self._cache_hits),
                "misses": int(self._cache_misses),
                "hit_rate": float(self._cache_hits / max(1, total)),
                "size": int(len(self._cache)),
            }

    def calculate(
        self,
        method: WeightMethod,
        metrics: list[ModelMetric],
        adaptive_mode: AdaptiveLearningMode = AdaptiveLearningMode.NEURAL,
        n_folds: int = 5,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
        normalize: bool = True,
        smoothing: bool = False,
        smoothing_factor: float = 0.1,
    ) -> dict[str, float]:
        if not metrics:
            return {}

        cache_key = (
            method.value,
            adaptive_mode.value,
            int(n_folds),
            float(min_weight),
            float(max_weight),
            bool(normalize),
            bool(smoothing),
            float(smoothing_factor),
            tuple(
                (
                    m.model_id,
                    round(float(m.rmse), 12),
                    round(float(m.mae), 12),
                    round(float(m.r2), 12),
                    round(float(m.mape), 12),
                    round(float(m.stability), 12),
                    round(float(m.uncertainty), 12),
                )
                for m in metrics
            ),
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            self._last_cache_hit = True
            return dict(cached)

        handlers = {
            WeightMethod.EQUAL: self._equal,
            WeightMethod.RMSE_BASED: self._rmse,
            WeightMethod.MAE_BASED: self._mae,
            WeightMethod.R2_BASED: self._r2,
            WeightMethod.CROSS_VALIDATION: lambda m: self._cross_validation(m, n_folds=n_folds),
            WeightMethod.BMA: self._bma,
            WeightMethod.UNCERTAINTY_BASED: self._uncertainty,
            WeightMethod.ADAPTIVE: lambda m: self._adaptive(m, mode=adaptive_mode),
        }

        raw = handlers.get(method, self._equal)(metrics)
        adjusted = self._apply_constraints(
            raw,
            min_weight=min_weight,
            max_weight=max_weight,
            normalize=normalize,
            smoothing=smoothing,
            smoothing_factor=smoothing_factor,
        )
        self._cache_set(cache_key, adjusted)
        self._last_cache_hit = False
        return adjusted

    def _cache_get(self, key: tuple) -> dict[str, float] | None:
        with self._lock:
            cached = self._cache.get(key)
            if cached is None:
                self._cache_misses += 1
                return None
            self._cache_hits += 1
            self._cache.move_to_end(key)
            return dict(cached)

    def _cache_set(self, key: tuple, value: dict[str, float]) -> None:
        with self._lock:
            self._cache[key] = dict(value)
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    def _equal(self, metrics: list[ModelMetric]) -> dict[str, float]:
        w = 1.0 / len(metrics)
        return {m.model_id: w for m in metrics}

    def _rmse(self, metrics: list[ModelMetric]) -> dict[str, float]:
        raw = {m.model_id: 1.0 / max(m.rmse * m.rmse, EPS) for m in metrics}
        return normalize_weights(raw)

    def _mae(self, metrics: list[ModelMetric]) -> dict[str, float]:
        raw = {m.model_id: 1.0 / max(m.mae, EPS) for m in metrics}
        return normalize_weights(raw)

    def _r2(self, metrics: list[ModelMetric]) -> dict[str, float]:
        scores = {m.model_id: max(0.0, m.r2 + 1e-4) for m in metrics}
        return normalize_weights(scores)

    def _cross_validation(self, metrics: list[ModelMetric], n_folds: int = 5) -> dict[str, float]:
        # 在缺少逐折明细时，用稳健综合分作为 CV 近似权重。
        fold_factor = 1.0 + 0.02 * max(2, int(n_folds))
        raw: dict[str, float] = {}
        for m in metrics:
            score = (
                0.40 * (1.0 / max(m.rmse, EPS))
                + 0.30 * (1.0 / max(m.mae, EPS))
                + 0.20 * max(0.0, m.r2)
                + 0.10 * max(0.0, m.stability)
            )
            raw[m.model_id] = max(EPS, score * fold_factor)
        return normalize_weights(raw)

    def _bma(self, metrics: list[ModelMetric]) -> dict[str, float]:
        # BMA 后验权重近似：exp(-0.5 * BIC)
        n = max(20, len(metrics) * 10)
        k = 3
        bic_scores: dict[str, float] = {}
        for m in metrics:
            mse = max(m.rmse * m.rmse, EPS)
            bic_scores[m.model_id] = n * math.log(mse) + k * math.log(n)

        min_bic = min(bic_scores.values())
        raw = {model_id: math.exp(-0.5 * (bic - min_bic)) for model_id, bic in bic_scores.items()}
        return normalize_weights(raw)

    def _uncertainty(self, metrics: list[ModelMetric]) -> dict[str, float]:
        raw: dict[str, float] = {}
        for m in metrics:
            proxy = max(m.uncertainty, EPS)
            raw[m.model_id] = 1.0 / proxy
        return normalize_weights(raw)

    def _adaptive(self, metrics: list[ModelMetric], mode: AdaptiveLearningMode) -> dict[str, float]:
        if mode == AdaptiveLearningMode.ATTENTION:
            return self._attention_adaptive(metrics)
        return self._neural_adaptive(metrics)

    def _neural_adaptive(self, metrics: list[ModelMetric]) -> dict[str, float]:
        # 轻量神经网络近似：两层感知机前向推断 + softmax。
        features = np.asarray(
            [[1.0 / max(m.rmse, EPS), 1.0 / max(m.mae, EPS), m.r2, m.stability] for m in metrics],
            dtype=float,
        )

        w1 = np.asarray(
            [
                [0.7, 0.2, 0.3, 0.4],
                [0.3, 0.8, 0.1, 0.2],
                [0.2, 0.1, 0.9, 0.5],
                [0.4, 0.3, 0.4, 0.8],
            ],
            dtype=float,
        )
        w2 = np.asarray([0.45, 0.35, 0.30, 0.40], dtype=float)

        hidden = np.tanh(features @ w1)
        logits = hidden @ w2
        logits = logits - np.max(logits)
        probs = np.exp(logits)
        probs = probs / np.clip(np.sum(probs), EPS, None)
        return {m.model_id: float(p) for m, p in zip(metrics, probs)}

    def _attention_adaptive(self, metrics: list[ModelMetric]) -> dict[str, float]:
        # 注意力近似：query 为全局质量，key/value 为模型质量。
        feature = np.asarray(
            [[1.0 / max(m.rmse, EPS), max(0.0, m.r2), m.stability, 1.0 / max(m.uncertainty, EPS)] for m in metrics],
            dtype=float,
        )
        query = np.mean(feature, axis=0, keepdims=True)
        score = (feature @ query.T).reshape(-1)
        score = score / max(1.0, feature.shape[1] ** 0.5)
        score = score - np.max(score)
        attn = np.exp(score)
        attn = attn / np.clip(np.sum(attn), EPS, None)
        return {m.model_id: float(w) for m, w in zip(metrics, attn)}

    def _apply_constraints(
        self,
        weights: dict[str, float],
        min_weight: float,
        max_weight: float,
        normalize: bool,
        smoothing: bool,
        smoothing_factor: float,
    ) -> dict[str, float]:
        constrained = {k: max(min_weight, min(max_weight, float(v))) for k, v in weights.items()}

        if normalize:
            constrained = normalize_weights(constrained)

        if smoothing and constrained:
            avg = 1.0 / len(constrained)
            alpha = float(np.clip(smoothing_factor, 0.0, 1.0))
            constrained = {k: alpha * avg + (1.0 - alpha) * v for k, v in constrained.items()}
            constrained = normalize_weights(constrained)

        return constrained
