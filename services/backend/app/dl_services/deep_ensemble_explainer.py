"""Deep Ensemble 模型解释适配器（LIME/SHAP）。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import copy
import hashlib
import json
import threading
import time
from typing import Any, Callable, Optional

import numpy as np
from sklearn.linear_model import Ridge


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class DeepEnsembleExplanationConfig:
    lime_num_samples: int = 160
    shap_nsamples: int = 100
    max_explain_nodes: int = 8
    cache_size: int = 16
    random_state: int = 42


class _BaseDeepEnsembleAdapter:
    def __init__(self, config: Optional[DeepEnsembleExplanationConfig] = None) -> None:
        self.config = config or DeepEnsembleExplanationConfig()
        self._lock = threading.Lock()
        self._result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0

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

    def _cache_metrics(self) -> dict[str, float | int]:
        with self._lock:
            total = self._cache_hits + self._cache_misses
            return {
                "result_cache_hits": int(self._cache_hits),
                "result_cache_misses": int(self._cache_misses),
                "result_cache_hit_rate": float(self._cache_hits / max(1, total)),
            }

    def _build_context(self, model: Any, features: np.ndarray) -> dict[str, Any]:
        x = np.asarray(features, dtype=float)
        pre = model.preprocess_deep_ensemble_data(x, use_training_stats=True)
        pred = model.predict_deep_ensemble(
            x,
            aggregation="mean",
            confidence=0.95,
            use_training_stats=True,
        )

        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        y_mean = np.asarray(pred["mean"], dtype=float).reshape(-1)
        y_var = np.asarray(pred["variance"], dtype=float).reshape(-1)
        if x_scaled.shape[0] != y_mean.shape[0]:
            raise ValueError("Deep Ensemble 预处理与预测样本数量不一致")

        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(x_scaled, y_mean)
        baseline = np.mean(x_scaled, axis=0)
        background = x_scaled if x_scaled.shape[0] <= 24 else x_scaled[np.linspace(0, x_scaled.shape[0] - 1, 24, dtype=int)]
        return {
            "scaled_x": x_scaled,
            "feature_names": list(pre["feature_names"]),
            "prediction_mean": y_mean,
            "prediction_variance": y_var,
            "surrogate": surrogate,
            "baseline": np.asarray(baseline, dtype=float),
            "background": np.asarray(background, dtype=float),
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
            },
            "ensemble": {
                "member_count": int(pred.get("member_count", len(pred.get("member_ids", [])))),
                "member_ids": [str(mid) for mid in pred.get("member_ids", [])],
                "aggregation": str(pred.get("aggregation", "mean")),
            },
        }

    @staticmethod
    def _top_features(feature_names: list[str], scores: np.ndarray, top_k: int) -> list[dict[str, float | str]]:
        arr = np.asarray(scores, dtype=float).reshape(-1)
        if arr.size == 0:
            return []
        k = max(1, min(int(top_k), arr.shape[0]))
        order = np.argsort(np.abs(arr))[::-1][:k]
        return [
            {
                "feature": str(feature_names[int(i)] if int(i) < len(feature_names) else f"feature_{int(i)}"),
                "score": float(arr[int(i)]),
                "abs_score": float(abs(arr[int(i)])),
            }
            for i in order.tolist()
        ]

    @staticmethod
    def _select_explained_nodes(variance: np.ndarray, max_explain_nodes: int) -> list[int]:
        values = np.asarray(variance, dtype=float).reshape(-1)
        if values.size == 0:
            return []
        n = max(1, min(int(max_explain_nodes), int(values.size)))
        return np.argsort(values)[::-1][:n].astype(int).tolist()

    def _predict_surrogate(self, context: dict[str, Any]) -> Callable[[np.ndarray], np.ndarray]:
        surrogate: Ridge = context["surrogate"]
        return lambda x: surrogate.predict(np.asarray(x, dtype=float))

    def _fallback_local_pairs(self, context: dict[str, Any], node_index: int) -> tuple[list[tuple[int, float]], float]:
        surrogate: Ridge = context["surrogate"]
        instance = np.asarray(context["scaled_x"][node_index], dtype=float)
        local = np.asarray(surrogate.coef_, dtype=float).reshape(-1) * instance
        pred = float(surrogate.predict(instance.reshape(1, -1))[0])
        pairs = [(int(i), float(local[i])) for i in range(local.shape[0])]
        return pairs, pred


class DeepEnsembleLIMEAdapter(_BaseDeepEnsembleAdapter):
    """Deep Ensemble 的 LIME 解释适配器。"""

    def explain(
        self,
        *,
        model: Any,
        features: np.ndarray | list[list[float]],
        top_k: int = 5,
        max_explain_nodes: int | None = None,
        num_samples: int | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        x = np.asarray(features, dtype=float)
        explain_nodes = int(max_explain_nodes or self.config.max_explain_nodes)
        effective_samples = int(num_samples or self.config.lime_num_samples)
        cache_key = self._stable_hash(
            {
                "method": "lime",
                "shape": [int(x.shape[0]), int(x.shape[1]) if x.ndim == 2 else 0],
                "feature_hash": hashlib.md5(np.ascontiguousarray(x).tobytes()).hexdigest(),
                "top_k": int(top_k),
                "max_explain_nodes": int(explain_nodes),
                "num_samples": int(effective_samples),
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

        context = self._build_context(model=model, features=x)
        node_indices = self._select_explained_nodes(context["prediction_variance"], explain_nodes)
        predict_fn = self._predict_surrogate(context)
        lime_module = self._load_lime_tabular()
        lime_explainer = None
        if lime_module is not None:
            try:
                lime_explainer = lime_module.LimeTabularExplainer(
                    training_data=np.asarray(context["scaled_x"], dtype=float),
                    feature_names=list(context["feature_names"]),
                    mode="regression",
                    random_state=int(self.config.random_state),
                )
            except Exception:
                lime_explainer = None

        batch_explanations: list[dict[str, Any]] = []
        raw_local: list[list[float]] = []
        for idx in node_indices:
            pairs: list[tuple[int, float]]
            local_pred: float
            if lime_explainer is not None:
                try:
                    instance = np.asarray(context["scaled_x"][idx], dtype=float)
                    exp = lime_explainer.explain_instance(
                        instance,
                        predict_fn=predict_fn,
                        num_features=int(np.asarray(instance).shape[0]),
                        num_samples=max(40, int(effective_samples)),
                    )
                    pairs = [(int(i), float(v)) for i, v in exp.local_exp.get(1, [])]
                    local_pred = _safe_float(
                        getattr(exp, "predicted_value", [0.0])[0],
                        float(predict_fn(instance.reshape(1, -1))[0]),
                    )
                except Exception:
                    pairs, local_pred = self._fallback_local_pairs(context, idx)
            else:
                pairs, local_pred = self._fallback_local_pairs(context, idx)

            local_arr = np.zeros(len(context["feature_names"]), dtype=float)
            for f_idx, score in pairs:
                if 0 <= int(f_idx) < local_arr.shape[0]:
                    local_arr[int(f_idx)] = float(score)
            raw_local.append([float(v) for v in local_arr.tolist()])
            batch_explanations.append(
                {
                    "node_index": int(idx),
                    "prediction_mean": float(context["prediction_mean"][idx]),
                    "prediction_variance": float(context["prediction_variance"][idx]),
                    "surrogate_prediction": float(local_pred),
                    "top_contributions": self._top_features(context["feature_names"], local_arr, int(top_k)),
                    "raw_local_weights": [float(v) for v in local_arr.tolist()],
                }
            )

        global_importance = np.mean(np.abs(np.asarray(raw_local, dtype=float)), axis=0) if raw_local else np.zeros(0, dtype=float)
        payload = {
            "summary": {
                "method": "lime",
                "explained_nodes": int(len(node_indices)),
                "num_features": int(len(context["feature_names"])),
                "num_samples": int(effective_samples),
                "sample_count": int(np.asarray(context["scaled_x"]).shape[0]),
            },
            "batch_explanations": batch_explanations,
            "global_feature_importance": self._top_features(context["feature_names"], global_importance, len(context["feature_names"])),
            "preprocess": dict(context["preprocess"]),
            "ensemble": dict(context["ensemble"]),
            "explainer": {
                "backend": "lime_tabular" if lime_module is not None else "surrogate_linear",
            },
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, payload)
        return payload


class DeepEnsembleSHAPAdapter(_BaseDeepEnsembleAdapter):
    """Deep Ensemble 的 SHAP 解释适配器。"""

    def explain(
        self,
        *,
        model: Any,
        features: np.ndarray | list[list[float]],
        top_k: int = 5,
        max_explain_nodes: int | None = None,
        nsamples: int | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        x = np.asarray(features, dtype=float)
        explain_nodes = int(max_explain_nodes or self.config.max_explain_nodes)
        effective_nsamples = int(nsamples or self.config.shap_nsamples)
        cache_key = self._stable_hash(
            {
                "method": "shap",
                "shape": [int(x.shape[0]), int(x.shape[1]) if x.ndim == 2 else 0],
                "feature_hash": hashlib.md5(np.ascontiguousarray(x).tobytes()).hexdigest(),
                "top_k": int(top_k),
                "max_explain_nodes": int(explain_nodes),
                "nsamples": int(effective_nsamples),
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

        context = self._build_context(model=model, features=x)
        node_indices = self._select_explained_nodes(context["prediction_variance"], explain_nodes)
        surrogate: Ridge = context["surrogate"]
        baseline = np.asarray(context["baseline"], dtype=float).reshape(-1)
        shap_module = self._load_shap()
        shap_explainer = None
        if shap_module is not None:
            try:
                shap_explainer = shap_module.KernelExplainer(
                    lambda data: surrogate.predict(np.asarray(data, dtype=float)),
                    np.asarray(context["background"], dtype=float),
                )
            except Exception:
                shap_explainer = None

        batch_explanations: list[dict[str, Any]] = []
        raw_values: list[list[float]] = []
        for idx in node_indices:
            instance = np.asarray(context["scaled_x"][idx], dtype=float).reshape(-1)
            expected_value = float(surrogate.predict(baseline.reshape(1, -1))[0])
            backend = "surrogate_linear"
            if shap_explainer is not None:
                try:
                    shap_arr = shap_explainer.shap_values(instance.reshape(1, -1), nsamples=max(20, int(effective_nsamples)))
                    if isinstance(shap_arr, list):
                        shap_arr = shap_arr[0]
                    shap_values = np.asarray(shap_arr, dtype=float).reshape(-1)
                    ev = getattr(shap_explainer, "expected_value", expected_value)
                    if isinstance(ev, (list, tuple, np.ndarray)):
                        expected_value = _safe_float(np.asarray(ev).reshape(-1)[0], expected_value)
                    else:
                        expected_value = _safe_float(ev, expected_value)
                    backend = "shap_kernel"
                except Exception:
                    shap_values = np.asarray(surrogate.coef_, dtype=float).reshape(-1) * (instance - baseline)
            else:
                shap_values = np.asarray(surrogate.coef_, dtype=float).reshape(-1) * (instance - baseline)

            pred_value = float(surrogate.predict(instance.reshape(1, -1))[0])
            raw_values.append([float(v) for v in shap_values.tolist()])
            batch_explanations.append(
                {
                    "node_index": int(idx),
                    "prediction_mean": float(context["prediction_mean"][idx]),
                    "prediction_variance": float(context["prediction_variance"][idx]),
                    "surrogate_prediction": pred_value,
                    "expected_value": float(expected_value),
                    "top_contributions": self._top_features(context["feature_names"], shap_values, int(top_k)),
                    "raw_shap_values": [float(v) for v in shap_values.tolist()],
                    "backend": backend,
                }
            )

        global_importance = np.mean(np.abs(np.asarray(raw_values, dtype=float)), axis=0) if raw_values else np.zeros(0, dtype=float)
        payload = {
            "summary": {
                "method": "shap",
                "explained_nodes": int(len(node_indices)),
                "num_features": int(len(context["feature_names"])),
                "nsamples": int(effective_nsamples),
                "sample_count": int(np.asarray(context["scaled_x"]).shape[0]),
            },
            "batch_explanations": batch_explanations,
            "global_feature_importance": self._top_features(context["feature_names"], global_importance, len(context["feature_names"])),
            "preprocess": dict(context["preprocess"]),
            "ensemble": dict(context["ensemble"]),
            "explainer": {
                "backend": "shap" if shap_module is not None else "surrogate_linear",
                "background_size": int(np.asarray(context["background"]).shape[0]),
            },
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, payload)
        return payload
