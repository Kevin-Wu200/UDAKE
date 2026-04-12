"""融合模型解释适配器（LIME/SHAP）。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import copy
import hashlib
import json
import threading
import time
from typing import Any, Optional

import numpy as np
from sklearn.linear_model import Ridge

EPS = 1e-12

from deep_learning.fusion.service import fusion_platform_service


@dataclass
class FusionExplanationConfig:
    lime_num_samples: int = 180
    shap_nsamples: int = 120
    max_explain_nodes: int = 8
    cache_size: int = 16
    random_state: int = 42


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


class _BaseFusionAdapter:
    def __init__(self, config: Optional[FusionExplanationConfig] = None) -> None:
        self.config = config or FusionExplanationConfig()
        self._lock = threading.Lock()
        self._result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._context_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0
        self._context_cache_hits = 0
        self._context_cache_misses = 0

    @staticmethod
    def _load_lime_tabular() -> Any:
        try:
            from lime import lime_tabular  # type: ignore
        except Exception:
            return None
        return lime_tabular

    @staticmethod
    def _load_shap() -> Any:
        try:
            import shap  # type: ignore
        except Exception:
            return None
        return shap

    def _stable_hash(self, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            cached = self._result_cache.get(key)
            if cached is None:
                self._cache_misses += 1
                return None
            self._cache_hits += 1
            self._result_cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._result_cache[key] = copy.deepcopy(value)
            self._result_cache.move_to_end(key)
            while len(self._result_cache) > max(1, int(self.config.cache_size)):
                self._result_cache.popitem(last=False)

    def _context_cache_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            cached = self._context_cache.get(key)
            if cached is None:
                self._context_cache_misses += 1
                return None
            self._context_cache_hits += 1
            self._context_cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _context_cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._context_cache[key] = copy.deepcopy(value)
            self._context_cache.move_to_end(key)
            while len(self._context_cache) > max(1, int(self.config.cache_size)):
                self._context_cache.popitem(last=False)

    def _cache_metrics(self) -> dict[str, float | int]:
        with self._lock:
            total = self._cache_hits + self._cache_misses
            ctx_total = self._context_cache_hits + self._context_cache_misses
            return {
                "result_cache_hits": int(self._cache_hits),
                "result_cache_misses": int(self._cache_misses),
                "result_cache_hit_rate": float(self._cache_hits / max(1, total)),
                "context_cache_hits": int(self._context_cache_hits),
                "context_cache_misses": int(self._context_cache_misses),
                "context_cache_hit_rate": float(self._context_cache_hits / max(1, ctx_total)),
            }

    @staticmethod
    def _array_bytes(*arrays: np.ndarray) -> int:
        total = 0
        for arr in arrays:
            total += int(np.asarray(arr).nbytes)
        return int(total)

    @staticmethod
    def _normalize_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for i, item in enumerate(models):
            normalized.append(
                {
                    "model_id": str(item.get("model_id", f"model_{i}")),
                    "model_name": item.get("model_name"),
                    "predictions": [float(v) for v in item.get("predictions", [])],
                    "variances": None if item.get("variances") is None else [float(v) for v in item.get("variances", [])],
                    "confidence_intervals": item.get("confidence_intervals"),
                    "metadata": dict(item.get("metadata", {})),
                }
            )
        return normalized

    @staticmethod
    def _resolve_strategy_alias(strategy: str | None) -> str | None:
        if strategy is None:
            return None
        normalized = str(strategy).strip().lower()
        aliases = {
            "bagging": "simple_average",
        }
        return aliases.get(normalized, normalized)

    @staticmethod
    def _validate_inputs(models: list[dict[str, Any]], true_values: list[float] | None = None) -> tuple[np.ndarray, list[str]]:
        if not models:
            raise ValueError("models cannot be empty")
        predictions = [np.asarray(item.get("predictions", []), dtype=float).reshape(-1) for item in models]
        lengths = {int(arr.shape[0]) for arr in predictions}
        if len(lengths) != 1:
            raise ValueError("all model predictions must have the same length")
        horizon = next(iter(lengths))
        if horizon <= 0:
            raise ValueError("prediction horizon must be positive")
        if true_values is not None and len(true_values) != horizon:
            raise ValueError("true_values length mismatch")

        model_ids = [str(item.get("model_id", f"model_{i}")) for i, item in enumerate(models)]
        # [n_samples, n_models]
        matrix = np.stack(predictions, axis=1)
        return matrix, model_ids

    def preprocess_fusion_data(
        self,
        *,
        models: list[dict[str, Any]],
        profile_id: str | None = None,
        strategy: str | None = None,
        weight_method: str | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        normalized_models = self._normalize_models(models)
        matrix, model_ids = self._validate_inputs(normalized_models, true_values=true_values)
        requested_strategy = None if strategy is None else str(strategy).strip().lower()
        effective_strategy = self._resolve_strategy_alias(strategy)
        payload = fusion_platform_service.inference(
            models=normalized_models,
            profile_id=profile_id,
            strategy=effective_strategy,
            weight_method=weight_method,
            true_values=true_values,
            context=context,
        )
        result = payload["result"]
        fused_predictions = np.asarray(result.get("fused_predictions", []), dtype=float).reshape(-1)
        if fused_predictions.shape[0] != matrix.shape[0]:
            raise ValueError("fusion prediction length mismatch")

        fused_variances = result.get("fused_variances")
        if fused_variances is None:
            variances = np.var(matrix, axis=1)
        else:
            variances = np.asarray(fused_variances, dtype=float).reshape(-1)
            if variances.shape[0] != matrix.shape[0]:
                variances = np.var(matrix, axis=1)

        surrogate = Ridge(alpha=1.0, random_state=int(self.config.random_state))
        surrogate.fit(matrix, fused_predictions)
        baseline = np.mean(matrix, axis=0)
        surrogate_coef = np.asarray(surrogate.coef_, dtype=float).reshape(-1)
        centered_matrix = matrix - np.asarray(baseline, dtype=float).reshape(1, -1)
        background = matrix if matrix.shape[0] <= 32 else matrix[np.linspace(0, matrix.shape[0] - 1, 32, dtype=int)]
        return {
            "matrix": matrix,
            "model_ids": model_ids,
            "fused_predictions": fused_predictions,
            "fused_variances": variances,
            "weights": dict(result.get("weights", {})),
            "online_weights": dict(payload.get("online_weights", {})),
            "strategy": str(result.get("strategy", "")),
            "requested_strategy": str(requested_strategy or result.get("strategy", "")),
            "effective_strategy": str(effective_strategy or result.get("strategy", "")),
            "weight_method": str(result.get("weight_method", "")),
            "selected_strategy": str(payload.get("selected_strategy", "")),
            "metrics": dict(result.get("metrics", {})),
            "diagnostics": dict(result.get("diagnostics", {})),
            "surrogate": surrogate,
            "baseline": np.asarray(baseline, dtype=float),
            "surrogate_coef": surrogate_coef,
            "centered_matrix": np.asarray(centered_matrix, dtype=float),
            "background": np.asarray(background, dtype=float),
            "preprocess": {
                "sample_count": int(matrix.shape[0]),
                "model_count": int(matrix.shape[1]),
                "model_ids": list(model_ids),
                "has_true_values": bool(true_values is not None),
                "requested_strategy": str(requested_strategy or result.get("strategy", strategy or "")),
                "effective_strategy": str(effective_strategy or result.get("strategy", strategy or "")),
                "strategy_alias_applied": bool(
                    requested_strategy is not None and effective_strategy is not None and requested_strategy != effective_strategy
                ),
                "strategy": str(result.get("strategy", strategy or "")),
                "weight_method": str(result.get("weight_method", weight_method or "")),
            },
        }

    def _build_context_cached(
        self,
        *,
        models: list[dict[str, Any]],
        profile_id: str | None,
        strategy: str | None,
        weight_method: str | None,
        true_values: list[float] | None,
        context: dict[str, list[float]] | None,
    ) -> tuple[dict[str, Any], bool, float]:
        key = self._stable_hash(
            {
                "models": self._normalize_models(models),
                "profile_id": profile_id,
                "strategy": strategy,
                "weight_method": weight_method,
                "true_values": true_values,
                "context": context or {},
            }
        )
        started = time.perf_counter()
        cached = self._context_cache_get(key)
        if cached is not None:
            return cached, True, float((time.perf_counter() - started) * 1000.0)
        built = self.preprocess_fusion_data(
            models=models,
            profile_id=profile_id,
            strategy=strategy,
            weight_method=weight_method,
            true_values=true_values,
            context=context,
        )
        self._context_cache_set(key, built)
        return built, False, float((time.perf_counter() - started) * 1000.0)

    @staticmethod
    def _predict_fusion_fn(context: dict[str, Any]):
        surrogate: Ridge = context["surrogate"]
        return lambda x: surrogate.predict(np.asarray(x, dtype=float))

    @staticmethod
    def _top_features(model_ids: list[str], scores: np.ndarray, top_k: int) -> list[dict[str, float | str]]:
        arr = np.asarray(scores, dtype=float).reshape(-1)
        if arr.size == 0:
            return []
        k = max(1, min(int(top_k), int(arr.shape[0])))
        order = np.argsort(np.abs(arr))[::-1][:k]
        return [
            {
                "feature": str(model_ids[int(i)] if int(i) < len(model_ids) else f"model_{int(i)}"),
                "score": float(arr[int(i)]),
                "abs_score": float(abs(arr[int(i)])),
            }
            for i in order.tolist()
        ]

    @staticmethod
    def _select_explained_nodes(context: dict[str, Any], max_explain_nodes: int, true_values: list[float] | None) -> list[int]:
        score = np.asarray(context["fused_variances"], dtype=float).reshape(-1)
        if true_values is not None:
            y = np.asarray(true_values, dtype=float).reshape(-1)
            if y.shape[0] == score.shape[0]:
                score = np.abs(np.asarray(context["fused_predictions"], dtype=float).reshape(-1) - y)
        k = max(1, min(int(max_explain_nodes), int(score.shape[0])))
        return np.argsort(score)[::-1][:k].astype(int).tolist()

    @staticmethod
    def _ordered_weights(model_ids: list[str], raw: dict[str, Any]) -> np.ndarray:
        vec = np.asarray([_safe_float(raw.get(mid, 0.0), 0.0) for mid in model_ids], dtype=float).reshape(-1)
        total = float(np.sum(vec))
        if total <= EPS:
            return np.full((len(model_ids),), 1.0 / max(1, len(model_ids)), dtype=float)
        return vec / total

    def _fusion_weight_analysis(self, context: dict[str, Any], top_k: int) -> dict[str, Any]:
        model_ids = list(context["model_ids"])
        offline = self._ordered_weights(model_ids, dict(context.get("weights", {})))
        online = self._ordered_weights(model_ids, dict(context.get("online_weights", {})))
        delta = online - offline
        entropy = float(-np.sum(online * np.log(np.clip(online, EPS, None))))
        effective = float(1.0 / np.clip(np.sum(np.square(online)), EPS, None))
        order = np.argsort(np.abs(delta))[::-1]
        k = max(1, min(int(top_k), len(model_ids)))
        dominant_idx = int(np.argmax(online)) if len(model_ids) else 0
        return {
            "summary": {
                "model_count": int(len(model_ids)),
                "requested_strategy": str(context.get("strategy", "")),
                "selected_strategy": str(context.get("selected_strategy", "")),
                "weight_method": str(context.get("weight_method", "")),
                "effective_model_count": float(effective),
                "weight_entropy": float(entropy),
                "dominant_model": str(model_ids[dominant_idx]) if model_ids else "",
            },
            "weight_distribution": [
                {
                    "model_id": str(mid),
                    "offline_weight": float(offline[i]),
                    "online_weight": float(online[i]),
                    "delta_weight": float(delta[i]),
                    "abs_delta_weight": float(abs(delta[i])),
                }
                for i, mid in enumerate(model_ids)
            ],
            "top_weight_shift_models": [
                {
                    "model_id": str(model_ids[int(i)]),
                    "offline_weight": float(offline[int(i)]),
                    "online_weight": float(online[int(i)]),
                    "delta_weight": float(delta[int(i)]),
                }
                for i in order[:k].tolist()
            ],
        }

    def _submodel_contribution_analysis(
        self,
        context: dict[str, Any],
        node_indices: list[int],
        top_k: int,
    ) -> dict[str, Any]:
        model_ids = list(context["model_ids"])
        local = np.asarray(context["centered_matrix"], dtype=float) * np.asarray(context["surrogate_coef"], dtype=float).reshape(1, -1)
        abs_local = np.abs(local)
        global_abs = np.mean(abs_local, axis=0) if abs_local.size else np.zeros((len(model_ids),), dtype=float)
        per_node: list[dict[str, Any]] = []
        dominant_counter = {mid: 0 for mid in model_ids}
        for idx in node_indices:
            row = np.asarray(local[int(idx)], dtype=float).reshape(-1)
            row_abs = np.abs(row)
            total = float(np.sum(row_abs))
            shares = row_abs / max(EPS, total)
            order = np.argsort(row_abs)[::-1]
            k = max(1, min(int(top_k), len(model_ids)))
            dominant = int(order[0]) if len(order) else 0
            if model_ids:
                dominant_counter[model_ids[dominant]] += 1
            per_node.append(
                {
                    "node_index": int(idx),
                    "dominant_model": {
                        "model_id": str(model_ids[dominant]) if model_ids else "",
                        "contribution": float(row[dominant]) if model_ids else 0.0,
                        "share": float(shares[dominant]) if model_ids else 0.0,
                    },
                    "top_contributions": [
                        {
                            "model_id": str(model_ids[int(i)]),
                            "contribution": float(row[int(i)]),
                            "abs_contribution": float(row_abs[int(i)]),
                            "share": float(shares[int(i)]),
                        }
                        for i in order[:k].tolist()
                    ],
                }
            )
        total_dominant = max(1, sum(dominant_counter.values()))
        ranking_order = np.argsort(global_abs)[::-1]
        return {
            "summary": {
                "model_count": int(len(model_ids)),
                "sample_count": int(local.shape[0]) if local.ndim == 2 else 0,
                "explained_nodes": int(len(node_indices)),
                "mean_abs_contribution": float(np.mean(global_abs)) if global_abs.size else 0.0,
            },
            "global_contribution_ranking": [
                {
                    "model_id": str(model_ids[int(i)]),
                    "mean_abs_contribution": float(global_abs[int(i)]),
                    "dominant_ratio": float(dominant_counter.get(model_ids[int(i)], 0) / total_dominant),
                }
                for i in ranking_order.tolist()
            ],
            "top_global_contributions": self._top_features(model_ids, global_abs, int(top_k)),
            "per_node": per_node,
        }

    def _strategy_selection_explanation(self, context: dict[str, Any], true_values: list[float] | None) -> dict[str, Any]:
        selected = str(context.get("selected_strategy", ""))
        requested = str(context.get("requested_strategy", context.get("strategy", "")))
        effective = str(context.get("effective_strategy", context.get("strategy", "")))
        metrics = dict(context.get("metrics", {}))
        diagnostics = dict(context.get("diagnostics", {}))
        fused = np.asarray(context.get("fused_predictions", []), dtype=float).reshape(-1)
        variances = np.asarray(context.get("fused_variances", []), dtype=float).reshape(-1)

        error_mean = 0.0
        error_max = 0.0
        has_truth = False
        if true_values is not None:
            y = np.asarray(true_values, dtype=float).reshape(-1)
            if y.shape[0] == fused.shape[0]:
                has_truth = True
                err = np.abs(fused - y)
                error_mean = float(np.mean(err))
                error_max = float(np.max(err))
        reason_tags: list[str] = []
        if requested and selected and requested != selected:
            reason_tags.append("adaptive_strategy_override")
        if has_truth:
            reason_tags.append("ground_truth_feedback")
        if float(np.mean(variances)) > 0.0:
            reason_tags.append("uncertainty_aware")
        if diagnostics:
            reason_tags.append("diagnostics_available")
        if requested == "bagging":
            reason_tags.append("bagging_alias_simple_average")

        strategy_explanations = self._build_strategy_explanations(context, true_values)
        active_strategy_key = "bagging" if requested == "bagging" else (selected or effective or requested or "weighted_average")
        active_strategy = strategy_explanations.get(active_strategy_key, strategy_explanations.get(selected, {}))

        return {
            "summary": {
                "requested_strategy": requested,
                "effective_strategy": effective,
                "selected_strategy": selected,
                "weight_method": str(context.get("weight_method", "")),
                "strategy_changed": bool(requested and selected and requested != selected),
                "has_ground_truth": bool(has_truth),
                "reason_tags": reason_tags,
            },
            "evidence": {
                "rmse": _safe_float(metrics.get("rmse"), 0.0),
                "mae": _safe_float(metrics.get("mae"), 0.0),
                "r2": _safe_float(metrics.get("r2"), 0.0),
                "mean_abs_error": float(error_mean),
                "max_abs_error": float(error_max),
                "mean_fused_variance": float(np.mean(variances)) if variances.size else 0.0,
                "std_fused_variance": float(np.std(variances)) if variances.size else 0.0,
            },
            "diagnostics_overview": {
                "keys": sorted(diagnostics.keys()),
                "has_dynamic_weights": bool(diagnostics.get("dynamic_weights")),
                "has_diversity": bool(diagnostics.get("diversity")),
                "has_uncertainty": bool(diagnostics.get("uncertainty")),
            },
            "active_strategy_explanation": active_strategy,
            "strategy_explanations": strategy_explanations,
        }

    def _build_strategy_explanations(self, context: dict[str, Any], true_values: list[float] | None) -> dict[str, Any]:
        return {
            "weighted_average": self._explain_weighted_average_strategy(context),
            "dynamic": self._explain_dynamic_strategy(context),
            "stacking": self._explain_stacking_strategy(context, true_values),
            "bagging": self._explain_bagging_strategy(context),
        }

    def _explain_weighted_average_strategy(self, context: dict[str, Any]) -> dict[str, Any]:
        model_ids = list(context.get("model_ids", []))
        online = self._ordered_weights(model_ids, dict(context.get("online_weights", {})))
        if online.size == 0:
            online = self._ordered_weights(model_ids, dict(context.get("weights", {})))
        dominant_idx = int(np.argmax(online)) if online.size else 0
        concentration = float(np.max(online)) if online.size else 0.0
        return {
            "strategy": "weighted_average",
            "display_name": "加权平均策略",
            "core_mechanism": "按模型权重线性加权，权重越高对融合输出影响越大。",
            "formula": "y_hat = sum_i(w_i * y_i), 其中 sum_i(w_i)=1",
            "evidence": {
                "dominant_model": str(model_ids[dominant_idx]) if model_ids else "",
                "dominant_weight": float(concentration),
                "effective_model_count": float(1.0 / np.clip(np.sum(np.square(online)), EPS, None)) if online.size else 0.0,
            },
            "interpretation": "当 dominant_weight 较高时，说明融合结果更依赖单个高性能子模型。",
        }

    def _explain_dynamic_strategy(self, context: dict[str, Any]) -> dict[str, Any]:
        diagnostics = dict(context.get("diagnostics", {}))
        dynamic_weights = diagnostics.get("dynamic_weights", {})
        summary: dict[str, dict[str, float]] = {}
        major_switches = 0
        if isinstance(dynamic_weights, dict) and dynamic_weights:
            model_ids = [str(k) for k in dynamic_weights.keys()]
            traces = [np.asarray(dynamic_weights.get(mid, []), dtype=float).reshape(-1) for mid in model_ids]
            trace_len = min((arr.shape[0] for arr in traces if arr.size > 0), default=0)
            if trace_len > 0:
                stacked = np.vstack([arr[:trace_len] for arr in traces])
                dominant = np.argmax(stacked, axis=0)
                major_switches = int(np.sum(dominant[1:] != dominant[:-1])) if dominant.size > 1 else 0
            for mid, arr in zip(model_ids, traces):
                summary[mid] = {
                    "mean_weight": float(np.mean(arr)) if arr.size else 0.0,
                    "weight_std": float(np.std(arr)) if arr.size else 0.0,
                    "weight_range": float(np.max(arr) - np.min(arr)) if arr.size else 0.0,
                }

        return {
            "strategy": "dynamic",
            "display_name": "动态权重策略",
            "core_mechanism": "每个时刻根据局部可靠性与难度动态调整权重，提升非平稳场景鲁棒性。",
            "formula": "w_i(t) = softmax(log(base_i) + log(reliability_i(t))/difficulty(t))",
            "evidence": {
                "has_dynamic_trace": bool(summary),
                "dominant_model_switches": int(major_switches),
                "per_model_weight_stats": summary,
            },
            "interpretation": "dominant_model_switches 越高，说明模型主导权切换越频繁，策略自适应程度越高。",
        }

    def _explain_stacking_strategy(self, context: dict[str, Any], true_values: list[float] | None) -> dict[str, Any]:
        diagnostics = dict(context.get("diagnostics", {}))
        learned = diagnostics.get("stacking_weights", {})
        metrics = dict(context.get("metrics", {}))
        has_truth = bool(context.get("preprocess", {}).get("has_true_values", False) or true_values is not None)
        return {
            "strategy": "stacking",
            "display_name": "Stacking策略",
            "core_mechanism": "通过元学习器学习子模型组合系数，利用监督信号优化融合误差。",
            "formula": "y_hat = g(y_1, y_2, ..., y_n)，其中 g 由交叉验证训练得到",
            "evidence": {
                "has_ground_truth": bool(has_truth),
                "has_learned_meta_weights": bool(isinstance(learned, dict) and len(learned) > 0),
                "meta_weights": {str(k): float(v) for k, v in (learned.items() if isinstance(learned, dict) else [])},
                "rmse": _safe_float(metrics.get("rmse"), 0.0),
                "r2": _safe_float(metrics.get("r2"), 0.0),
            },
            "interpretation": "当 has_learned_meta_weights=True 时，说明已完成元学习拟合；否则通常退化为普通加权策略。",
        }

    def _explain_bagging_strategy(self, context: dict[str, Any]) -> dict[str, Any]:
        matrix = np.asarray(context.get("matrix", []), dtype=float)
        variances = np.asarray(context.get("fused_variances", []), dtype=float).reshape(-1)
        disagreement = np.std(matrix, axis=1) if matrix.ndim == 2 and matrix.shape[1] > 0 else np.zeros((0,), dtype=float)
        return {
            "strategy": "bagging",
            "display_name": "Bagging策略",
            "core_mechanism": "通过多模型平均降低方差，强调集成稳定性。",
            "formula": "y_hat = (1/M) * sum_i(y_i)",
            "evidence": {
                "ensemble_size": int(matrix.shape[1]) if matrix.ndim == 2 else 0,
                "mean_model_disagreement": float(np.mean(disagreement)) if disagreement.size else 0.0,
                "std_model_disagreement": float(np.std(disagreement)) if disagreement.size else 0.0,
                "mean_fused_variance": float(np.mean(variances)) if variances.size else 0.0,
            },
            "interpretation": "模型分歧可被平均平滑时，Bagging可显著降低预测波动并提升稳定性。",
        }


class FusionLIMEAdapter(_BaseFusionAdapter):
    """融合模型的 LIME 解释适配器。"""

    def explain(
        self,
        *,
        models: list[dict[str, Any]],
        top_k: int = 5,
        max_explain_nodes: int | None = None,
        num_samples: int | None = None,
        profile_id: str | None = None,
        strategy: str | None = None,
        weight_method: str | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        selected_nodes = int(max_explain_nodes or self.config.max_explain_nodes)
        effective_samples = int(num_samples or self.config.lime_num_samples)
        cache_key = self._stable_hash(
            {
                "method": "lime",
                "models": self._normalize_models(models),
                "top_k": int(top_k),
                "max_explain_nodes": int(selected_nodes),
                "num_samples": int(effective_samples),
                "profile_id": profile_id,
                "strategy": strategy,
                "weight_method": weight_method,
                "true_values": true_values,
                "context": context or {},
            }
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["performance"] = {
                **dict(cached.get("performance", {})),
                "cache_hit": True,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                **self._cache_metrics(),
            }
            return cached

        built, context_cache_hit, context_ms = self._build_context_cached(
            models=models,
            profile_id=profile_id,
            strategy=strategy,
            weight_method=weight_method,
            true_values=true_values,
            context=context,
        )
        model_ids = list(built["model_ids"])
        node_indices = self._select_explained_nodes(built, selected_nodes, true_values)
        predict_fn = self._predict_fusion_fn(built)
        lime_module = self._load_lime_tabular()
        lime_explainer = None
        if lime_module is not None:
            try:
                lime_explainer = lime_module.LimeTabularExplainer(
                    training_data=np.asarray(built["matrix"], dtype=float),
                    feature_names=model_ids,
                    mode="regression",
                    random_state=int(self.config.random_state),
                )
            except Exception:
                lime_explainer = None

        batch: list[dict[str, Any]] = []
        backend = "surrogate_linear"
        baseline = np.asarray(built["baseline"], dtype=float).reshape(-1)
        surrogate_coef = np.asarray(built["surrogate_coef"], dtype=float).reshape(-1)
        for idx in node_indices:
            instance = np.asarray(built["matrix"][idx], dtype=float).reshape(-1)
            local_pred = float(predict_fn(instance.reshape(1, -1))[0])
            local_weights = surrogate_coef * (instance - baseline)
            pairs = [(int(i), float(local_weights[i])) for i in range(local_weights.shape[0])]
            if lime_explainer is not None:
                try:
                    exp = lime_explainer.explain_instance(
                        instance,
                        predict_fn=predict_fn,
                        num_features=int(instance.shape[0]),
                        num_samples=max(50, int(effective_samples)),
                    )
                    pairs = [(int(i), float(v)) for i, v in exp.as_map()[1]]
                    local_pred = _safe_float(getattr(exp, "predicted_value", [local_pred])[0], local_pred)
                    backend = "lime_tabular"
                except Exception:
                    pass
            score_arr = np.zeros((len(model_ids),), dtype=float)
            for i, v in pairs:
                if 0 <= int(i) < score_arr.shape[0]:
                    score_arr[int(i)] = float(v)
            batch.append(
                {
                    "node_index": int(idx),
                    "prediction": float(np.asarray(built["fused_predictions"], dtype=float).reshape(-1)[idx]),
                    "local_prediction": float(local_pred),
                    "top_contributions": self._top_features(model_ids, score_arr, int(top_k)),
                    "local_weights": [float(x) for x in score_arr.tolist()],
                    "confidence": float(1.0 / (1.0 + np.var(score_arr))),
                }
            )

        raw = np.asarray([item["local_weights"] for item in batch], dtype=float) if batch else np.zeros((1, len(model_ids)), dtype=float)
        importance = np.mean(np.abs(raw), axis=0)
        weight_analysis = self._fusion_weight_analysis(built, int(top_k))
        contribution_analysis = self._submodel_contribution_analysis(built, node_indices, int(top_k))
        strategy_explanation = self._strategy_selection_explanation(built, true_values)
        context_memory_bytes = self._array_bytes(
            np.asarray(built["matrix"], dtype=np.float32),
            np.asarray(built["fused_predictions"], dtype=np.float32),
            np.asarray(built["fused_variances"], dtype=np.float32),
            np.asarray(built["background"], dtype=np.float32),
        )
        result_memory_bytes = self._array_bytes(np.asarray(raw, dtype=np.float32))
        result: dict[str, Any] = {
            "summary": {
                "method": "lime",
                "explained_nodes": int(len(batch)),
                "num_features": int(len(model_ids)),
                "top_features": self._top_features(model_ids, importance, int(top_k)),
                "average_confidence": float(np.mean([item["confidence"] for item in batch])) if batch else 0.0,
                "num_samples": int(effective_samples),
            },
            "batch_explanations": batch,
            "global_feature_importance": [float(v) for v in importance.tolist()],
            "fusion_weight_analysis": weight_analysis,
            "submodel_contribution_analysis": contribution_analysis,
            "strategy_selection_explanation": strategy_explanation,
            "preprocess": dict(built["preprocess"]),
            "explainer": {
                "backend": backend,
                "context_cache_hit": bool(context_cache_hit),
            },
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                "context_build_ms": float(context_ms),
                "context_cache_hit": bool(context_cache_hit),
                "sample_count": int(np.asarray(built["matrix"]).shape[0]),
                "feature_dim": int(np.asarray(built["matrix"]).shape[1]) if np.asarray(built["matrix"]).ndim == 2 else 0,
                "context_memory_bytes": int(context_memory_bytes),
                "result_memory_bytes": int(result_memory_bytes),
                "latency_target_ms": 2500.0,
                "meets_latency_target": float((time.perf_counter() - started) * 1000.0) < 2500.0,
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, result)
        return result


class FusionSHAPAdapter(_BaseFusionAdapter):
    """融合模型的 SHAP 解释适配器。"""

    def explain(
        self,
        *,
        models: list[dict[str, Any]],
        top_k: int = 5,
        max_explain_nodes: int | None = None,
        nsamples: int | None = None,
        profile_id: str | None = None,
        strategy: str | None = None,
        weight_method: str | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        selected_nodes = int(max_explain_nodes or self.config.max_explain_nodes)
        effective_nsamples = int(nsamples or self.config.shap_nsamples)
        cache_key = self._stable_hash(
            {
                "method": "shap",
                "models": self._normalize_models(models),
                "top_k": int(top_k),
                "max_explain_nodes": int(selected_nodes),
                "nsamples": int(effective_nsamples),
                "profile_id": profile_id,
                "strategy": strategy,
                "weight_method": weight_method,
                "true_values": true_values,
                "context": context or {},
            }
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["performance"] = {
                **dict(cached.get("performance", {})),
                "cache_hit": True,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                **self._cache_metrics(),
            }
            return cached

        built, context_cache_hit, context_ms = self._build_context_cached(
            models=models,
            profile_id=profile_id,
            strategy=strategy,
            weight_method=weight_method,
            true_values=true_values,
            context=context,
        )
        model_ids = list(built["model_ids"])
        node_indices = self._select_explained_nodes(built, selected_nodes, true_values)
        baseline = np.asarray(built["baseline"], dtype=float).reshape(-1)
        predict_fn = self._predict_fusion_fn(built)
        shap_module = self._load_shap()
        kernel_explainer = None
        backend = "surrogate_linear"
        if shap_module is not None:
            try:
                kernel_explainer = shap_module.KernelExplainer(
                    model=predict_fn,
                    data=np.asarray(built["background"], dtype=float),
                )
                backend = "shap_kernel"
            except Exception:
                kernel_explainer = None

        batch: list[dict[str, Any]] = []
        raw_rows: list[list[float]] = []
        surrogate_coef = np.asarray(built["surrogate_coef"], dtype=float).reshape(-1)
        selected_matrix = np.asarray(built["matrix"], dtype=float)[node_indices] if node_indices else np.zeros((0, len(model_ids)))
        fallback_shap = (selected_matrix - baseline.reshape(1, -1)) * surrogate_coef.reshape(1, -1) if selected_matrix.size else np.zeros((0, len(model_ids)))
        expected_value = float(predict_fn(baseline.reshape(1, -1))[0])
        batch_shap_values = np.asarray(fallback_shap, dtype=float)
        batch_kernel_used = False
        if kernel_explainer is not None and selected_matrix.size:
            try:
                shap_arr = kernel_explainer.shap_values(
                    selected_matrix,
                    nsamples=max(20, int(effective_nsamples)),
                    silent=True,
                )
                if isinstance(shap_arr, list):
                    shap_arr = shap_arr[0]
                parsed = np.asarray(shap_arr, dtype=float)
                if parsed.ndim == 1:
                    parsed = parsed.reshape(1, -1)
                if parsed.shape == batch_shap_values.shape:
                    batch_shap_values = parsed
                    batch_kernel_used = True
                ev = getattr(kernel_explainer, "expected_value", expected_value)
                if np.asarray(ev).reshape(-1).size > 0:
                    expected_value = _safe_float(np.asarray(ev).reshape(-1)[0], expected_value)
            except Exception:
                batch_shap_values = np.asarray(fallback_shap, dtype=float)

        for row_idx, idx in enumerate(node_indices):
            instance = np.asarray(built["matrix"][idx], dtype=float).reshape(-1)
            shap_values = np.asarray(batch_shap_values[row_idx], dtype=float).reshape(-1)
            pred = float(predict_fn(instance.reshape(1, -1))[0])
            raw_rows.append([float(v) for v in shap_values.tolist()])
            batch.append(
                {
                    "node_index": int(idx),
                    "prediction": float(np.asarray(built["fused_predictions"], dtype=float).reshape(-1)[idx]),
                    "local_prediction": float(pred),
                    "expected_value": float(expected_value),
                    "top_contributions": self._top_features(model_ids, shap_values, int(top_k)),
                    "raw_shap_values": [float(v) for v in shap_values.tolist()],
                    "confidence": float(1.0 / (1.0 + np.var(shap_values))),
                }
            )

        arr = np.asarray(raw_rows, dtype=float) if raw_rows else np.zeros((1, len(model_ids)), dtype=float)
        importance = np.mean(np.abs(arr), axis=0)
        weight_analysis = self._fusion_weight_analysis(built, int(top_k))
        contribution_analysis = self._submodel_contribution_analysis(built, node_indices, int(top_k))
        strategy_explanation = self._strategy_selection_explanation(built, true_values)
        context_memory_bytes = self._array_bytes(
            np.asarray(built["matrix"], dtype=np.float32),
            np.asarray(built["fused_predictions"], dtype=np.float32),
            np.asarray(built["fused_variances"], dtype=np.float32),
            np.asarray(built["background"], dtype=np.float32),
        )
        result_memory_bytes = self._array_bytes(np.asarray(arr, dtype=np.float32))
        result: dict[str, Any] = {
            "summary": {
                "method": "shap",
                "explained_nodes": int(len(batch)),
                "num_features": int(len(model_ids)),
                "top_features": self._top_features(model_ids, importance, int(top_k)),
                "average_confidence": float(np.mean([item["confidence"] for item in batch])) if batch else 0.0,
                "nsamples": int(effective_nsamples),
            },
            "batch_explanations": batch,
            "global_feature_importance": [float(v) for v in importance.tolist()],
            "fusion_weight_analysis": weight_analysis,
            "submodel_contribution_analysis": contribution_analysis,
            "strategy_selection_explanation": strategy_explanation,
            "preprocess": dict(built["preprocess"]),
            "explainer": {
                "backend": backend,
                "background_size": int(np.asarray(built["background"]).shape[0]),
                "context_cache_hit": bool(context_cache_hit),
                "batch_kernel_shap": bool(batch_kernel_used),
            },
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                "context_build_ms": float(context_ms),
                "context_cache_hit": bool(context_cache_hit),
                "sample_count": int(np.asarray(built["matrix"]).shape[0]),
                "feature_dim": int(np.asarray(built["matrix"]).shape[1]) if np.asarray(built["matrix"]).ndim == 2 else 0,
                "context_memory_bytes": int(context_memory_bytes),
                "result_memory_bytes": int(result_memory_bytes),
                "batch_shap_size": int(len(node_indices)),
                "latency_target_ms": 2500.0,
                "meets_latency_target": float((time.perf_counter() - started) * 1000.0) < 2500.0,
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, result)
        return result
