"""GNN-Kriging 模型解释适配器（LIME/SHAP）。"""

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
class GNNKrigingExplanationConfig:
    lime_num_samples: int = 180
    shap_nsamples: int = 120
    max_explain_nodes: int = 8
    cache_size: int = 24
    random_state: int = 42


class _BaseGNNKrigingAdapter:
    def __init__(self, config: Optional[GNNKrigingExplanationConfig] = None) -> None:
        self.config = config or GNNKrigingExplanationConfig()
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

        pre = model.preprocess_gnn_kriging_data(
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
        background = x_scaled.copy() if x_scaled.shape[0] <= 24 else x_scaled[np.linspace(0, x_scaled.shape[0] - 1, 24, dtype=int)]
        residual = np.asarray(pred["residual"], dtype=float).reshape(-1)
        adjacency = np.asarray(pre["adjacency_matrix"], dtype=float)
        graph_analysis = self._graph_structure_analysis_payload(adjacency=adjacency)
        node_weight_explanation = self._node_weight_explanation_payload(
            adjacency=adjacency,
            prediction=y_pred,
            uncertainty=uncertainty,
            residual=residual,
        )
        edge_weight_explanation = self._edge_weight_explanation_payload(
            adjacency=adjacency,
            query_coords=queries,
            uncertainty=uncertainty,
            residual=residual,
        )

        context = {
            "context_key": key,
            "feature_names": list(pre["feature_names"]),
            "feature_matrix": np.asarray(pre["feature_matrix"], dtype=float),
            "scaled_x": x_scaled,
            "prediction": y_pred,
            "uncertainty": uncertainty,
            "residual": residual,
            "surrogate": surrogate,
            "background": np.asarray(background, dtype=float),
            "graph_structure_analysis": graph_analysis,
            "node_weight_explanation": node_weight_explanation,
            "edge_weight_explanation": edge_weight_explanation,
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

    def _graph_structure_analysis_payload(self, *, adjacency: np.ndarray) -> dict[str, Any]:
        adj = np.asarray(adjacency, dtype=float)
        if adj.ndim != 2 or adj.shape[0] == 0 or adj.shape[0] != adj.shape[1]:
            return {
                "node_count": 0,
                "edge_count": 0,
                "density": 0.0,
                "degree_stats": {},
                "weighted_degree_stats": {},
                "connected_components": {"count": 0, "sizes": []},
                "isolated_nodes": [],
            }

        n = int(adj.shape[0])
        off_diag = ~np.eye(n, dtype=bool)
        edge_mask = (adj > 1e-12) & off_diag
        undirected_mask = edge_mask | edge_mask.T
        edge_count = int(np.sum(edge_mask))
        density = float(edge_count / max(1, n * (n - 1)))
        degree = np.sum(undirected_mask, axis=1).astype(float)
        weighted_degree = np.sum(np.maximum(adj, 0.0) * off_diag, axis=1).astype(float)

        visited = np.zeros((n,), dtype=bool)
        component_sizes: list[int] = []
        for i in range(n):
            if visited[i]:
                continue
            stack = [i]
            visited[i] = True
            size = 0
            while stack:
                node = int(stack.pop())
                size += 1
                neighbors = np.where(undirected_mask[node])[0]
                for nb in neighbors.tolist():
                    if not visited[nb]:
                        visited[nb] = True
                        stack.append(int(nb))
            component_sizes.append(int(size))

        clustering_vals: list[float] = []
        for i in range(n):
            neighbors = np.where(undirected_mask[i])[0]
            k = int(neighbors.shape[0])
            if k < 2:
                clustering_vals.append(0.0)
                continue
            sub = undirected_mask[np.ix_(neighbors, neighbors)]
            links = int(np.sum(sub) // 2)
            clustering_vals.append(float((2.0 * links) / (k * (k - 1))))

        return {
            "node_count": n,
            "edge_count": edge_count,
            "density": density,
            "degree_stats": {
                "mean": float(np.mean(degree)),
                "std": float(np.std(degree)),
                "max": float(np.max(degree)),
                "min": float(np.min(degree)),
            },
            "weighted_degree_stats": {
                "mean": float(np.mean(weighted_degree)),
                "std": float(np.std(weighted_degree)),
                "max": float(np.max(weighted_degree)),
                "min": float(np.min(weighted_degree)),
            },
            "connected_components": {
                "count": int(len(component_sizes)),
                "sizes": component_sizes,
            },
            "isolated_nodes": np.where(degree <= 1e-9)[0].astype(int).tolist(),
            "clustering_coefficient_mean": float(np.mean(np.asarray(clustering_vals, dtype=float))),
            "symmetric_ratio": float(np.mean((edge_mask == edge_mask.T).astype(float))),
        }

    def _node_weight_explanation_payload(
        self,
        *,
        adjacency: np.ndarray,
        prediction: np.ndarray,
        uncertainty: np.ndarray,
        residual: np.ndarray,
    ) -> dict[str, Any]:
        adj = np.asarray(adjacency, dtype=float)
        pred = np.asarray(prediction, dtype=float).reshape(-1)
        unc = np.asarray(uncertainty, dtype=float).reshape(-1)
        res = np.asarray(residual, dtype=float).reshape(-1)
        n = int(adj.shape[0]) if adj.ndim == 2 else 0
        if n <= 0:
            return {"top_nodes": [], "per_node": [], "global_summary": {}}

        off_diag = ~np.eye(n, dtype=bool)
        undirected_mask = ((adj > 1e-12) & off_diag) | (((adj > 1e-12) & off_diag).T)
        degree = np.sum(undirected_mask, axis=1).astype(float)
        weighted_degree = np.sum(np.maximum(adj, 0.0) * off_diag, axis=1).astype(float)
        centrality = weighted_degree / (np.sum(weighted_degree) + 1e-12)
        unc_norm = unc / (np.max(unc) + 1e-12)
        res_norm = np.abs(res) / (np.max(np.abs(res)) + 1e-12)
        cen_norm = centrality / (np.max(centrality) + 1e-12)
        influence = 0.50 * cen_norm + 0.30 * unc_norm + 0.20 * res_norm

        per_node: list[dict[str, Any]] = []
        for i in range(n):
            per_node.append(
                {
                    "node_index": int(i),
                    "degree": float(degree[i]),
                    "weighted_degree": float(weighted_degree[i]),
                    "centrality": float(centrality[i]),
                    "prediction": float(pred[i]),
                    "uncertainty": float(unc[i]),
                    "residual": float(res[i]),
                    "influence_score": float(influence[i]),
                }
            )
        ranking = np.argsort(-influence).astype(int).tolist()
        top_nodes = [per_node[i] for i in ranking[: min(10, len(per_node))]]

        return {
            "top_nodes": top_nodes,
            "per_node": per_node,
            "global_summary": {
                "mean_influence_score": float(np.mean(influence)),
                "max_influence_score": float(np.max(influence)),
                "mean_centrality": float(np.mean(centrality)),
            },
        }

    def _edge_weight_explanation_payload(
        self,
        *,
        adjacency: np.ndarray,
        query_coords: np.ndarray,
        uncertainty: np.ndarray,
        residual: np.ndarray,
    ) -> dict[str, Any]:
        adj = np.asarray(adjacency, dtype=float)
        coords = np.asarray(query_coords, dtype=float)
        unc = np.asarray(uncertainty, dtype=float).reshape(-1)
        res = np.asarray(residual, dtype=float).reshape(-1)
        if adj.ndim != 2 or adj.shape[0] == 0 or adj.shape[0] != adj.shape[1]:
            return {"top_edges": [], "global_summary": {}, "edge_count": 0}

        n = int(adj.shape[0])
        off_diag = ~np.eye(n, dtype=bool)
        edge_indices = np.argwhere((adj > 1e-12) & off_diag)
        edges: list[dict[str, Any]] = []
        for i, j in edge_indices.tolist():
            i_idx = int(i)
            j_idx = int(j)
            weight = float(adj[i_idx, j_idx])
            dist = float(np.linalg.norm(coords[i_idx] - coords[j_idx])) if coords.shape[0] == n else 0.0
            uncertainty_pair = float(0.5 * (unc[i_idx] + unc[j_idx]))
            residual_pair = float(0.5 * (abs(res[i_idx]) + abs(res[j_idx])))
            influence = float(weight * (0.65 * uncertainty_pair + 0.35 * residual_pair))
            edges.append(
                {
                    "source": i_idx,
                    "target": j_idx,
                    "weight": weight,
                    "distance": dist,
                    "uncertainty_pair": uncertainty_pair,
                    "residual_pair": residual_pair,
                    "edge_influence_score": influence,
                }
            )

        if not edges:
            return {"top_edges": [], "global_summary": {}, "edge_count": 0}

        ranking = sorted(edges, key=lambda item: item["edge_influence_score"], reverse=True)
        weights = np.asarray([e["weight"] for e in edges], dtype=float)
        influences = np.asarray([e["edge_influence_score"] for e in edges], dtype=float)
        return {
            "edge_count": int(len(edges)),
            "top_edges": ranking[: min(20, len(ranking))],
            "global_summary": {
                "mean_weight": float(np.mean(weights)),
                "max_weight": float(np.max(weights)),
                "mean_edge_influence_score": float(np.mean(influences)),
                "max_edge_influence_score": float(np.max(influences)),
            },
        }


class GNNKrigingLIMEAdapter(_BaseGNNKrigingAdapter):
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
                "residual": np.asarray(context["residual"], dtype=float).tolist(),
            },
            "graph_structure_analysis": context["graph_structure_analysis"],
            "node_weight_explanation": context["node_weight_explanation"],
            "edge_weight_explanation": context["edge_weight_explanation"],
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "latency_target_ms": 8000.0,
                "meets_latency_target": bool((time.perf_counter() - started) * 1000 < 8000.0),
                "lime_training_size": int(training_data.shape[0]),
                "lime_sampling_budget": int(effective_samples),
            },
        }
        self._cache_set(cache_key, payload)
        return payload


class GNNKrigingSHAPAdapter(_BaseGNNKrigingAdapter):
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
                "residual": np.asarray(context["residual"], dtype=float).tolist(),
            },
            "graph_structure_analysis": context["graph_structure_analysis"],
            "node_weight_explanation": context["node_weight_explanation"],
            "edge_weight_explanation": context["edge_weight_explanation"],
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "backend": "shap" if shap_module is not None else "surrogate_linear",
                "latency_target_ms": 8000.0,
                "meets_latency_target": bool((time.perf_counter() - started) * 1000 < 8000.0),
                "shap_background_size": int(background.shape[0]),
                "shap_sampling_budget": int(effective_nsamples),
            },
        }
        self._cache_set(cache_key, payload)
        return payload
