"""阶段7：融合服务编排层（训练/推理/模型管理/监控）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

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
from .hybrid import HybridFusionBridge, HybridFusionMode, MultiModalFusion, MultiModalStrategy
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

    def _record_request(self, endpoint: str) -> None:
        # 入口占位，后续可扩展 tracing/span 打点。
        _ = endpoint


# 单例，供服务层直接复用。
fusion_platform_service = FusionPlatformService()
