"""阶段7：融合引擎。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from .common import FusionConfig, FusionResult, FusionStrategy, ModelPrediction, WeightMethod, ensure_prediction_matrix
from .evaluation import FusionEvaluator
from .strategies import FusionStrategies
from .weighting import FusionWeightCalculator


class ModelFusionEngine:
    """统一融合入口，负责权重计算、策略执行与评估。"""

    def __init__(self) -> None:
        self.weights = FusionWeightCalculator()
        self.strategies = FusionStrategies()
        self.evaluator = FusionEvaluator()

    def fuse(
        self,
        models: list[ModelPrediction],
        config: FusionConfig | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> FusionResult:
        cfg = config or FusionConfig()
        matrix = ensure_prediction_matrix(models)
        if true_values is not None and len(true_values) != matrix.shape[1]:
            raise ValueError("true_values 长度与模型预测长度不一致")

        model_metrics = self.evaluator.evaluate_model_metrics(models, true_values)
        raw_weights = self.weights.calculate(
            method=cfg.weight_method,
            metrics=model_metrics,
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

        if cfg.strategy == FusionStrategy.SIMPLE_AVERAGE:
            fused, variances = self.strategies.simple_average(models, enable_uncertainty=cfg.enable_uncertainty)
        elif cfg.strategy == FusionStrategy.WEIGHTED_AVERAGE:
            fused, variances = self.strategies.weighted_average(
                models,
                raw_weights,
                enable_uncertainty=cfg.enable_uncertainty,
            )
        elif cfg.strategy == FusionStrategy.MEDIAN:
            fused, variances = self.strategies.median(models, enable_uncertainty=cfg.enable_uncertainty)
        elif cfg.strategy == FusionStrategy.MAX_MIN:
            fused, variances = self.strategies.max_min(models, enable_uncertainty=cfg.enable_uncertainty)
        elif cfg.strategy == FusionStrategy.STACKING:
            fused, variances, learned = self.strategies.stacking(
                models,
                raw_weights,
                true_values=true_values,
                n_folds=cfg.n_folds,
                enable_uncertainty=cfg.enable_uncertainty,
            )
            effective_weights = learned
            diagnostics["stacking_weights"] = learned
        elif cfg.strategy == FusionStrategy.BAYESIAN_MODEL_AVERAGE:
            if cfg.weight_method != WeightMethod.BMA:
                bma_cfg = replace(cfg, weight_method=WeightMethod.BMA)
                bma_weights = self.weights.calculate(
                    method=bma_cfg.weight_method,
                    metrics=model_metrics,
                    adaptive_mode=bma_cfg.adaptive_mode,
                    n_folds=bma_cfg.n_folds,
                    min_weight=bma_cfg.min_weight,
                    max_weight=bma_cfg.max_weight,
                    normalize=bma_cfg.normalize,
                    smoothing=bma_cfg.smoothing,
                    smoothing_factor=bma_cfg.smoothing_factor,
                )
                effective_weights = bma_weights
            fused, variances = self.strategies.bayesian_model_average(
                models,
                effective_weights,
                enable_uncertainty=cfg.enable_uncertainty,
            )
        elif cfg.strategy == FusionStrategy.VARIANCE_WEIGHTED:
            fused, variances = self.strategies.variance_weighted(
                models,
                fallback_weights=raw_weights,
                enable_uncertainty=cfg.enable_uncertainty,
            )
        elif cfg.strategy == FusionStrategy.DYNAMIC:
            fused, variances, dynamic_diag = self.strategies.dynamic(
                models,
                base_weights=raw_weights,
                context=context,
                enable_uncertainty=cfg.enable_uncertainty,
            )
            diagnostics["dynamic_weights"] = dynamic_diag
        else:
            fused, variances = self.strategies.weighted_average(models, raw_weights, enable_uncertainty=cfg.enable_uncertainty)

        metrics = self.evaluator.evaluate_fusion(fused, true_values)
        improvement = self.evaluator.compute_improvement(model_metrics, metrics)
        diversity = self.evaluator.diversity_metrics(models)
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

        return FusionResult(
            fused_predictions=fused,
            fused_variances=variances,
            weights=effective_weights,
            metrics=metrics,
            strategy=cfg.strategy.value,
            weight_method=cfg.weight_method.value,
            improvement=improvement,
            diagnostics=diagnostics,
        )

    def compare_strategies(
        self,
        models: list[ModelPrediction],
        base_config: FusionConfig | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, FusionResult]:
        cfg = base_config or FusionConfig()
        results: dict[str, FusionResult] = {}

        for strategy in FusionStrategy:
            trial = replace(cfg, strategy=strategy)
            result = self.fuse(models=models, config=trial, true_values=true_values, context=context)
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

        for method in WeightMethod:
            trial = replace(cfg, weight_method=method)
            result = self.fuse(models=models, config=trial, true_values=true_values, context=context)
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
