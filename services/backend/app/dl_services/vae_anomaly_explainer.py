"""VAE 异常检测模型解释适配器。"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np
from sklearn.linear_model import Ridge

from deep_learning.models.anomaly_detection.common import (
    multiscale_value_features,
    robust_zscore,
)

from .anomaly_features import AnomalyFeatureRegistry


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class VAEExplanationConfig:
    lime_num_samples: int = 220
    shap_nsamples: int = 120
    max_explain_nodes: int = 8
    cache_size: int = 32
    random_state: int = 42


class _BaseVAEAdapter:
    def __init__(self, config: Optional[VAEExplanationConfig] = None) -> None:
        self.config = config or VAEExplanationConfig()
        self._lock = threading.Lock()
        self._result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._context_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._feature_registry = AnomalyFeatureRegistry()

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

    def _build_feature_matrix(self, coords: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, list[str]]:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)

        radius = np.linalg.norm(c, axis=1, keepdims=True)
        angle = np.arctan2(c[:, 1], c[:, 0]).reshape(-1, 1)
        centered_value = (v - np.mean(v)).reshape(-1, 1)
        squared_value = (v * v).reshape(-1, 1)
        raw_value = v.reshape(-1, 1)
        multi = multiscale_value_features(c, v, scales=(3, 5, 9))
        base = np.concatenate([c, radius, angle, raw_value, centered_value, squared_value, multi, c, raw_value], axis=1)
        names = [item.feature_name for item in self._feature_registry.model_features("vae")]
        return base, names

    def _standardize_column(self, values: np.ndarray, strategy: str) -> tuple[np.ndarray, dict[str, float]]:
        v = np.asarray(values, dtype=float).reshape(-1)
        if strategy == "minmax":
            v_min = float(np.min(v))
            v_max = float(np.max(v))
            scale = v_max - v_min
            if abs(scale) < 1e-9:
                return np.zeros_like(v), {"strategy": 2.0, "shift": v_min, "scale": 1.0}
            return (v - v_min) / (scale + 1e-9), {"strategy": 2.0, "shift": v_min, "scale": scale}

        if strategy == "robust_zscore":
            median = float(np.median(v))
            mad = float(np.median(np.abs(v - median)))
            if mad < 1e-9:
                mean = float(np.mean(v))
                std = float(np.std(v))
                std = std if std > 1e-9 else 1.0
                return (v - mean) / std, {"strategy": 1.0, "shift": mean, "scale": std}
            scaled = robust_zscore(v)
            return scaled, {"strategy": 1.0, "shift": median, "scale": mad}

        mean = float(np.mean(v))
        std = float(np.std(v))
        std = std if std > 1e-9 else 1.0
        return (v - mean) / std, {"strategy": 0.0, "shift": mean, "scale": std}

    def _preprocess(self, matrix: np.ndarray, feature_names: list[str]) -> tuple[np.ndarray, dict[str, dict[str, float]]]:
        plan = self._feature_registry.standardization_plan("vae")
        scaled = np.zeros_like(matrix, dtype=float)
        stats: dict[str, dict[str, float]] = {}
        for idx, name in enumerate(feature_names):
            strategy = plan.get(name, "zscore")
            scaled_col, st = self._standardize_column(matrix[:, idx], strategy)
            scaled[:, idx] = scaled_col
            stats[name] = st
        return scaled, stats

    def _predict_scores(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        bundle = model.anomaly_scores(np.asarray(coords, dtype=float), np.asarray(values, dtype=float))
        reconstruction = np.asarray(bundle.get("reconstruction", []), dtype=float)
        latent_distance = np.asarray(bundle.get("latent_distance", []), dtype=float)
        combined = np.asarray(bundle.get("combined", []), dtype=float)
        return {
            "reconstruction": reconstruction,
            "latent_distance": latent_distance,
            "combined": combined,
        }

    def _dynamic_lime_samples(self, n_features: int, n_points: int) -> int:
        base = max(80, int(self.config.lime_num_samples))
        return min(1000, base + n_features * 10 + n_points * 2)

    def _select_background(self, x_scaled: np.ndarray, scores: np.ndarray, size: int = 64) -> np.ndarray:
        n = x_scaled.shape[0]
        k = max(8, min(size, n))
        if n <= k:
            return x_scaled.copy()
        order = np.argsort(scores)
        evenly = np.linspace(0, n - 1, k, dtype=int)
        return x_scaled[np.unique(order[evenly])]

    def _top_node_indices(self, scores: np.ndarray, max_explain_nodes: int) -> list[int]:
        n = len(scores)
        explain_count = max(1, min(int(max_explain_nodes), n))
        return np.argsort(-scores)[:explain_count].astype(int).tolist()

    def _build_context(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> dict[str, Any]:
        key = self._stable_hash(
            {
                "coords_hash": hashlib.md5(np.asarray(coords).tobytes()).hexdigest(),
                "values_hash": hashlib.md5(np.asarray(values).tobytes()).hexdigest(),
                "shape": [int(coords.shape[0]), int(coords.shape[1])],
            }
        )
        cached = self._context_get(key)
        if cached is not None:
            return cached

        matrix, feature_names = self._build_feature_matrix(coords, values)
        scaled_x, scaler_stats = self._preprocess(matrix, feature_names)
        score_bundle = self._predict_scores(model=model, coords=coords, values=values)
        target = score_bundle["combined"].astype(float)
        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(scaled_x, target)

        context = {
            "context_key": key,
            "feature_matrix": self._to_float32(matrix),
            "scaled_x": self._to_float32(scaled_x),
            "feature_names": feature_names,
            "scaler_stats": scaler_stats,
            "score_bundle": score_bundle,
            "target": self._to_float32(target),
            "surrogate": surrogate,
            "background": self._to_float32(self._select_background(scaled_x, target, size=48)),
        }
        self._context_set(key, context)
        return context

    def _predict_surrogate(self, context: dict[str, Any]) -> Callable[[np.ndarray], np.ndarray]:
        model: Ridge = context["surrogate"]
        return lambda x: model.predict(np.asarray(x, dtype=float))

    @staticmethod
    def _to_float32(arr: np.ndarray) -> np.ndarray:
        x = np.asarray(arr, dtype=float)
        if x.dtype == np.float32:
            return x
        return x.astype(np.float32, copy=False)

    @staticmethod
    def _memory_bytes(context: dict[str, Any], extra_arrays: Optional[list[np.ndarray]] = None) -> int:
        keys = ["feature_matrix", "scaled_x", "background", "target"]
        total = 0
        for key in keys:
            arr = context.get(key)
            if isinstance(arr, np.ndarray):
                total += int(arr.nbytes)
        score_bundle = context.get("score_bundle", {})
        if isinstance(score_bundle, dict):
            for arr in score_bundle.values():
                if isinstance(arr, np.ndarray):
                    total += int(arr.nbytes)
        for arr in extra_arrays or []:
            total += int(np.asarray(arr).nbytes)
        return int(total)

    def _compressed_lime_training_data(self, context: dict[str, Any], explained_nodes: list[int]) -> np.ndarray:
        x = np.asarray(context["scaled_x"], dtype=float)
        if x.shape[0] <= 64:
            return x
        scores = np.asarray(context["target"], dtype=float).reshape(-1)
        keep = min(96, x.shape[0])
        top_k = max(8, min(len(explained_nodes) * 4, keep // 2))
        top_idx = np.argsort(-scores)[:top_k].astype(int)
        low_idx = np.argsort(scores)[:top_k].astype(int)
        mixed = np.concatenate([top_idx, low_idx], axis=0)
        if mixed.size < keep:
            stride = max(1, x.shape[0] // max(1, keep - mixed.size))
            sampled = np.arange(0, x.shape[0], stride, dtype=int)[: max(1, keep - mixed.size)]
            mixed = np.concatenate([mixed, sampled], axis=0)
        unique_idx = np.unique(mixed)[:keep]
        return x[unique_idx]

    def _feature_category(self, name: str) -> str:
        item = self._feature_registry._COMMON_DEFINITIONS.get(name)
        return item.category if item is not None else "unknown"

    def _feature_display(self, name: str) -> str:
        return self._feature_registry._COMMON_DEFINITIONS.get(name, None).display_name if name in self._feature_registry._COMMON_DEFINITIONS else name

    def _reconstruction_analysis(self, reconstruction: np.ndarray, explained_nodes: list[int]) -> dict[str, Any]:
        recon = np.asarray(reconstruction, dtype=float).reshape(-1)
        if recon.size == 0:
            return {"stats": {"mean": 0.0, "std": 0.0, "p95": 0.0}, "node_analysis": []}
        z = robust_zscore(recon)
        node_items = [
            {
                "node_index": int(node_idx),
                "reconstruction_error": float(recon[node_idx]),
                "reconstruction_zscore": float(z[node_idx]),
            }
            for node_idx in explained_nodes
            if 0 <= node_idx < len(recon)
        ]
        return {
            "stats": {
                "mean": float(np.mean(recon)),
                "std": float(np.std(recon)),
                "p95": float(np.percentile(recon, 95)),
            },
            "node_analysis": node_items,
        }


class VAEAnomalyLIMEAdapter(_BaseVAEAdapter):
    """VAE 的 LIME 解释适配器。"""

    def _fallback_local_pairs(self, context: dict[str, Any], node_index: int) -> tuple[list[tuple[int, float]], float]:
        surrogate: Ridge = context["surrogate"]
        instance = np.asarray(context["scaled_x"][node_index], dtype=float)
        coef = np.asarray(surrogate.coef_, dtype=float)
        local = coef * instance
        pairs = [(int(i), float(local[i])) for i in range(local.shape[0])]
        pred = float(surrogate.predict(instance.reshape(1, -1))[0])
        return pairs, pred

    def explain(
        self,
        *,
        model: Any,
        coords: np.ndarray,
        values: np.ndarray,
        top_k: int = 5,
        num_samples: Optional[int] = None,
        max_explain_nodes: Optional[int] = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        context = self._build_context(model=model, coords=c, values=v)
        target = np.asarray(context["target"], dtype=float)
        explained_nodes = self._top_node_indices(target, int(max_explain_nodes or self.config.max_explain_nodes))
        selected_samples = int(num_samples or self._dynamic_lime_samples(context["scaled_x"].shape[1], len(v)))

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

        lime_module = self._load_lime_tabular()
        feature_names: list[str] = context["feature_names"]
        predict_fn = self._predict_surrogate(context)
        lime_training_data = self._compressed_lime_training_data(context, explained_nodes)
        lime_explainer = None
        if lime_module is not None:
            try:
                lime_explainer = lime_module.LimeTabularExplainer(
                    training_data=lime_training_data,
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
                    local_pred_arr = getattr(exp, "local_pred", None)
                    if isinstance(local_pred_arr, (list, tuple, np.ndarray)) and len(local_pred_arr) > 0:
                        local_pred = _safe_float(local_pred_arr[0], local_pred)
                except Exception:
                    local_pairs, local_pred = self._fallback_local_pairs(context, node_idx)
            else:
                local_pairs, local_pred = self._fallback_local_pairs(context, node_idx)

            contributions = [
                {
                    "feature_index": int(i),
                    "feature_name": feature_names[i],
                    "feature_alias": self._feature_display(feature_names[i]),
                    "category": self._feature_category(feature_names[i]),
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
                    "prediction": local_pred,
                    "target_prediction": float(target[node_idx]),
                    "fidelity": float(fidelity),
                    "confidence": float(max(0.0, min(1.0, fidelity * np.exp(-abs(local_pred - target[node_idx]))))),
                    "top_contributions": contributions,
                }
            )

        global_importance: dict[str, float] = {}
        raw_importance = np.zeros((len(feature_names),), dtype=float)
        for item in batch_explanations:
            for contrib in item["top_contributions"]:
                idx = int(contrib["feature_index"])
                raw_importance[idx] += float(abs(contrib["weight"]))
                name = str(contrib["feature_name"])
                global_importance[name] = global_importance.get(name, 0.0) + float(abs(contrib["weight"]))
        global_items = sorted(global_importance.items(), key=lambda kv: kv[1], reverse=True)
        global_feature_importance = [
            {
                "feature_name": name,
                "feature_alias": self._feature_display(name),
                "importance": float(weight / max(1, len(batch_explanations))),
                "category": self._feature_category(name),
            }
            for name, weight in global_items[: max(1, int(top_k))]
        ]

        reconstruction = np.asarray(context["score_bundle"]["reconstruction"], dtype=float)
        payload = {
            "summary": {
                "method": "lime",
                "explained_nodes": len(explained_nodes),
                "num_samples": selected_samples,
                "num_features": len(feature_names),
                "top_features": [
                    {
                        "feature_index": int(feature_names.index(str(item["feature_name"]))),
                        "feature_name": item["feature_name"],
                        "importance": item["importance"],
                    }
                    for item in global_feature_importance
                ],
                "average_confidence": float(np.mean([item["confidence"] for item in batch_explanations])) if batch_explanations else 0.0,
            },
            "feature_importance": raw_importance.astype(float).tolist(),
            "batch_explanations": batch_explanations,
            "global_feature_importance": global_feature_importance,
            "score_components": {
                "reconstruction": reconstruction.astype(float).tolist(),
                "latent_distance": np.asarray(context["score_bundle"]["latent_distance"], dtype=float).astype(float).tolist(),
                "combined": target.astype(float).tolist(),
            },
            "reconstruction_analysis": self._reconstruction_analysis(reconstruction, explained_nodes),
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "lime_training_size": int(lime_training_data.shape[0]),
                "lime_sampling_budget": int(selected_samples),
                "memory_bytes": self._memory_bytes(context),
            },
        }
        self._cache_set(cache_key, payload)
        return payload


class VAEAnomalySHAPAdapter(_BaseVAEAdapter):
    """VAE 的 SHAP 解释适配器。"""

    def explain(
        self,
        *,
        model: Any,
        coords: np.ndarray,
        values: np.ndarray,
        top_k: int = 5,
        nsamples: Optional[int] = None,
        max_explain_nodes: Optional[int] = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        context = self._build_context(model=model, coords=c, values=v)
        target = np.asarray(context["target"], dtype=float)
        explained_nodes = self._top_node_indices(target, int(max_explain_nodes or self.config.max_explain_nodes))
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
            used_backend = "surrogate_linear"
            if shap_module is not None:
                try:
                    explainer = shap_module.KernelExplainer(
                        lambda x: surrogate.predict(np.asarray(x, dtype=float)),
                        background,
                    )
                    values_arr = explainer.shap_values(
                        instance.reshape(1, -1),
                        nsamples=max(40, selected_nsamples),
                        l1_reg="num_features(10)",
                    )
                    if isinstance(values_arr, list):
                        values_arr = values_arr[0]
                    shap_values = np.asarray(values_arr, dtype=float).reshape(-1)
                    ev = getattr(explainer, "expected_value", expected_value)
                    if isinstance(ev, (list, tuple, np.ndarray)):
                        expected_value = _safe_float(np.asarray(ev).reshape(-1)[0], expected_value)
                    else:
                        expected_value = _safe_float(ev, expected_value)
                    used_backend = "shap_kernel"
                except Exception:
                    shap_values = np.asarray(surrogate.coef_, dtype=float) * (instance - baseline)
            else:
                shap_values = np.asarray(surrogate.coef_, dtype=float) * (instance - baseline)

            pred = float(surrogate.predict(instance.reshape(1, -1))[0])
            contributions = []
            for idx, score in enumerate(shap_values.tolist()):
                feature = feature_names[idx]
                contributions.append(
                    {
                        "feature_index": int(idx),
                        "feature_name": feature,
                        "feature_alias": self._feature_display(feature),
                        "category": self._feature_category(feature),
                        "shap_value": float(score),
                        "abs_shap": float(abs(score)),
                        "feature_value": float(context["feature_matrix"][node_idx, idx]),
                    }
                )
            contributions.sort(key=lambda item: item["abs_shap"], reverse=True)
            contributions = contributions[: max(1, int(top_k))]
            batch_explanations.append(
                {
                    "node_index": int(node_idx),
                    "prediction": pred,
                    "target_prediction": float(target[node_idx]),
                    "expected_value": expected_value,
                    "backend": used_backend,
                    "confidence": float(np.exp(-abs(pred - target[node_idx]) / (abs(target[node_idx]) + 1e-6))),
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
                "feature_alias": self._feature_display(feature_names[idx]),
                "importance": float(mean_abs[idx]),
                "category": self._feature_category(feature_names[idx]),
            }
            for idx in ranking[: max(1, int(top_k))]
        ]

        reconstruction = np.asarray(context["score_bundle"]["reconstruction"], dtype=float)
        payload = {
            "summary": {
                "method": "shap",
                "explainer": "KernelExplainer",
                "explained_nodes": len(explained_nodes),
                "num_features": len(feature_names),
                "background_size": int(background.shape[0]),
                "nsamples": selected_nsamples,
                "top_features": top_features,
                "average_confidence": float(np.mean([item["confidence"] for item in batch_explanations])) if batch_explanations else 0.0,
            },
            "feature_importance": mean_abs.astype(float).tolist(),
            "batch_explanations": batch_explanations,
            "global_feature_importance": top_features,
            "score_components": {
                "reconstruction": reconstruction.astype(float).tolist(),
                "latent_distance": np.asarray(context["score_bundle"]["latent_distance"], dtype=float).astype(float).tolist(),
                "combined": target.astype(float).tolist(),
            },
            "reconstruction_analysis": self._reconstruction_analysis(reconstruction, explained_nodes),
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "backend": "shap" if shap_module is not None else "surrogate_linear",
            },
        }
        self._cache_set(cache_key, payload)
        return payload
