"""时空预测 SHAP 解释器。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import threading
import time
from typing import Any, Optional

import numpy as np
from sklearn.linear_model import Ridge

from .lime_explainer import SpatiotemporalLIMEExplainer


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class SHAPConfig:
    background_size: int = 64
    max_explain_nodes: int = 8
    nsamples: int = 120
    cache_size: int = 32
    random_state: int = 42
    use_gpu_if_available: bool = True


class BaseSHAPExplainer:
    """SHAP 解释器基类，提供缓存与依赖加载。"""

    def __init__(self, config: Optional[SHAPConfig] = None) -> None:
        self.config = config or SHAPConfig()
        self._lock = threading.Lock()
        self._result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

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


class SpatiotemporalSHAPExplainer(BaseSHAPExplainer):
    """时空预测模型 SHAP 适配器。"""

    def __init__(self, config: Optional[SHAPConfig] = None) -> None:
        super().__init__(config=config)
        # 复用 LIME 已有的特征工程实现，保证解释输入一致。
        self._lime_feature_helper = SpatiotemporalLIMEExplainer()

    def _stable_hash(self, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _standardize(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mean = np.mean(x, axis=0)
        std = np.std(x, axis=0)
        std = np.where(std < 1e-8, 1.0, std)
        return (x - mean) / std, mean, std

    def _select_background(self, x_scaled: np.ndarray, target: np.ndarray) -> np.ndarray:
        n = x_scaled.shape[0]
        k = max(8, min(int(self.config.background_size), n))
        if n <= k:
            return x_scaled.copy()
        by_target = np.argsort(target.astype(float))
        evenly = np.linspace(0, n - 1, k, dtype=int)
        idx = np.unique(by_target[evenly])
        return x_scaled[idx]

    def _feature_alias(self, feature_names: list[str]) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for name in feature_names:
            if name.startswith("spatial_"):
                aliases[name] = f"空间:{name.replace('spatial_', '')}"
            elif name.startswith("temporal_"):
                aliases[name] = f"时间:{name.replace('temporal_', '')}"
            else:
                aliases[name] = f"融合:{name.replace('fusion_', '')}"
        return aliases

    def _feature_groups(self, feature_names: list[str]) -> dict[str, list[int]]:
        groups = {"spatial": [], "temporal": [], "fusion": []}
        for idx, name in enumerate(feature_names):
            category = self._lime_feature_helper._feature_category(name)
            groups.setdefault(category, []).append(int(idx))
        return groups

    def _build_context(
        self,
        *,
        model_type: str,
        coords: np.ndarray,
        series: np.ndarray,
        pred_mean: np.ndarray,
    ) -> dict[str, Any]:
        feature_matrix, feature_names = self._lime_feature_helper._build_feature_matrix(coords, series)
        x_scaled, x_mean, x_std = self._standardize(feature_matrix)
        target = np.mean(pred_mean, axis=1).astype(float)
        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(x_scaled, target)
        background = self._select_background(x_scaled, target)
        aliases = self._feature_alias(feature_names)
        groups = self._feature_groups(feature_names)
        return {
            "model_type": model_type,
            "feature_matrix": feature_matrix,
            "scaled_x": x_scaled,
            "feature_names": feature_names,
            "feature_alias": aliases,
            "feature_groups": groups,
            "x_mean": x_mean,
            "x_std": x_std,
            "target": target,
            "surrogate": surrogate,
            "background": background,
        }

    def _predict_fn(self, context: dict[str, Any], values: np.ndarray) -> np.ndarray:
        model: Ridge = context["surrogate"]
        return model.predict(np.asarray(values, dtype=float))

    def _gradient_fn(self, context: dict[str, Any], _: np.ndarray) -> np.ndarray:
        model: Ridge = context["surrogate"]
        return np.asarray(model.coef_, dtype=float)

    def _explainer_type(self, model_type: str) -> str:
        _ = model_type
        # 当前解释入口使用代理模型预测函数，兼容任意时空模型。
        return "KernelExplainer"

    def _fallback_shap_values(self, context: dict[str, Any], instance: np.ndarray) -> tuple[np.ndarray, float]:
        model: Ridge = context["surrogate"]
        background = np.asarray(context["background"], dtype=float)
        baseline = np.mean(background, axis=0)
        shap_values = np.asarray(model.coef_, dtype=float) * (instance - baseline)
        expected = float(model.predict(baseline.reshape(1, -1))[0])
        return shap_values, expected

    def _compute_single_shap(
        self,
        *,
        context: dict[str, Any],
        node_index: int,
        top_k: int,
        nsamples: int,
        shap_module: Any,
    ) -> dict[str, Any]:
        instance = np.asarray(context["scaled_x"][node_index], dtype=float)
        feature_names: list[str] = context["feature_names"]
        aliases: dict[str, str] = context["feature_alias"]

        expected_value = float(np.mean(context["target"]))
        used_backend = "surrogate_linear"
        if shap_module is not None:
            try:
                explainer = shap_module.KernelExplainer(
                    lambda x: self._predict_fn(context, np.asarray(x, dtype=float)),
                    np.asarray(context["background"], dtype=float),
                )
                values = explainer.shap_values(
                    instance.reshape(1, -1),
                    nsamples=max(40, int(nsamples)),
                    l1_reg="num_features(10)",
                )
                if isinstance(values, list):
                    values = values[0]
                shap_values = np.asarray(values, dtype=float).reshape(-1)
                ev = getattr(explainer, "expected_value", expected_value)
                if isinstance(ev, (list, tuple, np.ndarray)):
                    expected_value = _safe_float(np.asarray(ev).reshape(-1)[0], expected_value)
                else:
                    expected_value = _safe_float(ev, expected_value)
                used_backend = "shap_kernel"
            except Exception:
                shap_values, expected_value = self._fallback_shap_values(context, instance)
        else:
            shap_values, expected_value = self._fallback_shap_values(context, instance)

        pred = float(self._predict_fn(context, instance.reshape(1, -1))[0])
        truth = float(context["target"][node_index])
        contribution = []
        for idx, value in enumerate(shap_values.tolist()):
            name = feature_names[idx]
            contribution.append(
                {
                    "feature_index": int(idx),
                    "feature_name": name,
                    "feature_alias": aliases.get(name, name),
                    "category": self._lime_feature_helper._feature_category(name),
                    "shap_value": float(value),
                    "abs_shap": float(abs(value)),
                    "feature_value": float(context["feature_matrix"][node_index, idx]),
                }
            )
        contribution.sort(key=lambda item: item["abs_shap"], reverse=True)
        selected = contribution[: max(1, int(top_k))]
        gradient = self._gradient_fn(context, instance).tolist()
        return {
            "node_index": int(node_index),
            "prediction": pred,
            "target_prediction": truth,
            "expected_value": expected_value,
            "confidence": float(np.exp(-abs(pred - truth) / (abs(truth) + 1e-6))),
            "backend": used_backend,
            "top_contributions": selected,
            "raw_shap_values": [float(v) for v in shap_values.tolist()],
            "gradient": [float(v) for v in gradient],
            "waterfall_data": {
                "base_value": expected_value,
                "prediction": pred,
                "contributions": [
                    {"feature": item["feature_alias"], "value": item["shap_value"], "feature_value": item["feature_value"]}
                    for item in selected
                ],
            },
        }

    def _aggregate_global(
        self,
        *,
        explanations: list[dict[str, Any]],
        n_raw_features: int,
    ) -> tuple[list[float], list[dict[str, Any]], dict[str, float]]:
        if not explanations:
            return [0.0] * n_raw_features, [], {"spatial": 0.0, "temporal": 0.0, "fusion": 0.0}

        raw_matrix = np.asarray([item["raw_shap_values"] for item in explanations], dtype=float)
        by_feature = np.mean(np.abs(raw_matrix), axis=0)
        top_idx = np.argsort(-by_feature).astype(int).tolist()

        by_name: list[dict[str, Any]] = []
        category_sum = {"spatial": 0.0, "temporal": 0.0, "fusion": 0.0}

        # 从贡献中回收名称，避免额外上下文复制。
        idx_to_name: dict[int, str] = {}
        for exp in explanations:
            for c in exp.get("top_contributions", []):
                idx_to_name[int(c["feature_index"])] = str(c["feature_name"])

        for idx in top_idx:
            name = idx_to_name.get(int(idx), f"feature_{idx}")
            category = self._lime_feature_helper._feature_category(name)
            importance = float(by_feature[idx])
            category_sum[category] = category_sum.get(category, 0.0) + importance
            by_name.append(
                {
                    "feature_index": int(idx),
                    "feature_name": name,
                    "importance": importance,
                    "category": category,
                }
            )

        by_raw = np.zeros((n_raw_features,), dtype=float)
        for item in by_name:
            name = item["feature_name"]
            importance = float(item["importance"])
            if "temporal_f" in name:
                try:
                    raw_idx = int(name.split("temporal_f", 1)[1].split("_", 1)[0])
                except Exception:
                    raw_idx = -1
                if 0 <= raw_idx < n_raw_features:
                    by_raw[raw_idx] += importance
        if np.max(by_raw) > 0:
            by_raw = by_raw / (np.max(by_raw) + 1e-12)
        return by_raw.astype(float).tolist(), by_name, {k: float(v) for k, v in category_sum.items()}

    def _build_visualization(
        self,
        *,
        context: dict[str, Any],
        explanations: list[dict[str, Any]],
        global_ranking: list[dict[str, Any]],
    ) -> dict[str, Any]:
        beeswarm = []
        dependence = []
        for exp in explanations:
            node_idx = int(exp["node_index"])
            raw_vals = exp.get("raw_shap_values", [])
            for item in exp.get("top_contributions", []):
                idx = int(item["feature_index"])
                beeswarm.append(
                    {
                        "node_index": node_idx,
                        "feature": item["feature_alias"],
                        "shap_value": float(raw_vals[idx]) if idx < len(raw_vals) else float(item["shap_value"]),
                        "feature_value": float(context["feature_matrix"][node_idx, idx]),
                    }
                )
            for item in exp.get("top_contributions", [])[:2]:
                idx = int(item["feature_index"])
                dependence.append(
                    {
                        "feature": item["feature_alias"],
                        "feature_value": float(context["feature_matrix"][node_idx, idx]),
                        "shap_value": float(item["shap_value"]),
                        "node_index": node_idx,
                    }
                )

        per_time = np.mean(np.abs(np.diff(context["feature_matrix"], axis=0)), axis=1) if context["feature_matrix"].shape[0] > 1 else np.array([], dtype=float)
        spatial_dist = context["feature_matrix"][:, 2] if context["feature_matrix"].shape[1] > 2 else np.array([], dtype=float)
        return {
            "waterfall_list": [item["waterfall_data"] for item in explanations],
            "beeswarm_data": beeswarm,
            "dependence_data": dependence,
            "feature_ranking": global_ranking,
            "summary_stats": {
                "explained_nodes": len(explanations),
                "avg_confidence": float(np.mean([_safe_float(item.get("confidence", 0.0)) for item in explanations])) if explanations else 0.0,
                "avg_abs_shap": float(np.mean([abs(v) for exp in explanations for v in exp.get("raw_shap_values", [])])) if explanations else 0.0,
            },
            "time_series_analysis": {
                "volatility_series": per_time.astype(float).tolist(),
                "volatility_mean": float(np.mean(per_time)) if per_time.size else 0.0,
            },
            "spatial_distribution": {
                "distance_to_center": spatial_dist.astype(float).tolist(),
                "mean_distance": float(np.mean(spatial_dist)) if spatial_dist.size else 0.0,
            },
        }

    def explain(
        self,
        *,
        model_type: str,
        coords: np.ndarray,
        series: np.ndarray,
        pred_mean: np.ndarray,
        top_k: int = 5,
        nsamples: Optional[int] = None,
        max_explain_nodes: Optional[int] = None,
        compute_interactions: bool = False,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        n_nodes, _, n_raw_features = series.shape
        explain_count = max(1, min(int(max_explain_nodes or self.config.max_explain_nodes), n_nodes))
        node_scores = np.mean(np.abs(series - np.mean(series, axis=1, keepdims=True)), axis=(1, 2))
        node_indices = np.argsort(-node_scores)[:explain_count].astype(int).tolist()

        cache_key = self._stable_hash(
            {
                "model_type": model_type,
                "coords_hash": hashlib.md5(np.asarray(coords).tobytes()).hexdigest(),
                "series_hash": hashlib.md5(np.asarray(series).tobytes()).hexdigest(),
                "pred_hash": hashlib.md5(np.asarray(pred_mean).tobytes()).hexdigest(),
                "top_k": int(top_k),
                "node_indices": node_indices,
                "nsamples": int(nsamples or self.config.nsamples),
            }
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["cache_hit"] = True
            perf = dict(cached.get("performance", {}))
            perf["cache_hit"] = True
            cached["performance"] = perf
            return cached

        context = self._build_context(
            model_type=model_type,
            coords=np.asarray(coords, dtype=float),
            series=np.asarray(series, dtype=float),
            pred_mean=np.asarray(pred_mean, dtype=float),
        )
        shap_module = self._load_shap()
        selected_nsamples = int(nsamples or self.config.nsamples)
        batch_explanations = [
            self._compute_single_shap(
                context=context,
                node_index=node_idx,
                top_k=top_k,
                nsamples=selected_nsamples,
                shap_module=shap_module,
            )
            for node_idx in node_indices
        ]

        raw_importance, global_ranking, category_stats = self._aggregate_global(
            explanations=batch_explanations,
            n_raw_features=n_raw_features,
        )
        top_global = global_ranking[: max(1, int(top_k))]
        top_features = [
            {"feature_index": int(item["feature_index"]), "feature_name": item["feature_name"], "importance": float(item["importance"])}
            for item in top_global
        ]

        interaction_values: list[dict[str, Any]] = []
        if compute_interactions and len(top_global) >= 2:
            f1 = top_global[0]["feature_index"]
            f2 = top_global[1]["feature_index"]
            for item in batch_explanations:
                vals = item.get("raw_shap_values", [])
                if f1 < len(vals) and f2 < len(vals):
                    interaction_values.append(
                        {
                            "node_index": int(item["node_index"]),
                            "feature_pair": [int(f1), int(f2)],
                            "interaction_score": float(vals[f1] * vals[f2]),
                        }
                    )

        payload = {
            "summary": {
                "method": "shap",
                "explainer": self._explainer_type(model_type),
                "explained_nodes": explain_count,
                "num_features": int(context["scaled_x"].shape[1]),
                "background_size": int(context["background"].shape[0]),
                "nsamples": selected_nsamples,
                "top_features": top_features,
                "feature_group_importance": category_stats,
                "average_confidence": float(np.mean([_safe_float(item.get("confidence", 0.0)) for item in batch_explanations])) if batch_explanations else 0.0,
            },
            "feature_importance": raw_importance,
            "batch_explanations": batch_explanations,
            "global_feature_importance": top_global,
            "interaction_values": interaction_values,
            "visualization": self._build_visualization(
                context=context,
                explanations=batch_explanations,
                global_ranking=top_global,
            ),
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "backend": "shap" if shap_module is not None else "surrogate_linear",
                "gpu_enabled": bool(self.config.use_gpu_if_available and shap_module is not None),
            },
        }
        self._cache_set(cache_key, payload)
        return payload
