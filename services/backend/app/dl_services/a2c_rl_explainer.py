"""A2C 强化学习模型解释适配器（LIME / SHAP）。"""

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
class A2CExplanationConfig:
    lime_num_samples: int = 180
    shap_nsamples: int = 120
    cache_size: int = 16
    batch_explain_chunk_size: int = 4
    random_state: int = 42


class _A2CBaseAdapter:
    def __init__(self, config: A2CExplanationConfig | None = None) -> None:
        self.config = config or A2CExplanationConfig()
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

    def _predict_from_raw(self, model: Any, raw_features: np.ndarray) -> dict[str, np.ndarray]:
        pred = model.predict_a2c(np.asarray(raw_features, dtype=float), deterministic=True)
        return {
            "actions": np.asarray(pred["action_indices"], dtype=int).reshape(-1),
            "selected_probs": np.asarray(pred["selected_action_probabilities"], dtype=float).reshape(-1),
            "state_values": np.asarray(pred["state_values"], dtype=float).reshape(-1),
            "policy_entropy": np.asarray(pred.get("policy_entropy", []), dtype=float).reshape(-1),
            "action_probabilities": np.asarray(pred.get("action_probabilities", []), dtype=float),
            "predict_performance": dict(pred.get("performance", {})),
        }

    def _build_context(self, model: Any, observations: list[dict[str, np.ndarray]] | np.ndarray) -> dict[str, Any]:
        pre = model.preprocess_a2c_data(observations, use_training_stats=True)
        x_raw = np.asarray(pre["raw_features"], dtype=float)
        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        feature_names = list(pre["feature_names"])

        pred = self._predict_from_raw(model, x_raw)
        actions = np.asarray(pred["actions"], dtype=int)
        selected_probs = np.asarray(pred["selected_probs"], dtype=float)
        state_values = np.asarray(pred["state_values"], dtype=float)
        policy_entropy = np.asarray(pred["policy_entropy"], dtype=float)
        action_probabilities = np.asarray(pred["action_probabilities"], dtype=float)
        predict_performance = dict(pred.get("predict_performance", {}))

        policy_surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        policy_surrogate.fit(x_scaled, selected_probs)
        value_surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        value_surrogate.fit(x_scaled, state_values)

        baseline = np.mean(x_scaled, axis=0)
        policy_coef = np.asarray(policy_surrogate.coef_, dtype=float).reshape(-1)
        value_coef = np.asarray(value_surrogate.coef_, dtype=float).reshape(-1)
        centered = x_scaled - baseline.reshape(1, -1)

        sample_count = int(x_scaled.shape[0])
        feature_dim = int(x_scaled.shape[1]) if x_scaled.ndim == 2 else 0
        action_dim = int(action_probabilities.shape[1]) if action_probabilities.ndim == 2 else int(getattr(model, "action_dim", 0))

        return {
            "raw_x": x_raw,
            "scaled_x": x_scaled,
            "feature_names": feature_names,
            "actions": actions,
            "selected_probs": selected_probs,
            "state_values": state_values,
            "policy_entropy": policy_entropy,
            "action_probabilities": action_probabilities,
            "policy_surrogate": policy_surrogate,
            "value_surrogate": value_surrogate,
            "baseline": baseline,
            "policy_coef": policy_coef,
            "value_coef": value_coef,
            "policy_local_weights": centered * policy_coef.reshape(1, -1),
            "value_local_weights": centered * value_coef.reshape(1, -1),
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

    def _build_actor_network_explanation(self, context: dict[str, Any], *, top_k: int) -> dict[str, Any]:
        feature_names = list(context["feature_names"])
        probs = np.asarray(context["selected_probs"], dtype=float).reshape(-1)
        entropy = np.asarray(context["policy_entropy"], dtype=float).reshape(-1)
        actions = np.asarray(context["actions"], dtype=int).reshape(-1)
        action_probs = np.asarray(context["action_probabilities"], dtype=float)
        policy_coef = np.asarray(context["policy_coef"], dtype=float).reshape(-1)

        action_hist = np.bincount(actions, minlength=max(1, int(context.get("action_dim", 0)))).astype(int)
        top_actions = np.argsort(action_hist)[::-1][: max(1, int(top_k))]

        max_action_prob_mean = 0.0
        if action_probs.ndim == 2 and action_probs.shape[0] == actions.shape[0] and action_probs.shape[1] > 0:
            max_action_prob_mean = float(np.mean(np.max(action_probs, axis=1)))

        return {
            "summary": {
                "network": "actor",
                "explained_samples": int(actions.shape[0]),
                "probability_mean": float(np.mean(probs)) if probs.size else 0.0,
                "probability_std": float(np.std(probs)) if probs.size else 0.0,
                "entropy_mean": float(np.mean(entropy)) if entropy.size else 0.0,
                "entropy_std": float(np.std(entropy)) if entropy.size else 0.0,
                "top_features": self._top_features(feature_names, policy_coef, int(top_k)),
                "top_actions": [
                    {"action_index": int(i), "count": int(action_hist[int(i)])}
                    for i in top_actions.tolist()
                    if action_hist[int(i)] > 0
                ],
            },
            "feature_importance": self._top_features(feature_names, policy_coef, len(feature_names)),
            "action_distribution": {
                "total_actions": int(actions.shape[0]),
                "distinct_actions": int(np.count_nonzero(action_hist)),
                "histogram": [
                    {"action_index": int(i), "count": int(c)}
                    for i, c in enumerate(action_hist.tolist())
                    if c > 0
                ],
            },
            "policy_confidence": {
                "selected_probabilities": [float(x) for x in probs.tolist()],
                "entropy": [float(x) for x in entropy.tolist()] if entropy.size else [],
                "max_action_probability_mean": max_action_prob_mean,
            },
        }

    def _build_critic_network_explanation(
        self,
        context: dict[str, Any],
        *,
        top_k: int,
        explained_nodes: np.ndarray,
    ) -> dict[str, Any]:
        feature_names = list(context["feature_names"])
        values = np.asarray(context["state_values"], dtype=float).reshape(-1)
        value_coef = np.asarray(context["value_coef"], dtype=float).reshape(-1)
        value_local = np.asarray(context["value_local_weights"], dtype=float)
        surrogate: Ridge = context["value_surrogate"]
        scaled_x = np.asarray(context["scaled_x"], dtype=float)

        node_details: list[dict[str, Any]] = []
        for idx in np.asarray(explained_nodes, dtype=int).tolist():
            node_details.append(
                {
                    "node_index": int(idx),
                    "state_value": float(values[idx]),
                    "value_prediction": float(surrogate.predict(scaled_x[idx].reshape(1, -1))[0]),
                    "top_contributions": self._top_features(feature_names, value_local[idx], int(top_k)),
                }
            )

        high_value_idx = np.argsort(values)[::-1][: max(1, int(top_k))]
        return {
            "summary": {
                "network": "critic",
                "explained_samples": int(values.shape[0]),
                "state_value_mean": float(np.mean(values)) if values.size else 0.0,
                "state_value_std": float(np.std(values)) if values.size else 0.0,
                "state_value_min": float(np.min(values)) if values.size else 0.0,
                "state_value_max": float(np.max(values)) if values.size else 0.0,
                "top_features": self._top_features(feature_names, value_coef, int(top_k)),
            },
            "feature_importance": self._top_features(feature_names, value_coef, len(feature_names)),
            "high_value_states": [{"node_index": int(i), "state_value": float(values[int(i)])} for i in high_value_idx.tolist()],
            "node_value_analysis": node_details,
        }

    def _build_policy_gradient_analysis(
        self,
        context: dict[str, Any],
        *,
        top_k: int,
        explained_nodes: np.ndarray,
    ) -> dict[str, Any]:
        feature_names = list(context["feature_names"])
        actions = np.asarray(context["actions"], dtype=int).reshape(-1)
        probs = np.asarray(context["selected_probs"], dtype=float).reshape(-1)
        entropy = np.asarray(context["policy_entropy"], dtype=float).reshape(-1)
        values = np.asarray(context["state_values"], dtype=float).reshape(-1)
        policy_local = np.asarray(context["policy_local_weights"], dtype=float)

        centered_values = values - (float(np.mean(values)) if values.size else 0.0)
        adv_std = float(np.std(centered_values)) + 1e-8
        normalized_advantage = centered_values / adv_std
        log_prob = np.log(np.clip(probs, 1e-12, 1.0))
        gradient_signal = -log_prob * normalized_advantage

        feature_gradient_score = (
            np.mean(np.abs(policy_local * normalized_advantage.reshape(-1, 1)), axis=0)
            if policy_local.size
            else np.zeros((len(feature_names),), dtype=float)
        )

        node_analysis: list[dict[str, Any]] = []
        for idx in np.asarray(explained_nodes, dtype=int).tolist():
            node_analysis.append(
                {
                    "node_index": int(idx),
                    "selected_action": int(actions[idx]),
                    "selected_probability": float(probs[idx]),
                    "state_value": float(values[idx]),
                    "normalized_advantage": float(normalized_advantage[idx]),
                    "policy_gradient_signal": float(gradient_signal[idx]),
                    "policy_entropy": float(entropy[idx]) if entropy.size else 0.0,
                    "dominant_features": self._top_features(feature_names, policy_local[idx], int(top_k)),
                }
            )

        return {
            "summary": {
                "analysis": "policy_gradient",
                "sample_count": int(probs.shape[0]),
                "gradient_signal_mean": float(np.mean(gradient_signal)) if gradient_signal.size else 0.0,
                "gradient_signal_std": float(np.std(gradient_signal)) if gradient_signal.size else 0.0,
                "positive_signal_ratio": float(np.mean(gradient_signal > 0.0)) if gradient_signal.size else 0.0,
                "entropy_mean": float(np.mean(entropy)) if entropy.size else 0.0,
                "top_features": self._top_features(feature_names, feature_gradient_score, int(top_k)),
            },
            "signals": {
                "log_probability": [float(x) for x in log_prob.tolist()],
                "normalized_advantage": [float(x) for x in normalized_advantage.tolist()],
                "policy_gradient_signal": [float(x) for x in gradient_signal.tolist()],
            },
            "node_gradient_analysis": node_analysis,
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


class A2CLIMEAdapter(_A2CBaseAdapter):
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
        target = np.asarray(context["selected_probs"], dtype=float)
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
        surrogate: Ridge = context["policy_surrogate"]
        policy_local = np.asarray(context["policy_local_weights"], dtype=float)

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
                    local_weights = np.asarray(policy_local[node_idx], dtype=np.float32)
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
                        "prediction": float(context["selected_probs"][node_idx]),
                        "state_value": float(context["state_values"][node_idx]),
                        "policy_entropy": float(context["policy_entropy"][node_idx]) if context["policy_entropy"].size else 0.0,
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
            np.asarray(context.get("action_probabilities", np.array([])), dtype=np.float32),
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
            "actor_network_explanation": self._build_actor_network_explanation(context, top_k=int(top_k)),
            "critic_network_explanation": self._build_critic_network_explanation(
                context,
                top_k=int(top_k),
                explained_nodes=explained_nodes,
            ),
            "policy_gradient_analysis": self._build_policy_gradient_analysis(
                context,
                top_k=int(top_k),
                explained_nodes=explained_nodes,
            ),
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


class A2CSHAPAdapter(_A2CBaseAdapter):
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
        target = np.asarray(context["selected_probs"], dtype=float)
        explained_nodes = self._select_explained_nodes(target, int(max_explain_nodes))
        selected_nsamples = int(nsamples or self.config.shap_nsamples)

        shap_module = self._load_shap()
        shap_backend = "surrogate_linear"
        surrogate: Ridge = context["policy_surrogate"]
        background = np.asarray(context["scaled_x"], dtype=np.float32)
        background = background[: max(1, min(32, background.shape[0]))]
        baseline = np.asarray(context["baseline"], dtype=np.float32)
        policy_local = np.asarray(context["policy_local_weights"], dtype=float)
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
                expected_value = float(surrogate.predict(baseline.reshape(1, -1))[0])

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
                        shap_values = np.asarray(policy_local[node_idx], dtype=np.float32)
                else:
                    shap_values = np.asarray(policy_local[node_idx], dtype=np.float32)

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
                        "target_prediction": float(context["selected_probs"][node_idx]),
                        "state_value": float(context["state_values"][node_idx]),
                        "policy_entropy": float(context["policy_entropy"][node_idx]) if context["policy_entropy"].size else 0.0,
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
            np.asarray(context.get("action_probabilities", np.array([])), dtype=np.float32),
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
            "actor_network_explanation": self._build_actor_network_explanation(context, top_k=int(top_k)),
            "critic_network_explanation": self._build_critic_network_explanation(
                context,
                top_k=int(top_k),
                explained_nodes=explained_nodes,
            ),
            "policy_gradient_analysis": self._build_policy_gradient_analysis(
                context,
                top_k=int(top_k),
                explained_nodes=explained_nodes,
            ),
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
