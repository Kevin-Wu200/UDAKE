"""阶段7：融合引擎。"""

from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import replace
from typing import Any

import numpy as np

from .common import (
    FusionConfig,
    FusionResult,
    FusionStrategy,
    ModelMetric,
    ModelPrediction,
    WeightMethod,
    ensure_prediction_matrix,
)
from .evaluation import FusionEvaluator
from .strategies import FusionStrategies
from .weighting import FusionWeightCalculator


class ModelFusionEngine:
    """统一融合入口，负责权重计算、策略执行与评估。"""

    def __init__(self, cache_size: int = 64) -> None:
        self.weights = FusionWeightCalculator()
        self.strategies = FusionStrategies()
        self.evaluator = FusionEvaluator()
        self._cache_size = max(8, int(cache_size))
        self._lock = threading.Lock()
        self._fuse_cache: "OrderedDict[str, FusionResult]" = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0

    @staticmethod
    def _stable_hash(payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _snapshot_models(models: list[ModelPrediction]) -> list[dict[str, Any]]:
        return [
            {
                "model_id": str(m.model_id),
                "predictions": [float(v) for v in m.predictions],
                "variances": None if m.variances is None else [float(v) for v in m.variances],
            }
            for m in models
        ]

    def _cache_metrics(self) -> dict[str, float | int]:
        with self._lock:
            total = self._cache_hits + self._cache_misses
            return {
                "hits": int(self._cache_hits),
                "misses": int(self._cache_misses),
                "hit_rate": float(self._cache_hits / max(1, total)),
                "size": int(len(self._fuse_cache)),
            }

    def _cache_get(self, key: str) -> FusionResult | None:
        with self._lock:
            cached = self._fuse_cache.get(key)
            if cached is None:
                self._cache_misses += 1
                return None
            self._cache_hits += 1
            self._fuse_cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _cache_set(self, key: str, value: FusionResult) -> None:
        with self._lock:
            self._fuse_cache[key] = copy.deepcopy(value)
            self._fuse_cache.move_to_end(key)
            while len(self._fuse_cache) > self._cache_size:
                self._fuse_cache.popitem(last=False)

    def fuse(
        self,
        models: list[ModelPrediction],
        config: FusionConfig | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
        prediction_matrix: np.ndarray | None = None,
        model_metrics: list[ModelMetric] | None = None,
    ) -> FusionResult:
        started = time.perf_counter()
        cfg = config or FusionConfig()
        matrix = ensure_prediction_matrix(models) if prediction_matrix is None else np.asarray(prediction_matrix, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != len(models):
            raise ValueError("prediction_matrix 维度与模型数量不一致")
        if true_values is not None and len(true_values) != matrix.shape[1]:
            raise ValueError("true_values 长度与模型预测长度不一致")

        cache_key = self._stable_hash(
            {
                "models": self._snapshot_models(models),
                "config": {
                    "strategy": cfg.strategy.value,
                    "weight_method": cfg.weight_method.value,
                    "adaptive_mode": cfg.adaptive_mode.value,
                    "min_weight": float(cfg.min_weight),
                    "max_weight": float(cfg.max_weight),
                    "normalize": bool(cfg.normalize),
                    "smoothing": bool(cfg.smoothing),
                    "smoothing_factor": float(cfg.smoothing_factor),
                    "n_folds": int(cfg.n_folds),
                    "enable_uncertainty": bool(cfg.enable_uncertainty),
                },
                "true_values": None if true_values is None else [float(v) for v in true_values],
                "context": context or {},
            }
        )
        cached_result = self._cache_get(cache_key)
        if cached_result is not None:
            cached_result.diagnostics = {
                **dict(cached_result.diagnostics),
                "cache_hit": True,
                "cache_key": str(cache_key[:16]),
                "cache_metrics": self._cache_metrics(),
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
            }
            return cached_result

        metrics_input = model_metrics or self.evaluator.evaluate_model_metrics(
            models,
            true_values,
            prediction_matrix=matrix,
        )
        raw_weights = self.weights.calculate(
            method=cfg.weight_method,
            metrics=metrics_input,
            adaptive_mode=cfg.adaptive_mode,
            n_folds=cfg.n_folds,
            min_weight=cfg.min_weight,
            max_weight=cfg.max_weight,
            normalize=cfg.normalize,
            smoothing=cfg.smoothing,
            smoothing_factor=cfg.smoothing_factor,
        )

        fused: list[float]
        variances: list[float] | None
        diagnostics: dict[str, Any] = {}
        effective_weights = dict(raw_weights)
        weight_cache_hit = self.weights.last_cache_hit

        if cfg.strategy == FusionStrategy.SIMPLE_AVERAGE:
            fused, variances = self.strategies.simple_average(
                models,
                enable_uncertainty=cfg.enable_uncertainty,
                prediction_matrix=matrix,
            )
        elif cfg.strategy == FusionStrategy.WEIGHTED_AVERAGE:
            fused, variances = self.strategies.weighted_average(
                models,
                raw_weights,
                enable_uncertainty=cfg.enable_uncertainty,
                prediction_matrix=matrix,
            )
        elif cfg.strategy == FusionStrategy.MEDIAN:
            fused, variances = self.strategies.median(
                models,
                enable_uncertainty=cfg.enable_uncertainty,
                prediction_matrix=matrix,
            )
        elif cfg.strategy == FusionStrategy.MAX_MIN:
            fused, variances = self.strategies.max_min(
                models,
                enable_uncertainty=cfg.enable_uncertainty,
                prediction_matrix=matrix,
            )
        elif cfg.strategy == FusionStrategy.STACKING:
            fused, variances, learned = self.strategies.stacking(
                models,
                raw_weights,
                true_values=true_values,
                n_folds=cfg.n_folds,
                enable_uncertainty=cfg.enable_uncertainty,
                prediction_matrix=matrix,
            )
            effective_weights = learned
            diagnostics["stacking_weights"] = learned
        elif cfg.strategy == FusionStrategy.BAYESIAN_MODEL_AVERAGE:
            if cfg.weight_method != WeightMethod.BMA:
                bma_cfg = replace(cfg, weight_method=WeightMethod.BMA)
                bma_weights = self.weights.calculate(
                    method=bma_cfg.weight_method,
                    metrics=metrics_input,
                    adaptive_mode=bma_cfg.adaptive_mode,
                    n_folds=bma_cfg.n_folds,
                    min_weight=bma_cfg.min_weight,
                    max_weight=bma_cfg.max_weight,
                    normalize=bma_cfg.normalize,
                    smoothing=bma_cfg.smoothing,
                    smoothing_factor=bma_cfg.smoothing_factor,
                )
                effective_weights = bma_weights
                weight_cache_hit = weight_cache_hit or self.weights.last_cache_hit
            fused, variances = self.strategies.bayesian_model_average(
                models,
                effective_weights,
                enable_uncertainty=cfg.enable_uncertainty,
                prediction_matrix=matrix,
            )
        elif cfg.strategy == FusionStrategy.VARIANCE_WEIGHTED:
            fused, variances = self.strategies.variance_weighted(
                models,
                fallback_weights=raw_weights,
                enable_uncertainty=cfg.enable_uncertainty,
                prediction_matrix=matrix,
            )
        elif cfg.strategy == FusionStrategy.DYNAMIC:
            fused, variances, dynamic_diag = self.strategies.dynamic(
                models,
                base_weights=raw_weights,
                context=context,
                enable_uncertainty=cfg.enable_uncertainty,
                prediction_matrix=matrix,
            )
            diagnostics["dynamic_weights"] = dynamic_diag
        else:
            fused, variances = self.strategies.weighted_average(
                models,
                raw_weights,
                enable_uncertainty=cfg.enable_uncertainty,
                prediction_matrix=matrix,
            )

        metrics = self.evaluator.evaluate_fusion(fused, true_values)
        improvement = self.evaluator.compute_improvement(metrics_input, metrics)
        diversity = self.evaluator.diversity_metrics(models, prediction_matrix=matrix)
        uncertainty = self.evaluator.uncertainty_metrics(
            FusionResult(
                fused_predictions=fused,
                fused_variances=variances,
                weights=effective_weights,
                metrics=metrics,
                strategy=cfg.strategy.value,
                weight_method=cfg.weight_method.value,
            ),
            true_values,
        )

        diagnostics["diversity"] = diversity
        diagnostics["uncertainty"] = uncertainty
        diagnostics["prediction_reuse"] = {"matrix_reused": True, "shape": [int(matrix.shape[0]), int(matrix.shape[1])]}
        diagnostics["weight_cache_hit"] = bool(weight_cache_hit)
        diagnostics["weight_cache_metrics"] = self.weights.cache_metrics()
        diagnostics["cache_hit"] = False
        diagnostics["cache_key"] = str(cache_key[:16])
        diagnostics["cache_metrics"] = self._cache_metrics()
        diagnostics["latency_ms"] = float((time.perf_counter() - started) * 1000.0)

        result = FusionResult(
            fused_predictions=fused,
            fused_variances=variances,
            weights=effective_weights,
            metrics=metrics,
            strategy=cfg.strategy.value,
            weight_method=cfg.weight_method.value,
            improvement=improvement,
            diagnostics=diagnostics,
        )
        self._cache_set(cache_key, result)
        return result

    def compare_strategies(
        self,
        models: list[ModelPrediction],
        base_config: FusionConfig | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, FusionResult]:
        cfg = base_config or FusionConfig()
        results: dict[str, FusionResult] = {}
        matrix = ensure_prediction_matrix(models)
        shared_metrics = self.evaluator.evaluate_model_metrics(models, true_values, prediction_matrix=matrix)

        for strategy in FusionStrategy:
            trial = replace(cfg, strategy=strategy)
            result = self.fuse(
                models=models,
                config=trial,
                true_values=true_values,
                context=context,
                prediction_matrix=matrix,
                model_metrics=shared_metrics,
            )
            results[strategy.value] = result

        return results

    def optimize_weight_methods(
        self,
        models: list[ModelPrediction],
        base_config: FusionConfig | None,
        true_values: list[float],
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        cfg = base_config or FusionConfig()
        score_table: dict[str, dict[str, float]] = {}
        best_method: str | None = None
        best_rmse = float("inf")
        matrix = ensure_prediction_matrix(models)
        shared_metrics = self.evaluator.evaluate_model_metrics(models, true_values, prediction_matrix=matrix)

        for method in WeightMethod:
            trial = replace(cfg, weight_method=method)
            result = self.fuse(
                models=models,
                config=trial,
                true_values=true_values,
                context=context,
                prediction_matrix=matrix,
                model_metrics=shared_metrics,
            )
            rmse = float(result.metrics.get("rmse", np.inf))
            score_table[method.value] = {
                "rmse": rmse,
                "mae": float(result.metrics.get("mae", np.inf)),
                "r2": float(result.metrics.get("r2", -np.inf)),
            }
            if rmse < best_rmse:
                best_rmse = rmse
                best_method = method.value

        return {
            "results": score_table,
            "best_method": best_method,
            "best_rmse": best_rmse,
        }
