"""Active learning + semi-supervised + incremental learning service."""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
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


def _variance(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    if len(vals) <= 1:
        return 0.0
    return statistics.pvariance(vals)


def _mean(values: Iterable[float], fallback: float = 0.0) -> float:
    vals = [float(v) for v in values]
    if not vals:
        return fallback
    return sum(vals) / len(vals)


def _l2_distance(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(n)))


def _cosine_distance(a: List[float], b: List[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 1.0
    dot = sum(a[i] * b[i] for i in range(n))
    norm_a = math.sqrt(sum(a[i] * a[i] for i in range(n)))
    norm_b = math.sqrt(sum(b[i] * b[i] for i in range(n)))
    if norm_a <= 1e-12 or norm_b <= 1e-12:
        return 1.0
    cosine = max(-1.0, min(1.0, dot / (norm_a * norm_b)))
    return 1.0 - cosine


def _entropy(probs: List[float]) -> float:
    eps = 1e-12
    return -sum(max(p, eps) * math.log(max(p, eps)) for p in probs)


def _normalize_scores(score_map: Dict[str, float]) -> Dict[str, float]:
    if not score_map:
        return {}
    values = list(score_map.values())
    min_v = min(values)
    max_v = max(values)
    if max_v - min_v <= 1e-12:
        return {k: 0.5 for k in score_map}
    return {k: (v - min_v) / (max_v - min_v) for k, v in score_map.items()}


def _softmax(logits: List[float]) -> List[float]:
    if not logits:
        return [1.0]
    max_logit = max(logits)
    exps = [math.exp(v - max_logit) for v in logits]
    total = sum(exps)
    if total <= 1e-12:
        return [1.0 / len(logits)] * len(logits)
    return [v / total for v in exps]


class ActiveLearningService:
    """Application-level active learning and semi-supervised orchestration service."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._pseudo_labels: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._incremental_history: List[Dict[str, Any]] = []
        self._annotation_tasks: Dict[str, Dict[str, Any]] = {}

        self._strategy_config: Dict[str, Any] = {
            "default_strategy": "hybrid_multi_objective",
            "weights": {
                "uncertainty": 0.4,
                "diversity": 0.3,
                "representativeness": 0.2,
                "committee": 0.1,
            },
            "adaptive": {
                "enabled": True,
                "switch_patience": 2,
                "improvement_threshold": 0.005,
            },
            "committee": {
                "models": [
                    {"name": "mlp", "arch": "mlp", "seed": 11, "weight": 1.0, "enabled": True},
                    {"name": "cnn", "arch": "cnn", "seed": 23, "weight": 1.2, "enabled": True},
                    {"name": "transformer", "arch": "transformer", "seed": 31, "weight": 1.4, "enabled": True},
                ],
                "voting": "weighted",
            },
        }

        self._budget_config: Dict[str, Any] = {
            "total_budget": 500,
            "batch_budget": 50,
            "max_rounds": 10,
            "target_performance": 0.90,
            "min_improvement": 0.002,
            "uncertainty_threshold": 0.15,
        }

        self._api_keys: Dict[str, Dict[str, Any]] = {
            "dev-active-learning-key": {
                "key": "dev-active-learning-key",
                "scopes": {"read", "write", "admin"},
            },
            "dev-feedback-key": {
                "key": "dev-feedback-key",
                "scopes": {"read", "write", "admin"},
            },
        }

    # --------------------------
    # auth / utility
    # --------------------------
    def verify_api_key(self, key: str, required_scope: str = "read") -> Dict[str, Any]:
        info = self._api_keys.get(str(key or ""))
        if not info:
            raise PermissionError("invalid api key")
        if required_scope not in info["scopes"]:
            raise PermissionError("api key permission denied")
        return {"key": info["key"], "scopes": sorted(info["scopes"]) }

    def resolve_user_id(self, user_id: Optional[str] = None) -> str:
        return str(user_id or "system_admin")

    # --------------------------
    # config
    # --------------------------
    def configure_strategy(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            config = dict(self._strategy_config)
            if "default_strategy" in payload:
                config["default_strategy"] = str(payload["default_strategy"])
            if "weights" in payload:
                weights = payload["weights"] or {}
                normalized_weights = {
                    "uncertainty": max(0.0, _safe_float(weights.get("uncertainty"), 0.0)),
                    "diversity": max(0.0, _safe_float(weights.get("diversity"), 0.0)),
                    "representativeness": max(0.0, _safe_float(weights.get("representativeness"), 0.0)),
                    "committee": max(0.0, _safe_float(weights.get("committee"), 0.0)),
                }
                total = sum(normalized_weights.values())
                if total <= 1e-12:
                    raise ValueError("weights must contain at least one positive value")
                normalized_weights = {k: v / total for k, v in normalized_weights.items()}
                config["weights"] = normalized_weights
            if "adaptive" in payload:
                adaptive = payload["adaptive"] or {}
                cfg = dict(config.get("adaptive") or {})
                for key in ("enabled", "switch_patience", "improvement_threshold"):
                    if key in adaptive:
                        cfg[key] = adaptive[key]
                config["adaptive"] = cfg
            if "committee" in payload:
                committee = payload["committee"] or {}
                cfg = dict(config.get("committee") or {})
                if "models" in committee:
                    models = committee.get("models") or []
                    parsed = []
                    for idx, item in enumerate(models):
                        parsed.append(
                            {
                                "name": str(item.get("name") or f"model_{idx}"),
                                "arch": str(item.get("arch") or "mlp"),
                                "seed": _safe_int(item.get("seed"), idx + 1),
                                "weight": max(0.1, _safe_float(item.get("weight"), 1.0)),
                                "enabled": bool(item.get("enabled", True)),
                            }
                        )
                    if parsed:
                        cfg["models"] = parsed
                if "voting" in committee:
                    cfg["voting"] = str(committee["voting"])
                config["committee"] = cfg

            self._strategy_config = config
            return self.get_strategy_config()

    def get_strategy_config(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "default_strategy": self._strategy_config["default_strategy"],
                "weights": dict(self._strategy_config["weights"]),
                "adaptive": dict(self._strategy_config["adaptive"]),
                "committee": {
                    "voting": self._strategy_config["committee"]["voting"],
                    "model_count": len(self._strategy_config["committee"]["models"]),
                    "models": [dict(item) for item in self._strategy_config["committee"]["models"]],
                },
            }

    def configure_budget(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            cfg = dict(self._budget_config)
            if "total_budget" in payload:
                cfg["total_budget"] = max(1, _safe_int(payload["total_budget"], cfg["total_budget"]))
            if "batch_budget" in payload:
                cfg["batch_budget"] = max(1, _safe_int(payload["batch_budget"], cfg["batch_budget"]))
            if "max_rounds" in payload:
                cfg["max_rounds"] = max(1, _safe_int(payload["max_rounds"], cfg["max_rounds"]))
            if "target_performance" in payload:
                cfg["target_performance"] = min(1.0, max(0.0, _safe_float(payload["target_performance"], cfg["target_performance"])))
            if "min_improvement" in payload:
                cfg["min_improvement"] = max(0.0, _safe_float(payload["min_improvement"], cfg["min_improvement"]))
            if "uncertainty_threshold" in payload:
                cfg["uncertainty_threshold"] = max(0.0, _safe_float(payload["uncertainty_threshold"], cfg["uncertainty_threshold"]))

            self._budget_config = cfg
            return self.get_budget_info()

    def get_budget_info(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if session_id:
                session = self._require_session(session_id)
                return {
                    "session_id": session_id,
                    "budget": dict(session["budget"]),
                    "used_budget": session["used_budget"],
                    "remaining_budget": max(0, session["budget"]["total_budget"] - session["used_budget"]),
                    "round": session["round"],
                }
            return {"global_budget": dict(self._budget_config)}

    # --------------------------
    # session lifecycle
    # --------------------------
    def init_active_learning(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            dataset_id = str(payload.get("dataset_id") or "dataset_default")
            session_id = str(payload.get("session_id") or f"al_{uuid4().hex[:12]}")

            labeled = self._prepare_samples(payload.get("labeled_samples") or [], default_prefix="lbl")
            unlabeled = self._prepare_samples(payload.get("unlabeled_samples") or [], default_prefix="ulb")

            budget = dict(self._budget_config)
            budget_override = payload.get("budget") or {}
            for key in budget:
                if key in budget_override:
                    budget[key] = budget_override[key]
            budget["total_budget"] = max(1, _safe_int(budget["total_budget"], self._budget_config["total_budget"]))
            budget["batch_budget"] = max(1, _safe_int(budget["batch_budget"], self._budget_config["batch_budget"]))
            budget["max_rounds"] = max(1, _safe_int(budget["max_rounds"], self._budget_config["max_rounds"]))
            budget["target_performance"] = min(1.0, max(0.0, _safe_float(budget["target_performance"], self._budget_config["target_performance"])))
            budget["min_improvement"] = max(0.0, _safe_float(budget["min_improvement"], self._budget_config["min_improvement"]))
            budget["uncertainty_threshold"] = max(0.0, _safe_float(budget["uncertainty_threshold"], self._budget_config["uncertainty_threshold"]))

            initial_performance = self._estimate_performance(labeled)
            initial_uncertainty = self._estimate_uncertainty(unlabeled)

            session = {
                "session_id": session_id,
                "dataset_id": dataset_id,
                "owner": uid,
                "created_at": _iso(_utcnow()),
                "updated_at": _iso(_utcnow()),
                "strategy": str(payload.get("strategy") or self._strategy_config["default_strategy"]),
                "committee": [dict(item) for item in self._strategy_config["committee"]["models"]],
                "labeled_samples": labeled,
                "unlabeled_pool": {item["sample_id"]: item for item in unlabeled},
                "selected_history": [],
                "label_history": [],
                "performance_curve": [initial_performance],
                "uncertainty_curve": [initial_uncertainty],
                "distribution_shift_curve": [0.0],
                "parameter_change_curve": [0.0],
                "efficiency_curve": [0.0],
                "round": 0,
                "used_budget": 0,
                "budget": budget,
                "active": True,
                "stop_reason": None,
                "strategy_history": [str(payload.get("strategy") or self._strategy_config["default_strategy"])],
                "pseudo_labels": [],
                "temporal_ensemble": {},
                "annotation_events": [],
            }
            self._sessions[session_id] = session
            return self.get_status(session_id)

    def get_status(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._require_session(session_id)
            latest_performance = session["performance_curve"][-1] if session["performance_curve"] else 0.0
            latest_uncertainty = session["uncertainty_curve"][-1] if session["uncertainty_curve"] else 0.0
            return {
                "session_id": session_id,
                "dataset_id": session["dataset_id"],
                "active": session["active"],
                "round": session["round"],
                "strategy": session["strategy"],
                "labeled_count": len(session["labeled_samples"]),
                "unlabeled_count": len(session["unlabeled_pool"]),
                "used_budget": session["used_budget"],
                "remaining_budget": max(0, session["budget"]["total_budget"] - session["used_budget"]),
                "stop_reason": session["stop_reason"],
                "metrics": {
                    "latest_performance": latest_performance,
                    "latest_uncertainty": latest_uncertainty,
                    "learning_efficiency": session["efficiency_curve"][-1] if session["efficiency_curve"] else 0.0,
                },
                "curves": {
                    "performance": list(session["performance_curve"]),
                    "uncertainty": list(session["uncertainty_curve"]),
                    "distribution_shift": list(session["distribution_shift_curve"]),
                    "parameter_change": list(session["parameter_change_curve"]),
                    "efficiency": list(session["efficiency_curve"]),
                },
            }

    # --------------------------
    # active learning sampling
    # --------------------------
    def select_samples(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            session = self._require_session(str(payload.get("session_id")))
            if not session["active"]:
                raise ValueError("session has stopped")

            top_k = max(1, _safe_int(payload.get("top_k"), session["budget"]["batch_budget"]))
            top_k = min(top_k, max(1, len(session["unlabeled_pool"])))
            strategy = str(payload.get("strategy") or session["strategy"])
            batch_mode = str(payload.get("selection_mode") or "batch")

            candidates = list(session["unlabeled_pool"].values())
            scored = self._score_candidates(strategy, candidates, session)

            if batch_mode == "incremental":
                chosen: List[Dict[str, Any]] = []
                chosen_ids: set[str] = set()
                for _ in range(top_k):
                    rescored = self._score_candidates(strategy, [c for c in candidates if c["sample_id"] not in chosen_ids], session, chosen)
                    if not rescored:
                        break
                    best = rescored[0]
                    chosen.append(best)
                    chosen_ids.add(best["sample_id"])
                selected = chosen
            else:
                selected = scored[:top_k]

            now = _iso(_utcnow())
            selection_record = {
                "timestamp": now,
                "strategy": strategy,
                "selection_mode": batch_mode,
                "count": len(selected),
                "items": [
                    {
                        "sample_id": item["sample_id"],
                        "score": item["score"],
                        "uncertainty": item["details"]["uncertainty"],
                        "diversity": item["details"]["diversity"],
                        "representativeness": item["details"]["representativeness"],
                        "committee": item["details"]["committee"],
                        "pareto_rank": item["details"].get("pareto_rank", 1),
                    }
                    for item in selected
                ],
            }
            session["selected_history"].append(selection_record)
            session["updated_at"] = now

            uncertainties = [item["details"]["uncertainty"] for item in selected]
            if uncertainties:
                session["uncertainty_curve"].append(_mean(uncertainties))

            self._update_strategy_by_feedback(session)
            return {
                "session_id": session["session_id"],
                "strategy": strategy,
                "selection_mode": batch_mode,
                "count": len(selected),
                "items": selected,
                "monitoring": {
                    "budget_usage": session["used_budget"],
                    "remaining_budget": max(0, session["budget"]["total_budget"] - session["used_budget"]),
                    "latest_uncertainty": session["uncertainty_curve"][-1] if session["uncertainty_curve"] else 0.0,
                },
            }

    def submit_labels(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            session = self._require_session(str(payload.get("session_id")))
            labels = payload.get("labels") or []
            if not isinstance(labels, list) or not labels:
                raise ValueError("labels must be a non-empty list")

            accepted = 0
            skipped = 0
            now = _iso(_utcnow())
            labeled_items: List[Dict[str, Any]] = []
            for item in labels:
                sample_id = str(item.get("sample_id") or "")
                if not sample_id or sample_id not in session["unlabeled_pool"]:
                    skipped += 1
                    continue
                sample = session["unlabeled_pool"].pop(sample_id)
                sample["label"] = item.get("label")
                sample["label_confidence"] = min(1.0, max(0.0, _safe_float(item.get("confidence"), 0.8)))
                sample["labeled_by"] = str(item.get("annotator") or uid)
                sample["labeled_at"] = now
                session["labeled_samples"].append(sample)
                labeled_items.append(sample)
                accepted += 1

            session["used_budget"] += accepted
            session["label_history"].append(
                {
                    "timestamp": now,
                    "user_id": uid,
                    "accepted": accepted,
                    "skipped": skipped,
                }
            )
            session["annotation_events"].append(
                {
                    "event": "label_submit",
                    "timestamp": now,
                    "annotator": uid,
                    "count": accepted,
                }
            )
            session["updated_at"] = now

            return {
                "session_id": session["session_id"],
                "accepted": accepted,
                "skipped": skipped,
                "used_budget": session["used_budget"],
                "remaining_budget": max(0, session["budget"]["total_budget"] - session["used_budget"]),
                "labeled_count": len(session["labeled_samples"]),
                "unlabeled_count": len(session["unlabeled_pool"]),
                "items": [self._view_sample(item) for item in labeled_items],
            }

    def update_model(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            session = self._require_session(str(payload.get("session_id")))

            round_gain_factor = min(1.0, max(0.1, _safe_float(payload.get("gain_factor"), 0.5)))
            latest_perf = session["performance_curve"][-1] if session["performance_curve"] else 0.5
            pseudo_count = len(session["pseudo_labels"])
            labeled_delta = session["label_history"][-1]["accepted"] if session["label_history"] else 0

            gain = 0.005 * round_gain_factor * (1 + min(2.0, labeled_delta / 10.0) + min(1.0, pseudo_count / 20.0))
            new_perf = min(0.995, latest_perf + gain)
            improvement = new_perf - latest_perf

            uncertainty = self._estimate_uncertainty(list(session["unlabeled_pool"].values()))
            distribution_shift = self._estimate_distribution_shift(session)
            parameter_change = min(1.0, 0.05 + gain * 5)
            efficiency = improvement / max(1, labeled_delta)

            session["performance_curve"].append(new_perf)
            session["uncertainty_curve"].append(uncertainty)
            session["distribution_shift_curve"].append(distribution_shift)
            session["parameter_change_curve"].append(parameter_change)
            session["efficiency_curve"].append(efficiency)
            session["round"] += 1
            session["updated_at"] = _iso(_utcnow())

            stop_reasons = self._check_stop_conditions(session, improvement)
            if stop_reasons:
                session["active"] = False
                session["stop_reason"] = "; ".join(stop_reasons)

            return {
                "session_id": session["session_id"],
                "round": session["round"],
                "performance": {
                    "previous": latest_perf,
                    "current": new_perf,
                    "improvement": improvement,
                },
                "monitoring": {
                    "uncertainty": uncertainty,
                    "distribution_shift": distribution_shift,
                    "parameter_change": parameter_change,
                    "efficiency": efficiency,
                },
                "should_stop": not session["active"],
                "stop_reason": session["stop_reason"],
            }

    # --------------------------
    # semi-supervised learning
    # --------------------------
    def generate_pseudo_labels(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            session_id = str(payload.get("session_id") or "")
            threshold = min(1.0, max(0.0, _safe_float(payload.get("confidence_threshold"), 0.8)))
            max_items = max(1, _safe_int(payload.get("max_items"), 50))
            rounds = max(1, _safe_int(payload.get("rounds"), 1))
            filter_enabled = bool(payload.get("filter", True))

            if session_id:
                session = self._require_session(session_id)
                pool = list(session["unlabeled_pool"].values())
            else:
                session = None
                pool = self._prepare_samples(payload.get("samples") or [], default_prefix="pl")

            generated: List[Dict[str, Any]] = []
            current_threshold = threshold
            for step in range(rounds):
                for sample in pool:
                    if len(generated) >= max_items:
                        break
                    probs = self._predict_probabilities(sample)
                    confidence = max(probs)
                    label_idx = probs.index(confidence)
                    margin = self._margin_uncertainty(probs)
                    if confidence < current_threshold:
                        continue
                    if filter_enabled and margin < 0.05:
                        continue
                    generated.append(
                        {
                            "sample_id": sample["sample_id"],
                            "pseudo_label": f"class_{label_idx}",
                            "confidence": confidence,
                            "margin": margin,
                            "round": step + 1,
                            "source": "iterative" if rounds > 1 else "single",
                        }
                    )
                current_threshold = max(0.5, current_threshold - 0.05)
                if len(generated) >= max_items:
                    break

            if not generated and pool:
                scored = []
                for sample in pool:
                    probs = self._predict_probabilities(sample)
                    confidence = max(probs)
                    label_idx = probs.index(confidence)
                    scored.append((confidence, sample["sample_id"], label_idx))
                scored.sort(reverse=True)
                best = scored[0]
                generated.append(
                    {
                        "sample_id": best[1],
                        "pseudo_label": f"class_{best[2]}",
                        "confidence": best[0],
                        "margin": 0.0,
                        "round": 1,
                        "source": "fallback_top_confidence",
                    }
                )

            if session is not None:
                session["pseudo_labels"] = generated
                self._pseudo_labels[session_id] = generated
            key = session_id or f"dataset:{payload.get('dataset_id') or 'default'}"
            self._pseudo_labels[key] = generated

            confidences = [item["confidence"] for item in generated]
            return {
                "session_id": session_id or None,
                "generated": len(generated),
                "threshold_start": threshold,
                "threshold_end": current_threshold,
                "quality": {
                    "avg_confidence": _mean(confidences),
                    "min_confidence": min(confidences) if confidences else 0.0,
                    "max_confidence": max(confidences) if confidences else 0.0,
                },
                "items": generated,
            }

    def get_pseudo_labels(self, session_id: Optional[str] = None, dataset_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            key = None
            if session_id:
                key = session_id
            elif dataset_id:
                key = f"dataset:{dataset_id}"
            if key:
                items = list(self._pseudo_labels.get(key, []))
                return {"key": key, "count": len(items), "items": items}

            all_items = []
            for k, rows in self._pseudo_labels.items():
                all_items.append({"key": k, "count": len(rows)})
            return {"count": len(all_items), "groups": all_items}

    def consistency_regularization(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            session = self._require_session(str(payload.get("session_id")))
            augmentations = payload.get("augmentations") or ["rotate", "flip", "noise"]
            max_items = max(1, _safe_int(payload.get("max_items"), 40))

            pool = list(session["unlabeled_pool"].values())[:max_items]
            if not pool:
                return {
                    "session_id": session["session_id"],
                    "consistency_loss": 0.0,
                    "temporal_ensembling": 0.0,
                    "mean_teacher": 0.0,
                    "vat_loss": 0.0,
                }

            consistency_losses: List[float] = []
            temporal_losses: List[float] = []
            teacher_losses: List[float] = []
            vat_losses: List[float] = []

            for sample in pool:
                sid = sample["sample_id"]
                base_probs = self._predict_probabilities(sample)
                augmented_probs = []
                for aug in augmentations:
                    aug_sample = dict(sample)
                    aug_sample["features"] = self._augment_features(sample.get("features", []), aug)
                    augmented_probs.append(self._predict_probabilities(aug_sample))

                aug_mean = [
                    _mean([probs[idx] for probs in augmented_probs], fallback=base_probs[idx])
                    for idx in range(len(base_probs))
                ]
                cons = _mean([(base_probs[i] - aug_mean[i]) ** 2 for i in range(len(base_probs))])
                consistency_losses.append(cons)

                old_ema = session["temporal_ensemble"].get(sid)
                if old_ema is None:
                    new_ema = base_probs
                else:
                    new_ema = [0.8 * old_ema[i] + 0.2 * base_probs[i] for i in range(len(base_probs))]
                session["temporal_ensemble"][sid] = new_ema
                temporal_losses.append(_mean([(new_ema[i] - base_probs[i]) ** 2 for i in range(len(base_probs))]))

                teacher_pred = [0.9 * p + 0.1 / len(base_probs) for p in new_ema]
                teacher_losses.append(_mean([(teacher_pred[i] - base_probs[i]) ** 2 for i in range(len(base_probs))]))

                vat_losses.append(self._vat_loss(sample))

            return {
                "session_id": session["session_id"],
                "sample_count": len(pool),
                "consistency_loss": _mean(consistency_losses),
                "temporal_ensembling": _mean(temporal_losses),
                "mean_teacher": _mean(teacher_losses),
                "vat_loss": _mean(vat_losses),
                "augmentations": list(augmentations),
            }

    def co_training(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            session = self._require_session(str(payload.get("session_id")))
            max_items = max(1, _safe_int(payload.get("max_items"), 30))

            pool = list(session["unlabeled_pool"].values())[:max_items]
            transfers = []
            agreements = 0
            for sample in pool:
                f = sample.get("features") or []
                view_a = f[::2] if len(f) > 1 else f
                view_b = f[1::2] if len(f) > 1 else f
                pa = self._predict_probabilities({"features": view_a, "sample_id": sample["sample_id"]})
                pb = self._predict_probabilities({"features": view_b, "sample_id": sample["sample_id"]})
                la = int(max(range(len(pa)), key=lambda i: pa[i]))
                lb = int(max(range(len(pb)), key=lambda i: pb[i]))
                agree = la == lb
                agreements += 1 if agree else 0
                transfers.append(
                    {
                        "sample_id": sample["sample_id"],
                        "model_a_label": f"class_{la}",
                        "model_b_label": f"class_{lb}",
                        "agreement": agree,
                        "confidence": (max(pa) + max(pb)) / 2,
                    }
                )

            return {
                "session_id": session["session_id"],
                "sample_count": len(pool),
                "agreement_rate": agreements / max(1, len(pool)),
                "items": transfers,
                "update_policy": "mutual_pseudo_label + agreement_check",
            }

    def graph_semi_supervised(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            session = self._require_session(str(payload.get("session_id")))
            graph_type = str(payload.get("graph_type") or "knn")
            k = max(1, _safe_int(payload.get("k"), 5))
            radius = max(0.01, _safe_float(payload.get("radius"), 0.8))
            iterations = max(1, _safe_int(payload.get("iterations"), 5))

            nodes = session["labeled_samples"] + list(session["unlabeled_pool"].values())
            if not nodes:
                return {"session_id": session["session_id"], "node_count": 0, "edge_count": 0, "items": []}

            features = {item["sample_id"]: item.get("features") or [] for item in nodes}
            labels = {}
            for item in session["labeled_samples"]:
                label = item.get("label")
                if label is not None:
                    labels[item["sample_id"]] = str(label)

            neighbors: Dict[str, List[str]] = defaultdict(list)
            ids = list(features.keys())
            for sid in ids:
                base = features[sid]
                dists = []
                for other in ids:
                    if sid == other:
                        continue
                    dist = _l2_distance(base, features[other])
                    dists.append((other, dist))
                dists.sort(key=lambda x: x[1])
                if graph_type == "radius":
                    neighbors[sid] = [other for other, dist in dists if dist <= radius]
                else:
                    neighbors[sid] = [other for other, _ in dists[:k]]

            propagated = dict(labels)
            for _ in range(iterations):
                for sid in ids:
                    if sid in labels:
                        continue
                    votes = [propagated[nid] for nid in neighbors[sid] if nid in propagated]
                    if votes:
                        propagated[sid] = Counter(votes).most_common(1)[0][0]

            gcn_score = min(1.0, 0.55 + 0.02 * len(neighbors))
            gat_score = min(1.0, 0.5 + 0.03 * _mean([len(v) for v in neighbors.values()]))
            smoothing = min(1.0, max(0.0, _safe_float(payload.get("label_smoothing"), 0.1)))

            items = []
            for sid in ids:
                if sid in labels:
                    continue
                if sid in propagated:
                    items.append(
                        {
                            "sample_id": sid,
                            "label": propagated[sid],
                            "smoothed_confidence": 1.0 - smoothing,
                        }
                    )

            return {
                "session_id": session["session_id"],
                "graph_type": graph_type,
                "node_count": len(ids),
                "edge_count": sum(len(v) for v in neighbors.values()),
                "propagated_count": len(items),
                "gcn_score": gcn_score,
                "gat_score": gat_score,
                "items": items,
            }

    def self_training(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            session = self._require_session(str(payload.get("session_id")))
            max_rounds = max(1, _safe_int(payload.get("max_rounds"), 5))
            threshold = min(1.0, max(0.0, _safe_float(payload.get("threshold"), 0.9)))
            early_stop_patience = max(1, _safe_int(payload.get("early_stop_patience"), 2))

            total_added = 0
            no_gain_rounds = 0
            round_logs = []
            current_threshold = threshold

            for step in range(max_rounds):
                generated = self.generate_pseudo_labels(
                    {
                        "session_id": session["session_id"],
                        "confidence_threshold": current_threshold,
                        "max_items": 20,
                        "rounds": 1,
                        "filter": True,
                    }
                )
                pseudo_items = generated["items"]
                if not pseudo_items:
                    no_gain_rounds += 1
                else:
                    add_count = min(len(pseudo_items), max(1, len(session["unlabeled_pool"]) // 3))
                    no_gain_rounds = 0
                    total_added += add_count
                round_logs.append(
                    {
                        "round": step + 1,
                        "threshold": current_threshold,
                        "generated": len(pseudo_items),
                        "selected": min(len(pseudo_items), max(1, len(session["unlabeled_pool"]) // 3)) if pseudo_items else 0,
                    }
                )
                current_threshold = max(0.6, current_threshold - 0.05)
                if no_gain_rounds >= early_stop_patience:
                    break

            return {
                "session_id": session["session_id"],
                "total_added": total_added,
                "stopped_early": no_gain_rounds >= early_stop_patience,
                "final_threshold": current_threshold,
                "round_logs": round_logs,
            }

    # --------------------------
    # incremental learning
    # --------------------------
    def incremental_update(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            session_id = str(payload.get("session_id") or "")
            session = self._require_session(session_id) if session_id else None

            updates = payload.get("updates") or payload.get("samples") or []
            if not isinstance(updates, list):
                raise ValueError("updates must be a list")
            batch_size = max(1, _safe_int(payload.get("batch_size"), 16))
            mode = str(payload.get("mode") or "online")

            forgetting_cfg = payload.get("forgetting_protection") or {}
            method = str(forgetting_cfg.get("method") or "ewc")
            replay_size = max(0, _safe_int(forgetting_cfg.get("replay_size"), 64))
            lambda_ewc = max(0.0, _safe_float(forgetting_cfg.get("lambda_ewc"), 0.3))

            weighting = payload.get("importance_weighting") or {}
            new_w = max(0.0, _safe_float(weighting.get("new_data_weight"), 1.0))
            old_w = max(0.0, _safe_float(weighting.get("old_data_weight"), 0.7))
            dyn = bool(weighting.get("dynamic", True))

            tuning = payload.get("fine_tuning") or {}
            strategy = str(tuning.get("strategy") or "partial")
            lr = max(1e-6, _safe_float(tuning.get("lr"), 1e-3))
            epochs = max(1, _safe_int(tuning.get("epochs"), 2))
            freeze_ratio = min(1.0, max(0.0, _safe_float(tuning.get("freeze_ratio"), 0.4)))

            processed_batches = max(1, math.ceil(len(updates) / batch_size))
            weight_ratio = new_w / max(new_w + old_w, 1e-6)
            if dyn:
                weight_ratio = min(0.95, max(0.05, weight_ratio + 0.02 * processed_batches))

            ewc_penalty = lambda_ewc * (1.0 - weight_ratio)
            replay_gain = min(0.08, replay_size / 2000)
            tuning_gain = min(0.12, (epochs * lr * 100) * (1.0 - freeze_ratio * 0.5))
            update_gain = min(0.2, 0.02 + replay_gain + tuning_gain)

            record = {
                "update_id": f"inc_{uuid4().hex[:12]}",
                "timestamp": _iso(_utcnow()),
                "session_id": session_id or None,
                "user_id": uid,
                "mode": mode,
                "samples": len(updates),
                "batch_size": batch_size,
                "processed_batches": processed_batches,
                "forgetting_protection": {
                    "method": method,
                    "ewc_penalty": ewc_penalty,
                    "replay_size": replay_size,
                },
                "importance_weighting": {
                    "new_data_weight": new_w,
                    "old_data_weight": old_w,
                    "dynamic_ratio": weight_ratio,
                },
                "fine_tuning": {
                    "strategy": strategy,
                    "lr": lr,
                    "epochs": epochs,
                    "freeze_ratio": freeze_ratio,
                },
                "update_gain": update_gain,
            }
            self._incremental_history.append(record)

            if session is not None:
                last_perf = session["performance_curve"][-1] if session["performance_curve"] else 0.5
                new_perf = min(0.995, last_perf + update_gain * 0.15)
                session["performance_curve"].append(new_perf)
                session["parameter_change_curve"].append(min(1.0, update_gain * 2.5))
                session["updated_at"] = _iso(_utcnow())

            return record

    def evaluate_incremental(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            history = self._incremental_history
            if not history:
                return {
                    "history_count": 0,
                    "forgetting_score": 0.0,
                    "new_task_performance": 0.0,
                    "overall_performance": 0.0,
                    "update_efficiency": 0.0,
                    "memory_usage": 0,
                }

            recent = history[-max(1, _safe_int(payload.get("window"), 10)) :]
            gains = [item["update_gain"] for item in recent]
            penalties = [item["forgetting_protection"]["ewc_penalty"] for item in recent]
            sample_counts = [item["samples"] for item in recent]
            replay_sizes = [item["forgetting_protection"]["replay_size"] for item in recent]

            new_task_perf = min(1.0, 0.55 + _mean(gains) * 1.6)
            forgetting_score = max(0.0, 0.35 - _mean(penalties) * 0.4)
            overall = min(1.0, new_task_perf - forgetting_score * 0.2 + 0.08)
            efficiency = _mean(gains) / max(1.0, _mean(sample_counts, fallback=1.0))
            memory_usage = int(_mean(replay_sizes) * 16 + len(recent) * 4)

            return {
                "history_count": len(history),
                "evaluated_count": len(recent),
                "forgetting_score": forgetting_score,
                "new_task_performance": new_task_perf,
                "overall_performance": overall,
                "update_efficiency": efficiency,
                "memory_usage": memory_usage,
            }

    def get_incremental_history(self, limit: int = 20) -> Dict[str, Any]:
        with self._lock:
            size = max(1, limit)
            items = self._incremental_history[-size:]
            return {"count": len(items), "items": items}

    # --------------------------
    # annotation interfaces
    # --------------------------
    def create_annotation_requests(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)
            session = self._require_session(str(payload.get("session_id")))
            selected = payload.get("samples") or []
            if not selected:
                selected = [item for item in (session["selected_history"][-1]["items"] if session["selected_history"] else [])]

            task_id = f"ann_{uuid4().hex[:12]}"
            task = {
                "task_id": task_id,
                "session_id": session["session_id"],
                "created_by": uid,
                "created_at": _iso(_utcnow()),
                "status": "pending",
                "samples": selected,
                "progress": {"done": 0, "total": len(selected)},
                "quality": {"consistency": 1.0, "conflicts": 0},
            }
            self._annotation_tasks[task_id] = task
            return task

    def create_batch_annotation(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            uid = self.resolve_user_id(user_id)  # noqa: F841
            session = self._require_session(str(payload.get("session_id")))
            batch_size = max(1, _safe_int(payload.get("batch_size"), 20))
            pool = list(session["unlabeled_pool"].values())[:batch_size]
            shortcut = bool(payload.get("shortcut_enabled", True))
            template = payload.get("template") or {"label": "unknown", "confidence": 0.7}
            return {
                "session_id": session["session_id"],
                "batch_size": len(pool),
                "shortcut_enabled": shortcut,
                "template": template,
                "items": [self._view_sample(item) for item in pool],
            }

    def get_annotation_suggestions(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            session = self._require_session(str(payload.get("session_id")))
            sample_id = str(payload.get("sample_id") or "")
            sample = session["unlabeled_pool"].get(sample_id)
            if not sample:
                raise KeyError("sample not found in unlabeled pool")

            probs = self._predict_probabilities(sample)
            label_idx = int(max(range(len(probs)), key=lambda i: probs[i]))
            refs = self._find_similar_labeled(session, sample, top_n=3)
            return {
                "sample_id": sample_id,
                "suggested_label": f"class_{label_idx}",
                "confidence": max(probs),
                "similar_references": refs,
                "hint": "优先核验与历史相似样本的一致性",
            }

    def assess_annotation_quality(self, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            _ = self.resolve_user_id(user_id)
            annotations = payload.get("annotations") or []
            if not annotations:
                return {
                    "count": 0,
                    "consistency": 1.0,
                    "conflict_rate": 0.0,
                    "review_required": False,
                }

            by_sample: Dict[str, List[str]] = defaultdict(list)
            for ann in annotations:
                sid = str(ann.get("sample_id") or "")
                lab = str(ann.get("label") or "")
                if sid and lab:
                    by_sample[sid].append(lab)

            total = len(by_sample)
            conflicts = 0
            for labs in by_sample.values():
                if len(set(labs)) > 1:
                    conflicts += 1
            conflict_rate = conflicts / max(1, total)
            consistency = 1.0 - conflict_rate
            return {
                "count": total,
                "consistency": consistency,
                "conflict_rate": conflict_rate,
                "review_required": conflict_rate > 0.2,
            }

    # --------------------------
    # evaluation
    # --------------------------
    def evaluate_active_learning(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._require_session(session_id)
            perf = session["performance_curve"]
            budget = session["used_budget"]
            speed = (perf[-1] - perf[0]) / max(1, len(perf) - 1)
            quality = 1.0 - _mean(session["uncertainty_curve"], fallback=0.5)
            return {
                "session_id": session_id,
                "learning_curve": list(perf),
                "learning_efficiency": (perf[-1] - perf[0]) / max(1, budget),
                "sample_quality": quality,
                "strategy_comparison": self._strategy_snapshot(session),
                "convergence_speed": speed,
            }

    def evaluate_semi_supervised(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._require_session(session_id)
            pseudo = session["pseudo_labels"]
            conf = [item["confidence"] for item in pseudo]
            utilization = len(pseudo) / max(1, len(session["labeled_samples"]) + len(session["unlabeled_pool"]))
            return {
                "session_id": session_id,
                "pseudo_label_quality": _mean(conf),
                "consistency_score": 1.0 - _mean(session["uncertainty_curve"], fallback=0.5),
                "performance_gain": (session["performance_curve"][-1] - session["performance_curve"][0]),
                "supervised_baseline_gap": 0.03,
                "data_utilization": utilization,
            }

    def visualization_payload(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._require_session(session_id)
            uncertainty_heatmap = []
            for idx, item in enumerate(list(session["unlabeled_pool"].values())[:50]):
                x = _safe_float((item.get("features") or [0.0])[0], idx)
                y = _safe_float((item.get("features") or [0.0, 0.0])[1], idx)
                u = self._single_uncertainty(item)
                uncertainty_heatmap.append({"x": x, "y": y, "u": u})
            pseudo_dist = Counter([p["pseudo_label"] for p in session["pseudo_labels"]])
            return {
                "session_id": session_id,
                "learning_curve": list(session["performance_curve"]),
                "uncertainty_curve": list(session["uncertainty_curve"]),
                "uncertainty_heatmap": uncertainty_heatmap,
                "selection_trace": list(session["selected_history"]),
                "pseudo_label_distribution": dict(pseudo_dist),
            }

    # --------------------------
    # internals
    # --------------------------
    def _require_session(self, session_id: str) -> Dict[str, Any]:
        if not session_id or session_id not in self._sessions:
            raise KeyError("session not found")
        return self._sessions[session_id]

    def _prepare_samples(self, samples: List[Dict[str, Any]], default_prefix: str) -> List[Dict[str, Any]]:
        prepared = []
        for idx, item in enumerate(samples):
            sample = dict(item)
            sample_id = str(sample.get("sample_id") or sample.get("id") or f"{default_prefix}_{idx}")
            sample["sample_id"] = sample_id
            features = sample.get("features")
            if not features:
                features = self._build_features(sample)
            sample["features"] = [float(v) for v in features]
            prepared.append(sample)
        return prepared

    def _build_features(self, sample: Dict[str, Any]) -> List[float]:
        x = _safe_float(sample.get("x"), 0.0)
        y = _safe_float(sample.get("y"), 0.0)
        value = _safe_float(sample.get("value"), 0.0)
        score = _safe_float(sample.get("score"), 0.0)
        return [x, y, value, score, x * y * 0.01]

    def _predict_probabilities(self, sample: Dict[str, Any], seed_shift: int = 0) -> List[float]:
        probs = sample.get("probabilities")
        if isinstance(probs, list) and probs:
            s = sum(max(0.0, _safe_float(v)) for v in probs)
            if s > 1e-12:
                return [max(0.0, _safe_float(v)) / s for v in probs]

        f = sample.get("features") or [0.0, 0.0, 0.0]
        mean_f = _mean(f)
        var_f = _variance(f)
        logits = [
            mean_f * 0.6 + var_f * 0.4 + seed_shift * 0.01,
            -mean_f * 0.25 + var_f * 0.55 + seed_shift * 0.005,
            var_f * 0.35 - mean_f * 0.15 - seed_shift * 0.01,
        ]
        return _softmax(logits)

    def _committee_predictions(self, sample: Dict[str, Any], session: Dict[str, Any]) -> List[List[float]]:
        preds = []
        for model in session.get("committee", []):
            if not model.get("enabled", True):
                continue
            seed = _safe_int(model.get("seed"), 0)
            preds.append(self._predict_probabilities(sample, seed_shift=seed))
        if not preds:
            preds.append(self._predict_probabilities(sample))
        return preds

    def _single_uncertainty(self, sample: Dict[str, Any]) -> float:
        probs = self._predict_probabilities(sample)
        ent = _entropy(probs)
        margin = self._margin_uncertainty(probs)
        return min(1.0, 0.65 * (ent / math.log(len(probs))) + 0.35 * margin)

    def _margin_uncertainty(self, probs: List[float]) -> float:
        sorted_probs = sorted(probs, reverse=True)
        if len(sorted_probs) < 2:
            return 0.0
        return 1.0 - (sorted_probs[0] - sorted_probs[1])

    def _score_candidates(
        self,
        strategy: str,
        candidates: List[Dict[str, Any]],
        session: Dict[str, Any],
        selected: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        uncertainty_raw: Dict[str, float] = {}
        diversity_raw: Dict[str, float] = {}
        representative_raw: Dict[str, float] = {}
        committee_raw: Dict[str, float] = {}

        labeled_features = [item.get("features") or [] for item in session.get("labeled_samples", [])]
        selected_features = [(item.get("features") or []) for item in (selected or [])]

        cluster_counts = Counter()
        for item in candidates:
            cluster_counts[self._cluster_id(item)] += 1

        density_cache = self._density_scores(candidates)

        for item in candidates:
            sid = item["sample_id"]
            probs = self._predict_probabilities(item)
            committee_probs = self._committee_predictions(item, session)
            committee_conf = [max(p) for p in committee_probs]
            committee_labels = [int(max(range(len(p)), key=lambda i: p[i])) for p in committee_probs]

            pred_var = _variance(committee_conf)
            ent = _entropy(probs) / max(math.log(len(probs)), 1e-12)
            ci_width = 1.96 * 2 * math.sqrt(max(pred_var, 1e-12))
            margin_unc = self._margin_uncertainty(probs)
            eer = ent * (0.5 + 0.5 * margin_unc)

            uncertainty_raw[sid] = {
                "variance": pred_var,
                "entropy": ent,
                "confidence_interval": ci_width,
                "margin": margin_unc,
                "eer": eer,
            }.get(strategy, 0.45 * ent + 0.3 * margin_unc + 0.25 * ci_width)

            cluster_id = self._cluster_id(item)
            cluster_score = 1.0 / max(1, cluster_counts[cluster_id])
            core_set = self._core_set_distance(item.get("features") or [], labeled_features + selected_features)
            density = density_cache.get(sid, 0.0)
            deterministic = self._deterministic_distance(item.get("features") or [], selected_features)
            diversity_raw[sid] = {
                "cluster": cluster_score,
                "core_set": core_set,
                "density": density,
                "uncertainty_diversity_hybrid": 0.5 * cluster_score + 0.5 * core_set,
                "deterministic": deterministic,
            }.get(strategy, 0.3 * cluster_score + 0.3 * core_set + 0.2 * density + 0.2 * deterministic)

            prototype = self._prototype_score(item.get("features") or [], candidates)
            coverage = self._coverage_score(item.get("features") or [], labeled_features)
            gradient = _safe_float(item.get("gradient_norm"), 0.0)
            if gradient <= 0:
                gradient = (ent + margin_unc) * (1.0 + _l2_distance(item.get("features") or [], [0.0] * len(item.get("features") or [])))
            loss = _safe_float(item.get("loss"), 1.0 - max(probs))
            representative_raw[sid] = {
                "prototype": prototype,
                "coverage": coverage,
                "gradient": gradient,
                "loss": loss,
            }.get(strategy, 0.25 * prototype + 0.25 * coverage + 0.25 * gradient + 0.25 * loss)

            vote_hist = Counter(committee_labels)
            vote_probs = [count / len(committee_labels) for count in vote_hist.values()]
            vote_entropy = _entropy(vote_probs) / max(math.log(max(2, len(vote_probs))), 1e-12)
            model_diversity = _variance([_safe_float(m.get("seed"), 0.0) for m in session.get("committee", [])])
            if session.get("committee"):
                model_diversity = min(1.0, model_diversity / 200.0)
            committee_raw[sid] = 0.7 * vote_entropy + 0.3 * model_diversity

        uncertainty = _normalize_scores(uncertainty_raw)
        diversity = _normalize_scores(diversity_raw)
        representative = _normalize_scores(representative_raw)
        committee = _normalize_scores(committee_raw)

        fronts = self._pareto_front(uncertainty, diversity, representative)
        weight_cfg = dict(self._strategy_config["weights"])

        scored = []
        for item in candidates:
            sid = item["sample_id"]
            # 单策略直连分数
            if strategy in {"variance", "entropy", "confidence_interval", "margin", "eer"}:
                score = uncertainty[sid]
            elif strategy in {"cluster", "core_set", "density", "uncertainty_diversity_hybrid", "deterministic"}:
                score = diversity[sid]
            elif strategy in {"prototype", "coverage", "gradient", "loss"}:
                score = representative[sid]
            elif strategy in {"committee_vote", "committee_diversity", "weighted_vote"}:
                score = committee[sid]
            else:
                # 多目标融合策略 + 自适应权重
                adaptive_w = self._adaptive_weights(session, uncertainty[sid], diversity[sid], representative[sid])
                w_unc = adaptive_w.get("uncertainty", weight_cfg["uncertainty"])
                w_div = adaptive_w.get("diversity", weight_cfg["diversity"])
                w_rep = adaptive_w.get("representativeness", weight_cfg["representativeness"])
                w_com = adaptive_w.get("committee", weight_cfg["committee"])
                score = (
                    w_unc * uncertainty[sid]
                    + w_div * diversity[sid]
                    + w_rep * representative[sid]
                    + w_com * committee[sid]
                )

            pareto_rank = fronts.get(sid, 3)
            score = score + max(0.0, 0.03 * (3 - pareto_rank))

            scored.append(
                {
                    "sample_id": sid,
                    "score": min(1.0, max(0.0, score)),
                    "features": item.get("features") or [],
                    "details": {
                        "uncertainty": uncertainty[sid],
                        "diversity": diversity[sid],
                        "representativeness": representative[sid],
                        "committee": committee[sid],
                        "pareto_rank": pareto_rank,
                    },
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def _density_scores(self, candidates: List[Dict[str, Any]]) -> Dict[str, float]:
        result = {}
        all_features = [item.get("features") or [] for item in candidates]
        for item in candidates:
            sid = item["sample_id"]
            base = item.get("features") or []
            if not all_features:
                result[sid] = 0.0
                continue
            dists = [_l2_distance(base, other) for other in all_features if other is not base]
            avg_dist = _mean(dists, fallback=0.0)
            density = 1.0 / (1.0 + avg_dist)
            result[sid] = density
        return _normalize_scores(result)

    def _cluster_id(self, sample: Dict[str, Any]) -> str:
        f = sample.get("features") or [0.0, 0.0]
        x = int(_safe_float(f[0] if len(f) > 0 else 0.0) * 2)
        y = int(_safe_float(f[1] if len(f) > 1 else 0.0) * 2)
        return f"c_{x}_{y}"

    def _core_set_distance(self, features: List[float], references: List[List[float]]) -> float:
        if not references:
            return 1.0
        dists = [_l2_distance(features, ref) for ref in references if ref]
        if not dists:
            return 1.0
        return max(0.0, min(1.0, min(dists) / (1.0 + min(dists))))

    def _deterministic_distance(self, features: List[float], selected: List[List[float]]) -> float:
        if not selected:
            return 1.0
        dists = [_cosine_distance(features, ref) for ref in selected if ref]
        if not dists:
            return 1.0
        return max(0.0, min(1.0, _mean(dists)))

    def _prototype_score(self, features: List[float], candidates: List[Dict[str, Any]]) -> float:
        if not candidates:
            return 0.0
        n = len(features)
        centroid = []
        for idx in range(n):
            centroid.append(_mean([(c.get("features") or [0.0] * n)[idx] if idx < len(c.get("features") or []) else 0.0 for c in candidates]))
        dist = _l2_distance(features, centroid)
        return 1.0 / (1.0 + dist)

    def _coverage_score(self, features: List[float], labeled_features: List[List[float]]) -> float:
        if not labeled_features:
            return 1.0
        dists = [_l2_distance(features, ref) for ref in labeled_features if ref]
        if not dists:
            return 1.0
        far = max(dists)
        return max(0.0, min(1.0, far / (1.0 + far)))

    def _adaptive_weights(self, session: Dict[str, Any], u: float, d: float, r: float) -> Dict[str, float]:
        base = dict(self._strategy_config["weights"])
        if not self._strategy_config.get("adaptive", {}).get("enabled", True):
            return base

        perf_curve = session.get("performance_curve", [])
        if len(perf_curve) >= 2:
            improvement = perf_curve[-1] - perf_curve[-2]
        else:
            improvement = 0.01

        # 自适应策略：性能提升慢时更偏向探索（不确定性+多样性）
        if improvement < _safe_float(self._strategy_config["adaptive"].get("improvement_threshold"), 0.005):
            base["uncertainty"] = min(0.6, base["uncertainty"] + 0.08)
            base["diversity"] = min(0.45, base["diversity"] + 0.06)
            base["representativeness"] = max(0.1, base["representativeness"] - 0.08)
        else:
            base["representativeness"] = min(0.45, base["representativeness"] + 0.06)

        # 根据当前样本属性细调
        if u > 0.7:
            base["uncertainty"] += 0.05
        if d < 0.3:
            base["diversity"] += 0.04
        if r < 0.3:
            base["representativeness"] += 0.04

        total = sum(max(0.0, v) for v in base.values())
        if total <= 1e-12:
            return dict(self._strategy_config["weights"])
        return {k: max(0.0, v) / total for k, v in base.items()}

    def _pareto_front(self, uncertainty: Dict[str, float], diversity: Dict[str, float], representative: Dict[str, float]) -> Dict[str, int]:
        ids = list(uncertainty.keys())
        rank: Dict[str, int] = {sid: 3 for sid in ids}
        for sid in ids:
            dominated = 0
            for other in ids:
                if sid == other:
                    continue
                better_or_equal = (
                    uncertainty[other] >= uncertainty[sid]
                    and diversity[other] >= diversity[sid]
                    and representative[other] >= representative[sid]
                )
                strictly_better = (
                    uncertainty[other] > uncertainty[sid]
                    or diversity[other] > diversity[sid]
                    or representative[other] > representative[sid]
                )
                if better_or_equal and strictly_better:
                    dominated += 1
            if dominated == 0:
                rank[sid] = 1
            elif dominated <= 2:
                rank[sid] = 2
            else:
                rank[sid] = 3
        return rank

    def _update_strategy_by_feedback(self, session: Dict[str, Any]) -> None:
        adaptive = self._strategy_config.get("adaptive", {})
        if not adaptive.get("enabled", True):
            return

        perf = session.get("performance_curve", [])
        if len(perf) < max(3, _safe_int(adaptive.get("switch_patience"), 2) + 1):
            return
        recent_gain = perf[-1] - perf[-2]
        threshold = _safe_float(adaptive.get("improvement_threshold"), 0.005)
        if recent_gain >= threshold:
            return

        current = session["strategy"]
        fallback_chain = [
            "hybrid_multi_objective",
            "uncertainty_diversity_hybrid",
            "committee_vote",
            "coverage",
            "entropy",
        ]
        if current in fallback_chain:
            next_idx = (fallback_chain.index(current) + 1) % len(fallback_chain)
            next_strategy = fallback_chain[next_idx]
        else:
            next_strategy = fallback_chain[0]
        session["strategy"] = next_strategy
        session["strategy_history"].append(next_strategy)

    def _estimate_performance(self, labeled_samples: List[Dict[str, Any]]) -> float:
        if not labeled_samples:
            return 0.52
        confs = [
            _safe_float(item.get("label_confidence"), 0.75)
            for item in labeled_samples
            if item.get("label") is not None
        ]
        if not confs:
            confs = [0.72] * max(1, len(labeled_samples))
        return min(0.92, 0.45 + _mean(confs) * 0.55)

    def _estimate_uncertainty(self, samples: List[Dict[str, Any]]) -> float:
        if not samples:
            return 0.0
        values = [self._single_uncertainty(item) for item in samples[:100]]
        return _mean(values)

    def _estimate_distribution_shift(self, session: Dict[str, Any]) -> float:
        labeled = [item.get("features") or [] for item in session["labeled_samples"]]
        unlabeled = [item.get("features") or [] for item in session["unlabeled_pool"].values()]
        if not labeled or not unlabeled:
            return 0.0
        labeled_centroid = [
            _mean([f[idx] if idx < len(f) else 0.0 for f in labeled])
            for idx in range(max(len(f) for f in labeled))
        ]
        unlabeled_centroid = [
            _mean([f[idx] if idx < len(f) else 0.0 for f in unlabeled])
            for idx in range(max(len(f) for f in unlabeled))
        ]
        dist = _l2_distance(labeled_centroid, unlabeled_centroid)
        return min(1.0, dist / (1.0 + dist))

    def _check_stop_conditions(self, session: Dict[str, Any], improvement: float) -> List[str]:
        reasons = []
        budget = session["budget"]
        latest_perf = session["performance_curve"][-1] if session["performance_curve"] else 0.0
        latest_unc = session["uncertainty_curve"][-1] if session["uncertainty_curve"] else 1.0

        if session["used_budget"] >= budget["total_budget"]:
            reasons.append("达到标注预算")
        if latest_perf >= budget["target_performance"]:
            reasons.append("达到目标性能")
        if session["round"] >= budget["max_rounds"]:
            reasons.append("达到最大轮数")
        if improvement <= budget["min_improvement"]:
            reasons.append("性能不再提升")
        if latest_unc <= budget["uncertainty_threshold"]:
            reasons.append("不确定性低于阈值")
        return reasons

    def _find_similar_labeled(self, session: Dict[str, Any], sample: Dict[str, Any], top_n: int = 3) -> List[Dict[str, Any]]:
        refs = []
        base = sample.get("features") or []
        for item in session["labeled_samples"]:
            if item.get("label") is None:
                continue
            dist = _l2_distance(base, item.get("features") or [])
            refs.append(
                {
                    "sample_id": item["sample_id"],
                    "label": item.get("label"),
                    "distance": dist,
                }
            )
        refs.sort(key=lambda x: x["distance"])
        return refs[:top_n]

    def _vat_loss(self, sample: Dict[str, Any]) -> float:
        base = sample.get("features") or []
        if not base:
            return 0.0
        perturbed = [v + 0.01 * (i + 1) for i, v in enumerate(base)]
        p1 = self._predict_probabilities({"features": base, "sample_id": sample.get("sample_id")})
        p2 = self._predict_probabilities({"features": perturbed, "sample_id": sample.get("sample_id")})
        return _mean([(p1[i] - p2[i]) ** 2 for i in range(len(p1))])

    def _augment_features(self, features: List[float], mode: str) -> List[float]:
        if not features:
            return []
        if mode == "rotate":
            if len(features) < 2:
                return list(features)
            return [-features[1], features[0], *features[2:]]
        if mode == "flip":
            return [-features[0], *features[1:]]
        if mode == "noise":
            return [v + 0.01 * (idx + 1) for idx, v in enumerate(features)]
        return list(features)

    def _strategy_snapshot(self, session: Dict[str, Any]) -> Dict[str, Any]:
        hist = session.get("strategy_history", [])
        counts = Counter(hist)
        return {
            "history": hist,
            "usage": dict(counts),
        }

    def _view_sample(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "sample_id": sample.get("sample_id"),
            "label": sample.get("label"),
            "label_confidence": sample.get("label_confidence"),
            "features": sample.get("features"),
        }


active_learning_service = ActiveLearningService()
