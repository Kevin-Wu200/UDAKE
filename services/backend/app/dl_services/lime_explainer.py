"""时空预测 LIME 解释器。"""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import math
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
class LIMEConfig:
    num_samples: int = 240
    num_features: int = 8
    random_state: int = 42
    max_workers: int = 4
    cache_size: int = 32


class BaseLIMEExplainer:
    """LIME 解释器基类，提供缓存和公共工具。"""

    def __init__(self, config: Optional[LIMEConfig] = None) -> None:
        self.config = config or LIMEConfig()
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


class SpatiotemporalLIMEExplainer(BaseLIMEExplainer):
    """时空预测模型 LIME 适配器。"""

    def _stable_hash(self, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _dynamic_num_samples(self, n_features: int, n_nodes: int) -> int:
        base = max(80, int(self.config.num_samples))
        adaptive = min(1200, base + n_features * 12 + n_nodes * 3)
        return adaptive

    def _build_feature_names(self, seq_len: int, n_raw_features: int) -> list[str]:
        names = ["spatial_lon", "spatial_lat", "spatial_dist_center", "spatial_neighbor_density"]
        for feature_idx in range(n_raw_features):
            names.extend(
                [
                    f"temporal_f{feature_idx}_latest",
                    f"temporal_f{feature_idx}_mean",
                    f"temporal_f{feature_idx}_std",
                    f"temporal_f{feature_idx}_trend",
                    f"temporal_f{feature_idx}_periodicity",
                ]
            )
        for feature_idx in range(n_raw_features):
            names.extend(
                [
                    f"fusion_f{feature_idx}_space_mean",
                    f"fusion_f{feature_idx}_space_trend",
                ]
            )
        names.extend(["fusion_xy_cross", f"fusion_seq_len_{seq_len}"])
        return names

    def _feature_category(self, name: str) -> str:
        if name.startswith("spatial_"):
            return "spatial"
        if name.startswith("temporal_"):
            return "temporal"
        return "fusion"

    def _extract_spatial_features(self, coords: np.ndarray) -> np.ndarray:
        center = np.mean(coords, axis=0, keepdims=True)
        dist = np.linalg.norm(coords - center, axis=1)
        n_nodes = int(coords.shape[0])
        if n_nodes < 2:
            density = np.ones((n_nodes,), dtype=float)
        else:
            diff = coords[:, None, :] - coords[None, :, :]
            pair_dist = np.linalg.norm(diff, axis=2)
            pair_dist = pair_dist + np.eye(n_nodes) * 1e9
            k = min(3, n_nodes - 1)
            knn = np.sort(pair_dist, axis=1)[:, :k]
            density = 1.0 / (np.mean(knn, axis=1) + 1e-6)
        return np.column_stack((coords[:, 0], coords[:, 1], dist, density))

    def _extract_temporal_features(self, series: np.ndarray) -> np.ndarray:
        n_nodes, seq_len, n_features = series.shape
        out = np.zeros((n_nodes, n_features * 5), dtype=float)
        for f_idx in range(n_features):
            values = series[:, :, f_idx]
            latest = values[:, -1]
            mean = np.mean(values, axis=1)
            std = np.std(values, axis=1)
            trend = values[:, -1] - values[:, 0]
            periodicity = np.mean(np.abs(np.diff(values, axis=1)), axis=1) if seq_len > 1 else np.zeros((n_nodes,), dtype=float)
            offset = f_idx * 5
            out[:, offset:offset + 5] = np.column_stack((latest, mean, std, trend, periodicity))
        return out

    def _extract_fusion_features(self, coords: np.ndarray, series: np.ndarray, spatial_features: np.ndarray) -> np.ndarray:
        n_nodes, _, n_features = series.shape
        dist = spatial_features[:, 2]
        out = np.zeros((n_nodes, n_features * 2 + 2), dtype=float)
        for f_idx in range(n_features):
            values = series[:, :, f_idx]
            mean = np.mean(values, axis=1)
            trend = values[:, -1] - values[:, 0]
            offset = f_idx * 2
            out[:, offset:offset + 2] = np.column_stack((dist * mean, dist * trend))
        out[:, -2] = coords[:, 0] * coords[:, 1]
        out[:, -1] = float(series.shape[1])
        return out

    def _build_feature_matrix(self, coords: np.ndarray, series: np.ndarray) -> tuple[np.ndarray, list[str]]:
        spatial = self._extract_spatial_features(coords)
        temporal = self._extract_temporal_features(series)
        fusion = self._extract_fusion_features(coords, series, spatial)
        matrix = np.concatenate((spatial, temporal, fusion), axis=1)
        names = self._build_feature_names(seq_len=int(series.shape[1]), n_raw_features=int(series.shape[2]))
        return matrix, names

    def _standardize(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mean = np.mean(x, axis=0)
        std = np.std(x, axis=0)
        std = np.where(std < 1e-8, 1.0, std)
        return (x - mean) / std, mean, std

    def _build_context(
        self,
        *,
        model_type: str,
        coords: np.ndarray,
        series: np.ndarray,
        pred_mean: np.ndarray,
    ) -> dict[str, Any]:
        key = self._stable_hash(
            {
                "model_type": model_type,
                "coords_shape": list(coords.shape),
                "series_shape": list(series.shape),
                "coords_mean": np.mean(coords, axis=0).round(6).tolist(),
                "series_mean": _safe_float(np.mean(series)),
            }
        )
        cached = self._context_get(key)
        if cached is not None:
            return cached

        feature_matrix, feature_names = self._build_feature_matrix(coords, series)
        scaled_x, scaler_mean, scaler_std = self._standardize(feature_matrix)
        target = np.mean(pred_mean, axis=1).astype(float)
        model = Ridge(alpha=1.0)
        model.fit(scaled_x, target)

        context = {
            "key": key,
            "feature_matrix": feature_matrix,
            "scaled_x": scaled_x,
            "feature_names": feature_names,
            "scaler_mean": scaler_mean,
            "scaler_std": scaler_std,
            "target": target,
            "surrogate": model,
        }
        self._context_set(key, context)
        return context

    def _predict_surrogate(self, context: dict[str, Any]) -> Callable[[np.ndarray], np.ndarray]:
        model: Ridge = context["surrogate"]
        return lambda x: model.predict(np.asarray(x, dtype=float))

    def _fallback_local_weights(
        self,
        context: dict[str, Any],
        instance_scaled: np.ndarray,
    ) -> tuple[list[tuple[int, float]], float, float]:
        model: Ridge = context["surrogate"]
        coef = np.asarray(model.coef_, dtype=float)
        local = coef * instance_scaled
        pairs = [(idx, float(local[idx])) for idx in range(local.shape[0])]
        predicted = float(model.predict(instance_scaled.reshape(1, -1))[0])
        return pairs, 0.5, predicted

    def _compute_confidence(self, *, fidelity: float, predicted: float, true_value: float) -> float:
        err_ratio = abs(predicted - true_value) / (abs(true_value) + 1e-6)
        penalty = math.exp(-err_ratio)
        score = max(0.0, min(1.0, fidelity)) * penalty
        return float(max(0.0, min(1.0, score)))

    def _format_single(
        self,
        *,
        node_index: int,
        context: dict[str, Any],
        local_pairs: list[tuple[int, float]],
        fidelity: float,
        local_pred: float,
        top_k: int,
    ) -> dict[str, Any]:
        feature_names: list[str] = context["feature_names"]
        truth = float(context["target"][node_index])
        contribution = [
            {
                "feature_index": int(idx),
                "feature_name": feature_names[idx],
                "category": self._feature_category(feature_names[idx]),
                "weight": float(weight),
                "abs_weight": float(abs(weight)),
                "direction": "positive" if weight >= 0 else "negative",
            }
            for idx, weight in local_pairs
        ]
        contribution.sort(key=lambda x: x["abs_weight"], reverse=True)
        selected = contribution[: max(1, int(top_k))]
        confidence = self._compute_confidence(fidelity=fidelity, predicted=local_pred, true_value=truth)
        return {
            "node_index": int(node_index),
            "confidence": confidence,
            "fidelity": float(max(0.0, min(1.0, fidelity))),
            "prediction": local_pred,
            "target_prediction": truth,
            "top_contributions": selected,
            "local_plot_data": {
                "base_value": float(np.mean(context["target"])),
                "prediction": local_pred,
                "contributions": [
                    {"feature": item["feature_name"], "weight": item["weight"], "direction": item["direction"]}
                    for item in selected
                ],
            },
        }

    def _explain_single(self, *, node_index: int, context: dict[str, Any], top_k: int, num_samples: int) -> dict[str, Any]:
        feature_names: list[str] = context["feature_names"]
        instance = np.asarray(context["scaled_x"][node_index], dtype=float)
        predict_fn = self._predict_surrogate(context)
        lime_tabular = self._load_lime_tabular()
        local_pairs: list[tuple[int, float]]
        fidelity = 0.5
        local_pred = float(predict_fn(instance.reshape(1, -1))[0])

        if lime_tabular is not None:
            explainer = lime_tabular.LimeTabularExplainer(
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
                num_samples=max(80, int(num_samples)),
            )
            local_exp_map = exp.local_exp.get(1) or exp.local_exp.get(0) or []
            local_pairs = [(int(idx), float(weight)) for idx, weight in local_exp_map]
            fidelity = _safe_float(getattr(exp, "score", 0.5), default=0.5)
            local_pred_values = getattr(exp, "local_pred", None)
            if isinstance(local_pred_values, (list, tuple, np.ndarray)) and len(local_pred_values) > 0:
                local_pred = _safe_float(local_pred_values[0], default=local_pred)
        else:
            local_pairs, fidelity, local_pred = self._fallback_local_weights(context, instance)

        return self._format_single(
            node_index=node_index,
            context=context,
            local_pairs=local_pairs,
            fidelity=fidelity,
            local_pred=local_pred,
            top_k=top_k,
        )

    def _aggregate_feature_importance(
        self,
        explanations: list[dict[str, Any]],
        n_raw_features: int,
    ) -> tuple[list[float], list[dict[str, Any]]]:
        by_raw = np.zeros((n_raw_features,), dtype=float)
        by_name: dict[str, float] = {}
        for item in explanations:
            for contrib in item.get("top_contributions", []):
                name = str(contrib.get("feature_name", ""))
                weight = abs(float(contrib.get("weight", 0.0)))
                by_name[name] = by_name.get(name, 0.0) + weight
                if "temporal_f" in name:
                    try:
                        raw_idx = int(name.split("temporal_f", 1)[1].split("_", 1)[0])
                    except Exception:
                        raw_idx = -1
                    if 0 <= raw_idx < n_raw_features:
                        by_raw[raw_idx] += weight
        if np.max(by_raw) > 0:
            by_raw = by_raw / (np.max(by_raw) + 1e-12)

        ranked = sorted(by_name.items(), key=lambda kv: kv[1], reverse=True)
        global_items = [
            {
                "feature_name": name,
                "importance": float(weight / max(1, len(explanations))),
                "category": self._feature_category(name),
            }
            for name, weight in ranked
        ]
        return by_raw.astype(float).tolist(), global_items

    def _summary_text(self, explanations: list[dict[str, Any]], top_features: list[dict[str, Any]]) -> str:
        if not explanations:
            return "本次LIME解释未产出有效结果。"
        conf = float(np.mean([_safe_float(item.get("confidence", 0.0)) for item in explanations]))
        feature_names = [str(item.get("feature_name", "")) for item in top_features[:3]]
        joined = "、".join([name for name in feature_names if name]) or "无"
        return f"平均解释置信度为 {conf:.3f}，主要影响特征为：{joined}。"

    def explain(
        self,
        *,
        model_type: str,
        coords: np.ndarray,
        series: np.ndarray,
        pred_mean: np.ndarray,
        top_k: int = 5,
        num_samples: Optional[int] = None,
        max_explain_nodes: int = 8,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        n_nodes, _, n_raw_features = series.shape
        node_scores = np.mean(np.abs(series - np.mean(series, axis=1, keepdims=True)), axis=(1, 2))
        explain_count = max(1, min(int(max_explain_nodes), n_nodes))
        node_indices = np.argsort(-node_scores)[:explain_count].astype(int).tolist()

        cache_key = self._stable_hash(
            {
                "model_type": model_type,
                "coords_hash": hashlib.md5(np.asarray(coords).tobytes()).hexdigest(),
                "series_hash": hashlib.md5(np.asarray(series).tobytes()).hexdigest(),
                "pred_hash": hashlib.md5(np.asarray(pred_mean).tobytes()).hexdigest(),
                "top_k": int(top_k),
                "nodes": node_indices,
            }
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["cache_hit"] = True
            performance = dict(cached.get("performance", {}))
            performance["cache_hit"] = True
            cached["performance"] = performance
            return cached

        context = self._build_context(model_type=model_type, coords=coords, series=series, pred_mean=pred_mean)
        samples = int(num_samples or self._dynamic_num_samples(context["scaled_x"].shape[1], n_nodes))

        max_workers = max(1, min(self.config.max_workers, explain_count))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="lime-explain") as pool:
            futures = [
                pool.submit(
                    self._explain_single,
                    node_index=node_idx,
                    context=context,
                    top_k=top_k,
                    num_samples=samples,
                )
                for node_idx in node_indices
            ]
            batch_explanations = [future.result() for future in futures]

        feature_importance, global_feature_list = self._aggregate_feature_importance(batch_explanations, n_raw_features=n_raw_features)
        top_global = global_feature_list[: max(1, int(top_k))]
        top_features = [
            {"feature_index": idx, "feature_name": item["feature_name"], "importance": item["importance"]}
            for idx, item in enumerate(top_global)
        ]
        avg_confidence = float(np.mean([_safe_float(item.get("confidence", 0.0)) for item in batch_explanations]))

        payload = {
            "summary": {
                "method": "lime",
                "top_features": top_features,
                "explained_nodes": explain_count,
                "num_samples": samples,
                "num_features": context["scaled_x"].shape[1],
                "average_confidence": avg_confidence,
            },
            "feature_importance": feature_importance,
            "batch_explanations": batch_explanations,
            "global_feature_importance": top_global,
            "visualization": {
                "feature_importance_list": top_global,
                "local_explanations": [item["local_plot_data"] for item in batch_explanations],
                "feature_contributions": [
                    {
                        "node_index": item["node_index"],
                        "contributions": item["top_contributions"],
                    }
                    for item in batch_explanations
                ],
                "summary_text": self._summary_text(batch_explanations, top_global),
            },
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "parallel_workers": max_workers,
                "cache_hit": False,
            },
        }
        self._cache_set(cache_key, payload)
        return payload
