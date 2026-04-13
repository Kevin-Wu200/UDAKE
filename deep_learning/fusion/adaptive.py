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
    fault_count: int = 0
    degraded_models: list[str] = field(default_factory=list)


@dataclass
class AdaptiveFusionState:
    current_strategy: FusionStrategy = FusionStrategy.DYNAMIC
    online_weights: dict[str, float] = field(default_factory=dict)
    history: list[FusionMonitorRecord] = field(default_factory=list)
    strategy_scores: dict[str, float] = field(default_factory=dict)
    model_health: dict[str, dict[str, Any]] = field(default_factory=dict)
    fault_events: list[dict[str, Any]] = field(default_factory=list)


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
        model_health: dict[str, dict[str, Any]] | None = None,
    ) -> FusionStrategy:
        arr = np.asarray([m.predictions for m in models], dtype=float)
        spread = float(np.mean(np.std(arr, axis=0))) if arr.size else 0.0
        has_variance = all(m.variances is not None for m in models)
        health = model_health or {}
        degraded = [m for m, info in health.items() if str(info.get("status", "healthy")) != "healthy"]
        degraded_ratio = float(len(degraded) / max(1, len(models)))

        candidates: dict[FusionStrategy, float] = {
            FusionStrategy.WEIGHTED_AVERAGE: 0.20,
            FusionStrategy.DYNAMIC: 0.15,
            FusionStrategy.MEDIAN: 0.10,
            FusionStrategy.VARIANCE_WEIGHTED: 0.10 if has_variance else 0.0,
            FusionStrategy.STACKING: 0.0,
        }
        if true_values is not None and len(true_values) >= max(12, len(models) * 3):
            candidates[FusionStrategy.STACKING] += 0.80
        if has_variance and spread > 0.12:
            candidates[FusionStrategy.VARIANCE_WEIGHTED] += min(0.60, spread)
        if context and "difficulty" in context:
            difficulty = float(np.mean(np.asarray(context.get("difficulty", []), dtype=float))) if context.get("difficulty") else 0.0
            candidates[FusionStrategy.DYNAMIC] += 0.35 + max(0.0, min(0.25, difficulty * 0.1))
        if spread > 0.25:
            candidates[FusionStrategy.MEDIAN] += min(0.70, spread)
        if degraded_ratio >= 0.34:
            candidates[FusionStrategy.MEDIAN] += 0.50
            candidates[FusionStrategy.DYNAMIC] += 0.20

        for strategy, score in self.state.strategy_scores.items():
            try:
                enum_strategy = FusionStrategy(strategy)
            except ValueError:
                continue
            if enum_strategy in candidates:
                candidates[enum_strategy] += float(np.clip(score, 0.0, 1.0)) * 0.30

        return max(candidates.items(), key=lambda item: item[1])[0]

    def online_fuse(
        self,
        models: list[ModelPrediction],
        base_config: FusionConfig | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        sanitized_models = self._sanitize_models(models)
        health = self._detect_model_faults(sanitized_models, true_values=true_values)
        self.state.model_health = health["model_health"]
        self._append_fault_events(health["fault_events"])

        cfg = base_config or FusionConfig()
        chosen = self.select_strategy(
            models=sanitized_models,
            true_values=true_values,
            context=context,
            model_health=self.state.model_health,
        )
        cfg.strategy = chosen

        result = self.engine.fuse(models=sanitized_models, config=cfg, true_values=true_values, context=context)
        realtime_info = self._update_online_weights(
            new_weights=result.weights,
            models=sanitized_models,
            true_values=true_values,
            model_health=self.state.model_health,
        )

        rmse = result.metrics.get("rmse") if result.metrics else None
        mae = result.metrics.get("mae") if result.metrics else None
        throughput = float(len(result.fused_predictions))
        latency = float(result.diagnostics.get("latency_ms", 0.0))
        degraded_models = [m for m, info in self.state.model_health.items() if str(info.get("status", "healthy")) != "healthy"]
        self._record(
            strategy=result.strategy,
            rmse=rmse,
            mae=mae,
            throughput=throughput,
            latency_ms=latency,
            fault_count=len(health["fault_events"]),
            degraded_models=degraded_models,
        )

        return {
            "result": result,
            "online_weights": dict(self.state.online_weights),
            "selected_strategy": chosen.value,
            "realtime_adjustment": realtime_info,
            "model_health": dict(self.state.model_health),
            "fault_events": list(health["fault_events"]),
        }

    def monitor(self) -> dict[str, Any]:
        hist = self.state.history
        last = hist[-1] if hist else None
        unhealthy = [m for m, info in self.state.model_health.items() if str(info.get("status", "healthy")) != "healthy"]
        return {
            "current_strategy": self.state.current_strategy.value,
            "online_weights": dict(self.state.online_weights),
            "history_size": len(hist),
            "last_record": None if last is None else last.__dict__,
            "strategy_scores": dict(self.state.strategy_scores),
            "model_health": dict(self.state.model_health),
            "fault_summary": {
                "recent_faults": len(self.state.fault_events),
                "unhealthy_models": unhealthy,
            },
        }

    def _update_online_weights(
        self,
        new_weights: dict[str, float],
        models: list[ModelPrediction],
        true_values: list[float] | None,
        model_health: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if not new_weights:
            return {"ema_alpha": float(self.ema_alpha), "health_penalties": {}, "performance_weights": {}}
        if not self.state.online_weights:
            self.state.online_weights = dict(new_weights)
        else:
            alpha = self.ema_alpha
            keys = set(self.state.online_weights.keys()) | set(new_weights.keys())
            merged: dict[str, float] = {}
            for key in keys:
                old = self.state.online_weights.get(key, 0.0)
                new = new_weights.get(key, 0.0)
                merged[key] = alpha * new + (1.0 - alpha) * old

            self.state.online_weights = self._normalize(merged)

        health_penalties: dict[str, float] = {}
        penalized: dict[str, float] = {}
        for key, value in self.state.online_weights.items():
            status = str(model_health.get(key, {}).get("status", "healthy"))
            penalty = 1.0
            if status == "warning":
                penalty = 0.5
            elif status == "fault":
                penalty = 0.1
            health_penalties[key] = penalty
            penalized[key] = float(value) * penalty
        penalized = self._normalize(penalized)

        performance_weights: dict[str, float] = {}
        if true_values is not None and len(true_values) > 0:
            truth = np.asarray(true_values, dtype=float)
            raw_perf: dict[str, float] = {}
            for model in models:
                pred = np.asarray(model.predictions, dtype=float)
                err = float(np.sqrt(np.mean((pred - truth) ** 2)))
                raw_perf[model.model_id] = 1.0 / max(1e-8, err)
            performance_weights = self._normalize(raw_perf)
            blended = {
                key: 0.70 * penalized.get(key, 0.0) + 0.30 * performance_weights.get(key, 0.0)
                for key in set(penalized) | set(performance_weights)
            }
            self.state.online_weights = self._normalize(blended)
        else:
            self.state.online_weights = penalized

        return {
            "ema_alpha": float(self.ema_alpha),
            "health_penalties": health_penalties,
            "performance_weights": performance_weights,
        }

    def _record(
        self,
        strategy: str,
        rmse: float | None,
        mae: float | None,
        throughput: float,
        latency_ms: float,
        fault_count: int = 0,
        degraded_models: list[str] | None = None,
    ) -> None:
        self.state.current_strategy = FusionStrategy(strategy)
        score = self._performance_score(rmse=rmse, mae=mae, fault_count=fault_count)
        prev = self.state.strategy_scores.get(strategy, score)
        self.state.strategy_scores[strategy] = float(0.35 * score + 0.65 * prev)
        self.state.history.append(
            FusionMonitorRecord(
                timestamp=datetime.now(timezone.utc).isoformat(),
                strategy=strategy,
                rmse=rmse,
                mae=mae,
                throughput=throughput,
                latency_ms=latency_ms,
                fault_count=int(fault_count),
                degraded_models=list(degraded_models or []),
            )
        )
        if len(self.state.history) > 200:
            self.state.history = self.state.history[-200:]

    @staticmethod
    def _performance_score(rmse: float | None, mae: float | None, fault_count: int) -> float:
        rmse_term = 1.0 / (1.0 + max(0.0, float(rmse))) if rmse is not None else 0.4
        mae_term = 1.0 / (1.0 + max(0.0, float(mae))) if mae is not None else 0.4
        fault_term = 1.0 / (1.0 + max(0, int(fault_count)))
        return float(np.clip(0.5 * rmse_term + 0.3 * mae_term + 0.2 * fault_term, 0.0, 1.0))

    @staticmethod
    def _normalize(weights: dict[str, float]) -> dict[str, float]:
        cleaned = {k: max(0.0, float(v)) for k, v in weights.items()}
        total = float(sum(cleaned.values()))
        if total <= 1e-12:
            if not cleaned:
                return {}
            equal = 1.0 / float(len(cleaned))
            return {k: equal for k in cleaned}
        return {k: float(v / total) for k, v in cleaned.items()}

    @staticmethod
    def _sanitize_models(models: list[ModelPrediction]) -> list[ModelPrediction]:
        if not models:
            return []
        matrix = np.asarray([m.predictions for m in models], dtype=float)
        col_fallback = np.nanmedian(np.where(np.isfinite(matrix), matrix, np.nan), axis=0)
        col_fallback = np.where(np.isfinite(col_fallback), col_fallback, 0.0)

        sanitized: list[ModelPrediction] = []
        for model in models:
            pred = np.asarray(model.predictions, dtype=float)
            valid = np.isfinite(pred)
            repaired_pred = np.where(valid, pred, col_fallback)
            repaired_var = None
            if model.variances is not None:
                var_arr = np.asarray(model.variances, dtype=float)
                var_valid = np.isfinite(var_arr) & (var_arr >= 0.0)
                repaired_var = np.where(var_valid, var_arr, 0.0).astype(float).tolist()
            sanitized.append(
                ModelPrediction(
                    model_id=model.model_id,
                    predictions=repaired_pred.astype(float).tolist(),
                    model_name=model.model_name,
                    variances=repaired_var,
                    confidence_intervals=model.confidence_intervals,
                    metadata=dict(model.metadata),
                )
            )
        return sanitized

    @staticmethod
    def _append_trigger(triggers: list[str], predicate: bool, name: str) -> None:
        if predicate:
            triggers.append(name)

    def _detect_model_faults(
        self,
        models: list[ModelPrediction],
        true_values: list[float] | None,
    ) -> dict[str, Any]:
        matrix = np.asarray([m.predictions for m in models], dtype=float) if models else np.zeros((0, 0), dtype=float)
        ensemble = np.mean(matrix, axis=0) if matrix.size else np.array([], dtype=float)
        deviations: dict[str, float] = {}
        for model in models:
            pred = np.asarray(model.predictions, dtype=float)
            deviations[model.model_id] = float(np.mean(np.abs(pred - ensemble))) if ensemble.size else 0.0
        dev_values = np.asarray(list(deviations.values()), dtype=float) if deviations else np.array([], dtype=float)
        dev_median = float(np.median(dev_values)) if dev_values.size else 0.0
        dev_mad = float(np.median(np.abs(dev_values - dev_median))) if dev_values.size else 0.0
        dev_threshold = dev_median + 3.0 * max(1e-8, dev_mad)

        rmse_threshold = None
        rmse_by_model: dict[str, float] = {}
        if true_values is not None and len(true_values) > 0 and models:
            y = np.asarray(true_values, dtype=float)
            for model in models:
                pred = np.asarray(model.predictions, dtype=float)
                rmse_by_model[model.model_id] = float(np.sqrt(np.mean((pred - y) ** 2)))
            rmse_values = np.asarray(list(rmse_by_model.values()), dtype=float)
            rmse_threshold = float(np.median(rmse_values) * 2.5 + 1e-8)

        model_health: dict[str, dict[str, Any]] = {}
        fault_events: list[dict[str, Any]] = []
        for model in models:
            pred = np.asarray(model.predictions, dtype=float)
            diffs = np.diff(pred)
            diff_scale = float(np.median(np.abs(diffs))) if diffs.size else 0.0
            spike_ratio = float(np.mean(np.abs(diffs) > (6.0 * max(1e-8, diff_scale)))) if diffs.size else 0.0
            std_value = float(np.std(pred)) if pred.size else 0.0
            triggers: list[str] = []
            self._append_trigger(triggers, bool(np.isnan(pred).any() or np.isinf(pred).any()), "invalid_prediction")
            self._append_trigger(triggers, bool(std_value < 1e-8 and pred.size >= 3), "stagnant_output")
            self._append_trigger(triggers, bool(spike_ratio >= 0.20), "prediction_spike")
            self._append_trigger(triggers, bool(deviations.get(model.model_id, 0.0) > dev_threshold), "ensemble_outlier")
            if rmse_threshold is not None:
                self._append_trigger(
                    triggers,
                    bool(rmse_by_model.get(model.model_id, 0.0) > rmse_threshold),
                    "high_rmse",
                )
            if model.variances is not None and len(model.variances) > 0:
                var_arr = np.asarray(model.variances, dtype=float)
                self._append_trigger(triggers, bool(float(np.mean(var_arr)) > 1.0), "high_uncertainty")

            if len(triggers) >= 2:
                status = "fault"
            elif len(triggers) == 1:
                status = "warning"
            else:
                status = "healthy"
            health_item = {
                "status": status,
                "trigger_count": len(triggers),
                "triggers": triggers,
                "deviation": float(deviations.get(model.model_id, 0.0)),
                "std": std_value,
                "spike_ratio": spike_ratio,
            }
            if model.model_id in rmse_by_model:
                health_item["rmse"] = float(rmse_by_model[model.model_id])
            model_health[model.model_id] = health_item
            if status != "healthy":
                fault_events.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "model_id": model.model_id,
                        "status": status,
                        "triggers": triggers,
                    }
                )

        return {"model_health": model_health, "fault_events": fault_events}

    def _append_fault_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        self.state.fault_events.extend(events)
        if len(self.state.fault_events) > 300:
            self.state.fault_events = self.state.fault_events[-300:]
