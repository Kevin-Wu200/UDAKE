"""Attention-Kriging 模型解释适配器（LIME/SHAP）。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
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
class AttentionKrigingExplanationConfig:
    lime_num_samples: int = 180
    shap_nsamples: int = 120
    max_explain_nodes: int = 8
    cache_size: int = 24
    random_state: int = 42


class _BaseAttentionKrigingAdapter:
    def __init__(self, config: Optional[AttentionKrigingExplanationConfig] = None) -> None:
        self.config = config or AttentionKrigingExplanationConfig()
        self._lock = threading.Lock()
        self._result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._context_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

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

    def _cache_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            item = self._result_cache.get(key)
            if item is None:
                return None
            self._result_cache.move_to_end(key)
            return dict(item)

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._result_cache[key] = dict(value)
            self._result_cache.move_to_end(key)
            while len(self._result_cache) > self.config.cache_size:
                self._result_cache.popitem(last=False)

    def _context_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            item = self._context_cache.get(key)
            if item is None:
                return None
            self._context_cache.move_to_end(key)
            return item

    def _context_set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._context_cache[key] = value
            self._context_cache.move_to_end(key)
            while len(self._context_cache) > self.config.cache_size:
                self._context_cache.popitem(last=False)

    def _stable_hash(self, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _top_node_indices(self, uncertainty: np.ndarray, max_explain_nodes: int) -> list[int]:
        n = int(len(uncertainty))
        if n <= 0:
            return []
        explain_count = max(1, min(int(max_explain_nodes), n))
        return np.argsort(-np.asarray(uncertainty, dtype=float))[:explain_count].astype(int).tolist()

    def _build_context(
        self,
        *,
        model: Any,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray | None,
    ) -> dict[str, Any]:
        samples = np.asarray(sample_coords, dtype=float)
        values = np.asarray(sample_values, dtype=float).reshape(-1)
        queries = np.asarray(query_coords, dtype=float) if query_coords is not None else samples
        key = self._stable_hash(
            {
                "sample_shape": [int(samples.shape[0]), int(samples.shape[1])],
                "query_shape": [int(queries.shape[0]), int(queries.shape[1])],
                "sample_hash": hashlib.md5(samples.tobytes()).hexdigest(),
                "value_hash": hashlib.md5(values.tobytes()).hexdigest(),
                "query_hash": hashlib.md5(queries.tobytes()).hexdigest(),
            }
        )
        cached = self._context_get(key)
        if cached is not None:
            return cached

        pre = model.preprocess_attention_kriging_data(
            sample_coords=samples,
            sample_values=values,
            query_coords=queries,
            use_runtime_stats=True,
        )
        pred = model.predict_standard(
            sample_coords=samples,
            sample_values=values,
            query_coords=queries,
        )
        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        y_pred = np.asarray(pred["prediction"], dtype=float).reshape(-1)
        uncertainty = np.asarray(pred["uncertainty"], dtype=float).reshape(-1)
        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(x_scaled, y_pred)
        background = x_scaled.copy() if x_scaled.shape[0] <= 32 else x_scaled[np.linspace(0, x_scaled.shape[0] - 1, 32, dtype=int)]

        context = {
            "context_key": key,
            "feature_names": list(pre["feature_names"]),
            "feature_matrix": np.asarray(pre["feature_matrix"], dtype=float),
            "scaled_x": x_scaled,
            "prediction": y_pred,
            "uncertainty": uncertainty,
            "attention_mean_weight": np.asarray(pred.get("attention_summary", {}).get("mean_weight", []), dtype=float).reshape(-1),
            "surrogate": surrogate,
            "background": np.asarray(background, dtype=float),
        }
        self._context_set(key, context)
        return context

    def _predict_surrogate(self, context: dict[str, Any]) -> Callable[[np.ndarray], np.ndarray]:
        surrogate: Ridge = context["surrogate"]
        return lambda x: surrogate.predict(np.asarray(x, dtype=float))

    def _fallback_local_pairs(self, context: dict[str, Any], node_index: int) -> tuple[list[tuple[int, float]], float]:
        surrogate: Ridge = context["surrogate"]
        instance = np.asarray(context["scaled_x"][node_index], dtype=float)
        coef = np.asarray(surrogate.coef_, dtype=float)
        local = coef * instance
        pairs = [(int(i), float(local[i])) for i in range(local.shape[0])]
        pred = float(surrogate.predict(instance.reshape(1, -1))[0])
        return pairs, pred


class AttentionKrigingLIMEAdapter(_BaseAttentionKrigingAdapter):
    def explain(
        self,
        *,
        model: Any,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray | None = None,
        top_k: int = 5,
        num_samples: Optional[int] = None,
        max_explain_nodes: Optional[int] = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        context = self._build_context(
            model=model,
            sample_coords=sample_coords,
            sample_values=sample_values,
            query_coords=query_coords,
        )
        explained_nodes = self._top_node_indices(
            context["uncertainty"],
            int(max_explain_nodes or self.config.max_explain_nodes),
        )
        selected_samples = int(num_samples or self.config.lime_num_samples)
        cache_key = self._stable_hash(
            {
                "method": "lime",
                "context_key": context["context_key"],
                "top_k": int(top_k),
                "nodes": explained_nodes,
                "num_samples": selected_samples,
            }
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["performance"] = {**cached.get("performance", {}), "cache_hit": True}
            return cached

        feature_names: list[str] = context["feature_names"]
        predict_fn = self._predict_surrogate(context)
        lime_module = self._load_lime_tabular()
        lime_explainer = None
        if lime_module is not None:
            try:
                lime_explainer = lime_module.LimeTabularExplainer(
                    training_data=np.asarray(context["scaled_x"], dtype=float),
                    feature_names=feature_names,
                    mode="regression",
                    discretize_continuous=False,
                    random_state=self.config.random_state,
                )
            except Exception:
                lime_explainer = None

        batch_explanations: list[dict[str, Any]] = []
        for node_idx in explained_nodes:
            instance = np.asarray(context["scaled_x"][node_idx], dtype=float)
            local_pairs: list[tuple[int, float]]
            local_pred = float(predict_fn(instance.reshape(1, -1))[0])
            fidelity = 0.5
            if lime_explainer is not None:
                try:
                    exp = lime_explainer.explain_instance(
                        data_row=instance,
                        predict_fn=predict_fn,
                        num_features=max(1, min(int(top_k), len(feature_names))),
                        num_samples=max(80, selected_samples),
                    )
                    local_map = exp.local_exp.get(1) or exp.local_exp.get(0) or []
                    local_pairs = [(int(i), float(w)) for i, w in local_map]
                    fidelity = _safe_float(getattr(exp, "score", 0.5), 0.5)
                except Exception:
                    local_pairs, local_pred = self._fallback_local_pairs(context, node_idx)
            else:
                local_pairs, local_pred = self._fallback_local_pairs(context, node_idx)

            contributions = [
                {
                    "feature_index": int(i),
                    "feature_name": feature_names[i],
                    "weight": float(w),
                    "abs_weight": float(abs(w)),
                    "feature_value": float(context["feature_matrix"][node_idx, i]),
                }
                for i, w in local_pairs
            ]
            contributions.sort(key=lambda item: item["abs_weight"], reverse=True)
            contributions = contributions[: max(1, int(top_k))]
            batch_explanations.append(
                {
                    "node_index": int(node_idx),
                    "prediction": float(local_pred),
                    "target_prediction": float(context["prediction"][node_idx]),
                    "uncertainty": float(context["uncertainty"][node_idx]),
                    "fidelity": float(fidelity),
                    "top_contributions": contributions,
                }
            )

        raw_importance = np.zeros((len(feature_names),), dtype=float)
        for item in batch_explanations:
            for contrib in item["top_contributions"]:
                raw_importance[int(contrib["feature_index"])] += float(abs(contrib["weight"]))
        order = np.argsort(-raw_importance)[: max(1, min(int(top_k), len(feature_names)))]
        top_features = [
            {
                "feature_index": int(idx),
                "feature_name": feature_names[int(idx)],
                "importance": float(raw_importance[int(idx)] / max(1, len(batch_explanations))),
            }
            for idx in order
        ]

        payload = {
            "summary": {
                "method": "lime",
                "explained_nodes": len(explained_nodes),
                "num_features": len(feature_names),
                "num_samples": selected_samples,
                "top_features": top_features,
            },
            "feature_importance": raw_importance.astype(float).tolist(),
            "batch_explanations": batch_explanations,
            "global_feature_importance": top_features,
            "score_components": {
                "prediction": np.asarray(context["prediction"], dtype=float).tolist(),
                "uncertainty": np.asarray(context["uncertainty"], dtype=float).tolist(),
                "attention_mean_weight": np.asarray(context["attention_mean_weight"], dtype=float).tolist(),
            },
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
            },
        }
        self._cache_set(cache_key, payload)
        return payload


class AttentionKrigingSHAPAdapter(_BaseAttentionKrigingAdapter):
    def explain(
        self,
        *,
        model: Any,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords: np.ndarray | None = None,
        top_k: int = 5,
        nsamples: Optional[int] = None,
        max_explain_nodes: Optional[int] = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        context = self._build_context(
            model=model,
            sample_coords=sample_coords,
            sample_values=sample_values,
            query_coords=query_coords,
        )
        explained_nodes = self._top_node_indices(
            context["uncertainty"],
            int(max_explain_nodes or self.config.max_explain_nodes),
        )
        selected_nsamples = int(nsamples or self.config.shap_nsamples)
        cache_key = self._stable_hash(
            {
                "method": "shap",
                "context_key": context["context_key"],
                "top_k": int(top_k),
                "nodes": explained_nodes,
                "nsamples": selected_nsamples,
            }
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["performance"] = {**cached.get("performance", {}), "cache_hit": True}
            return cached

        shap_module = self._load_shap()
        surrogate: Ridge = context["surrogate"]
        feature_names: list[str] = context["feature_names"]
        background = np.asarray(context["background"], dtype=float)
        baseline = np.mean(background, axis=0)

        batch_explanations: list[dict[str, Any]] = []
        for node_idx in explained_nodes:
            instance = np.asarray(context["scaled_x"][node_idx], dtype=float)
            expected_value = float(surrogate.predict(baseline.reshape(1, -1))[0])
            backend = "surrogate_linear"
            if shap_module is not None:
                try:
                    explainer = shap_module.KernelExplainer(lambda x: surrogate.predict(np.asarray(x, dtype=float)), background)
                    shap_arr = explainer.shap_values(
                        instance.reshape(1, -1),
                        nsamples=max(40, selected_nsamples),
                        l1_reg="num_features(10)",
                    )
                    if isinstance(shap_arr, list):
                        shap_arr = shap_arr[0]
                    shap_values = np.asarray(shap_arr, dtype=float).reshape(-1)
                    ev = getattr(explainer, "expected_value", expected_value)
                    if isinstance(ev, (list, tuple, np.ndarray)):
                        expected_value = _safe_float(np.asarray(ev).reshape(-1)[0], expected_value)
                    else:
                        expected_value = _safe_float(ev, expected_value)
                    backend = "shap_kernel"
                except Exception:
                    shap_values = np.asarray(surrogate.coef_, dtype=float) * (instance - baseline)
            else:
                shap_values = np.asarray(surrogate.coef_, dtype=float) * (instance - baseline)

            pred = float(surrogate.predict(instance.reshape(1, -1))[0])
            contributions = [
                {
                    "feature_index": int(i),
                    "feature_name": feature_names[i],
                    "shap_value": float(score),
                    "abs_shap": float(abs(score)),
                    "feature_value": float(context["feature_matrix"][node_idx, i]),
                }
                for i, score in enumerate(shap_values.tolist())
            ]
            contributions.sort(key=lambda item: item["abs_shap"], reverse=True)
            contributions = contributions[: max(1, int(top_k))]
            batch_explanations.append(
                {
                    "node_index": int(node_idx),
                    "prediction": float(pred),
                    "target_prediction": float(context["prediction"][node_idx]),
                    "uncertainty": float(context["uncertainty"][node_idx]),
                    "expected_value": float(expected_value),
                    "backend": backend,
                    "top_contributions": contributions,
                    "raw_shap_values": [float(x) for x in shap_values.tolist()],
                }
            )

        mean_abs = np.mean(np.abs(np.asarray([item["raw_shap_values"] for item in batch_explanations], dtype=float)), axis=0)
        ranking = np.argsort(-mean_abs).astype(int).tolist()
        top_features = [
            {
                "feature_index": int(idx),
                "feature_name": feature_names[idx],
                "importance": float(mean_abs[idx]),
            }
            for idx in ranking[: max(1, min(int(top_k), len(feature_names)))]
        ]

        payload = {
            "summary": {
                "method": "shap",
                "explainer": "KernelExplainer",
                "explained_nodes": len(explained_nodes),
                "num_features": len(feature_names),
                "nsamples": selected_nsamples,
                "top_features": top_features,
            },
            "feature_importance": mean_abs.astype(float).tolist(),
            "batch_explanations": batch_explanations,
            "global_feature_importance": top_features,
            "score_components": {
                "prediction": np.asarray(context["prediction"], dtype=float).tolist(),
                "uncertainty": np.asarray(context["uncertainty"], dtype=float).tolist(),
                "attention_mean_weight": np.asarray(context["attention_mean_weight"], dtype=float).tolist(),
            },
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "backend": "shap" if shap_module is not None else "surrogate_linear",
            },
        }
        self._cache_set(cache_key, payload)
        return payload
