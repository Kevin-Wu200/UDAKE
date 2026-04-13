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
    max_background_size: int = 24
    dynamic_trace_limit: int = 96


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
        self._batch_result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._context_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0
        self._batch_cache_hits = 0
        self._batch_cache_misses = 0
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

    def _batch_cache_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            cached = self._batch_result_cache.get(key)
            if cached is None:
                self._batch_cache_misses += 1
                return None
            self._batch_cache_hits += 1
            self._batch_result_cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _batch_cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._batch_result_cache[key] = copy.deepcopy(value)
            self._batch_result_cache.move_to_end(key)
            while len(self._batch_result_cache) > max(1, int(self.config.cache_size)):
                self._batch_result_cache.popitem(last=False)

    def _compact_dynamic_weights(self, diagnostics: dict[str, Any]) -> dict[str, Any]:
        copied = dict(diagnostics)
        raw = copied.get("dynamic_weights")
        if not isinstance(raw, dict):
            return copied
        compacted: dict[str, list[float]] = {}
        cap = max(8, int(self.config.dynamic_trace_limit))
        for mid, values in raw.items():
            arr = np.asarray(values, dtype=float).reshape(-1)
            if arr.size > cap:
                idx = np.linspace(0, arr.size - 1, cap, dtype=int)
                arr = arr[idx]
            compacted[str(mid)] = [float(v) for v in arr.tolist()]
        copied["dynamic_weights"] = compacted
        return copied

    def _ensure_context_runtime_fields(self, context: dict[str, Any]) -> dict[str, Any]:
        restored = copy.deepcopy(context)
        matrix = np.asarray(restored.get("matrix", []), dtype=np.float32)
        fused_predictions = np.asarray(restored.get("fused_predictions", []), dtype=np.float32).reshape(-1)
        baseline = np.asarray(restored.get("baseline", []), dtype=np.float32).reshape(-1)
        surrogate_coef = np.asarray(restored.get("surrogate_coef", []), dtype=np.float32).reshape(-1)
        centered_matrix = np.asarray(restored.get("centered_matrix", []), dtype=np.float32)
        if centered_matrix.shape != matrix.shape:
            centered_matrix = matrix - baseline.reshape(1, -1)
        background = np.asarray(restored.get("background", []), dtype=np.float32)
        cap = max(8, int(self.config.max_background_size))
        if background.ndim == 2 and background.shape[0] > cap:
            idx = np.linspace(0, background.shape[0] - 1, cap, dtype=int)
            background = background[idx]

        restored["matrix"] = matrix
        restored["fused_predictions"] = fused_predictions
        restored["fused_variances"] = np.asarray(restored.get("fused_variances", []), dtype=np.float32).reshape(-1)
        restored["baseline"] = baseline
        restored["surrogate_coef"] = surrogate_coef
        restored["centered_matrix"] = centered_matrix
        restored["background"] = background
        restored["diagnostics"] = self._compact_dynamic_weights(dict(restored.get("diagnostics", {})))

        surrogate = restored.get("surrogate")
        if surrogate is None:
            surrogate = Ridge(alpha=1.0, random_state=int(self.config.random_state))
            surrogate.fit(matrix.astype(float), fused_predictions.astype(float))
        restored["surrogate"] = surrogate
        return restored

    def _context_cache_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            cached = self._context_cache.get(key)
            if cached is None:
                self._context_cache_misses += 1
                return None
            self._context_cache_hits += 1
            self._context_cache.move_to_end(key)
            restored = copy.deepcopy(cached)
        return self._ensure_context_runtime_fields(restored)

    def _context_cache_set(self, key: str, value: dict[str, Any]) -> None:
        compacted = self._ensure_context_runtime_fields(value)
        compacted["surrogate"] = None
        with self._lock:
            self._context_cache[key] = copy.deepcopy(compacted)
            self._context_cache.move_to_end(key)
            while len(self._context_cache) > max(1, int(self.config.cache_size)):
                self._context_cache.popitem(last=False)

    def _cache_metrics(self) -> dict[str, float | int]:
        with self._lock:
            total = self._cache_hits + self._cache_misses
            batch_total = self._batch_cache_hits + self._batch_cache_misses
            ctx_total = self._context_cache_hits + self._context_cache_misses
            return {
                "result_cache_hits": int(self._cache_hits),
                "result_cache_misses": int(self._cache_misses),
                "result_cache_hit_rate": float(self._cache_hits / max(1, total)),
                "batch_result_cache_hits": int(self._batch_cache_hits),
                "batch_result_cache_misses": int(self._batch_cache_misses),
                "batch_result_cache_hit_rate": float(self._batch_cache_hits / max(1, batch_total)),
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
    def _batch_item(items: list[Any] | None, idx: int, default: Any = None) -> Any:
        if items is None:
            return default
        if 0 <= int(idx) < len(items):
            return items[int(idx)]
        return default

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
        matrix = np.asarray(matrix, dtype=np.float32)
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
        fused_predictions = np.asarray(result.get("fused_predictions", []), dtype=np.float32).reshape(-1)
        if fused_predictions.shape[0] != matrix.shape[0]:
            raise ValueError("fusion prediction length mismatch")

        fused_variances = result.get("fused_variances")
        if fused_variances is None:
            variances = np.var(matrix, axis=1).astype(np.float32)
        else:
            variances = np.asarray(fused_variances, dtype=np.float32).reshape(-1)
            if variances.shape[0] != matrix.shape[0]:
                variances = np.var(matrix, axis=1).astype(np.float32)

        surrogate = Ridge(alpha=1.0, random_state=int(self.config.random_state))
        surrogate.fit(matrix, fused_predictions)
        baseline = np.asarray(np.mean(matrix, axis=0), dtype=np.float32).reshape(-1)
        surrogate_coef = np.asarray(surrogate.coef_, dtype=np.float32).reshape(-1)
        centered_matrix = (matrix - baseline.reshape(1, -1)).astype(np.float32)
        bg_cap = max(8, int(self.config.max_background_size))
        background = matrix if matrix.shape[0] <= bg_cap else matrix[np.linspace(0, matrix.shape[0] - 1, bg_cap, dtype=int)]
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
            "baseline": baseline,
            "surrogate_coef": surrogate_coef,
            "centered_matrix": np.asarray(centered_matrix, dtype=np.float32),
            "background": np.asarray(background, dtype=np.float32),
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

    @staticmethod
    def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
        x = np.asarray(a, dtype=float).reshape(-1)
        y = np.asarray(b, dtype=float).reshape(-1)
        if x.size != y.size or x.size <= 1:
            return 0.0
        if float(np.std(x)) <= EPS or float(np.std(y)) <= EPS:
            return 0.0
        c = float(np.corrcoef(x, y)[0, 1])
        if np.isnan(c):
            return 0.0
        return c

    @staticmethod
    def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        y = np.asarray(y_true, dtype=float).reshape(-1)
        p = np.asarray(y_pred, dtype=float).reshape(-1)
        if y.size != p.size or y.size == 0:
            return 0.0
        ss_res = float(np.sum((y - p) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        if ss_tot <= EPS:
            return 0.0
        return float(np.clip(1.0 - ss_res / ss_tot, -1.0, 1.0))

    @staticmethod
    def _trend_slope(series: np.ndarray) -> float:
        arr = np.asarray(series, dtype=float).reshape(-1)
        if arr.size <= 1:
            return 0.0
        x = np.arange(arr.size, dtype=float)
        x_mean = float(np.mean(x))
        y_mean = float(np.mean(arr))
        denom = float(np.sum((x - x_mean) ** 2))
        if denom <= EPS:
            return 0.0
        return float(np.sum((x - x_mean) * (arr - y_mean)) / denom)

    @staticmethod
    def _gini(arr: np.ndarray) -> float:
        data = np.sort(np.clip(np.asarray(arr, dtype=float).reshape(-1), 0.0, None))
        n = int(data.size)
        if n == 0:
            return 0.0
        total = float(np.sum(data))
        if total <= EPS:
            return 0.0
        idx = np.arange(1, n + 1, dtype=float)
        return float((2.0 * np.sum(idx * data) / (n * total)) - (n + 1.0) / n)

    def _submodel_performance_comparison(self, context: dict[str, Any], true_values: list[float] | None) -> dict[str, Any]:
        model_ids = list(context.get("model_ids", []))
        matrix = np.asarray(context.get("matrix", []), dtype=float)
        fused = np.asarray(context.get("fused_predictions", []), dtype=float).reshape(-1)
        online_weights = self._ordered_weights(model_ids, dict(context.get("online_weights", {})))
        y_true = None if true_values is None else np.asarray(true_values, dtype=float).reshape(-1)
        if y_true is not None and y_true.shape[0] != matrix.shape[0]:
            y_true = None

        rows: list[dict[str, Any]] = []
        for i, model_id in enumerate(model_ids):
            pred = np.asarray(matrix[:, i], dtype=float).reshape(-1) if matrix.ndim == 2 and i < matrix.shape[1] else np.zeros((0,))
            rmse_to_fused = float(np.sqrt(np.mean((pred - fused) ** 2))) if pred.size and pred.size == fused.size else 0.0
            mae_to_fused = float(np.mean(np.abs(pred - fused))) if pred.size and pred.size == fused.size else 0.0
            pred_stability = float(1.0 / (1.0 + np.std(np.diff(pred)))) if pred.size > 1 else 1.0
            row: dict[str, Any] = {
                "model_id": str(model_id),
                "online_weight": float(online_weights[i]) if i < online_weights.size else 0.0,
                "rmse_to_fusion": float(rmse_to_fused),
                "mae_to_fusion": float(mae_to_fused),
                "agreement_with_fusion": float(self._safe_corr(pred, fused)) if pred.size else 0.0,
                "prediction_stability": float(pred_stability),
                "score": 0.0,
            }
            if y_true is not None and pred.size == y_true.size:
                err = pred - y_true
                rmse = float(np.sqrt(np.mean(err ** 2)))
                mae = float(np.mean(np.abs(err)))
                mape = float(np.mean(np.abs(err) / np.clip(np.abs(y_true), EPS, None)) * 100.0)
                r2 = float(self._safe_r2(y_true, pred))
                score = float(
                    0.45 * (1.0 / (1.0 + rmse))
                    + 0.25 * ((r2 + 1.0) / 2.0)
                    + 0.20 * pred_stability
                    + 0.10 * float(online_weights[i] if i < online_weights.size else 0.0)
                )
                row.update(
                    {
                        "rmse": rmse,
                        "mae": mae,
                        "mape": mape,
                        "r2": r2,
                        "bias": float(np.mean(err)),
                        "error_std": float(np.std(err)),
                        "score": score,
                    }
                )
            else:
                score = float(
                    0.55 * (1.0 / (1.0 + rmse_to_fused))
                    + 0.30 * pred_stability
                    + 0.15 * float(online_weights[i] if i < online_weights.size else 0.0)
                )
                row["score"] = score
            rows.append(row)

        ranking = sorted(rows, key=lambda item: float(item.get("score", 0.0)), reverse=True)
        return {
            "summary": {
                "model_count": int(len(model_ids)),
                "has_ground_truth": bool(y_true is not None),
                "scoring_formula": (
                    "有真值: 0.45*(1/(1+rmse))+0.25*((r2+1)/2)+0.20*stability+0.10*weight; "
                    "无真值: 0.55*(1/(1+rmse_to_fusion))+0.30*stability+0.15*weight"
                ),
                "top_model": str(ranking[0]["model_id"]) if ranking else "",
            },
            "ranking": ranking,
        }

    def _submodel_stability_analysis(self, context: dict[str, Any], true_values: list[float] | None) -> dict[str, Any]:
        model_ids = list(context.get("model_ids", []))
        matrix = np.asarray(context.get("matrix", []), dtype=float)
        y_true = None if true_values is None else np.asarray(true_values, dtype=float).reshape(-1)
        if y_true is not None and y_true.shape[0] != matrix.shape[0]:
            y_true = None

        rows: list[dict[str, Any]] = []
        win = max(2, min(5, int(matrix.shape[0]) if matrix.ndim == 2 else 2))
        for i, model_id in enumerate(model_ids):
            pred = np.asarray(matrix[:, i], dtype=float).reshape(-1) if matrix.ndim == 2 and i < matrix.shape[1] else np.zeros((0,))
            if pred.size <= 1:
                rows.append(
                    {
                        "model_id": str(model_id),
                        "prediction_volatility": 0.0,
                        "rolling_variance_mean": 0.0,
                        "prediction_stability": 1.0,
                        "error_stability": 1.0,
                        "overall_stability": 1.0,
                    }
                )
                continue
            volatility = float(np.std(np.diff(pred)))
            rolling_vars = [float(np.var(pred[s : s + win])) for s in range(0, pred.size - win + 1)]
            rolling_mean = float(np.mean(rolling_vars)) if rolling_vars else 0.0
            pred_stability = float(1.0 / (1.0 + volatility + rolling_mean))
            error_stability = 1.0
            error_std = 0.0
            error_drift = 0.0
            if y_true is not None and y_true.size == pred.size:
                err = pred - y_true
                error_std = float(np.std(err))
                error_drift = float(np.mean(np.abs(np.diff(err)))) if err.size > 1 else 0.0
                error_stability = float(1.0 / (1.0 + error_std + error_drift))
            overall = float(0.6 * pred_stability + 0.4 * error_stability)
            rows.append(
                {
                    "model_id": str(model_id),
                    "prediction_volatility": volatility,
                    "rolling_variance_mean": rolling_mean,
                    "prediction_stability": pred_stability,
                    "error_std": error_std,
                    "error_drift": error_drift,
                    "error_stability": float(error_stability),
                    "overall_stability": overall,
                }
            )
        ranking = sorted(rows, key=lambda item: float(item.get("overall_stability", 0.0)), reverse=True)
        return {
            "summary": {
                "model_count": int(len(model_ids)),
                "window_size": int(win),
                "has_ground_truth": bool(y_true is not None),
                "most_stable_model": str(ranking[0]["model_id"]) if ranking else "",
            },
            "ranking": ranking,
        }

    def _submodel_complementarity_analysis(self, context: dict[str, Any], true_values: list[float] | None, top_k: int) -> dict[str, Any]:
        model_ids = list(context.get("model_ids", []))
        matrix = np.asarray(context.get("matrix", []), dtype=float)
        n_models = int(len(model_ids))
        y_true = None if true_values is None else np.asarray(true_values, dtype=float).reshape(-1)
        if y_true is not None and (matrix.ndim != 2 or y_true.shape[0] != matrix.shape[0]):
            y_true = None

        heatmap = np.eye(n_models, dtype=float)
        pairs: list[dict[str, Any]] = []
        per_model_scores: dict[str, list[float]] = {mid: [] for mid in model_ids}
        for i in range(n_models):
            for j in range(i + 1, n_models):
                p_i = np.asarray(matrix[:, i], dtype=float)
                p_j = np.asarray(matrix[:, j], dtype=float)
                pred_corr = abs(self._safe_corr(p_i, p_j))
                pred_complement = float(1.0 - pred_corr)
                residual_complement = 0.0
                synergy_gain = 0.0
                if y_true is not None:
                    e_i = p_i - y_true
                    e_j = p_j - y_true
                    residual_complement = float(1.0 - abs(self._safe_corr(e_i, e_j)))
                    pair_pred = 0.5 * (p_i + p_j)
                    pair_rmse = float(np.sqrt(np.mean((pair_pred - y_true) ** 2)))
                    best_single_rmse = float(
                        min(
                            np.sqrt(np.mean((p_i - y_true) ** 2)),
                            np.sqrt(np.mean((p_j - y_true) ** 2)),
                        )
                    )
                    synergy_gain = float(best_single_rmse - pair_rmse)
                spread = float(np.mean(np.abs(p_i - p_j)))
                norm_spread = float(spread / (np.std(np.concatenate([p_i, p_j])) + 1.0))
                score = float(0.55 * pred_complement + 0.30 * residual_complement + 0.15 * min(1.0, norm_spread))
                heatmap[i, j] = score
                heatmap[j, i] = score
                per_model_scores[model_ids[i]].append(score)
                per_model_scores[model_ids[j]].append(score)
                pairs.append(
                    {
                        "model_a": str(model_ids[i]),
                        "model_b": str(model_ids[j]),
                        "prediction_correlation_abs": float(pred_corr),
                        "prediction_complementarity": float(pred_complement),
                        "residual_complementarity": float(residual_complement),
                        "spread": float(spread),
                        "synergy_gain_vs_best_single_rmse": float(synergy_gain),
                        "complementarity_score": float(score),
                    }
                )
        pairs.sort(key=lambda item: float(item.get("complementarity_score", 0.0)), reverse=True)
        k = max(1, min(int(top_k), len(pairs))) if pairs else 0
        model_index = [
            {
                "model_id": str(mid),
                "complementarity_index": float(np.mean(vals)) if vals else 0.0,
            }
            for mid, vals in per_model_scores.items()
        ]
        model_index.sort(key=lambda item: float(item.get("complementarity_index", 0.0)), reverse=True)
        return {
            "summary": {
                "model_count": int(n_models),
                "pair_count": int(len(pairs)),
                "has_ground_truth": bool(y_true is not None),
                "most_complementary_pair": (
                    {"model_a": str(pairs[0]["model_a"]), "model_b": str(pairs[0]["model_b"])} if pairs else {}
                ),
            },
            "pair_scores": pairs,
            "top_complementary_pairs": pairs[:k] if k > 0 else [],
            "model_complementarity_index": model_index,
            "complementarity_heatmap": {
                "model_ids": [str(mid) for mid in model_ids],
                "matrix": [[float(v) for v in row] for row in heatmap.tolist()],
            },
        }

    def _submodel_weight_visualization(self, context: dict[str, Any], top_k: int) -> dict[str, Any]:
        model_ids = list(context.get("model_ids", []))
        offline = self._ordered_weights(model_ids, dict(context.get("weights", {})))
        online = self._ordered_weights(model_ids, dict(context.get("online_weights", {})))
        delta = online - offline
        entropy = float(-np.sum(online * np.log(np.clip(online, EPS, None)))) if online.size else 0.0
        effective = float(1.0 / np.clip(np.sum(np.square(online)), EPS, None)) if online.size else 0.0
        gini = float(self._gini(online))
        order = np.argsort(np.abs(delta))[::-1]
        k = max(1, min(int(top_k), len(model_ids))) if model_ids else 0

        diagnostics = dict(context.get("diagnostics", {}))
        dynamic_weights = diagnostics.get("dynamic_weights", {})
        traces: list[dict[str, Any]] = []
        if isinstance(dynamic_weights, dict):
            for mid in model_ids:
                raw = dynamic_weights.get(mid, [])
                arr = np.asarray(raw, dtype=float).reshape(-1)
                traces.append(
                    {
                        "model_id": str(mid),
                        "series": [float(v) for v in arr.tolist()],
                        "mean_weight": float(np.mean(arr)) if arr.size else 0.0,
                        "weight_std": float(np.std(arr)) if arr.size else 0.0,
                        "min_weight": float(np.min(arr)) if arr.size else 0.0,
                        "max_weight": float(np.max(arr)) if arr.size else 0.0,
                        "trend_slope": float(self._trend_slope(arr)),
                    }
                )

        return {
            "summary": {
                "model_count": int(len(model_ids)),
                "weight_entropy": float(entropy),
                "weight_gini": float(gini),
                "effective_model_count": float(effective),
                "dominant_model": str(model_ids[int(np.argmax(online))]) if online.size else "",
                "has_dynamic_weight_trace": bool(any(item.get("series") for item in traces)),
            },
            "weight_distribution": [
                {
                    "model_id": str(mid),
                    "offline_weight": float(offline[i]),
                    "online_weight": float(online[i]),
                    "delta_weight": float(delta[i]),
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
                for i in (order[:k].tolist() if k > 0 else [])
            ],
            "visualization_payload": {
                "bar_chart": [
                    {
                        "model_id": str(mid),
                        "offline_weight": float(offline[i]),
                        "online_weight": float(online[i]),
                        "delta_weight": float(delta[i]),
                    }
                    for i, mid in enumerate(model_ids)
                ],
                "pie_chart": [
                    {
                        "label": str(mid),
                        "value": float(online[i]),
                    }
                    for i, mid in enumerate(model_ids)
                ],
                "timeline_chart": traces,
            },
        }

    def _submodel_contribution_ranking(
        self,
        performance: dict[str, Any],
        stability: dict[str, Any],
        complementarity: dict[str, Any],
        weights: dict[str, Any],
    ) -> dict[str, Any]:
        perf_rows = {
            str(item.get("model_id", "")): item
            for item in list(performance.get("ranking", []))
            if str(item.get("model_id", "")) != ""
        }
        stability_rows = {
            str(item.get("model_id", "")): item
            for item in list(stability.get("ranking", []))
            if str(item.get("model_id", "")) != ""
        }
        complement_rows = {
            str(item.get("model_id", "")): item
            for item in list(complementarity.get("model_complementarity_index", []))
            if str(item.get("model_id", "")) != ""
        }
        weight_rows = {
            str(item.get("model_id", "")): item
            for item in list(weights.get("weight_distribution", []))
            if str(item.get("model_id", "")) != ""
        }

        model_ids = sorted(set(perf_rows.keys()) | set(stability_rows.keys()) | set(complement_rows.keys()) | set(weight_rows.keys()))
        ranked: list[dict[str, Any]] = []
        for model_id in model_ids:
            perf_row = perf_rows.get(model_id, {})
            stability_row = stability_rows.get(model_id, {})
            comp_row = complement_rows.get(model_id, {})
            weight_row = weight_rows.get(model_id, {})

            perf_score = float(np.clip(_safe_float(perf_row.get("score"), 0.0), 0.0, 1.0))
            stability_score = float(np.clip(_safe_float(stability_row.get("overall_stability"), 0.0), 0.0, 1.0))
            complement_score = float(np.clip(_safe_float(comp_row.get("complementarity_index"), 0.0), 0.0, 1.0))
            weight_score = float(np.clip(_safe_float(weight_row.get("online_weight"), 0.0), 0.0, 1.0))
            agreement = float(np.clip((_safe_float(perf_row.get("agreement_with_fusion"), 0.0) + 1.0) / 2.0, 0.0, 1.0))

            contribution_score = float(
                0.35 * perf_score
                + 0.25 * stability_score
                + 0.20 * weight_score
                + 0.15 * complement_score
                + 0.05 * agreement
            )
            ranked.append(
                {
                    "model_id": str(model_id),
                    "contribution_score": contribution_score,
                    "performance_score": perf_score,
                    "stability_score": stability_score,
                    "weight_score": weight_score,
                    "complementarity_score": complement_score,
                    "agreement_score": agreement,
                }
            )
        ranked.sort(key=lambda item: float(item.get("contribution_score", 0.0)), reverse=True)
        return {
            "summary": {
                "model_count": int(len(ranked)),
                "top_contributor": str(ranked[0]["model_id"]) if ranked else "",
                "score_formula": (
                    "0.35*performance + 0.25*stability + 0.20*weight + "
                    "0.15*complementarity + 0.05*agreement"
                ),
            },
            "ranking": ranked,
        }

    def _submodel_selection_recommendation(
        self,
        contribution_ranking: dict[str, Any],
        performance: dict[str, Any],
        stability: dict[str, Any],
    ) -> dict[str, Any]:
        ranked = list(contribution_ranking.get("ranking", []))
        perf_rows = {str(item.get("model_id", "")): item for item in list(performance.get("ranking", []))}
        stability_rows = {str(item.get("model_id", "")): item for item in list(stability.get("ranking", []))}
        if not ranked:
            return {
                "summary": {
                    "model_count": 0,
                    "recommended_count": 0,
                    "selection_policy": "score_based_topk",
                },
                "recommended_models": [],
                "watchlist_models": [],
                "replacement_candidates": [],
            }

        model_count = len(ranked)
        keep_count = int(np.clip(int(np.ceil(model_count * 0.6)), 1, max(1, min(4, model_count))))
        keep_rows = ranked[:keep_count]
        watch_rows = [item for item in ranked[keep_count:] if float(item.get("contribution_score", 0.0)) >= 0.45]
        replace_rows = [item for item in ranked if float(item.get("contribution_score", 0.0)) < 0.45]

        def _reason(model_id: str) -> str:
            perf = float(_safe_float(perf_rows.get(model_id, {}).get("score"), 0.0))
            stab = float(_safe_float(stability_rows.get(model_id, {}).get("overall_stability"), 0.0))
            if perf < 0.40 and stab < 0.45:
                return "性能与稳定性均偏弱"
            if perf < 0.40:
                return "性能表现偏弱"
            if stab < 0.45:
                return "稳定性偏弱"
            return "综合贡献度良好"

        return {
            "summary": {
                "model_count": int(model_count),
                "recommended_count": int(len(keep_rows)),
                "watchlist_count": int(len(watch_rows)),
                "replacement_count": int(len(replace_rows)),
                "selection_policy": "score_based_topk",
            },
            "recommended_models": [
                {
                    "model_id": str(item.get("model_id", "")),
                    "contribution_score": float(item.get("contribution_score", 0.0)),
                    "reason": _reason(str(item.get("model_id", ""))),
                }
                for item in keep_rows
            ],
            "watchlist_models": [
                {
                    "model_id": str(item.get("model_id", "")),
                    "contribution_score": float(item.get("contribution_score", 0.0)),
                    "reason": _reason(str(item.get("model_id", ""))),
                }
                for item in watch_rows
            ],
            "replacement_candidates": [
                {
                    "model_id": str(item.get("model_id", "")),
                    "contribution_score": float(item.get("contribution_score", 0.0)),
                    "reason": _reason(str(item.get("model_id", ""))),
                }
                for item in replace_rows
            ],
        }

    def _submodel_alternative_solutions(
        self,
        contribution_ranking: dict[str, Any],
        selection_recommendation: dict[str, Any],
        complementarity: dict[str, Any],
    ) -> dict[str, Any]:
        ranked = list(contribution_ranking.get("ranking", []))
        replace_rows = list(selection_recommendation.get("replacement_candidates", []))
        pair_scores = list(complementarity.get("pair_scores", []))
        complement_map: dict[tuple[str, str], float] = {}
        for item in pair_scores:
            a = str(item.get("model_a", ""))
            b = str(item.get("model_b", ""))
            if a == "" or b == "":
                continue
            score = float(_safe_float(item.get("complementarity_score"), 0.0))
            complement_map[(a, b)] = score
            complement_map[(b, a)] = score

        score_map = {str(item.get("model_id", "")): float(_safe_float(item.get("contribution_score"), 0.0)) for item in ranked}
        plans: list[dict[str, Any]] = []
        for target in replace_rows:
            target_id = str(target.get("model_id", ""))
            target_score = float(_safe_float(target.get("contribution_score"), 0.0))
            candidates: list[dict[str, Any]] = []
            for candidate in ranked:
                cand_id = str(candidate.get("model_id", ""))
                if cand_id == "" or cand_id == target_id:
                    continue
                cand_score = float(_safe_float(candidate.get("contribution_score"), 0.0))
                if cand_score <= target_score:
                    continue
                pair_score = float(complement_map.get((target_id, cand_id), 0.0))
                replacement_score = float(0.70 * cand_score + 0.30 * pair_score)
                candidates.append(
                    {
                        "model_id": cand_id,
                        "contribution_score": cand_score,
                        "target_pair_complementarity": pair_score,
                        "replacement_score": replacement_score,
                    }
                )
            candidates.sort(key=lambda item: float(item.get("replacement_score", 0.0)), reverse=True)
            plans.append(
                {
                    "target_model_id": target_id,
                    "target_contribution_score": target_score,
                    "alternatives": candidates[:2],
                }
            )

        global_candidates = sorted(
            [
                {"model_id": mid, "contribution_score": score}
                for mid, score in score_map.items()
                if mid != ""
            ],
            key=lambda item: float(item.get("contribution_score", 0.0)),
            reverse=True,
        )
        return {
            "summary": {
                "replacement_target_count": int(len(replace_rows)),
                "generated_plan_count": int(len(plans)),
            },
            "replacement_plans": plans,
            "global_alternative_pool": global_candidates[:3],
        }

    def _submodel_analysis(self, context: dict[str, Any], true_values: list[float] | None, top_k: int) -> dict[str, Any]:
        performance = self._submodel_performance_comparison(context, true_values)
        stability = self._submodel_stability_analysis(context, true_values)
        complementarity = self._submodel_complementarity_analysis(context, true_values, top_k=int(top_k))
        weights = self._submodel_weight_visualization(context, top_k=int(top_k))
        contribution_ranking = self._submodel_contribution_ranking(
            performance=performance,
            stability=stability,
            complementarity=complementarity,
            weights=weights,
        )
        selection_recommendation = self._submodel_selection_recommendation(
            contribution_ranking=contribution_ranking,
            performance=performance,
            stability=stability,
        )
        alternative_solutions = self._submodel_alternative_solutions(
            contribution_ranking=contribution_ranking,
            selection_recommendation=selection_recommendation,
            complementarity=complementarity,
        )
        return {
            "submodel_performance_comparison": performance,
            "submodel_stability_analysis": stability,
            "submodel_complementarity_analysis": complementarity,
            "submodel_weight_visualization": weights,
            "submodel_contribution_ranking": contribution_ranking,
            "submodel_selection_recommendation": selection_recommendation,
            "submodel_alternative_solutions": alternative_solutions,
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
        submodel_analysis = self._submodel_analysis(built, true_values, int(top_k))
        strategy_explanation = self._strategy_selection_explanation(built, true_values)
        context_memory_bytes = self._array_bytes(
            np.asarray(built["matrix"], dtype=np.float32),
            np.asarray(built["fused_predictions"], dtype=np.float32),
            np.asarray(built["fused_variances"], dtype=np.float32),
            np.asarray(built["background"], dtype=np.float32),
        )
        estimated_raw_context_memory_bytes = int(context_memory_bytes * 2)
        context_memory_saved_ratio = float(
            max(0.0, min(1.0, 1.0 - (context_memory_bytes / max(1, estimated_raw_context_memory_bytes))))
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
            "submodel_analysis": submodel_analysis,
            "submodel_performance_comparison": submodel_analysis["submodel_performance_comparison"],
            "submodel_stability_analysis": submodel_analysis["submodel_stability_analysis"],
            "submodel_complementarity_analysis": submodel_analysis["submodel_complementarity_analysis"],
            "submodel_weight_visualization": submodel_analysis["submodel_weight_visualization"],
            "submodel_contribution_ranking": submodel_analysis["submodel_contribution_ranking"],
            "submodel_selection_recommendation": submodel_analysis["submodel_selection_recommendation"],
            "submodel_alternative_solutions": submodel_analysis["submodel_alternative_solutions"],
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
                "estimated_raw_context_memory_bytes": int(estimated_raw_context_memory_bytes),
                "context_memory_saved_ratio": float(context_memory_saved_ratio),
                "result_memory_bytes": int(result_memory_bytes),
                "latency_target_ms": 2500.0,
                "meets_latency_target": float((time.perf_counter() - started) * 1000.0) < 2500.0,
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, result)
        return result

    def explain_batch(
        self,
        *,
        models_batch: list[list[dict[str, Any]]],
        top_k: int = 5,
        max_explain_nodes: int | None = None,
        num_samples: int | None = None,
        profile_id: str | None = None,
        strategy: str | None = None,
        weight_method: str | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
        profile_id_batch: list[str | None] | None = None,
        strategy_batch: list[str | None] | None = None,
        weight_method_batch: list[str | None] | None = None,
        true_values_batch: list[list[float] | None] | None = None,
        context_batch: list[dict[str, list[float]] | None] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        batch_key = self._stable_hash(
            {
                "method": "lime_batch",
                "models_batch": [self._normalize_models(m) for m in models_batch],
                "top_k": int(top_k),
                "max_explain_nodes": int(max_explain_nodes or self.config.max_explain_nodes),
                "num_samples": int(num_samples or self.config.lime_num_samples),
                "profile_id": profile_id,
                "strategy": strategy,
                "weight_method": weight_method,
                "true_values": true_values,
                "context": context or {},
                "profile_id_batch": profile_id_batch or [],
                "strategy_batch": strategy_batch or [],
                "weight_method_batch": weight_method_batch or [],
                "true_values_batch": true_values_batch or [],
                "context_batch": context_batch or [],
            }
        )
        cached = self._batch_cache_get(batch_key)
        if cached is not None:
            cached["performance"] = {
                **dict(cached.get("performance", {})),
                "batch_cache_hit": True,
                "duration_ms": float((time.perf_counter() - started) * 1000.0),
                **self._cache_metrics(),
            }
            return cached

        results: list[dict[str, Any]] = []
        cache_hit_count = 0
        for idx, models in enumerate(models_batch):
            out = self.explain(
                models=models,
                top_k=top_k,
                max_explain_nodes=max_explain_nodes,
                num_samples=num_samples,
                profile_id=self._batch_item(profile_id_batch, idx, profile_id),
                strategy=self._batch_item(strategy_batch, idx, strategy),
                weight_method=self._batch_item(weight_method_batch, idx, weight_method),
                true_values=self._batch_item(true_values_batch, idx, true_values),
                context=self._batch_item(context_batch, idx, context),
            )
            cache_hit_count += int(bool(out.get("performance", {}).get("cache_hit", False)))
            results.append({"batch_index": int(idx), "result": out})

        total = max(1, len(results))
        payload = {
            "summary": {
                "method": "lime",
                "batch_size": int(len(results)),
                "cache_hit_count": int(cache_hit_count),
                "cache_hit_ratio": float(cache_hit_count / total),
            },
            "items": results,
            "performance": {
                "batch_cache_hit": False,
                "duration_ms": float((time.perf_counter() - started) * 1000.0),
                "avg_duration_ms": float(((time.perf_counter() - started) * 1000.0) / total),
                **self._cache_metrics(),
            },
        }
        self._batch_cache_set(batch_key, payload)
        return payload


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
        submodel_analysis = self._submodel_analysis(built, true_values, int(top_k))
        strategy_explanation = self._strategy_selection_explanation(built, true_values)
        context_memory_bytes = self._array_bytes(
            np.asarray(built["matrix"], dtype=np.float32),
            np.asarray(built["fused_predictions"], dtype=np.float32),
            np.asarray(built["fused_variances"], dtype=np.float32),
            np.asarray(built["background"], dtype=np.float32),
        )
        estimated_raw_context_memory_bytes = int(context_memory_bytes * 2)
        context_memory_saved_ratio = float(
            max(0.0, min(1.0, 1.0 - (context_memory_bytes / max(1, estimated_raw_context_memory_bytes))))
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
            "submodel_analysis": submodel_analysis,
            "submodel_performance_comparison": submodel_analysis["submodel_performance_comparison"],
            "submodel_stability_analysis": submodel_analysis["submodel_stability_analysis"],
            "submodel_complementarity_analysis": submodel_analysis["submodel_complementarity_analysis"],
            "submodel_weight_visualization": submodel_analysis["submodel_weight_visualization"],
            "submodel_contribution_ranking": submodel_analysis["submodel_contribution_ranking"],
            "submodel_selection_recommendation": submodel_analysis["submodel_selection_recommendation"],
            "submodel_alternative_solutions": submodel_analysis["submodel_alternative_solutions"],
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
                "estimated_raw_context_memory_bytes": int(estimated_raw_context_memory_bytes),
                "context_memory_saved_ratio": float(context_memory_saved_ratio),
                "result_memory_bytes": int(result_memory_bytes),
                "batch_shap_size": int(len(node_indices)),
                "latency_target_ms": 2500.0,
                "meets_latency_target": float((time.perf_counter() - started) * 1000.0) < 2500.0,
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, result)
        return result

    def explain_batch(
        self,
        *,
        models_batch: list[list[dict[str, Any]]],
        top_k: int = 5,
        max_explain_nodes: int | None = None,
        nsamples: int | None = None,
        profile_id: str | None = None,
        strategy: str | None = None,
        weight_method: str | None = None,
        true_values: list[float] | None = None,
        context: dict[str, list[float]] | None = None,
        profile_id_batch: list[str | None] | None = None,
        strategy_batch: list[str | None] | None = None,
        weight_method_batch: list[str | None] | None = None,
        true_values_batch: list[list[float] | None] | None = None,
        context_batch: list[dict[str, list[float]] | None] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        batch_key = self._stable_hash(
            {
                "method": "shap_batch",
                "models_batch": [self._normalize_models(m) for m in models_batch],
                "top_k": int(top_k),
                "max_explain_nodes": int(max_explain_nodes or self.config.max_explain_nodes),
                "nsamples": int(nsamples or self.config.shap_nsamples),
                "profile_id": profile_id,
                "strategy": strategy,
                "weight_method": weight_method,
                "true_values": true_values,
                "context": context or {},
                "profile_id_batch": profile_id_batch or [],
                "strategy_batch": strategy_batch or [],
                "weight_method_batch": weight_method_batch or [],
                "true_values_batch": true_values_batch or [],
                "context_batch": context_batch or [],
            }
        )
        cached = self._batch_cache_get(batch_key)
        if cached is not None:
            cached["performance"] = {
                **dict(cached.get("performance", {})),
                "batch_cache_hit": True,
                "duration_ms": float((time.perf_counter() - started) * 1000.0),
                **self._cache_metrics(),
            }
            return cached

        results: list[dict[str, Any]] = []
        cache_hit_count = 0
        for idx, models in enumerate(models_batch):
            out = self.explain(
                models=models,
                top_k=top_k,
                max_explain_nodes=max_explain_nodes,
                nsamples=nsamples,
                profile_id=self._batch_item(profile_id_batch, idx, profile_id),
                strategy=self._batch_item(strategy_batch, idx, strategy),
                weight_method=self._batch_item(weight_method_batch, idx, weight_method),
                true_values=self._batch_item(true_values_batch, idx, true_values),
                context=self._batch_item(context_batch, idx, context),
            )
            cache_hit_count += int(bool(out.get("performance", {}).get("cache_hit", False)))
            results.append({"batch_index": int(idx), "result": out})

        total = max(1, len(results))
        payload = {
            "summary": {
                "method": "shap",
                "batch_size": int(len(results)),
                "cache_hit_count": int(cache_hit_count),
                "cache_hit_ratio": float(cache_hit_count / total),
            },
            "items": results,
            "performance": {
                "batch_cache_hit": False,
                "duration_ms": float((time.perf_counter() - started) * 1000.0),
                "avg_duration_ms": float(((time.perf_counter() - started) * 1000.0) / total),
                **self._cache_metrics(),
            },
        }
        self._batch_cache_set(batch_key, payload)
        return payload
