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
        self._result_cache_hits = 0
        self._result_cache_misses = 0
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

    def _cache_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            item = self._result_cache.get(key)
            if item is None:
                self._result_cache_misses += 1
                return None
            self._result_cache_hits += 1
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
                self._context_cache_misses += 1
                return None
            self._context_cache_hits += 1
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

    def _cache_metrics(self) -> dict[str, float | int]:
        with self._lock:
            result_total = self._result_cache_hits + self._result_cache_misses
            context_total = self._context_cache_hits + self._context_cache_misses
            return {
                "result_cache_hits": int(self._result_cache_hits),
                "result_cache_misses": int(self._result_cache_misses),
                "result_cache_hit_rate": float(self._result_cache_hits / max(1, result_total)),
                "context_cache_hits": int(self._context_cache_hits),
                "context_cache_misses": int(self._context_cache_misses),
                "context_cache_hit_rate": float(self._context_cache_hits / max(1, context_total)),
            }

    @staticmethod
    def _array_nbytes(value: Any) -> int:
        try:
            arr = np.asarray(value)
            return int(arr.nbytes)
        except Exception:
            return 0

    def _context_memory_bytes(self, context: dict[str, Any]) -> int:
        total = 0
        total += self._array_nbytes(context.get("feature_matrix"))
        total += self._array_nbytes(context.get("scaled_x"))
        total += self._array_nbytes(context.get("prediction"))
        total += self._array_nbytes(context.get("uncertainty"))
        total += self._array_nbytes(context.get("attention_mean_weight"))
        total += self._array_nbytes(context.get("background"))
        return int(total)

    def _top_node_indices(self, uncertainty: np.ndarray, max_explain_nodes: int) -> list[int]:
        n = int(len(uncertainty))
        if n <= 0:
            return []
        explain_count = max(1, min(int(max_explain_nodes), n))
        return np.argsort(-np.asarray(uncertainty, dtype=float))[:explain_count].astype(int).tolist()

    @staticmethod
    def _normalize_queries(sample_coords: np.ndarray, query_coords: np.ndarray | None) -> np.ndarray:
        samples = np.asarray(sample_coords, dtype=float)
        if query_coords is None:
            return samples

        queries = np.asarray(query_coords, dtype=float)
        # 边界场景：空查询时回退到样本点查询，避免解释上下文构建失败。
        if queries.size == 0:
            return samples
        return queries

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
        queries = self._normalize_queries(samples, query_coords)
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
        out = model.forward(
            sample_coords=samples,
            sample_values=values,
            query_coords=queries,
        )
        x_scaled = np.asarray(pre["processed_features"], dtype=np.float32)
        y_pred = np.asarray(out.mean, dtype=np.float32).reshape(-1)
        uncertainty = np.sqrt(np.maximum(np.asarray(out.variance, dtype=np.float32).reshape(-1), 1e-9))
        attention_weights = np.asarray(out.attention_weights, dtype=np.float32)
        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(x_scaled, y_pred)
        background = (
            x_scaled.copy()
            if x_scaled.shape[0] <= 32
            else x_scaled[np.linspace(0, x_scaled.shape[0] - 1, 32, dtype=int)]
        )
        attention_viz = self._attention_visualization_payload(
            query_coords=queries,
            sample_coords=samples,
            attention_weights=attention_weights,
        )
        neighborhood_impact = self._neighborhood_impact_payload(
            query_coords=queries,
            sample_coords=samples,
            sample_values=values,
            attention_weights=attention_weights,
            top_neighbors=5,
        )
        spatial_distribution = self._spatial_weight_distribution_payload(
            query_coords=queries,
            attention_weights=attention_weights,
            bins=10,
        )

        context = {
            "context_key": key,
            "feature_names": list(pre["feature_names"]),
            "feature_matrix": np.asarray(pre["feature_matrix"], dtype=np.float32),
            "scaled_x": x_scaled,
            "prediction": y_pred,
            "uncertainty": uncertainty,
            "attention_mean_weight": np.mean(attention_weights, axis=1).astype(np.float32).reshape(-1),
            "attention_visualization": attention_viz,
            "neighborhood_impact_analysis": neighborhood_impact,
            "spatial_weight_distribution": spatial_distribution,
            "surrogate": surrogate,
            "background": np.asarray(background, dtype=np.float32),
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

    def _compressed_lime_training_data(self, context: dict[str, Any], explained_nodes: list[int]) -> np.ndarray:
        x = np.asarray(context["scaled_x"], dtype=float)
        n = int(x.shape[0])
        keep = max(64, min(n, max(96, len(explained_nodes) * 16)))
        if n <= keep:
            return x

        uncertainty = np.asarray(context["uncertainty"], dtype=float).reshape(-1)
        top_k = max(8, min(len(explained_nodes) * 4, keep // 2))
        top_idx = np.argsort(-uncertainty)[:top_k]
        remaining = keep - int(top_idx.shape[0])
        uniform_idx = np.linspace(0, n - 1, remaining, dtype=int) if remaining > 0 else np.asarray([], dtype=int)
        selected = np.unique(np.concatenate([top_idx.astype(int), uniform_idx.astype(int)])).astype(int)
        if selected.shape[0] < keep:
            fill = np.setdiff1d(np.arange(n, dtype=int), selected, assume_unique=False)[: keep - selected.shape[0]]
            selected = np.concatenate([selected, fill]).astype(int)
        return x[selected[:keep]]

    def _attention_visualization_payload(
        self,
        *,
        query_coords: np.ndarray,
        sample_coords: np.ndarray,
        attention_weights: np.ndarray,
    ) -> dict[str, Any]:
        q = np.asarray(query_coords, dtype=float)
        s = np.asarray(sample_coords, dtype=float)
        w = np.asarray(attention_weights, dtype=float)
        if w.ndim != 2 or w.shape[0] == 0 or w.shape[1] == 0:
            return {"type": "query_sample_heatmap", "shape": [0, 0], "heatmap": [], "top_attention_links": []}

        w_norm = w / (np.sum(w, axis=1, keepdims=True) + 1e-12)
        top_links: list[dict[str, Any]] = []
        for qi in range(w_norm.shape[0]):
            sj = int(np.argmax(w_norm[qi]))
            top_links.append(
                {
                    "query_index": int(qi),
                    "sample_index": int(sj),
                    "weight": float(w_norm[qi, sj]),
                    "query_coord": q[qi].astype(float).tolist(),
                    "sample_coord": s[sj].astype(float).tolist(),
                }
            )

        return {
            "type": "query_sample_heatmap",
            "shape": [int(w_norm.shape[0]), int(w_norm.shape[1])],
            "heatmap": w_norm.astype(float).tolist(),
            "query_coords": q.astype(float).tolist(),
            "sample_coords": s.astype(float).tolist(),
            "top_attention_links": top_links,
        }

    def _neighborhood_impact_payload(
        self,
        *,
        query_coords: np.ndarray,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        attention_weights: np.ndarray,
        top_neighbors: int = 5,
    ) -> dict[str, Any]:
        q = np.asarray(query_coords, dtype=float)
        s = np.asarray(sample_coords, dtype=float)
        v = np.asarray(sample_values, dtype=float).reshape(-1)
        w = np.asarray(attention_weights, dtype=float)
        if w.ndim != 2 or w.shape[0] == 0 or w.shape[1] == 0:
            return {"top_neighbors": int(max(1, top_neighbors)), "per_query": [], "global_summary": {}}

        w_norm = w / (np.sum(w, axis=1, keepdims=True) + 1e-12)
        distances = np.linalg.norm(q[:, None, :] - s[None, :, :], axis=2)
        k = max(1, min(int(top_neighbors), w_norm.shape[1]))
        top_idx = np.argsort(-w_norm, axis=1)[:, :k]
        neighborhood_mean = np.sum(w_norm * v.reshape(1, -1), axis=1)

        per_query: list[dict[str, Any]] = []
        for qi in range(w_norm.shape[0]):
            neighbors: list[dict[str, Any]] = []
            for rank, sj in enumerate(top_idx[qi].tolist(), start=1):
                weight = float(w_norm[qi, sj])
                neighbors.append(
                    {
                        "rank": int(rank),
                        "sample_index": int(sj),
                        "weight": weight,
                        "distance": float(distances[qi, sj]),
                        "sample_value": float(v[sj]),
                        "impact_score": float(weight * v[sj]),
                    }
                )
            per_query.append(
                {
                    "query_index": int(qi),
                    "query_coord": q[qi].astype(float).tolist(),
                    "dominant_neighbor": neighbors[0] if neighbors else None,
                    "weighted_neighborhood_mean": float(neighborhood_mean[qi]),
                    "neighbors": neighbors,
                }
            )

        return {
            "top_neighbors": int(k),
            "per_query": per_query,
            "global_summary": {
                "mean_weighted_neighborhood_mean": float(np.mean(neighborhood_mean)),
                "std_weighted_neighborhood_mean": float(np.std(neighborhood_mean)),
                "mean_dominant_weight": float(np.mean(np.max(w_norm, axis=1))),
            },
        }

    def _spatial_weight_distribution_payload(
        self,
        *,
        query_coords: np.ndarray,
        attention_weights: np.ndarray,
        bins: int = 10,
    ) -> dict[str, Any]:
        q = np.asarray(query_coords, dtype=float)
        w = np.asarray(attention_weights, dtype=float)
        if w.ndim != 2 or w.shape[0] == 0 or w.shape[1] == 0:
            return {"histogram": {"edges": [], "counts": []}, "quantiles": {}, "spatial_bins": []}

        w_norm = w / (np.sum(w, axis=1, keepdims=True) + 1e-12)
        dominant_weight = np.max(w_norm, axis=1)
        entropy = -np.sum(w_norm * np.log(w_norm + 1e-12), axis=1)
        hist_counts, hist_edges = np.histogram(dominant_weight, bins=max(4, int(bins)), range=(0.0, 1.0))
        quantiles = np.quantile(dominant_weight, [0.1, 0.25, 0.5, 0.75, 0.9])

        x_mid = float(np.median(q[:, 0]))
        y_mid = float(np.median(q[:, 1]))
        masks = [
            (q[:, 0] <= x_mid) & (q[:, 1] <= y_mid),
            (q[:, 0] > x_mid) & (q[:, 1] <= y_mid),
            (q[:, 0] <= x_mid) & (q[:, 1] > y_mid),
            (q[:, 0] > x_mid) & (q[:, 1] > y_mid),
        ]
        labels = ["SW", "SE", "NW", "NE"]
        spatial_bins: list[dict[str, Any]] = []
        for label, mask in zip(labels, masks):
            idx = np.where(mask)[0]
            if idx.size == 0:
                spatial_bins.append({"region": label, "query_count": 0, "mean_dominant_weight": 0.0, "mean_entropy": 0.0})
                continue
            spatial_bins.append(
                {
                    "region": label,
                    "query_count": int(idx.size),
                    "mean_dominant_weight": float(np.mean(dominant_weight[idx])),
                    "mean_entropy": float(np.mean(entropy[idx])),
                }
            )

        return {
            "histogram": {
                "edges": hist_edges.astype(float).tolist(),
                "counts": hist_counts.astype(int).tolist(),
            },
            "quantiles": {
                "p10": float(quantiles[0]),
                "p25": float(quantiles[1]),
                "p50": float(quantiles[2]),
                "p75": float(quantiles[3]),
                "p90": float(quantiles[4]),
            },
            "summary": {
                "mean_dominant_weight": float(np.mean(dominant_weight)),
                "mean_entropy": float(np.mean(entropy)),
            },
            "spatial_bins": spatial_bins,
        }


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
            cached["performance"] = {**cached.get("performance", {}), "cache_hit": True, **self._cache_metrics()}
            return cached

        feature_names: list[str] = context["feature_names"]
        predict_fn = self._predict_surrogate(context)
        lime_module = self._load_lime_tabular()
        lime_explainer = None
        training_data = self._compressed_lime_training_data(context, explained_nodes)
        effective_samples = max(80, min(selected_samples, 240))
        if lime_module is not None:
            try:
                lime_explainer = lime_module.LimeTabularExplainer(
                    training_data=np.asarray(training_data, dtype=float),
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
                        num_samples=effective_samples,
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
            "attention_visualization": context["attention_visualization"],
            "neighborhood_impact_analysis": context["neighborhood_impact_analysis"],
            "spatial_weight_distribution": context["spatial_weight_distribution"],
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "latency_target_ms": 8000.0,
                "meets_latency_target": bool((time.perf_counter() - started) * 1000 < 8000.0),
                "lime_training_size": int(training_data.shape[0]),
                "lime_sampling_budget": int(effective_samples),
                "context_memory_bytes": int(self._context_memory_bytes(context)),
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, payload)
        return payload

    def explain_batch(
        self,
        *,
        model: Any,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords_batch: list[np.ndarray | None],
        top_k: int = 5,
        num_samples: Optional[int] = None,
        max_explain_nodes: Optional[int] = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        results: list[dict[str, Any]] = []
        cache_hit_count = 0
        for i, query_coords in enumerate(query_coords_batch):
            out = self.explain(
                model=model,
                sample_coords=sample_coords,
                sample_values=sample_values,
                query_coords=query_coords,
                top_k=top_k,
                num_samples=num_samples,
                max_explain_nodes=max_explain_nodes,
            )
            cache_hit_count += int(bool(out.get("performance", {}).get("cache_hit", False)))
            results.append(
                {
                    "batch_index": int(i),
                    "query_count": int(np.asarray(query_coords if query_coords is not None else sample_coords).shape[0]),
                    "result": out,
                }
            )
        total = max(1, len(results))
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "summary": {
                "method": "lime",
                "batch_size": int(len(results)),
                "cache_hit_count": int(cache_hit_count),
                "cache_hit_ratio": float(cache_hit_count / total),
            },
            "items": results,
            "performance": {
                "duration_ms": duration_ms,
                "avg_duration_ms": float(duration_ms / total),
            },
        }


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
            cached["performance"] = {**cached.get("performance", {}), "cache_hit": True, **self._cache_metrics()}
            return cached

        shap_module = self._load_shap()
        surrogate: Ridge = context["surrogate"]
        feature_names: list[str] = context["feature_names"]
        background = np.asarray(context["background"], dtype=float)
        baseline = np.mean(background, axis=0)
        effective_nsamples = max(40, min(selected_nsamples, 180))
        shap_kernel_explainer = None
        if shap_module is not None:
            try:
                shap_kernel_explainer = shap_module.KernelExplainer(
                    lambda x: surrogate.predict(np.asarray(x, dtype=float)),
                    background,
                )
            except Exception:
                shap_kernel_explainer = None

        batch_explanations: list[dict[str, Any]] = []
        for node_idx in explained_nodes:
            instance = np.asarray(context["scaled_x"][node_idx], dtype=float)
            expected_value = float(surrogate.predict(baseline.reshape(1, -1))[0])
            backend = "surrogate_linear"
            if shap_kernel_explainer is not None:
                try:
                    shap_arr = shap_kernel_explainer.shap_values(
                        instance.reshape(1, -1),
                        nsamples=effective_nsamples,
                        l1_reg="num_features(10)",
                    )
                    if isinstance(shap_arr, list):
                        shap_arr = shap_arr[0]
                    shap_values = np.asarray(shap_arr, dtype=float).reshape(-1)
                    ev = getattr(shap_kernel_explainer, "expected_value", expected_value)
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
            "attention_visualization": context["attention_visualization"],
            "neighborhood_impact_analysis": context["neighborhood_impact_analysis"],
            "spatial_weight_distribution": context["spatial_weight_distribution"],
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "backend": "shap" if shap_module is not None else "surrogate_linear",
                "latency_target_ms": 8000.0,
                "meets_latency_target": bool((time.perf_counter() - started) * 1000 < 8000.0),
                "shap_background_size": int(background.shape[0]),
                "shap_sampling_budget": int(effective_nsamples),
                "context_memory_bytes": int(self._context_memory_bytes(context)),
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, payload)
        return payload

    def explain_batch(
        self,
        *,
        model: Any,
        sample_coords: np.ndarray,
        sample_values: np.ndarray,
        query_coords_batch: list[np.ndarray | None],
        top_k: int = 5,
        nsamples: Optional[int] = None,
        max_explain_nodes: Optional[int] = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        results: list[dict[str, Any]] = []
        cache_hit_count = 0
        for i, query_coords in enumerate(query_coords_batch):
            out = self.explain(
                model=model,
                sample_coords=sample_coords,
                sample_values=sample_values,
                query_coords=query_coords,
                top_k=top_k,
                nsamples=nsamples,
                max_explain_nodes=max_explain_nodes,
            )
            cache_hit_count += int(bool(out.get("performance", {}).get("cache_hit", False)))
            results.append(
                {
                    "batch_index": int(i),
                    "query_count": int(np.asarray(query_coords if query_coords is not None else sample_coords).shape[0]),
                    "result": out,
                }
            )
        total = max(1, len(results))
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        return {
            "summary": {
                "method": "shap",
                "batch_size": int(len(results)),
                "cache_hit_count": int(cache_hit_count),
                "cache_hit_ratio": float(cache_hit_count / total),
            },
            "items": results,
            "performance": {
                "duration_ms": duration_ms,
                "avg_duration_ms": float(duration_ms / total),
            },
        }
