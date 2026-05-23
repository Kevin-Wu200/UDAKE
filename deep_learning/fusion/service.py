"""阶段7：融合服务编排层（训练/推理/模型管理/监控）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from .adaptive import AdaptiveFusionSystem
from .common import (
    AdaptiveLearningMode,
    FusionConfig,
    FusionProfile,
    FusionStrategy,
    ModelPrediction,
    WeightMethod,
)
from .engine import ModelFusionEngine
from .evaluation import FusionEvaluator
from .feature_analysis import FusionFeatureAnalyzer
from .hybrid import (
    HybridFusionBridge,
    HybridFusionMode,
    MultiModalFusion,
    MultiModalStrategy,
)
from .model_management import FusionModelManager


@dataclass
class ServiceMonitor:
    total_requests: int = 0
    success_requests: int = 0
    failed_requests: int = 0
    endpoint_counters: dict[str, int] = field(default_factory=dict)

    def record(self, endpoint: str, ok: bool) -> None:
        self.total_requests += 1
        self.endpoint_counters[endpoint] = self.endpoint_counters.get(endpoint, 0) + 1
        if ok:
            self.success_requests += 1
        else:
            self.failed_requests += 1


class FusionPlatformService:
    """阶段7系统集成服务。"""

    def __init__(self, repository_dir: str = "deep_learning/fusion/repository") -> None:
        self.engine = ModelFusionEngine()
        self.evaluator = FusionEvaluator()
        self.adaptive = AdaptiveFusionSystem(self.engine)
        self.hybrid = HybridFusionBridge()
        self.multimodal = MultiModalFusion()
        self.feature_analyzer = FusionFeatureAnalyzer()
        self.model_manager = FusionModelManager(root_dir=repository_dir)
        self.monitor = ServiceMonitor()

        self._tokens: set[str] = {"internal-token"}
        self._rate_limit: dict[str, list[datetime]] = {}
        self._max_requests = 120
        self._window_seconds = 60
        self._profiles: dict[str, FusionProfile] = {}

    def configure_auth(self, tokens: list[str]) -> None:
        self._tokens = {t for t in tokens if t}

    def configure_rate_limit(self, max_requests: int = 120, window_seconds: int = 60) -> None:
        self._max_requests = max(1, int(max_requests))
        self._window_seconds = max(1, int(window_seconds))

    def train_fusion_profile(
        self,
        profile_id: str,
        models: list[dict[str, Any]],
        true_values: list[float],
        strategy: str = "dynamic",
        weight_method: str = "adaptive",
        adaptive_mode: str = "neural",
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        self._record_request("train_fusion_profile")
        preds = self._parse_predictions(models)
        cfg = FusionConfig(
            strategy=FusionStrategy(strategy),
            weight_method=WeightMethod(weight_method),
            adaptive_mode=AdaptiveLearningMode(adaptive_mode),
        )

        result = self.engine.fuse(models=preds, config=cfg, true_values=true_values, context=context)

        profile = FusionProfile(
            profile_id=profile_id,
            strategy=cfg.strategy,
            weight_method=cfg.weight_method,
            weights=dict(result.weights),
            metrics=dict(result.metrics),
            metadata={"created_at": datetime.now(timezone.utc).isoformat(), "adaptive_mode": cfg.adaptive_mode.value},
        )
        self._profiles[profile_id] = profile

        # 将 profile 作为模型元学习器持久化。
        reg = self.model_manager.store_model(
            model_id=f"fusion_profile_{profile_id}",
            model_obj=asdict(profile),
            model_type="fusion_profile",
            config={"strategy": profile.strategy.value, "weight_method": profile.weight_method.value},
            metrics=result.metrics,
            metadata={"kind": "profile"},
        )
        self.monitor.record("train_fusion_profile", ok=True)
        return {
            "profile": asdict(profile),
            "storage": asdict(reg),
            "result": self._serialize_result(result),
        }

    def inference(
        self,
        models: list[dict[str, Any]],
        profile_id: str | None = None,
        strategy: str | None = None,
        weight_method: str | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        self._record_request("inference")
        preds = self._parse_predictions(models)

        if profile_id and profile_id in self._profiles:
            profile = self._profiles[profile_id]
            cfg = FusionConfig(strategy=profile.strategy, weight_method=profile.weight_method)
        else:
            cfg = FusionConfig(
                strategy=FusionStrategy(strategy or "dynamic"),
                weight_method=WeightMethod(weight_method or "adaptive"),
            )

        payload = self.adaptive.online_fuse(models=preds, base_config=cfg, true_values=true_values, context=context)
        result = payload["result"]
        self.monitor.record("inference", ok=True)
        return {
            "result": self._serialize_result(result),
            "online_weights": payload["online_weights"],
            "selected_strategy": payload["selected_strategy"],
        }

    def compare_strategies(
        self,
        models: list[dict[str, Any]],
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        self._record_request("compare_strategies")
        preds = self._parse_predictions(models)
        results = self.engine.compare_strategies(models=preds, true_values=true_values, context=context)
        self.monitor.record("compare_strategies", ok=True)
        return {k: self._serialize_result(v) for k, v in results.items()}

    def strategy_analysis(
        self,
        models: list[dict[str, Any]],
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        self._record_request("strategy_analysis")
        preds = self._parse_predictions(models)
        compared = self.engine.compare_strategies(models=preds, true_values=true_values, context=context)
        serialized = {k: self._serialize_result(v) for k, v in compared.items()}
        ranking = self._build_strategy_ranking(serialized, true_values=true_values)
        self.monitor.record("strategy_analysis", ok=True)
        return {
            "strategies": serialized,
            "analysis": {
                "ranking": ranking,
                "best_strategy": ranking[0]["strategy"] if ranking else "",
                "has_ground_truth": bool(true_values is not None),
            },
        }

    def recommend_strategy(
        self,
        models: list[dict[str, Any]],
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
        objective: str = "balanced",
    ) -> dict[str, Any]:
        self._record_request("recommend_strategy")
        analysis = self.strategy_analysis(models=models, true_values=true_values, context=context)
        ranking = list(analysis.get("analysis", {}).get("ranking", []))
        if not ranking:
            self.monitor.record("recommend_strategy", ok=True)
            return {
                "objective": objective,
                "recommended_strategy": "",
                "reason": "no_strategy_available",
                "candidates": [],
                "analysis": analysis.get("analysis", {}),
            }

        normalized_objective = str(objective or "balanced").strip().lower()
        if normalized_objective not in {"balanced", "rmse", "mae", "r2", "stability"}:
            normalized_objective = "balanced"

        objective_rank = self._sort_ranking_by_objective(ranking, objective=normalized_objective)
        recommended = objective_rank[0]
        self.monitor.record("recommend_strategy", ok=True)
        return {
            "objective": normalized_objective,
            "recommended_strategy": recommended["strategy"],
            "reason": recommended.get("reason", ""),
            "summary": {
                "score": float(recommended.get("score", 0.0)),
                "rmse": float(recommended.get("rmse", np.inf)),
                "mae": float(recommended.get("mae", np.inf)),
                "r2": float(recommended.get("r2", -np.inf)),
                "mean_sigma": float(recommended.get("mean_sigma", 0.0)),
                "ensemble_diversity": float(recommended.get("ensemble_diversity", 0.0)),
            },
            "candidates": objective_rank[:3],
            "analysis": analysis.get("analysis", {}),
        }

    def evaluate_strategy_effectiveness(
        self,
        models: list[dict[str, Any]],
        strategy: str,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
        baseline_strategy: str = FusionStrategy.WEIGHTED_AVERAGE.value,
    ) -> dict[str, Any]:
        self._record_request("evaluate_strategy_effectiveness")
        preds = self._parse_predictions(models)
        target_cfg = FusionConfig(strategy=FusionStrategy(str(strategy).strip().lower() or FusionStrategy.WEIGHTED_AVERAGE.value))
        baseline_cfg = FusionConfig(
            strategy=FusionStrategy(str(baseline_strategy).strip().lower() or FusionStrategy.WEIGHTED_AVERAGE.value)
        )

        target = self.engine.fuse(models=preds, config=target_cfg, true_values=true_values, context=context)
        baseline = self.engine.fuse(models=preds, config=baseline_cfg, true_values=true_values, context=context)

        target_metrics = dict(target.metrics)
        baseline_metrics = dict(baseline.metrics)
        target_uncertainty = dict(target.diagnostics.get("uncertainty", {}))
        baseline_uncertainty = dict(baseline.diagnostics.get("uncertainty", {}))
        improvement_vs_baseline = self._effectiveness_delta(target_metrics, baseline_metrics)

        target_rmse = float(target_metrics.get("rmse", np.inf))
        baseline_rmse = float(baseline_metrics.get("rmse", np.inf))
        target_sigma = float(target_uncertainty.get("mean_sigma", 0.0))
        baseline_sigma = float(baseline_uncertainty.get("mean_sigma", 0.0))

        score = 0.0
        if np.isfinite(target_rmse) and np.isfinite(baseline_rmse):
            score += float((baseline_rmse - target_rmse) / max(baseline_rmse, 1e-8) * 100.0)
        if baseline_sigma > 0:
            score += float((baseline_sigma - target_sigma) / baseline_sigma * 100.0) * 0.3

        effectiveness_level = "weak"
        if score >= 15.0:
            effectiveness_level = "excellent"
        elif score >= 6.0:
            effectiveness_level = "good"
        elif score >= 0.0:
            effectiveness_level = "fair"

        self.monitor.record("evaluate_strategy_effectiveness", ok=True)
        return {
            "target_strategy": target.strategy,
            "baseline_strategy": baseline.strategy,
            "target": self._serialize_result(target),
            "baseline": self._serialize_result(baseline),
            "effectiveness": {
                "score": float(score),
                "level": effectiveness_level,
                "has_ground_truth": bool(true_values is not None),
                "improvement_vs_baseline": improvement_vs_baseline,
                "target_uncertainty": target_uncertainty,
                "baseline_uncertainty": baseline_uncertainty,
            },
        }

    def optimize_weights(
        self,
        models: list[dict[str, Any]],
        true_values: list[float],
        strategy: str = "weighted_average",
    ) -> dict[str, Any]:
        self._record_request("optimize_weights")
        preds = self._parse_predictions(models)
        cfg = FusionConfig(strategy=FusionStrategy(strategy), weight_method=WeightMethod.RMSE_BASED)
        payload = self.engine.optimize_weight_methods(models=preds, base_config=cfg, true_values=true_values)
        self.monitor.record("optimize_weights", ok=True)
        return payload

    def hybrid_fusion(
        self,
        kriging_prediction: list[float],
        deep_prediction: list[float],
        mode: str = "residual",
        ratio: float = 0.6,
        kriging_variance: list[float] | None = None,
        deep_variance: list[float] | None = None,
    ) -> dict[str, Any]:
        self._record_request("hybrid_fusion")
        result = self.hybrid.fuse_kriging_and_deep_learning(
            kriging_prediction=kriging_prediction,
            deep_prediction=deep_prediction,
            kriging_variance=kriging_variance,
            deep_variance=deep_variance,
            mode=HybridFusionMode(mode),
            ratio=ratio,
        )
        self.monitor.record("hybrid_fusion", ok=True)
        return asdict(result)

    def multimodal_fusion(
        self,
        modalities: list[list[float]],
        strategy: str = "hybrid",
        weights: list[float] | None = None,
    ) -> dict[str, Any]:
        self._record_request("multimodal_fusion")
        fused = self.multimodal.fuse(modalities=modalities, strategy=MultiModalStrategy(strategy), weights=weights)
        self.monitor.record("multimodal_fusion", ok=True)
        return {"fused": fused, "strategy": strategy}

    def select_model(
        self,
        performance_scores: dict[str, float] | None = None,
        uncertainty_scores: dict[str, float] | None = None,
        input_score: float | None = None,
    ) -> dict[str, Any]:
        self._record_request("select_model")
        selected = self.hybrid.adaptive_model_selection(
            performance_scores=performance_scores,
            uncertainty_scores=uncertainty_scores,
            input_score=input_score,
        )
        self.monitor.record("select_model", ok=True)
        return {"selected_model": selected}

    def feature_analysis(
        self,
        models: list[dict[str, Any]],
        profile_id: str | None = None,
        strategy: str | None = None,
        weight_method: str | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        self._record_request("feature_analysis")
        preds = self._parse_predictions(models)
        if profile_id and profile_id in self._profiles:
            profile = self._profiles[profile_id]
            cfg = FusionConfig(strategy=profile.strategy, weight_method=profile.weight_method)
        else:
            cfg = FusionConfig(
                strategy=FusionStrategy(strategy or "dynamic"),
                weight_method=WeightMethod(weight_method or "adaptive"),
            )

        payload = self.adaptive.online_fuse(models=preds, base_config=cfg, true_values=true_values, context=context)
        result = self._serialize_result(payload["result"])
        inference = {
            "result": result,
            "online_weights": payload["online_weights"],
            "selected_strategy": payload["selected_strategy"],
        }
        analysis = self.feature_analyzer.analyze(
            models=preds,
            weights=result.get("weights", {}),
            strategy=str(result.get("strategy", strategy or "weighted_average")),
            weight_method=str(result.get("weight_method", weight_method or "adaptive")),
            fused_predictions=[float(x) for x in result.get("fused_predictions", [])],
            true_values=true_values,
            diagnostics=result.get("diagnostics"),
        )
        self.monitor.record("feature_analysis", ok=True)
        return {
            "analysis": analysis,
            "inference": inference,
        }

    def model_registry_status(self) -> dict[str, Any]:
        return {
            "registered_builders": self.model_manager.list_models(),
            "profiles": sorted(self._profiles.keys()),
        }

    def monitor_status(self) -> dict[str, Any]:
        success_rate = self.monitor.success_requests / self.monitor.total_requests if self.monitor.total_requests else 0.0
        return {
            "requests": {
                "total": self.monitor.total_requests,
                "success": self.monitor.success_requests,
                "failed": self.monitor.failed_requests,
                "success_rate": success_rate,
            },
            "endpoint_counters": dict(self.monitor.endpoint_counters),
            "adaptive": self.adaptive.monitor(),
        }

    def check_access(self, token: str | None, client_id: str = "anonymous") -> dict[str, Any]:
        if self._tokens and token not in self._tokens:
            return {"ok": False, "reason": "unauthorized"}

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self._window_seconds)
        history = [t for t in self._rate_limit.get(client_id, []) if t >= window_start]
        if len(history) >= self._max_requests:
            self._rate_limit[client_id] = history
            return {"ok": False, "reason": "rate_limited", "retry_after": self._window_seconds}

        history.append(now)
        self._rate_limit[client_id] = history
        return {"ok": True}

    def _parse_predictions(self, models: list[dict[str, Any]]) -> list[ModelPrediction]:
        preds: list[ModelPrediction] = []
        for idx, item in enumerate(models):
            preds.append(
                ModelPrediction(
                    model_id=str(item.get("model_id", f"model_{idx}")),
                    model_name=item.get("model_name"),
                    predictions=[float(x) for x in item.get("predictions", [])],
                    variances=None
                    if item.get("variances") is None
                    else [float(v) for v in item.get("variances")],
                    confidence_intervals=item.get("confidence_intervals"),
                    metadata=item.get("metadata", {}),
                )
            )
        return preds

    def _serialize_result(self, result: Any) -> dict[str, Any]:
        return {
            "fused_predictions": result.fused_predictions,
            "fused_variances": result.fused_variances,
            "weights": result.weights,
            "metrics": result.metrics,
            "strategy": result.strategy,
            "weight_method": result.weight_method,
            "improvement": result.improvement,
            "diagnostics": result.diagnostics,
        }

    def _build_strategy_ranking(
        self,
        strategies: dict[str, dict[str, Any]],
        true_values: list[float] | None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        metric_rows: list[tuple[float, float, float]] = []
        uncertainty_rows: list[tuple[float, float]] = []
        for name, payload in strategies.items():
            metrics = dict(payload.get("metrics", {}))
            diagnostics = dict(payload.get("diagnostics", {}))
            uncertainty = dict(diagnostics.get("uncertainty", {}))
            diversity = dict(diagnostics.get("diversity", {}))
            rmse = float(metrics.get("rmse", np.inf))
            mae = float(metrics.get("mae", np.inf))
            r2 = float(metrics.get("r2", -np.inf))
            mean_sigma = float(uncertainty.get("mean_sigma", 0.0))
            ensemble_diversity = float(diversity.get("ensemble_diversity", 0.0))
            rows.append(
                {
                    "strategy": str(name),
                    "rmse": rmse,
                    "mae": mae,
                    "r2": r2,
                    "mean_sigma": mean_sigma,
                    "ensemble_diversity": ensemble_diversity,
                }
            )
            if np.isfinite(rmse) and np.isfinite(mae) and np.isfinite(r2):
                metric_rows.append((rmse, mae, r2))
            uncertainty_rows.append((mean_sigma, ensemble_diversity))

        rmse_best = min((v[0] for v in metric_rows), default=np.inf)
        mae_best = min((v[1] for v in metric_rows), default=np.inf)
        r2_best = max((v[2] for v in metric_rows), default=-np.inf)
        sigma_best = min((v[0] for v in uncertainty_rows), default=0.0)
        diversity_best = max((v[1] for v in uncertainty_rows), default=0.0)

        for row in rows:
            rmse_score = float(rmse_best / row["rmse"]) if np.isfinite(rmse_best) and row["rmse"] > 0 else 0.0
            mae_score = float(mae_best / row["mae"]) if np.isfinite(mae_best) and row["mae"] > 0 else 0.0
            if np.isfinite(r2_best):
                r2_gap = max(0.0, r2_best - row["r2"])
                r2_score = float(1.0 / (1.0 + r2_gap))
            else:
                r2_score = 0.0
            sigma_score = float(1.0 / (1.0 + max(0.0, row["mean_sigma"] - sigma_best)))
            diversity_score = float(0.0 if diversity_best <= 0 else row["ensemble_diversity"] / diversity_best)

            if true_values is None:
                score = 0.65 * sigma_score + 0.35 * diversity_score
                reason = "uncertainty_and_diversity"
            else:
                score = 0.45 * rmse_score + 0.25 * mae_score + 0.2 * r2_score + 0.1 * sigma_score
                reason = "error_metrics_and_uncertainty"
            row["score"] = float(score)
            row["reason"] = reason

        rows.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        return rows

    def _sort_ranking_by_objective(self, ranking: list[dict[str, Any]], objective: str) -> list[dict[str, Any]]:
        out = [dict(item) for item in ranking]
        if objective == "rmse":
            out.sort(key=lambda item: float(item.get("rmse", np.inf)))
            for row in out:
                row["reason"] = "lowest_rmse"
            return out
        if objective == "mae":
            out.sort(key=lambda item: float(item.get("mae", np.inf)))
            for row in out:
                row["reason"] = "lowest_mae"
            return out
        if objective == "r2":
            out.sort(key=lambda item: float(item.get("r2", -np.inf)), reverse=True)
            for row in out:
                row["reason"] = "highest_r2"
            return out
        if objective == "stability":
            out.sort(
                key=lambda item: (
                    float(item.get("mean_sigma", np.inf)),
                    -float(item.get("ensemble_diversity", 0.0)),
                )
            )
            for row in out:
                row["reason"] = "lowest_uncertainty_and_high_diversity"
            return out
        return out

    def _effectiveness_delta(self, target: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        target_rmse = float(target.get("rmse", np.inf))
        baseline_rmse = float(baseline.get("rmse", np.inf))
        if np.isfinite(target_rmse) and np.isfinite(baseline_rmse) and baseline_rmse > 0:
            out["rmse_improvement_pct"] = float((baseline_rmse - target_rmse) / baseline_rmse * 100.0)
        target_mae = float(target.get("mae", np.inf))
        baseline_mae = float(baseline.get("mae", np.inf))
        if np.isfinite(target_mae) and np.isfinite(baseline_mae) and baseline_mae > 0:
            out["mae_improvement_pct"] = float((baseline_mae - target_mae) / baseline_mae * 100.0)
        target_r2 = float(target.get("r2", -np.inf))
        baseline_r2 = float(baseline.get("r2", -np.inf))
        if np.isfinite(target_r2) and np.isfinite(baseline_r2):
            out["r2_gain"] = float(target_r2 - baseline_r2)
        target_max = float(target.get("max_error", np.inf))
        baseline_max = float(baseline.get("max_error", np.inf))
        if np.isfinite(target_max) and np.isfinite(baseline_max) and baseline_max > 0:
            out["max_error_improvement_pct"] = float((baseline_max - target_max) / baseline_max * 100.0)
        return out

    def _record_request(self, endpoint: str) -> None:
        # 入口占位，后续可扩展 tracing/span 打点。
        _ = endpoint


# 单例，供服务层直接复用。
fusion_platform_service = FusionPlatformService()
