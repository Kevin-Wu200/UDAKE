"""DQN 强化学习模型解释适配器（LIME / SHAP）。"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class DQNExplanationConfig:
    lime_num_samples: int = 180
    shap_nsamples: int = 120
    cache_size: int = 16
    batch_explain_chunk_size: int = 4
    random_state: int = 42


class _DQNBaseAdapter:
    def __init__(self, config: DQNExplanationConfig | None = None) -> None:
        self.config = config or DQNExplanationConfig()
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = {}

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
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _observation_fingerprint(self, observations: list[dict[str, np.ndarray]] | np.ndarray) -> str:
        h = hashlib.sha256()
        if isinstance(observations, np.ndarray):
            arr = np.ascontiguousarray(np.asarray(observations, dtype=float))
            h.update(str(tuple(int(v) for v in arr.shape)).encode("utf-8"))
            h.update(arr.tobytes())
            return h.hexdigest()

        order = ["sampling_distribution", "uncertainty_map", "sampled_values", "spatial_features", "boundary_info"]
        h.update(str(len(observations)).encode("utf-8"))
        for obs in observations:
            for key in order:
                arr = np.ascontiguousarray(np.asarray(obs.get(key, np.array([])), dtype=float).reshape(-1))
                h.update(key.encode("utf-8"))
                h.update(str(int(arr.shape[0])).encode("utf-8"))
                h.update(arr.tobytes())
        return h.hexdigest()

    def _split_explained_batches(self, explained_nodes: np.ndarray) -> list[np.ndarray]:
        nodes = np.asarray(explained_nodes, dtype=int).reshape(-1)
        if nodes.size == 0:
            return []
        chunk = max(1, int(self.config.batch_explain_chunk_size))
        return [nodes[i : i + chunk] for i in range(0, int(nodes.size), chunk)]

    @staticmethod
    def _array_bytes(*arrays: np.ndarray) -> int:
        total = 0
        for arr in arrays:
            try:
                total += int(np.asarray(arr).nbytes)
            except Exception:
                continue
        return int(total)

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            found = self._cache.get(key)
            return None if found is None else dict(found)

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._cache[key] = dict(value)
            if len(self._cache) > max(1, int(self.config.cache_size)):
                oldest = next(iter(self._cache.keys()))
                self._cache.pop(oldest, None)

    def _build_context(self, model: Any, observations: list[dict[str, np.ndarray]] | np.ndarray) -> dict[str, Any]:
        pre = model.preprocess_dqn_data(observations, use_training_stats=True)
        x_raw = np.asarray(pre["raw_features"], dtype=float)
        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        feature_names = list(pre["feature_names"])

        pred = model.predict_dqn(np.asarray(x_raw, dtype=float), deterministic=True)
        actions = np.asarray(pred["action_indices"], dtype=int)
        selected_q_values = np.asarray(pred["selected_q_values"], dtype=float)
        max_q_values = np.asarray(pred["max_q_values"], dtype=float)
        q_values = np.asarray(pred["q_values"], dtype=float)
        action_probabilities = np.asarray(pred.get("action_probabilities", []), dtype=float)
        predict_performance = dict(pred.get("performance", {}))

        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(x_scaled, selected_q_values)
        baseline = np.mean(x_scaled, axis=0)
        surrogate_coef = np.asarray(surrogate.coef_, dtype=float).reshape(-1)
        surrogate_local_weights = (x_scaled - baseline.reshape(1, -1)) * surrogate_coef.reshape(1, -1)
        sample_count = int(x_scaled.shape[0])
        feature_dim = int(x_scaled.shape[1]) if x_scaled.ndim == 2 else 0
        action_dim = int(q_values.shape[1]) if q_values.ndim == 2 else 0

        return {
            "raw_x": x_raw,
            "scaled_x": x_scaled,
            "feature_names": feature_names,
            "actions": actions,
            "selected_q_values": selected_q_values,
            "max_q_values": max_q_values,
            "q_values": q_values,
            "action_probabilities": action_probabilities,
            "surrogate": surrogate,
            "baseline": baseline,
            "surrogate_coef": surrogate_coef,
            "surrogate_local_weights": surrogate_local_weights,
            "sample_count": sample_count,
            "feature_dim": feature_dim,
            "action_dim": action_dim,
            "preprocess": {
                "scaler": pre["scaler"],
                "validation": pre["validation"],
            },
            "predict_performance": predict_performance,
        }

    def _select_explained_nodes(self, target: np.ndarray, max_explain_nodes: int) -> np.ndarray:
        values = np.asarray(target, dtype=float).reshape(-1)
        if values.size == 0:
            return np.zeros((0,), dtype=int)
        n = min(max(1, int(max_explain_nodes)), int(values.size))
        if n >= int(values.size):
            return np.argsort(values)[::-1].astype(int)
        idx = np.argpartition(values, -n)[-n:]
        return idx[np.argsort(values[idx])[::-1]].astype(int)

    def _build_q_value_explanation(self, context: dict[str, Any], *, top_k: int, explained_nodes: np.ndarray) -> dict[str, Any]:
        q_values = np.asarray(context["q_values"], dtype=float)
        selected = np.asarray(context["selected_q_values"], dtype=float).reshape(-1)
        max_q = np.asarray(context["max_q_values"], dtype=float).reshape(-1)
        actions = np.asarray(context["actions"], dtype=int).reshape(-1)
        feature_names = list(context["feature_names"])
        local_matrix = np.asarray(context["surrogate_local_weights"], dtype=float)

        if q_values.ndim == 2 and q_values.shape[0] > 0 and q_values.shape[1] > 1:
            sorted_q = np.sort(q_values, axis=1)
            top1_top2_gap = sorted_q[:, -1] - sorted_q[:, -2]
            q_flat = q_values.reshape(-1)
        else:
            top1_top2_gap = np.zeros_like(selected)
            q_flat = selected

        hist_counts, hist_edges = np.histogram(q_flat, bins=min(12, max(4, int(np.sqrt(max(1, q_flat.size))))))
        node_analysis: list[dict[str, Any]] = []
        for idx in np.asarray(explained_nodes, dtype=int).tolist():
            instance_q = q_values[idx] if q_values.ndim == 2 else np.asarray([selected[idx]], dtype=float)
            order = np.argsort(instance_q)[::-1][: max(1, int(top_k))]
            node_analysis.append(
                {
                    "node_index": int(idx),
                    "selected_action": int(actions[idx]),
                    "selected_q_value": float(selected[idx]),
                    "max_q_value": float(max_q[idx]),
                    "q_value_std": float(np.std(instance_q)) if instance_q.size else 0.0,
                    "top1_top2_gap": float(top1_top2_gap[idx]) if top1_top2_gap.size > idx else 0.0,
                    "top_actions_by_q": [
                        {"action_index": int(a), "q_value": float(instance_q[int(a)])}
                        for a in order.tolist()
                    ],
                    "dominant_features": self._top_features(feature_names, local_matrix[idx], int(top_k)),
                }
            )

        return {
            "summary": {
                "network": "q_value",
                "explained_samples": int(selected.shape[0]),
                "q_value_mean": float(np.mean(selected)) if selected.size else 0.0,
                "q_value_std": float(np.std(selected)) if selected.size else 0.0,
                "q_value_min": float(np.min(selected)) if selected.size else 0.0,
                "q_value_max": float(np.max(selected)) if selected.size else 0.0,
                "top1_top2_gap_mean": float(np.mean(top1_top2_gap)) if top1_top2_gap.size else 0.0,
                "top_features": self._top_features(feature_names, np.mean(np.abs(local_matrix), axis=0), int(top_k))
                if local_matrix.size
                else [],
            },
            "q_value_distribution": {
                "sample_count": int(q_flat.size),
                "counts": [int(x) for x in hist_counts.tolist()],
                "bin_edges": [float(x) for x in hist_edges.tolist()],
            },
            "node_q_value_analysis": node_analysis,
        }

    def _build_action_value_analysis(self, context: dict[str, Any], *, top_k: int, explained_nodes: np.ndarray) -> dict[str, Any]:
        q_values = np.asarray(context["q_values"], dtype=float)
        actions = np.asarray(context["actions"], dtype=int).reshape(-1)
        if q_values.ndim != 2 or q_values.size == 0:
            return {
                "summary": {"network": "action_value", "explained_samples": int(actions.shape[0]), "distinct_actions": 0},
                "top_actions": [],
                "action_selection_distribution": {"histogram": []},
                "node_action_value_analysis": [],
            }

        action_mean = np.mean(q_values, axis=0)
        action_std = np.std(q_values, axis=0)
        order = np.argsort(action_mean)[::-1][: max(1, int(top_k))]
        hist = np.bincount(actions, minlength=q_values.shape[1]).astype(int)
        selection_ratio = hist / max(1, int(actions.size))

        node_analysis: list[dict[str, Any]] = []
        for idx in np.asarray(explained_nodes, dtype=int).tolist():
            row = np.asarray(q_values[idx], dtype=float)
            row_order = np.argsort(row)[::-1][: max(1, int(top_k))]
            node_analysis.append(
                {
                    "node_index": int(idx),
                    "selected_action": int(actions[idx]),
                    "selected_action_rank": int(np.where(np.argsort(row)[::-1] == actions[idx])[0][0] + 1),
                    "top_actions_by_q": [
                        {"action_index": int(a), "q_value": float(row[int(a)])}
                        for a in row_order.tolist()
                    ],
                }
            )

        return {
            "summary": {
                "network": "action_value",
                "explained_samples": int(actions.shape[0]),
                "distinct_actions": int(np.count_nonzero(hist)),
                "mean_selected_action_value": float(np.mean(q_values[np.arange(q_values.shape[0]), actions])) if actions.size else 0.0,
                "top_action_mean_value": float(action_mean[int(order[0])]) if order.size else 0.0,
            },
            "top_actions": [
                {
                    "action_index": int(i),
                    "mean_q_value": float(action_mean[int(i)]),
                    "std_q_value": float(action_std[int(i)]),
                    "selected_count": int(hist[int(i)]),
                    "selected_ratio": float(selection_ratio[int(i)]),
                }
                for i in order.tolist()
            ],
            "action_selection_distribution": {
                "histogram": [
                    {"action_index": int(i), "count": int(c), "ratio": float(selection_ratio[int(i)])}
                    for i, c in enumerate(hist.tolist())
                    if c > 0
                ]
            },
            "node_action_value_analysis": node_analysis,
        }

    def _build_exploration_exploitation_analysis(self, model: Any, context: dict[str, Any], *, top_k: int) -> dict[str, Any]:
        actions = np.asarray(context["actions"], dtype=int).reshape(-1)
        q_values = np.asarray(context["q_values"], dtype=float)
        action_probs = np.asarray(context["action_probabilities"], dtype=float)

        action_dim = int(context.get("action_dim", q_values.shape[1] if q_values.ndim == 2 else 0))
        epsilon = _safe_float(getattr(model, "epsilon", 0.0), 0.0)
        exploration_mode = str(getattr(getattr(model, "config", {}), "exploration", "epsilon_greedy"))
        visit = np.asarray(getattr(model, "action_visit", np.zeros((action_dim,), dtype=float)), dtype=float).reshape(-1)
        if visit.size != action_dim:
            visit = np.zeros((action_dim,), dtype=float)

        if action_probs.ndim == 2 and action_probs.shape[0] == actions.shape[0] and action_probs.shape[1] > 0:
            max_prob = np.max(action_probs, axis=1)
            selected_prob = action_probs[np.arange(actions.shape[0]), actions]
            entropy = -np.sum(action_probs * np.log(np.clip(action_probs, 1e-12, 1.0)), axis=1)
            norm = np.log(max(2, action_probs.shape[1]))
            normalized_entropy = entropy / norm
        else:
            max_prob = np.ones_like(actions, dtype=float)
            selected_prob = np.ones_like(actions, dtype=float)
            normalized_entropy = np.zeros_like(actions, dtype=float)

        sorted_gap = np.sort(q_values, axis=1)[:, -1] - np.sort(q_values, axis=1)[:, -2] if q_values.ndim == 2 and q_values.shape[1] > 1 else np.zeros_like(selected_prob)
        action_hist = np.bincount(actions, minlength=max(1, action_dim)).astype(int)
        top_actions = np.argsort(action_hist)[::-1][: max(1, int(top_k))]

        total_visit = float(np.sum(visit))
        visit_ratio = visit / max(1.0, total_visit)
        return {
            "summary": {
                "mode": exploration_mode,
                "epsilon": float(epsilon),
                "sample_count": int(actions.shape[0]),
                "action_coverage_ratio": float(np.count_nonzero(action_hist) / max(1, action_dim)),
                "mean_selected_probability": float(np.mean(selected_prob)) if selected_prob.size else 0.0,
                "mean_normalized_entropy": float(np.mean(normalized_entropy)) if normalized_entropy.size else 0.0,
                "mean_top1_top2_gap": float(np.mean(sorted_gap)) if sorted_gap.size else 0.0,
            },
            "exploration_signals": {
                "normalized_entropy": [float(x) for x in normalized_entropy.tolist()],
                "selected_action_probability": [float(x) for x in selected_prob.tolist()],
                "max_action_probability": [float(x) for x in max_prob.tolist()],
                "top1_top2_gap": [float(x) for x in sorted_gap.tolist()],
            },
            "action_preference": {
                "top_selected_actions": [
                    {"action_index": int(i), "count": int(action_hist[int(i)])}
                    for i in top_actions.tolist()
                    if action_hist[int(i)] > 0
                ],
                "visit_distribution": [
                    {"action_index": int(i), "visit": float(visit[int(i)]), "visit_ratio": float(visit_ratio[int(i)])}
                    for i in np.argsort(visit)[::-1][: max(1, int(top_k))].tolist()
                    if visit[int(i)] > 0.0
                ],
            },
        }

    def _top_features(self, feature_names: list[str], scores: np.ndarray, top_k: int) -> list[dict[str, Any]]:
        if scores.size == 0:
            return []
        order = np.argsort(np.abs(scores))[::-1][: max(1, int(top_k))]
        return [
            {
                "feature_index": int(i),
                "feature_name": str(feature_names[int(i)]),
                "importance": float(abs(scores[int(i)])),
            }
            for i in order
        ]


class DQNLIMEAdapter(_DQNBaseAdapter):
    def explain(
        self,
        *,
        model: Any,
        observations: list[dict[str, np.ndarray]] | np.ndarray,
        top_k: int = 5,
        max_explain_nodes: int = 8,
        num_samples: int | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        arr = np.asarray(observations, dtype=object)
        cache_key = self._stable_hash(
            {
                "method": "lime",
                "shape": list(arr.shape),
                "obs_fp": self._observation_fingerprint(observations),
                "top_k": int(top_k),
                "max_explain_nodes": int(max_explain_nodes),
                "num_samples": int(num_samples or self.config.lime_num_samples),
            }
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["performance"] = dict(cached.get("performance", {}))
            cached["performance"]["cache_hit"] = True
            return cached

        context = self._build_context(model, observations)
        target = np.asarray(context["selected_q_values"], dtype=float)
        explained_nodes = self._select_explained_nodes(target, int(max_explain_nodes))
        selected_samples = int(num_samples or self.config.lime_num_samples)

        lime_module = self._load_lime_tabular()
        lime_explainer = None
        if lime_module is not None:
            try:
                lime_explainer = lime_module.LimeTabularExplainer(
                    training_data=np.asarray(context["scaled_x"], dtype=float),
                    feature_names=list(context["feature_names"]),
                    mode="regression",
                    random_state=self.config.random_state,
                )
            except Exception:
                lime_explainer = None

        batch_explanations: list[dict[str, Any]] = []
        raw_weight_rows: list[np.ndarray] = []
        surrogate: Ridge = context["surrogate"]
        baseline = np.asarray(context["baseline"], dtype=float)  # noqa: F841
        local_weight_matrix = np.asarray(context["surrogate_local_weights"], dtype=float)

        explained_batches = self._split_explained_batches(explained_nodes)
        for node_batch in explained_batches:
            for node_idx in node_batch.tolist():
                instance = np.asarray(context["scaled_x"][node_idx], dtype=float)
                local_pairs: list[tuple[int, float]] = []
                backend = "surrogate_linear"
                if lime_explainer is not None:
                    try:
                        exp = lime_explainer.explain_instance(
                            instance,
                            predict_fn=lambda x: surrogate.predict(np.asarray(x, dtype=float)),
                            num_features=max(1, int(top_k)),
                            num_samples=selected_samples,
                        )
                        local_pairs = [(int(i), float(w)) for i, w in exp.as_map().get(1, [])]
                        backend = "lime_tabular"
                    except Exception:
                        local_pairs = []

                if not local_pairs:
                    local_weights = np.asarray(local_weight_matrix[node_idx], dtype=np.float32)
                    local_pairs = [(int(i), float(local_weights[i])) for i in range(local_weights.shape[0])]
                else:
                    local_weights = np.zeros((len(context["feature_names"]),), dtype=np.float32)
                    for i, w in local_pairs:
                        if 0 <= i < local_weights.shape[0]:
                            local_weights[i] = float(w)

                local_pairs.sort(key=lambda item: abs(float(item[1])), reverse=True)
                local_pairs = local_pairs[: max(1, int(top_k))]
                raw_weight_rows.append(local_weights)
                batch_explanations.append(
                    {
                        "node_index": int(node_idx),
                        "selected_action": int(context["actions"][node_idx]),
                        "prediction": float(context["selected_q_values"][node_idx]),
                        "max_q_value": float(context["max_q_values"][node_idx]),
                        "backend": backend,
                        "contributions": [
                            {
                                "feature_index": int(i),
                                "feature_name": str(context["feature_names"][int(i)]),
                                "weight": float(w),
                                "abs_weight": float(abs(w)),
                                "feature_value": float(instance[int(i)]),
                            }
                            for i, w in local_pairs
                        ],
                    }
                )

        raw_matrix = np.asarray(raw_weight_rows, dtype=np.float32) if raw_weight_rows else np.zeros((0, len(context["feature_names"])), dtype=np.float32)
        global_scores = np.mean(np.abs(raw_matrix), axis=0) if raw_matrix.size > 0 else np.zeros((len(context["feature_names"]),), dtype=float)
        context_memory_bytes = self._array_bytes(
            np.asarray(context.get("raw_x", np.array([])), dtype=np.float32),
            np.asarray(context.get("scaled_x", np.array([])), dtype=np.float32),
            np.asarray(context.get("q_values", np.array([])), dtype=np.float32),
        )
        result_memory_bytes = self._array_bytes(raw_matrix)
        result = {
            "summary": {
                "method": "lime",
                "explained_nodes": int(len(batch_explanations)),
                "top_k": int(top_k),
                "num_samples": int(selected_samples),
                "top_features": self._top_features(context["feature_names"], global_scores, int(top_k)),
            },
            "batch_explanations": batch_explanations,
            "global_feature_importance": self._top_features(context["feature_names"], global_scores, len(context["feature_names"])),
            "q_value_explanation": self._build_q_value_explanation(context, top_k=int(top_k), explained_nodes=explained_nodes),
            "action_value_analysis": self._build_action_value_analysis(context, top_k=int(top_k), explained_nodes=explained_nodes),
            "exploration_exploitation_analysis": self._build_exploration_exploitation_analysis(model, context, top_k=int(top_k)),
            "preprocess": context["preprocess"],
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - start) * 1000.0),
                "sample_count": int(context["sample_count"]),
                "feature_dim": int(context["feature_dim"]),
                "action_dim": int(context["action_dim"]),
                "batch_count": int(len(explained_batches)),
                "batch_chunk_size": int(max(1, int(self.config.batch_explain_chunk_size))),
                "policy_inference_ms": _safe_float(context.get("predict_performance", {}).get("policy_inference_ms", 0.0)),
                "value_inference_ms": _safe_float(context.get("predict_performance", {}).get("value_inference_ms", 0.0)),
                "model_predict_cache_hit": bool(context.get("predict_performance", {}).get("cache_hit", False)),
                "context_memory_bytes": int(context_memory_bytes),
                "result_memory_bytes": int(result_memory_bytes),
                "result_cache_key": str(cache_key[:16]),
                "latency_target_ms": 15000.0,
                "meets_latency_target": float((time.perf_counter() - start) * 1000.0) < 15000.0,
            },
        }
        self._cache_set(cache_key, result)
        return result


class DQNSHAPAdapter(_DQNBaseAdapter):
    def explain(
        self,
        *,
        model: Any,
        observations: list[dict[str, np.ndarray]] | np.ndarray,
        top_k: int = 5,
        max_explain_nodes: int = 8,
        nsamples: int | None = None,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        arr = np.asarray(observations, dtype=object)
        cache_key = self._stable_hash(
            {
                "method": "shap",
                "shape": list(arr.shape),
                "obs_fp": self._observation_fingerprint(observations),
                "top_k": int(top_k),
                "max_explain_nodes": int(max_explain_nodes),
                "nsamples": int(nsamples or self.config.shap_nsamples),
            }
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["performance"] = dict(cached.get("performance", {}))
            cached["performance"]["cache_hit"] = True
            return cached

        context = self._build_context(model, observations)
        target = np.asarray(context["selected_q_values"], dtype=float)
        explained_nodes = self._select_explained_nodes(target, int(max_explain_nodes))
        selected_nsamples = int(nsamples or self.config.shap_nsamples)

        shap_module = self._load_shap()
        shap_backend = "surrogate_linear"
        surrogate: Ridge = context["surrogate"]
        background = np.asarray(context["scaled_x"], dtype=np.float32)
        background = background[: max(1, min(32, background.shape[0]))]
        baseline = np.asarray(context["baseline"], dtype=np.float32)
        baseline_pred = float(surrogate.predict(baseline.reshape(1, -1))[0])
        local_weight_matrix = np.asarray(context["surrogate_local_weights"], dtype=float)
        kernel_explainer = None

        if shap_module is not None:
            try:
                kernel_explainer = shap_module.KernelExplainer(
                    lambda x: surrogate.predict(np.asarray(x, dtype=float)),
                    background,
                )
                shap_backend = "shap_kernel"
            except Exception:
                kernel_explainer = None

        batch_explanations: list[dict[str, Any]] = []
        raw_rows: list[np.ndarray] = []

        explained_batches = self._split_explained_batches(explained_nodes)
        for node_batch in explained_batches:
            for node_idx in node_batch.tolist():
                instance = np.asarray(context["scaled_x"][node_idx], dtype=np.float32)
                expected_value = baseline_pred

                if kernel_explainer is not None:
                    try:
                        shap_arr = kernel_explainer.shap_values(instance.reshape(1, -1), nsamples=selected_nsamples, silent=True)
                        if isinstance(shap_arr, list):
                            shap_arr = shap_arr[0]
                        shap_values = np.asarray(shap_arr, dtype=np.float32).reshape(-1)
                        ev = getattr(kernel_explainer, "expected_value", expected_value)
                        if np.asarray(ev).reshape(-1).size > 0:
                            expected_value = _safe_float(np.asarray(ev).reshape(-1)[0], expected_value)
                    except Exception:
                        shap_values = np.asarray(local_weight_matrix[node_idx], dtype=np.float32)
                else:
                    shap_values = np.asarray(local_weight_matrix[node_idx], dtype=np.float32)

                raw_rows.append(shap_values)
                pred = float(surrogate.predict(instance.reshape(1, -1))[0])
                order = np.argsort(np.abs(shap_values))[::-1][: max(1, int(top_k))]
                contributions = [
                    {
                        "feature_index": int(i),
                        "feature_name": str(context["feature_names"][int(i)]),
                        "shap_value": float(shap_values[int(i)]),
                        "abs_shap": float(abs(shap_values[int(i)])),
                        "feature_value": float(instance[int(i)]),
                    }
                    for i in order
                ]
                batch_explanations.append(
                    {
                        "node_index": int(node_idx),
                        "selected_action": int(context["actions"][node_idx]),
                        "prediction": pred,
                        "target_prediction": float(context["selected_q_values"][node_idx]),
                        "max_q_value": float(context["max_q_values"][node_idx]),
                        "expected_value": expected_value,
                        "backend": shap_backend,
                        "contributions": contributions,
                        "raw_shap_values": [float(x) for x in shap_values.tolist()],
                    }
                )

        raw_matrix = np.asarray(raw_rows, dtype=np.float32) if raw_rows else np.zeros((0, len(context["feature_names"])), dtype=np.float32)
        global_scores = np.mean(np.abs(raw_matrix), axis=0) if raw_matrix.size > 0 else np.zeros((len(context["feature_names"]),), dtype=float)
        context_memory_bytes = self._array_bytes(
            np.asarray(context.get("raw_x", np.array([])), dtype=np.float32),
            np.asarray(context.get("scaled_x", np.array([])), dtype=np.float32),
            np.asarray(context.get("q_values", np.array([])), dtype=np.float32),
        )
        result_memory_bytes = self._array_bytes(raw_matrix, background)
        result = {
            "summary": {
                "method": "shap",
                "explained_nodes": int(len(batch_explanations)),
                "top_k": int(top_k),
                "nsamples": int(selected_nsamples),
                "top_features": self._top_features(context["feature_names"], global_scores, int(top_k)),
            },
            "batch_explanations": batch_explanations,
            "global_feature_importance": self._top_features(context["feature_names"], global_scores, len(context["feature_names"])),
            "q_value_explanation": self._build_q_value_explanation(context, top_k=int(top_k), explained_nodes=explained_nodes),
            "action_value_analysis": self._build_action_value_analysis(context, top_k=int(top_k), explained_nodes=explained_nodes),
            "exploration_exploitation_analysis": self._build_exploration_exploitation_analysis(model, context, top_k=int(top_k)),
            "preprocess": context["preprocess"],
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - start) * 1000.0),
                "sample_count": int(context["sample_count"]),
                "feature_dim": int(context["feature_dim"]),
                "action_dim": int(context["action_dim"]),
                "batch_count": int(len(explained_batches)),
                "batch_chunk_size": int(max(1, int(self.config.batch_explain_chunk_size))),
                "policy_inference_ms": _safe_float(context.get("predict_performance", {}).get("policy_inference_ms", 0.0)),
                "value_inference_ms": _safe_float(context.get("predict_performance", {}).get("value_inference_ms", 0.0)),
                "model_predict_cache_hit": bool(context.get("predict_performance", {}).get("cache_hit", False)),
                "context_memory_bytes": int(context_memory_bytes),
                "result_memory_bytes": int(result_memory_bytes),
                "result_cache_key": str(cache_key[:16]),
                "latency_target_ms": 15000.0,
                "meets_latency_target": float((time.perf_counter() - start) * 1000.0) < 15000.0,
            },
            "explainer": {
                "backend": "shap" if shap_module is not None else "surrogate_linear",
                "effective_backend": shap_backend,
                "background_size": int(background.shape[0]),
            },
        }
        self._cache_set(cache_key, result)
        return result
