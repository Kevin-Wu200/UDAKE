"""阶段7：自适应融合系统。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

from .common import FusionConfig, FusionStrategy, ModelPrediction
from .engine import ModelFusionEngine


@dataclass
class FusionMonitorRecord:
    timestamp: str
    strategy: str
    rmse: float | None
    mae: float | None
    throughput: float
    latency_ms: float


@dataclass
class AdaptiveFusionState:
    current_strategy: FusionStrategy = FusionStrategy.DYNAMIC
    online_weights: dict[str, float] = field(default_factory=dict)
    history: list[FusionMonitorRecord] = field(default_factory=list)


class AdaptiveFusionSystem:
    """在线权重更新 + 策略自动选择 + 监控。"""

    def __init__(self, engine: ModelFusionEngine | None = None, ema_alpha: float = 0.2) -> None:
        self.engine = engine or ModelFusionEngine()
        self.state = AdaptiveFusionState()
        self.ema_alpha = float(np.clip(ema_alpha, 0.01, 0.95))

    def select_strategy(
        self,
        models: list[ModelPrediction],
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> FusionStrategy:
        arr = np.asarray([m.predictions for m in models], dtype=float)
        spread = float(np.mean(np.std(arr, axis=0))) if arr.size else 0.0
        has_variance = all(m.variances is not None for m in models)

        if true_values is not None and len(true_values) >= max(12, len(models) * 3):
            return FusionStrategy.STACKING
        if has_variance and spread > 0.12:
            return FusionStrategy.VARIANCE_WEIGHTED
        if context and "difficulty" in context:
            return FusionStrategy.DYNAMIC
        if spread > 0.25:
            return FusionStrategy.MEDIAN
        return FusionStrategy.WEIGHTED_AVERAGE

    def online_fuse(
        self,
        models: list[ModelPrediction],
        base_config: FusionConfig | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        cfg = base_config or FusionConfig()
        chosen = self.select_strategy(models=models, true_values=true_values, context=context)
        cfg.strategy = chosen

        result = self.engine.fuse(models=models, config=cfg, true_values=true_values, context=context)
        self._update_online_weights(result.weights)

        rmse = result.metrics.get("rmse") if result.metrics else None
        mae = result.metrics.get("mae") if result.metrics else None
        throughput = float(len(result.fused_predictions))
        latency = float(result.diagnostics.get("latency_ms", 0.0))
        self._record(strategy=result.strategy, rmse=rmse, mae=mae, throughput=throughput, latency_ms=latency)

        return {
            "result": result,
            "online_weights": dict(self.state.online_weights),
            "selected_strategy": chosen.value,
        }

    def monitor(self) -> dict[str, Any]:
        hist = self.state.history
        last = hist[-1] if hist else None
        return {
            "current_strategy": self.state.current_strategy.value,
            "online_weights": dict(self.state.online_weights),
            "history_size": len(hist),
            "last_record": None if last is None else last.__dict__,
        }

    def _update_online_weights(self, new_weights: dict[str, float]) -> None:
        if not new_weights:
            return
        if not self.state.online_weights:
            self.state.online_weights = dict(new_weights)
            return

        alpha = self.ema_alpha
        keys = set(self.state.online_weights.keys()) | set(new_weights.keys())
        merged: dict[str, float] = {}
        for key in keys:
            old = self.state.online_weights.get(key, 0.0)
            new = new_weights.get(key, 0.0)
            merged[key] = alpha * new + (1.0 - alpha) * old

        total = sum(max(v, 0.0) for v in merged.values())
        if total > 0:
            merged = {k: max(v, 0.0) / total for k, v in merged.items()}
        self.state.online_weights = merged

    def _record(self, strategy: str, rmse: float | None, mae: float | None, throughput: float, latency_ms: float) -> None:
        self.state.current_strategy = FusionStrategy(strategy)
        self.state.history.append(
            FusionMonitorRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                strategy=strategy,
                rmse=rmse,
                mae=mae,
                throughput=throughput,
                latency_ms=latency_ms,
            )
        )
        if len(self.state.history) > 200:
            self.state.history = self.state.history[-200:]
