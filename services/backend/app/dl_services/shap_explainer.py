"""时空预测 SHAP 解释器。"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
from sklearn.linear_model import Ridge

from .lime_explainer import SpatiotemporalLIMEExplainer
from .parallel_runtime import ParallelExecutionManager, ParallelTask


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class SHAPConfig:
    background_size: int = 64
    min_background_size: int = 16
    max_background_size: int = 128
    max_explain_nodes: int = 8
    nsamples: int = 120
    cache_size: int = 32
    background_cache_size: int = 16
    background_update_interval_seconds: int = 300
    background_drift_threshold: float = 0.12
    random_state: int = 42
    use_gpu_if_available: bool = True
    max_workers: int = 4
    min_parallel_workers: int = 1


class BaseSHAPExplainer:
    """SHAP 解释器基类，提供缓存与依赖加载。"""

    def __init__(self, config: Optional[SHAPConfig] = None) -> None:
        self.config = config or SHAPConfig()
        self._lock = threading.Lock()
        self._result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._background_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._background_cache_hits = 0
        self._background_cache_misses = 0
        self._parallel = ParallelExecutionManager(
            name="shap",
            max_workers=max(1, int(self.config.max_workers)),
            min_workers=max(1, int(self.config.min_parallel_workers)),
        )

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

    def _background_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            item = self._background_cache.get(key)
            if item is None:
                self._background_cache_misses += 1
                return None
            self._background_cache_hits += 1
            self._background_cache.move_to_end(key)
            return item

    def _background_set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._background_cache[key] = value
            self._background_cache.move_to_end(key)
            max_size = max(1, int(self.config.background_cache_size))
            while len(self._background_cache) > max_size:
                self._background_cache.popitem(last=False)

    def _background_cache_stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._background_cache_hits + self._background_cache_misses
            hit_rate = float(self._background_cache_hits / total) if total > 0 else 0.0
            return {
                "entries": int(len(self._background_cache)),
                "hits": int(self._background_cache_hits),
                "misses": int(self._background_cache_misses),
                "hit_rate": hit_rate,
            }


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

    def _estimate_background_size(self, x_scaled: np.ndarray, target: np.ndarray, explain_count: int) -> int:
        n = int(x_scaled.shape[0])
        min_k = max(8, int(self.config.min_background_size))
        max_k = max(min_k, int(self.config.max_background_size))
        base = max(int(self.config.background_size), min_k)

        target_std = float(np.std(target))
        feature_dispersion = float(np.mean(np.std(x_scaled, axis=0)))
        complexity = min(1.0, 0.55 * target_std + 0.45 * feature_dispersion)
        node_factor = min(1.0, float(max(1, explain_count)) / max(1.0, float(n)))
        scaled = int(round(base * (0.85 + 0.45 * complexity + 0.25 * node_factor)))
        return int(max(min_k, min(max_k, min(n, scaled))))

    def _dynamic_background_pool(
        self,
        *,
        x_scaled: np.ndarray,
        target: np.ndarray,
        node_indices: list[int],
        pool_size: int,
    ) -> np.ndarray:
        n = int(x_scaled.shape[0])
        if n <= pool_size:
            return np.arange(n, dtype=int)
        if not node_indices:
            node_indices = [0]

        focus = x_scaled[np.asarray(node_indices, dtype=int)]
        focus_center = np.mean(focus, axis=0)
        focus_dist = np.linalg.norm(x_scaled - focus_center.reshape(1, -1), axis=1)
        focus_dist = focus_dist / (np.max(focus_dist) + 1e-8)

        target_center = float(np.mean(target[np.asarray(node_indices, dtype=int)]))
        target_dev = np.abs(target - target_center)
        target_dev = target_dev / (np.max(target_dev) + 1e-8)

        score = 0.6 * focus_dist + 0.4 * target_dev
        score[np.asarray(node_indices, dtype=int)] = 2.0
        selected = np.argsort(-score)[:pool_size].astype(int)
        return np.unique(selected)

    def _select_diverse_indices(self, x_values: np.ndarray, size: int, seed_indices: np.ndarray) -> np.ndarray:
        n = int(x_values.shape[0])
        if n <= size:
            return np.arange(n, dtype=int)
        if seed_indices.size == 0:
            seed_indices = np.asarray([0], dtype=int)

        chosen: list[int] = [int(seed_indices[0])]
        if n > 1:
            dist_to_seed = np.linalg.norm(x_values - x_values[chosen[0]].reshape(1, -1), axis=1)
            chosen.append(int(np.argmax(dist_to_seed)))

        while len(chosen) < size:
            chosen_arr = np.asarray(chosen, dtype=int)
            centers = x_values[chosen_arr]
            min_dist = np.min(np.linalg.norm(x_values[:, None, :] - centers[None, :, :], axis=2), axis=1)
            min_dist[chosen_arr] = -1.0
            next_idx = int(np.argmax(min_dist))
            if next_idx in chosen:
                break
            chosen.append(next_idx)
        return np.asarray(chosen[:size], dtype=int)

    def _select_background(
        self,
        *,
        x_scaled: np.ndarray,
        target: np.ndarray,
        node_indices: list[int],
        background_size: int,
    ) -> np.ndarray:
        n = int(x_scaled.shape[0])
        k = max(8, min(int(background_size), n))
        if n <= k:
            return x_scaled.copy()

        pool_size = max(k * 3, min(n, k + max(12, int(np.sqrt(n)))))
        pool_indices = self._dynamic_background_pool(
            x_scaled=x_scaled,
            target=target,
            node_indices=node_indices,
            pool_size=pool_size,
        )
        x_pool = x_scaled[pool_indices]
        target_pool = target[pool_indices]

        by_target = np.argsort(target_pool.astype(float))
        strata = np.linspace(0, len(by_target) - 1, max(k, min(len(by_target), k * 2)), dtype=int)
        stratified = np.unique(by_target[strata]).astype(int)
        diverse = self._select_diverse_indices(x_pool, size=k, seed_indices=stratified)
        chosen = np.unique(diverse).astype(int)
        if len(chosen) < k:
            fill = np.setdiff1d(np.arange(len(pool_indices), dtype=int), chosen, assume_unique=False)
            chosen = np.concatenate((chosen, fill[: max(0, k - len(chosen))]))
        return x_pool[np.asarray(chosen[:k], dtype=int)]

    def _evaluate_background_quality(
        self,
        *,
        x_scaled: np.ndarray,
        target: np.ndarray,
        background: np.ndarray,
        node_indices: list[int],
    ) -> dict[str, float]:
        if background.size == 0:
            return {"coverage": 0.0, "diversity": 0.0, "target_balance": 0.0, "local_focus": 0.0, "overall": 0.0}

        dist = np.linalg.norm(x_scaled[:, None, :] - background[None, :, :], axis=2)
        coverage = float(1.0 / (1.0 + np.mean(np.min(dist, axis=1))))

        if background.shape[0] > 1:
            pair = np.linalg.norm(background[:, None, :] - background[None, :, :], axis=2)
            diversity = float(np.mean(pair[np.triu_indices(background.shape[0], k=1)]))
            diversity = float(diversity / (1.0 + diversity))
        else:
            diversity = 0.0

        bins = np.linspace(float(np.min(target)), float(np.max(target)) + 1e-12, 6)
        hist_all, _ = np.histogram(target, bins=bins)
        nearest = np.argmin(dist, axis=0)
        bg_target = target[nearest]
        hist_bg, _ = np.histogram(bg_target, bins=bins)
        p_all = hist_all / (np.sum(hist_all) + 1e-8)
        p_bg = hist_bg / (np.sum(hist_bg) + 1e-8)
        target_balance = float(max(0.0, 1.0 - 0.5 * np.sum(np.abs(p_all - p_bg))))

        if node_indices:
            focus_center = np.mean(x_scaled[np.asarray(node_indices, dtype=int)], axis=0, keepdims=True)
            local_focus = float(1.0 / (1.0 + np.mean(np.linalg.norm(background - focus_center, axis=1))))
        else:
            local_focus = coverage

        overall = 0.3 * coverage + 0.25 * diversity + 0.2 * target_balance + 0.25 * local_focus
        return {
            "coverage": float(max(0.0, min(1.0, coverage))),
            "diversity": float(max(0.0, min(1.0, diversity))),
            "target_balance": float(max(0.0, min(1.0, target_balance))),
            "local_focus": float(max(0.0, min(1.0, local_focus))),
            "overall": float(max(0.0, min(1.0, overall))),
        }

    def _analyze_background_size_impact(
        self,
        *,
        x_scaled: np.ndarray,
        target: np.ndarray,
        node_indices: list[int],
    ) -> list[dict[str, Any]]:
        n = int(x_scaled.shape[0])
        if n == 0:
            return []
        sizes = sorted(
            {
                max(8, min(n, int(self.config.min_background_size))),
                max(8, min(n, int(self.config.background_size))),
                max(8, min(n, int(self.config.max_background_size))),
            }
        )
        analysis: list[dict[str, Any]] = []
        for size in sizes:
            bg = self._select_background(
                x_scaled=x_scaled,
                target=target,
                node_indices=node_indices,
                background_size=size,
            )
            quality = self._evaluate_background_quality(
                x_scaled=x_scaled,
                target=target,
                background=bg,
                node_indices=node_indices,
            )
            analysis.append(
                {
                    "size": int(size),
                    "quality_score": float(quality["overall"]),
                    "coverage": float(quality["coverage"]),
                    "diversity": float(quality["diversity"]),
                }
            )
        return analysis

    def _build_background_key(self, *, model_type: str, x_scaled: np.ndarray, target: np.ndarray) -> str:
        payload = {
            "model_type": model_type,
            "x_shape": list(x_scaled.shape),
            "target_shape": list(target.shape),
            "x_hash": hashlib.md5(np.asarray(x_scaled, dtype=float).tobytes()).hexdigest(),
        }
        return self._stable_hash(payload)

    def _should_refresh_background(
        self,
        cached_item: Optional[dict[str, Any]],
        *,
        target: np.ndarray,
        background_size: int,
    ) -> bool:
        if cached_item is None:
            return True
        cached_bg = np.asarray(cached_item.get("background", np.zeros((0, 0), dtype=float)), dtype=float)
        if cached_bg.shape[0] != int(background_size):
            return True
        now = time.time()
        updated_at = _safe_float(cached_item.get("updated_at", 0.0), 0.0)
        if now - updated_at >= float(self.config.background_update_interval_seconds):
            return True
        ref_mean = _safe_float(cached_item.get("target_mean", 0.0), 0.0)
        ref_std = _safe_float(cached_item.get("target_std", 1.0), 1.0)
        cur_mean = float(np.mean(target))
        cur_std = float(np.std(target))
        drift = abs(cur_mean - ref_mean) / (abs(ref_std) + 1e-6) + abs(cur_std - ref_std) / (abs(ref_std) + 1e-6)
        return bool(drift >= float(self.config.background_drift_threshold))

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
        node_indices: list[int],
    ) -> dict[str, Any]:
        feature_matrix, feature_names = self._lime_feature_helper._build_feature_matrix(coords, series)
        x_scaled, x_mean, x_std = self._standardize(feature_matrix)
        target = np.mean(pred_mean, axis=1).astype(float)
        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(x_scaled, target)

        dynamic_bg_size = self._estimate_background_size(x_scaled, target, explain_count=len(node_indices))
        background_key = self._build_background_key(model_type=model_type, x_scaled=x_scaled, target=target)
        cached_bg = self._background_get(background_key)
        refresh = self._should_refresh_background(cached_bg, target=target, background_size=dynamic_bg_size)
        if refresh:
            background = self._select_background(
                x_scaled=x_scaled,
                target=target,
                node_indices=node_indices,
                background_size=dynamic_bg_size,
            )
            self._background_set(
                background_key,
                {
                    "background": background,
                    "target_mean": float(np.mean(target)),
                    "target_std": float(np.std(target)),
                    "updated_at": time.time(),
                },
            )
            background_cache_hit = False
            update_reason = "new_or_refreshed"
        else:
            background = np.asarray(cached_bg["background"], dtype=float)
            background_cache_hit = True
            update_reason = "cache_reuse"

        background_quality = self._evaluate_background_quality(
            x_scaled=x_scaled,
            target=target,
            background=background,
            node_indices=node_indices,
        )
        size_impact = self._analyze_background_size_impact(
            x_scaled=x_scaled,
            target=target,
            node_indices=node_indices,
        )
        size_scores = {int(item["size"]): float(item["quality_score"]) for item in size_impact}
        recommended = max(size_scores, key=size_scores.get) if size_scores else int(background.shape[0])

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
            "background_info": {
                "dynamic_size": int(dynamic_bg_size),
                "selected_size": int(background.shape[0]),
                "recommended_size": int(recommended),
                "cache_hit": bool(background_cache_hit),
                "update_reason": update_reason,
                "quality": background_quality,
                "size_impact": size_impact,
                "cache_stats": self._background_cache_stats(),
            },
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
            node_indices=node_indices,
        )
        shap_module = self._load_shap()
        selected_nsamples = int(nsamples or self.config.nsamples)
        tasks = [
            ParallelTask(
                task_id=f"shap-node-{node_idx}",
                priority=max(0, int(rank)),
                payload={
                    "node_index": int(node_idx),
                    "top_k": int(top_k),
                    "nsamples": int(selected_nsamples),
                },
            )
            for rank, node_idx in enumerate(node_indices)
        ]
        batch_explanations, run_report = self._parallel.run_tasks(
            tasks=tasks,
            task_type="cpu",
            worker_fn=lambda payload: self._compute_single_shap(
                context=context,
                node_index=int(payload["node_index"]),
                top_k=int(payload["top_k"]),
                nsamples=int(payload["nsamples"]),
                shap_module=shap_module,
            ),
        )

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
                "background_recommended_size": int(context["background_info"]["recommended_size"]),
                "background_quality_score": float(context["background_info"]["quality"]["overall"]),
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
                "background_cache_hit": bool(context["background_info"]["cache_hit"]),
                "background_update_reason": str(context["background_info"]["update_reason"]),
                "background_size_impact": context["background_info"]["size_impact"],
                "background_quality": context["background_info"]["quality"],
                "background_cache_stats": context["background_info"]["cache_stats"],
                "parallel_workers": int(run_report.workers),
                "parallel_report": {
                    "task_count": int(run_report.task_count),
                    "queue_peak": int(run_report.queue_peak),
                    "wait_ms_avg": float(run_report.wait_ms_avg),
                    "exec_ms_avg": float(run_report.exec_ms_avg),
                    "failed_tasks": int(run_report.failed_tasks),
                    "task_type": run_report.task_type,
                },
                "parallel_monitor": self._parallel.snapshot(),
            },
        }
        self._cache_set(cache_key, payload)
        return payload
