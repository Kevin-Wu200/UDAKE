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
        payload = fusion_platform_service.inference(
            models=normalized_models,
            profile_id=profile_id,
            strategy=strategy,
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
        background = matrix if matrix.shape[0] <= 32 else matrix[np.linspace(0, matrix.shape[0] - 1, 32, dtype=int)]
        return {
            "matrix": matrix,
            "model_ids": model_ids,
            "fused_predictions": fused_predictions,
            "fused_variances": variances,
            "weights": dict(result.get("weights", {})),
            "online_weights": dict(payload.get("online_weights", {})),
            "strategy": str(result.get("strategy", "")),
            "weight_method": str(result.get("weight_method", "")),
            "selected_strategy": str(payload.get("selected_strategy", "")),
            "metrics": dict(result.get("metrics", {})),
            "surrogate": surrogate,
            "baseline": np.asarray(baseline, dtype=float),
            "background": np.asarray(background, dtype=float),
            "preprocess": {
                "sample_count": int(matrix.shape[0]),
                "model_count": int(matrix.shape[1]),
                "model_ids": list(model_ids),
                "has_true_values": bool(true_values is not None),
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
        for idx in node_indices:
            instance = np.asarray(built["matrix"][idx], dtype=float).reshape(-1)
            local_pred = float(predict_fn(instance.reshape(1, -1))[0])
            local_weights = np.asarray(built["surrogate"].coef_, dtype=float).reshape(-1) * (
                instance - np.asarray(built["baseline"], dtype=float).reshape(-1)
            )
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
            "preprocess": dict(built["preprocess"]),
            "explainer": {
                "backend": backend,
                "context_cache_hit": bool(context_cache_hit),
            },
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                "context_build_ms": float(context_ms),
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
        for idx in node_indices:
            instance = np.asarray(built["matrix"][idx], dtype=float).reshape(-1)
            expected_value = float(predict_fn(baseline.reshape(1, -1))[0])
            shap_values = np.asarray(built["surrogate"].coef_, dtype=float).reshape(-1) * (instance - baseline)
            if kernel_explainer is not None:
                try:
                    shap_arr = kernel_explainer.shap_values(
                        instance.reshape(1, -1),
                        nsamples=max(20, int(effective_nsamples)),
                        silent=True,
                    )
                    if isinstance(shap_arr, list):
                        shap_arr = shap_arr[0]
                    shap_values = np.asarray(shap_arr, dtype=float).reshape(-1)
                    ev = getattr(kernel_explainer, "expected_value", expected_value)
                    if np.asarray(ev).reshape(-1).size > 0:
                        expected_value = _safe_float(np.asarray(ev).reshape(-1)[0], expected_value)
                except Exception:
                    pass
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
            "preprocess": dict(built["preprocess"]),
            "explainer": {
                "backend": backend,
                "background_size": int(np.asarray(built["background"]).shape[0]),
                "context_cache_hit": bool(context_cache_hit),
            },
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                "context_build_ms": float(context_ms),
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, result)
        return result
