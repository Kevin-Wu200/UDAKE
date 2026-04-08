"""对比学习异常检测模型 LIME 解释适配器。"""

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

from .anomaly_features import AnomalyFeatureRegistry


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class ContrastiveExplanationConfig:
    lime_num_samples: int = 240
    max_explain_nodes: int = 8
    cache_size: int = 32
    random_state: int = 42


class ContrastiveLimeAdapter:
    """对比学习模型的 LIME 解释适配器。"""

    def __init__(self, config: Optional[ContrastiveExplanationConfig] = None) -> None:
        self.config = config or ContrastiveExplanationConfig()
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

    def _stable_hash(self, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

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

    def _feature_category(self, name: str) -> str:
        item = self._feature_registry._COMMON_DEFINITIONS.get(name)
        return item.category if item is not None else "unknown"

    def _feature_display(self, name: str) -> str:
        if name in self._feature_registry._COMMON_DEFINITIONS:
            return self._feature_registry._COMMON_DEFINITIONS[name].display_name
        return name

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
            scaled = (v - median) / (1.4826 * mad + 1e-9)
            return scaled, {"strategy": 1.0, "shift": median, "scale": mad}

        mean = float(np.mean(v))
        std = float(np.std(v))
        std = std if std > 1e-9 else 1.0
        return (v - mean) / std, {"strategy": 0.0, "shift": mean, "scale": std}

    def _preprocess(self, matrix: np.ndarray, feature_names: list[str]) -> tuple[np.ndarray, dict[str, dict[str, float]]]:
        plan = self._feature_registry.standardization_plan("contrastive")
        scaled = np.zeros_like(matrix, dtype=float)
        stats: dict[str, dict[str, float]] = {}
        for idx, name in enumerate(feature_names):
            strategy = plan.get(name, "zscore")
            scaled_col, st = self._standardize_column(matrix[:, idx], strategy)
            scaled[:, idx] = scaled_col
            stats[name] = st
        return scaled, stats

    def _build_feature_matrix(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, list[str], dict[str, Any]]:
        pre = model.preprocess_contrastive_data(
            np.asarray(coords, dtype=float),
            np.asarray(values, dtype=float),
            use_training_stats=True,
            augmentation=False,
        )
        matrix = np.asarray(pre["processed_features"], dtype=float)
        names = [str(x) for x in pre["feature_names"]]
        return matrix, names, pre

    def _predict_encoder_response(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        emb = np.asarray(model.encode(np.asarray(coords, dtype=float), np.asarray(values, dtype=float)), dtype=float)
        if emb.ndim != 2 or emb.shape[0] == 0:
            return {"embedding_norm": np.zeros((0,), dtype=float), "embedding_cos_center": np.zeros((0,), dtype=float)}
        norm = np.linalg.norm(emb, axis=1)
        center = np.mean(emb, axis=0, keepdims=True)
        center_norm = np.linalg.norm(center, axis=1).reshape(-1)[0] + 1e-9
        emb_norm = np.linalg.norm(emb, axis=1) + 1e-9
        cos_center = np.sum(emb * center, axis=1) / (emb_norm * center_norm)
        return {"embedding_norm": norm.astype(float), "embedding_cos_center": cos_center.astype(float)}

    def _predict_contrastive_scores(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        bundle = model.anomaly_scores(np.asarray(coords, dtype=float), np.asarray(values, dtype=float))
        return {
            "feature_distance": np.asarray(bundle.get("feature_distance", []), dtype=float),
            "density": np.asarray(bundle.get("density", []), dtype=float),
            "nearest_neighbor": np.asarray(bundle.get("nearest_neighbor", []), dtype=float),
            "bank_similarity": np.asarray(bundle.get("bank_similarity", []), dtype=float),
            "combined": np.asarray(bundle.get("combined", []), dtype=float),
        }

    def _dynamic_lime_samples(self, n_features: int, n_points: int) -> int:
        base = max(80, int(self.config.lime_num_samples))
        return min(1200, base + n_features * 8 + n_points * 2)

    def _top_node_indices(self, scores: np.ndarray, max_explain_nodes: int) -> list[int]:
        n = len(scores)
        explain_count = max(1, min(int(max_explain_nodes), n))
        return np.argsort(-scores)[:explain_count].astype(int).tolist()

    def _select_explained_nodes(self, scores: np.ndarray, max_explain_nodes: int) -> tuple[list[int], float]:
        s = np.asarray(scores, dtype=float).reshape(-1)
        if s.size == 0:
            return [], 0.0
        threshold = float(np.percentile(s, 95))
        anomaly_nodes = np.where(s >= threshold)[0].astype(int).tolist()
        ranked_nodes = self._top_node_indices(s, max_explain_nodes)
        selected: list[int] = []
        for idx in anomaly_nodes + ranked_nodes:
            if idx not in selected:
                selected.append(int(idx))
            if len(selected) >= max(1, int(max_explain_nodes)):
                break
        return selected, threshold

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

        matrix, feature_names, pre_info = self._build_feature_matrix(model=model, coords=coords, values=values)
        scaled_x, scaler_stats = self._preprocess(matrix, feature_names)
        score_bundle = self._predict_contrastive_scores(model=model, coords=coords, values=values)
        encoder_bundle = self._predict_encoder_response(model=model, coords=coords, values=values)
        target = np.asarray(score_bundle["combined"], dtype=float)
        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(scaled_x, target)

        pred_train = surrogate.predict(scaled_x)
        train_rmse = float(np.sqrt(np.mean((pred_train - target) ** 2))) if len(target) else 0.0
        target_std = float(np.std(target)) if len(target) else 0.0
        fidelity = float(max(0.0, 1.0 - train_rmse / (target_std + 1e-6))) if len(target) else 0.0

        context = {
            "context_key": key,
            "feature_matrix": matrix,
            "scaled_x": scaled_x,
            "feature_names": feature_names,
            "scaler_stats": scaler_stats,
            "score_bundle": score_bundle,
            "encoder_bundle": encoder_bundle,
            "target": target,
            "surrogate": surrogate,
            "surrogate_metrics": {"train_rmse": train_rmse, "fidelity": fidelity},
            "preprocess": {
                "batch_slices": pre_info.get("batch_slices", []),
                "validation": pre_info.get("validation", {}),
                "pair_count": len(pre_info.get("positive_pairs", [])),
            },
        }
        self._context_set(key, context)
        return context

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
        explained_nodes, anomaly_threshold = self._select_explained_nodes(target, int(max_explain_nodes or self.config.max_explain_nodes))
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
        batch_explanations: list[dict[str, Any]] = []
        for node_idx in explained_nodes:
            instance = np.asarray(context["scaled_x"][node_idx], dtype=float)
            local_pairs: list[tuple[int, float]]
            local_pred = float(predict_fn(instance.reshape(1, -1))[0])
            fidelity = _safe_float(context["surrogate_metrics"].get("fidelity", 0.5), 0.5)

            if lime_module is not None:
                try:
                    explainer = lime_module.LimeTabularExplainer(
                        training_data=np.asarray(context["scaled_x"], dtype=float),
                        feature_names=feature_names,
                        mode="regression",
                        discretize_continuous=False,
                        random_state=self.config.random_state,
                    )
                    exp = explainer.explain_instance(
                        data_row=instance,
                        predict_fn=predict_fn,
                        num_features=max(1, min(int(top_k), len(feature_names))),
                        num_samples=max(80, selected_samples),
                    )
                    local_map = exp.local_exp.get(1) or exp.local_exp.get(0) or []
                    local_pairs = [(int(i), float(w)) for i, w in local_map]
                    fidelity = _safe_float(getattr(exp, "score", fidelity), fidelity)
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
                    "is_anomaly": bool(target[node_idx] >= anomaly_threshold),
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

        payload = {
            "summary": {
                "method": "lime",
                "explained_nodes": len(explained_nodes),
                "num_samples": selected_samples,
                "num_features": len(feature_names),
                "anomaly_threshold_p95": anomaly_threshold,
                "top_features": [
                    {"feature_index": int(idx), "feature_name": item["feature_name"], "importance": item["importance"]}
                    for idx, item in enumerate(global_feature_importance)
                ],
                "average_confidence": float(np.mean([item["confidence"] for item in batch_explanations])) if batch_explanations else 0.0,
            },
            "feature_importance": raw_importance.astype(float).tolist(),
            "batch_explanations": batch_explanations,
            "global_feature_importance": global_feature_importance,
            "score_components": {
                "feature_distance": np.asarray(context["score_bundle"]["feature_distance"], dtype=float).astype(float).tolist(),
                "density": np.asarray(context["score_bundle"]["density"], dtype=float).astype(float).tolist(),
                "nearest_neighbor": np.asarray(context["score_bundle"]["nearest_neighbor"], dtype=float).astype(float).tolist(),
                "bank_similarity": np.asarray(context["score_bundle"]["bank_similarity"], dtype=float).astype(float).tolist(),
                "combined": target.astype(float).tolist(),
            },
            "encoder_components": {
                "embedding_norm": np.asarray(context["encoder_bundle"]["embedding_norm"], dtype=float).astype(float).tolist(),
                "embedding_cos_center": np.asarray(context["encoder_bundle"]["embedding_cos_center"], dtype=float).astype(float).tolist(),
            },
            "surrogate_metrics": context["surrogate_metrics"],
            "preprocess": context["preprocess"],
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
            },
        }
        self._cache_set(cache_key, payload)
        return payload
