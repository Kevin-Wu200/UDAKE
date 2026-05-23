"""User validation and model self-evaluation service."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _mean(values: Iterable[float], fallback: float = 0.0) -> float:
    vals = [float(v) for v in values]
    if not vals:
        return fallback
    return sum(vals) / len(vals)


def _variance(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    if len(vals) <= 1:
        return 0.0
    return statistics.pvariance(vals)


def _std(values: Iterable[float]) -> float:
    return math.sqrt(max(0.0, _variance(values)))


def _quantile(values: List[float], q: float, fallback: float = 0.0) -> float:
    if not values:
        return fallback
    arr = sorted(float(v) for v in values)
    if len(arr) == 1:
        return arr[0]
    q = min(1.0, max(0.0, float(q)))
    pos = (len(arr) - 1) * q
    low = int(math.floor(pos))
    high = int(math.ceil(pos))
    if low == high:
        return arr[low]
    return arr[low] + (arr[high] - arr[low]) * (pos - low)


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    text = str(value or "").strip()
    if not text:
        return _utcnow()

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_distribution(values: List[float], bins: int = 10) -> List[Dict[str, float]]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if abs(high - low) <= 1e-12:
        return [{"left": low, "right": high, "count": float(len(values)), "density": 1.0}]

    width = (high - low) / max(1, bins)
    edges = [low + width * i for i in range(bins + 1)]
    counts = [0 for _ in range(bins)]

    for val in values:
        idx = int((val - low) / width)
        if idx >= bins:
            idx = bins - 1
        if idx < 0:
            idx = 0
        counts[idx] += 1

    total = float(len(values))
    output: List[Dict[str, float]] = []
    for i, count in enumerate(counts):
        output.append(
            {
                "left": edges[i],
                "right": edges[i + 1],
                "count": float(count),
                "density": count / total,
            }
        )
    return output


class SelfEvaluationService:
    """Self-evaluation service for user validation feedback and adaptive model management."""

    def __init__(self) -> None:
        self._lock = RLock()

        self._events: List[Dict[str, Any]] = []
        self._alerts: List[Dict[str, Any]] = []
        self._performance_timeline: List[Dict[str, Any]] = []
        self._reports: Dict[str, Dict[str, Any]] = {}

        self._models: Dict[str, Dict[str, Any]] = {}
        self._current_model_id: Optional[str] = None
        self._last_ranking: List[Dict[str, Any]] = []
        self._switch_logs: List[Dict[str, Any]] = []
        self._rollback_logs: List[Dict[str, Any]] = []

        self._ab_tests: Dict[str, Dict[str, Any]] = {}
        self._optimization_tasks: Dict[str, Dict[str, Any]] = {}

        self._metrics_cache: Dict[str, Dict[str, Any]] = {}
        self._data_version = 0

        self._api_keys: Dict[str, Dict[str, Any]] = {
            "dev-evaluation-key": {"key": "dev-evaluation-key", "scopes": {"read", "write", "admin"}},
            "dev-feedback-key": {"key": "dev-feedback-key", "scopes": {"read", "write", "admin"}},
            "dev-active-learning-key": {"key": "dev-active-learning-key", "scopes": {"read", "write", "admin"}},
        }

        self._evaluation_config: Dict[str, Any] = {
            "update_frequency_seconds": 5,
            "window_minutes": 120,
            "max_samples": 500,
            "regression_tolerance": 0.5,
            "region_precision": 1,
            "expected_regions": 20,
        }

        self._drift_thresholds: Dict[str, float] = {
            "accuracy_drop": 0.08,
            "mae_increase": 0.25,
            "input_shift": 0.20,
            "output_shift": 0.20,
        }

        self._alert_thresholds: Dict[str, float] = {
            "accuracy_min": 0.70,
            "mae_max": 1.20,
            "rmse_max": 1.60,
            "ece_max": 0.20,
            "drift_score_max": 0.60,
        }

        self._model_weight_config: Dict[str, float] = {
            "performance": 0.5,
            "uncertainty": 0.3,
            "scenario": 0.2,
            "smoothing": 0.7,
        }
        self._last_weights: Dict[str, float] = {
            "performance": 0.5,
            "uncertainty": 0.3,
            "scenario": 0.2,
        }

    # --------------------------
    # auth
    # --------------------------
    def verify_api_key(self, key: str, required_scope: str = "read") -> Dict[str, Any]:
        info = self._api_keys.get(str(key or ""))
        if not info:
            raise PermissionError("invalid api key")
        if required_scope not in info["scopes"]:
            raise PermissionError("api key permission denied")
        return {"key": info["key"], "scopes": sorted(info["scopes"])}

    def resolve_user_id(self, user_id: Optional[str] = None) -> str:
        return str(user_id or "system_admin")

    # --------------------------
    # realtime evaluation
    # --------------------------
    def evaluate_realtime(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            records = payload.get("records")
            if not records:
                records = [payload]

            accepted = 0
            for item in records:
                event = self._normalize_event(item, uid)
                self._events.append(event)
                accepted += 1

            if len(self._events) > 50000:
                self._events = self._events[-50000:]

            self._data_version += 1
            self._metrics_cache.clear()

            window_minutes = _safe_int(payload.get("window_minutes"), self._evaluation_config["window_minutes"])
            sample_size = _safe_int(payload.get("sample_size"), self._evaluation_config["max_samples"])

            performance = self.get_performance_metrics(window_minutes=window_minutes, sample_size=sample_size)
            errors = self.get_error_analysis(window_minutes=window_minutes, sample_size=sample_size)
            uncertainty = self.get_uncertainty_assessment(window_minutes=window_minutes, sample_size=sample_size)
            drift = self.detect_model_drift(window_minutes=window_minutes, sample_size=sample_size)
            alerts = self._evaluate_alerts(performance, uncertainty, drift)

            self._performance_timeline.append(
                {
                    "timestamp": _iso(_utcnow()),
                    "accuracy": performance["overall_accuracy"],
                    "mae": performance["regression_accuracy"]["mae"],
                    "rmse": performance["regression_accuracy"]["rmse"],
                }
            )
            if len(self._performance_timeline) > 5000:
                self._performance_timeline = self._performance_timeline[-5000:]

            return {
                "accepted": accepted,
                "evaluation_window_minutes": window_minutes,
                "sample_size": sample_size,
                "performance": performance,
                "errors": errors,
                "uncertainty": uncertainty,
                "drift": drift,
                "alerts": alerts,
            }

    def get_performance_metrics(
        self,
        window_minutes: int = 120,
        sample_size: int = 500,
        include_partition: bool = True,
    ) -> Dict[str, Any]:
        cache_key = f"perf:{self._data_version}:{window_minutes}:{sample_size}:{int(include_partition)}"
        if cache_key in self._metrics_cache:
            return dict(self._metrics_cache[cache_key])

        events = self._slice_events(window_minutes=window_minutes, sample_size=sample_size)
        if not events:
            result = self._empty_performance(window_minutes, sample_size)
            self._metrics_cache[cache_key] = dict(result)
            return result

        tolerance = _safe_float(self._evaluation_config.get("regression_tolerance"), 0.5)
        accepted = sum(1 for e in events if e["result"] == "accept")
        rejected = sum(1 for e in events if e["result"] == "reject")
        corrected = sum(1 for e in events if e["result"] == "correct")

        errors = [e["error"] for e in events]
        abs_errors = [abs(v) for v in errors]
        mae = _mean(abs_errors)
        rmse = math.sqrt(_mean([v * v for v in errors]))

        regression_accuracy = sum(1 for err in abs_errors if err <= tolerance) / len(abs_errors)
        feedback_acceptance = accepted / len(events)
        overall_accuracy = 0.6 * feedback_acceptance + 0.4 * regression_accuracy

        region_stats: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        hour_stats: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        class_stats: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for event in events:
            region_stats[event["region_key"]].append(event)
            hour_stats[event["hour_bucket"]].append(event)
            cls = str(event.get("class_label") or "unlabeled")
            class_stats[cls].append(event)

        local_accuracy = {
            key: round(
                0.6 * (sum(1 for e in items if e["result"] == "accept") / len(items))
                + 0.4 * (sum(1 for e in items if abs(e["error"]) <= tolerance) / len(items)),
                6,
            )
            for key, items in region_stats.items()
        }

        time_accuracy = {
            key: round(
                0.6 * (sum(1 for e in items if e["result"] == "accept") / len(items))
                + 0.4 * (sum(1 for e in items if abs(e["error"]) <= tolerance) / len(items)),
                6,
            )
            for key, items in hour_stats.items()
        }

        classification_accuracy = {
            key: round(
                sum(1 for e in items if e.get("predicted_label") == e.get("actual_label")) / max(1, len(items)),
                6,
            )
            for key, items in class_stats.items()
        }

        confidence_values = [e["confidence"] for e in events]
        confidence_distribution = _normalize_distribution(confidence_values, bins=10)

        response_times = [e["response_time_seconds"] for e in events]
        verify_times = [e["verification_time_seconds"] for e in events]

        unique_regions = max(1, len(region_stats))
        expected_regions = max(unique_regions, _safe_int(self._evaluation_config.get("expected_regions"), 20))
        region_counts = [len(v) for v in region_stats.values()]
        density = len(events) / unique_regions
        balance = max(0.0, 1.0 - _std(region_counts) / (max(1.0, _mean(region_counts))))

        result = {
            "window_minutes": window_minutes,
            "sample_size": sample_size,
            "event_count": len(events),
            "overall_accuracy": round(overall_accuracy, 6),
            "local_accuracy": local_accuracy,
            "time_accuracy": time_accuracy,
            "classification_accuracy": classification_accuracy,
            "regression_accuracy": {
                "mae": round(mae, 6),
                "rmse": round(rmse, 6),
                "within_tolerance_rate": round(regression_accuracy, 6),
            },
            "user_satisfaction": {
                "accept_rate": round(accepted / len(events), 6),
                "reject_rate": round(rejected / len(events), 6),
                "correct_rate": round(corrected / len(events), 6),
                "average_confidence": round(_mean(confidence_values), 6),
                "confidence_distribution": confidence_distribution,
            },
            "feedback_analysis": {
                "avg_response_seconds": round(_mean(response_times), 6),
                "avg_verify_seconds": round(_mean(verify_times), 6),
                "active_users": len({e["user_id"] for e in events}),
                "events_per_minute": round(len(events) / max(1.0, window_minutes), 6),
            },
            "coverage": {
                "spatial_coverage": round(unique_regions / expected_regions, 6),
                "time_coverage": round(len(hour_stats) / 24.0, 6),
                "data_density": round(density, 6),
                "distribution_balance": round(balance, 6),
                "data_gaps": [key for key, value in region_stats.items() if len(value) <= 1],
            },
            "partition": {
                "region_count": len(region_stats),
                "hour_count": len(hour_stats),
            }
            if include_partition
            else {},
        }

        self._metrics_cache[cache_key] = dict(result)
        return result

    def get_error_analysis(self, window_minutes: int = 120, sample_size: int = 500) -> Dict[str, Any]:
        cache_key = f"err:{self._data_version}:{window_minutes}:{sample_size}"
        if cache_key in self._metrics_cache:
            return dict(self._metrics_cache[cache_key])

        events = self._slice_events(window_minutes=window_minutes, sample_size=sample_size)
        if not events:
            result = {
                "window_minutes": window_minutes,
                "sample_size": sample_size,
                "event_count": 0,
                "error_statistics": {},
                "error_distribution": [],
                "error_correlation": {},
                "anomaly_errors": [],
                "error_trend": [],
                "error_heatmap": {},
            }
            self._metrics_cache[cache_key] = dict(result)
            return result

        errors = [e["error"] for e in events]
        abs_errors = [abs(v) for v in errors]
        q1 = _quantile(abs_errors, 0.25)
        q2 = _quantile(abs_errors, 0.5)
        q3 = _quantile(abs_errors, 0.75)
        iqr = max(1e-6, q3 - q1)
        outlier_threshold = q3 + 1.5 * iqr

        anomaly_rows = [
            {
                "evaluation_id": e["evaluation_id"],
                "timestamp": e["timestamp"],
                "error": e["error"],
                "abs_error": abs(e["error"]),
                "region": e["region_key"],
                "user_id": e["user_id"],
            }
            for e in events
            if abs(e["error"]) > outlier_threshold
        ]

        heatmap: Dict[str, Dict[str, float]] = {}
        by_region: Dict[str, List[float]] = defaultdict(list)
        for event in events:
            by_region[event["region_key"]].append(abs(event["error"]))
        for key, values in by_region.items():
            heatmap[key] = {
                "mae": round(_mean(values), 6),
                "rmse": round(math.sqrt(_mean([v * v for v in values])), 6),
                "count": float(len(values)),
            }

        trend = []
        by_hour: Dict[str, List[float]] = defaultdict(list)
        for event in events:
            by_hour[event["hour_bucket"]].append(abs(event["error"]))
        for hour in sorted(by_hour):
            vals = by_hour[hour]
            trend.append({"hour": hour, "mae": round(_mean(vals), 6), "count": len(vals)})

        x_values = [e.get("x", 0.0) for e in events]
        y_values = [e.get("y", 0.0) for e in events]  # noqa: F841
        corr_space = self._corr(x_values, abs_errors)
        corr_time = self._corr([e["timestamp_epoch"] for e in events], abs_errors)

        result = {
            "window_minutes": window_minutes,
            "sample_size": sample_size,
            "event_count": len(events),
            "error_statistics": {
                "mean": round(_mean(errors), 6),
                "variance": round(_variance(errors), 6),
                "std": round(_std(errors), 6),
                "mae": round(_mean(abs_errors), 6),
                "rmse": round(math.sqrt(_mean([v * v for v in errors])), 6),
                "quantiles": {
                    "q10": round(_quantile(abs_errors, 0.10), 6),
                    "q25": round(q1, 6),
                    "q50": round(q2, 6),
                    "q75": round(q3, 6),
                    "q90": round(_quantile(abs_errors, 0.90), 6),
                },
            },
            "error_distribution": _normalize_distribution(errors, bins=12),
            "error_correlation": {
                "space_error_correlation": round(corr_space, 6),
                "time_error_correlation": round(corr_time, 6),
            },
            "anomaly_errors": anomaly_rows,
            "error_trend": trend,
            "error_heatmap": heatmap,
        }
        self._metrics_cache[cache_key] = dict(result)
        return result

    def get_uncertainty_assessment(self, window_minutes: int = 120, sample_size: int = 500) -> Dict[str, Any]:
        cache_key = f"unc:{self._data_version}:{window_minutes}:{sample_size}"
        if cache_key in self._metrics_cache:
            return dict(self._metrics_cache[cache_key])

        events = self._slice_events(window_minutes=window_minutes, sample_size=sample_size)
        if not events:
            result = {
                "window_minutes": window_minutes,
                "sample_size": sample_size,
                "event_count": 0,
                "reliability_diagram": [],
                "ece": 0.0,
                "brier_score": 0.0,
                "log_loss": 0.0,
                "sharpness": 0.0,
                "coverage": {"picp": 0.0, "pinaw": 0.0},
            }
            self._metrics_cache[cache_key] = dict(result)
            return result

        tolerance = _safe_float(self._evaluation_config.get("regression_tolerance"), 0.5)
        confidences = [min(1.0, max(0.0, e["confidence"])) for e in events]
        correctness = [1.0 if abs(e["error"]) <= tolerance else 0.0 for e in events]

        bins = [[] for _ in range(10)]
        for conf, ok in zip(confidences, correctness):
            idx = min(9, int(conf * 10))
            bins[idx].append((conf, ok))

        reliability = []
        ece = 0.0
        total = len(events)
        for i, bucket in enumerate(bins):
            left = i / 10.0
            right = (i + 1) / 10.0
            if not bucket:
                reliability.append(
                    {
                        "bin": f"{left:.1f}-{right:.1f}",
                        "count": 0,
                        "avg_confidence": 0.0,
                        "empirical_accuracy": 0.0,
                    }
                )
                continue
            avg_conf = _mean([item[0] for item in bucket])
            emp_acc = _mean([item[1] for item in bucket])
            weight = len(bucket) / total
            ece += weight * abs(avg_conf - emp_acc)
            reliability.append(
                {
                    "bin": f"{left:.1f}-{right:.1f}",
                    "count": len(bucket),
                    "avg_confidence": round(avg_conf, 6),
                    "empirical_accuracy": round(emp_acc, 6),
                }
            )

        brier = _mean([(c - y) ** 2 for c, y in zip(confidences, correctness)])
        eps = 1e-12
        log_loss = -_mean(
            [
                y * math.log(max(eps, c)) + (1.0 - y) * math.log(max(eps, 1.0 - c))
                for c, y in zip(confidences, correctness)
            ]
        )

        covered = 0
        interval_widths: List[float] = []
        targets = [e["actual_value"] for e in events]
        target_range = max(1e-6, max(targets) - min(targets))

        for event in events:
            if event["interval_lower"] is not None and event["interval_upper"] is not None:
                lower = float(event["interval_lower"])
                upper = float(event["interval_upper"])
            else:
                radius = max(0.05, event["uncertainty"])
                lower = event["predicted_value"] - radius
                upper = event["predicted_value"] + radius
            width = max(0.0, upper - lower)
            interval_widths.append(width)
            if lower <= event["actual_value"] <= upper:
                covered += 1

        picp = covered / len(events)
        pinaw = (_mean(interval_widths) / target_range) if interval_widths else 0.0

        result = {
            "window_minutes": window_minutes,
            "sample_size": sample_size,
            "event_count": len(events),
            "reliability_diagram": reliability,
            "ece": round(ece, 6),
            "brier_score": round(brier, 6),
            "log_loss": round(log_loss, 6),
            "sharpness": round(_std(confidences), 6),
            "coverage": {
                "picp": round(picp, 6),
                "pinaw": round(pinaw, 6),
                "avg_interval_width": round(_mean(interval_widths), 6),
            },
        }

        self._metrics_cache[cache_key] = dict(result)
        return result

    def detect_model_drift(self, window_minutes: int = 120, sample_size: int = 500) -> Dict[str, Any]:
        events = self._slice_events(window_minutes=window_minutes, sample_size=sample_size)
        if not events:
            return {
                "window_minutes": window_minutes,
                "sample_size": sample_size,
                "event_count": 0,
                "baseline": {},
                "current": {},
                "drift": {"performance": False, "data": False, "concept": False, "score": 0.0},
                "recommendations": [],
            }

        split = max(1, len(events) // 3)
        baseline_events = events[:split]
        current_events = events[-split:]

        base_accuracy = self._accept_accuracy(baseline_events)
        curr_accuracy = self._accept_accuracy(current_events)
        base_mae = self._mae(baseline_events)
        curr_mae = self._mae(current_events)

        base_input = self._input_signature(baseline_events)
        curr_input = self._input_signature(current_events)
        input_shift = abs(curr_input - base_input)

        base_output = _mean([e["predicted_value"] for e in baseline_events])
        curr_output = _mean([e["predicted_value"] for e in current_events])
        output_shift = abs(curr_output - base_output)

        performance_drift = (base_accuracy - curr_accuracy) >= self._drift_thresholds["accuracy_drop"] or (
            curr_mae - base_mae
        ) >= self._drift_thresholds["mae_increase"]
        data_drift = input_shift >= self._drift_thresholds["input_shift"]
        concept_drift = output_shift >= self._drift_thresholds["output_shift"]

        score = 0.0
        score += min(1.0, max(0.0, (base_accuracy - curr_accuracy) / max(1e-6, self._drift_thresholds["accuracy_drop"])))
        score += min(1.0, max(0.0, (curr_mae - base_mae) / max(1e-6, self._drift_thresholds["mae_increase"])))
        score += min(1.0, max(0.0, input_shift / max(1e-6, self._drift_thresholds["input_shift"])))
        score += min(1.0, max(0.0, output_shift / max(1e-6, self._drift_thresholds["output_shift"])))
        score = min(1.0, score / 4.0)

        recommendations: List[str] = []
        if performance_drift:
            recommendations.append("建议触发模型重训练或增量微调")
        if data_drift:
            recommendations.append("建议更新输入特征归一化参数并检查采样分布")
        if concept_drift:
            recommendations.append("建议执行模型切换或启用A/B实验验证")
        if not recommendations:
            recommendations.append("当前无显著漂移，继续监控")

        return {
            "window_minutes": window_minutes,
            "sample_size": sample_size,
            "event_count": len(events),
            "baseline": {
                "accuracy": round(base_accuracy, 6),
                "mae": round(base_mae, 6),
                "input_signature": round(base_input, 6),
                "output_signature": round(base_output, 6),
            },
            "current": {
                "accuracy": round(curr_accuracy, 6),
                "mae": round(curr_mae, 6),
                "input_signature": round(curr_input, 6),
                "output_signature": round(curr_output, 6),
            },
            "drift": {
                "performance": performance_drift,
                "data": data_drift,
                "concept": concept_drift,
                "input_shift": round(input_shift, 6),
                "output_shift": round(output_shift, 6),
                "score": round(score, 6),
            },
            "recommendations": recommendations,
        }

    # --------------------------
    # model selection
    # --------------------------
    def select_best_model(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            candidates = payload.get("candidates") or []
            for item in candidates:
                self._register_or_update_model(item)

            if not self._models:
                raise ValueError("no candidate models available")

            weights = self._build_dynamic_weights(payload)
            ranking = self._rank_models(weights)
            if not ranking:
                raise ValueError("no models can be ranked")

            selected = ranking[0]
            previous = self._current_model_id
            switch_result: Optional[Dict[str, Any]] = None

            if self._current_model_id is None:
                self._current_model_id = selected["model_id"]

            auto_switch = bool(payload.get("auto_switch", True))
            force_switch = bool(payload.get("force_switch", False))
            min_gain = max(0.0, _safe_float(payload.get("switch_min_gain"), 0.02))

            if auto_switch:
                current_score = self._find_score(ranking, self._current_model_id)
                gain = selected["score"] - current_score
                if force_switch or (selected["model_id"] != self._current_model_id and gain >= min_gain):
                    switch_result = self._switch_model(
                        target_model_id=selected["model_id"],
                        strategy=str(payload.get("switch_strategy") or "smooth"),
                        reason=str(payload.get("switch_reason") or "auto_selection"),
                        trigger="performance_or_drift",
                        user_id=uid,
                        validate_payload=payload.get("validation") or {},
                    )

            ab_result = None
            if isinstance(payload.get("ab_test"), dict):
                ab_result = self._start_ab_test(payload["ab_test"], selected["model_id"], uid)

            self._last_ranking = ranking

            return {
                "selected_model": selected,
                "current_model_id": self._current_model_id,
                "previous_model_id": previous,
                "weights": weights,
                "ranking": ranking,
                "switch": switch_result,
                "ab_test": ab_result,
            }

    def get_model_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_model_id": self._current_model_id,
                "model_count": len(self._models),
                "models": [dict(v) for v in self._models.values()],
                "ranking": list(self._last_ranking),
                "switch_history_count": len(self._switch_logs),
                "switch_history": list(self._switch_logs[-20:]),
                "rollback_history": list(self._rollback_logs[-20:]),
                "ab_tests": list(self._ab_tests.values())[-20:],
            }

    def switch_model(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            target = str(payload.get("target_model_id") or "").strip()
            if not target:
                raise ValueError("target_model_id is required")
            if target not in self._models:
                raise ValueError("target model not registered")
            return self._switch_model(
                target_model_id=target,
                strategy=str(payload.get("strategy") or "smooth"),
                reason=str(payload.get("reason") or "manual_switch"),
                trigger="manual",
                user_id=uid,
                validate_payload=payload.get("validation") or {},
            )

    def rollback_model(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            target = str(payload.get("target_model_id") or "").strip()

            if not target:
                if not self._switch_logs:
                    raise ValueError("no switch history for rollback")
                # rollback to previous model from latest switch
                latest = self._switch_logs[-1]
                target = str(latest.get("from_model_id") or "").strip()
                if not target:
                    raise ValueError("rollback target not found")

            if target not in self._models:
                raise ValueError("rollback target model not registered")

            before = self._current_model_id
            self._current_model_id = target
            record = {
                "rollback_id": f"rbk_{uuid4().hex[:10]}",
                "timestamp": _iso(_utcnow()),
                "from_model_id": before,
                "to_model_id": target,
                "reason": str(payload.get("reason") or "rollback_request"),
                "user_id": uid,
            }
            self._rollback_logs.append(record)
            return record

    # --------------------------
    # optimization lifecycle
    # --------------------------
    def trigger_optimization(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            trigger_type = str(payload.get("trigger_type") or "manual").strip().lower()
            if trigger_type not in {
                "periodic",
                "performance_degradation",
                "data_accumulation",
                "user_feedback",
                "manual",
            }:
                raise ValueError("unsupported trigger_type")

            task_id = f"opt_{uuid4().hex[:12]}"
            now = _utcnow()
            async_mode = bool(payload.get("async", False))

            stages = [
                {"name": "data_preparation", "status": "completed", "progress": 100},
                {"name": "model_training", "status": "running" if async_mode else "completed", "progress": 35 if async_mode else 100},
                {"name": "model_validation", "status": "pending" if async_mode else "completed", "progress": 0 if async_mode else 100},
                {"name": "model_deployment", "status": "pending" if async_mode else "completed", "progress": 0 if async_mode else 100},
            ]

            task = {
                "task_id": task_id,
                "status": "running" if async_mode else "completed",
                "trigger_type": trigger_type,
                "created_at": _iso(now),
                "updated_at": _iso(now),
                "user_id": uid,
                "config": {
                    "retrain_mode": str(payload.get("retrain_mode") or "incremental"),
                    "hyperparameter_search": bool(payload.get("hyperparameter_search", True)),
                    "architecture_search": bool(payload.get("architecture_search", False)),
                    "feature_optimization": bool(payload.get("feature_optimization", True)),
                    "anomaly_update": bool(payload.get("anomaly_update", True)),
                },
                "stages": stages,
                "summary": {
                    "performance_delta": round(_safe_float(payload.get("expected_performance_delta"), 0.03), 6),
                    "data_volume": _safe_int(payload.get("data_volume"), 0),
                    "negative_feedback_ratio": round(_safe_float(payload.get("negative_feedback_ratio"), 0.0), 6),
                },
            }

            self._optimization_tasks[task_id] = task
            return task

    def get_optimization_status(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if task_id:
                task = self._optimization_tasks.get(task_id)
                if not task:
                    raise KeyError("optimization task not found")
                return dict(task)

            rows = list(self._optimization_tasks.values())
            running = sum(1 for item in rows if item["status"] == "running")
            completed = sum(1 for item in rows if item["status"] == "completed")
            canceled = sum(1 for item in rows if item["status"] == "canceled")
            return {
                "count": len(rows),
                "running": running,
                "completed": completed,
                "canceled": canceled,
                "items": rows[-20:],
            }

    def cancel_optimization(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            task_id = str(payload.get("task_id") or "").strip()
            if not task_id:
                raise ValueError("task_id is required")
            task = self._optimization_tasks.get(task_id)
            if not task:
                raise KeyError("optimization task not found")
            if task["status"] == "completed":
                return {"task_id": task_id, "status": "completed", "canceled": False}

            task["status"] = "canceled"
            task["updated_at"] = _iso(_utcnow())
            for stage in task["stages"]:
                if stage["status"] in {"running", "pending"}:
                    stage["status"] = "canceled"
            return {"task_id": task_id, "status": "canceled", "canceled": True}

    # --------------------------
    # report
    # --------------------------
    def get_performance_report(self, window_minutes: int = 120, sample_size: int = 500) -> Dict[str, Any]:
        perf = self.get_performance_metrics(window_minutes=window_minutes, sample_size=sample_size)
        drift = self.detect_model_drift(window_minutes=window_minutes, sample_size=sample_size)
        return {
            "generated_at": _iso(_utcnow()),
            "type": "performance",
            "performance": perf,
            "drift": drift,
            "alerts": self._alerts[-20:],
            "timeline": self._performance_timeline[-100:],
        }

    def get_evaluation_report(self, window_minutes: int = 120, sample_size: int = 500) -> Dict[str, Any]:
        perf = self.get_performance_metrics(window_minutes=window_minutes, sample_size=sample_size)
        err = self.get_error_analysis(window_minutes=window_minutes, sample_size=sample_size)
        unc = self.get_uncertainty_assessment(window_minutes=window_minutes, sample_size=sample_size)
        return {
            "generated_at": _iso(_utcnow()),
            "type": "evaluation",
            "performance": perf,
            "errors": err,
            "uncertainty": unc,
        }

    def get_optimization_report(self) -> Dict[str, Any]:
        status = self.get_optimization_status()
        return {
            "generated_at": _iso(_utcnow()),
            "type": "optimization",
            "summary": {
                "count": status["count"],
                "running": status["running"],
                "completed": status["completed"],
                "canceled": status["canceled"],
            },
            "items": status["items"],
        }

    def generate_report(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            report_type = str(payload.get("report_type") or "evaluation").lower().strip()
            fmt = str(payload.get("format") or "json").lower().strip()
            window = _safe_int(payload.get("window_minutes"), self._evaluation_config["window_minutes"])
            sample_size = _safe_int(payload.get("sample_size"), self._evaluation_config["max_samples"])

            if report_type == "performance":
                content = self.get_performance_report(window_minutes=window, sample_size=sample_size)
            elif report_type == "optimization":
                content = self.get_optimization_report()
            elif report_type == "all":
                content = {
                    "performance": self.get_performance_report(window_minutes=window, sample_size=sample_size),
                    "evaluation": self.get_evaluation_report(window_minutes=window, sample_size=sample_size),
                    "optimization": self.get_optimization_report(),
                    "model_status": self.get_model_status(),
                }
            else:
                content = self.get_evaluation_report(window_minutes=window, sample_size=sample_size)

            if fmt == "markdown":
                rendered = self._render_markdown(content)
            else:
                rendered = content

            report_id = f"rep_{uuid4().hex[:12]}"
            item = {
                "report_id": report_id,
                "report_type": report_type,
                "format": fmt,
                "generated_at": _iso(_utcnow()),
                "generated_by": uid,
                "content": rendered,
            }
            self._reports[report_id] = item
            return item

    # --------------------------
    # internals
    # --------------------------
    def _normalize_event(self, payload: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        ts = _parse_ts(payload.get("timestamp"))
        x = _safe_float(payload.get("x"), 0.0)
        y = _safe_float(payload.get("y"), 0.0)
        precision = max(0, _safe_int(self._evaluation_config.get("region_precision"), 1))
        region_key = str(payload.get("region") or f"{round(x, precision):.{precision}f},{round(y, precision):.{precision}f}")

        predicted = _safe_float(payload.get("predicted_value"), _safe_float(payload.get("prediction"), 0.0))
        actual = _safe_float(payload.get("actual_value"), _safe_float(payload.get("observed_value"), predicted))
        result = str(payload.get("result") or "accept").lower().strip()
        if result not in {"accept", "reject", "correct"}:
            result = "accept"

        corrected_value = payload.get("corrected_value")
        if result == "correct" and corrected_value is not None:
            actual = _safe_float(corrected_value, actual)

        confidence = _safe_float(payload.get("confidence"), 0.5)
        confidence = min(1.0, max(0.0, confidence))
        uncertainty = max(0.0, _safe_float(payload.get("uncertainty"), abs(actual - predicted)))

        lower = payload.get("interval_lower")
        upper = payload.get("interval_upper")

        return {
            "evaluation_id": str(payload.get("evaluation_id") or f"ev_{uuid4().hex[:12]}"),
            "dataset_id": str(payload.get("dataset_id") or "default_dataset"),
            "model_id": str(payload.get("model_id") or "unknown_model"),
            "module": str(payload.get("module") or "general"),
            "user_id": user_id,
            "timestamp": _iso(ts),
            "timestamp_epoch": ts.timestamp(),
            "hour_bucket": ts.strftime("%Y-%m-%d %H:00"),
            "x": x,
            "y": y,
            "region_key": region_key,
            "predicted_value": predicted,
            "actual_value": actual,
            "error": actual - predicted,
            "result": result,
            "confidence": confidence,
            "uncertainty": uncertainty,
            "response_time_seconds": max(0.0, _safe_float(payload.get("response_time_seconds"), 0.0)),
            "verification_time_seconds": max(0.0, _safe_float(payload.get("verification_time_seconds"), 0.0)),
            "class_label": payload.get("class_label"),
            "predicted_label": payload.get("predicted_label"),
            "actual_label": payload.get("actual_label"),
            "features": [float(v) for v in (payload.get("features") or []) if isinstance(v, (int, float))],
            "interval_lower": _safe_float(lower, 0.0) if lower is not None else None,
            "interval_upper": _safe_float(upper, 0.0) if upper is not None else None,
            "metadata": payload.get("metadata") or {},
        }

    def _slice_events(self, window_minutes: int, sample_size: int) -> List[Dict[str, Any]]:
        if not self._events:
            return []
        cutoff = _utcnow() - timedelta(minutes=max(1, window_minutes))
        rows = [event for event in self._events if _parse_ts(event["timestamp"]) >= cutoff]
        if not rows:
            rows = list(self._events)
        if sample_size > 0:
            rows = rows[-sample_size:]
        return rows

    def _empty_performance(self, window_minutes: int, sample_size: int) -> Dict[str, Any]:
        return {
            "window_minutes": window_minutes,
            "sample_size": sample_size,
            "event_count": 0,
            "overall_accuracy": 0.0,
            "local_accuracy": {},
            "time_accuracy": {},
            "classification_accuracy": {},
            "regression_accuracy": {"mae": 0.0, "rmse": 0.0, "within_tolerance_rate": 0.0},
            "user_satisfaction": {
                "accept_rate": 0.0,
                "reject_rate": 0.0,
                "correct_rate": 0.0,
                "average_confidence": 0.0,
                "confidence_distribution": [],
            },
            "feedback_analysis": {
                "avg_response_seconds": 0.0,
                "avg_verify_seconds": 0.0,
                "active_users": 0,
                "events_per_minute": 0.0,
            },
            "coverage": {
                "spatial_coverage": 0.0,
                "time_coverage": 0.0,
                "data_density": 0.0,
                "distribution_balance": 0.0,
                "data_gaps": [],
            },
            "partition": {},
        }

    def _accept_accuracy(self, events: List[Dict[str, Any]]) -> float:
        if not events:
            return 0.0
        return sum(1 for e in events if e["result"] == "accept") / len(events)

    def _mae(self, events: List[Dict[str, Any]]) -> float:
        if not events:
            return 0.0
        return _mean([abs(e["error"]) for e in events])

    def _input_signature(self, events: List[Dict[str, Any]]) -> float:
        rows = []
        for event in events:
            if event["features"]:
                rows.append(_mean(event["features"]))
            else:
                rows.append((event["x"] + event["y"]) / 2.0)
        return _mean(rows)

    def _corr(self, xs: List[float], ys: List[float]) -> float:
        if len(xs) != len(ys) or len(xs) <= 1:
            return 0.0
        mean_x = _mean(xs)
        mean_y = _mean(ys)
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
        den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
        if den_x <= 1e-12 or den_y <= 1e-12:
            return 0.0
        return num / (den_x * den_y)

    def _evaluate_alerts(
        self,
        performance: Dict[str, Any],
        uncertainty: Dict[str, Any],
        drift: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []

        accuracy = _safe_float(performance.get("overall_accuracy"), 0.0)
        mae = _safe_float(performance.get("regression_accuracy", {}).get("mae"), 0.0)
        rmse = _safe_float(performance.get("regression_accuracy", {}).get("rmse"), 0.0)
        ece = _safe_float(uncertainty.get("ece"), 0.0)
        drift_score = _safe_float(drift.get("drift", {}).get("score"), 0.0)

        if accuracy < self._alert_thresholds["accuracy_min"]:
            alerts.append(self._new_alert("performance", "warning", f"准确率偏低: {accuracy:.3f}"))
        if mae > self._alert_thresholds["mae_max"]:
            alerts.append(self._new_alert("error", "warning", f"MAE偏高: {mae:.3f}"))
        if rmse > self._alert_thresholds["rmse_max"]:
            alerts.append(self._new_alert("error", "critical", f"RMSE偏高: {rmse:.3f}"))
        if ece > self._alert_thresholds["ece_max"]:
            alerts.append(self._new_alert("uncertainty", "warning", f"校准误差偏高: {ece:.3f}"))
        if drift_score > self._alert_thresholds["drift_score_max"]:
            alerts.append(self._new_alert("drift", "critical", f"漂移分数过高: {drift_score:.3f}"))

        self._alerts.extend(alerts)
        if len(self._alerts) > 3000:
            self._alerts = self._alerts[-3000:]
        return alerts

    def _new_alert(self, category: str, level: str, message: str) -> Dict[str, Any]:
        return {
            "alert_id": f"alt_{uuid4().hex[:10]}",
            "timestamp": _iso(_utcnow()),
            "category": category,
            "level": level,
            "message": message,
            "acknowledged": False,
        }

    def _register_or_update_model(self, payload: Dict[str, Any]) -> None:
        model_id = str(payload.get("model_id") or "").strip()
        if not model_id:
            return

        existing = self._models.get(model_id, {})
        performance_score = _safe_float(payload.get("performance_score"), _safe_float(existing.get("performance_score"), 0.5))
        uncertainty_score = _safe_float(payload.get("uncertainty_score"), _safe_float(existing.get("uncertainty_score"), 0.5))
        scenario_score = _safe_float(payload.get("scenario_score"), _safe_float(existing.get("scenario_score"), 0.5))

        item = {
            "model_id": model_id,
            "model_name": str(payload.get("model_name") or existing.get("model_name") or model_id),
            "version": str(payload.get("version") or existing.get("version") or "v1"),
            "performance_score": max(0.0, min(1.0, performance_score)),
            "uncertainty_score": max(0.0, min(1.0, uncertainty_score)),
            "scenario_score": max(0.0, min(1.0, scenario_score)),
            "metadata": payload.get("metadata") or existing.get("metadata") or {},
            "updated_at": _iso(_utcnow()),
        }
        self._models[model_id] = item
        if self._current_model_id is None:
            self._current_model_id = model_id

    def _build_dynamic_weights(self, payload: Dict[str, Any]) -> Dict[str, float]:
        user_weights = payload.get("weights") or {}
        base = {
            "performance": max(0.0, _safe_float(user_weights.get("performance"), self._model_weight_config["performance"])),
            "uncertainty": max(0.0, _safe_float(user_weights.get("uncertainty"), self._model_weight_config["uncertainty"])),
            "scenario": max(0.0, _safe_float(user_weights.get("scenario"), self._model_weight_config["scenario"])),
        }
        total = sum(base.values())
        if total <= 1e-12:
            base = {"performance": 0.5, "uncertainty": 0.3, "scenario": 0.2}
        else:
            base = {k: v / total for k, v in base.items()}

        # smoothing to avoid weight oscillation
        alpha = max(0.0, min(1.0, _safe_float(user_weights.get("smoothing"), self._model_weight_config["smoothing"])))
        smoothed = {
            key: round(alpha * self._last_weights.get(key, base[key]) + (1.0 - alpha) * base[key], 6)
            for key in base
        }
        total2 = sum(smoothed.values())
        smoothed = {k: round(v / total2, 6) for k, v in smoothed.items()}

        self._last_weights = dict(smoothed)
        return smoothed

    def _rank_models(self, weights: Dict[str, float]) -> List[Dict[str, Any]]:
        rows = []
        for model in self._models.values():
            perf = max(0.0, min(1.0, _safe_float(model.get("performance_score"), 0.0)))
            unc = max(0.0, min(1.0, _safe_float(model.get("uncertainty_score"), 0.0)))
            scenario = max(0.0, min(1.0, _safe_float(model.get("scenario_score"), 0.0)))

            # uncertainty 越低越好，因此使用 (1 - unc)
            score = (
                weights["performance"] * perf
                + weights["uncertainty"] * (1.0 - unc)
                + weights["scenario"] * scenario
            )
            rows.append(
                {
                    "model_id": model["model_id"],
                    "model_name": model["model_name"],
                    "version": model["version"],
                    "score": round(score, 6),
                    "performance_score": perf,
                    "uncertainty_score": unc,
                    "scenario_score": scenario,
                }
            )

        rows.sort(key=lambda item: item["score"], reverse=True)
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
        return rows

    def _find_score(self, ranking: List[Dict[str, Any]], model_id: Optional[str]) -> float:
        if not model_id:
            return 0.0
        for row in ranking:
            if row["model_id"] == model_id:
                return _safe_float(row["score"], 0.0)
        return 0.0

    def _switch_model(
        self,
        target_model_id: str,
        strategy: str,
        reason: str,
        trigger: str,
        user_id: str,
        validate_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if target_model_id not in self._models:
            raise ValueError("target model not registered")

        current = self._current_model_id
        strategy = strategy.lower().strip()
        if strategy not in {"smooth", "immediate"}:
            strategy = "smooth"

        validation_passed = self._validate_switch(validate_payload)
        switched = validation_passed

        if switched:
            self._current_model_id = target_model_id

        log = {
            "switch_id": f"swt_{uuid4().hex[:12]}",
            "timestamp": _iso(_utcnow()),
            "from_model_id": current,
            "to_model_id": target_model_id,
            "strategy": strategy,
            "reason": reason,
            "trigger": trigger,
            "validated": validation_passed,
            "switched": switched,
            "user_id": user_id,
        }
        self._switch_logs.append(log)
        if len(self._switch_logs) > 2000:
            self._switch_logs = self._switch_logs[-2000:]
        return log

    def _validate_switch(self, payload: Dict[str, Any]) -> bool:
        if not payload:
            return True
        min_accuracy = _safe_float(payload.get("min_accuracy"), 0.0)
        max_mae = _safe_float(payload.get("max_mae"), 9999)
        actual_accuracy = _safe_float(payload.get("actual_accuracy"), 1.0)
        actual_mae = _safe_float(payload.get("actual_mae"), 0.0)
        return actual_accuracy >= min_accuracy and actual_mae <= max_mae

    def _start_ab_test(self, payload: Dict[str, Any], selected_model_id: str, user_id: str) -> Dict[str, Any]:
        baseline_model_id = str(payload.get("baseline_model_id") or self._current_model_id or selected_model_id)
        experiment_model_id = str(payload.get("experiment_model_id") or selected_model_id)
        traffic_split = max(0.05, min(0.95, _safe_float(payload.get("traffic_split"), 0.5)))

        test_id = f"abt_{uuid4().hex[:10]}"
        effect = _safe_float(payload.get("effect_size"), 0.03)
        significant = abs(effect) >= _safe_float(payload.get("significance_threshold"), 0.02)

        record = {
            "test_id": test_id,
            "created_at": _iso(_utcnow()),
            "baseline_model_id": baseline_model_id,
            "experiment_model_id": experiment_model_id,
            "traffic_split": traffic_split,
            "result": {
                "effect_size": round(effect, 6),
                "significant": significant,
                "recommended_model_id": experiment_model_id if effect >= 0 else baseline_model_id,
            },
            "status": "completed" if significant else "running",
            "user_id": user_id,
        }
        self._ab_tests[test_id] = record
        return record

    def _render_markdown(self, content: Any) -> str:
        # 统一输出简要 markdown 文本，便于直接展示或保存。
        lines = ["# 自评估报告", ""]
        lines.append(f"生成时间: {_iso(_utcnow())}")
        lines.append("")

        if isinstance(content, dict):
            for key, value in content.items():
                lines.append(f"## {key}")
                lines.append("```")
                lines.append(str(value))
                lines.append("```")
                lines.append("")
        else:
            lines.append("```")
            lines.append(str(content))
            lines.append("```")

        return "\n".join(lines)


self_evaluation_service = SelfEvaluationService()
