"""PPO 强化学习模型解释适配器（LIME / SHAP）。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import threading
import time
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class PPOExplanationConfig:
    lime_num_samples: int = 180
    shap_nsamples: int = 120
    cache_size: int = 16
    random_state: int = 42


class _PPOBaseAdapter:
    def __init__(self, config: PPOExplanationConfig | None = None) -> None:
        self.config = config or PPOExplanationConfig()
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
        pred = model.predict_ppo(np.asarray(raw_features, dtype=float), deterministic=True)
        return {
            "actions": np.asarray(pred["action_indices"], dtype=int).reshape(-1),
            "selected_probs": np.asarray(pred["selected_action_probabilities"], dtype=float).reshape(-1),
            "state_values": np.asarray(pred["state_values"], dtype=float).reshape(-1),
            "policy_entropy": np.asarray(pred.get("policy_entropy", []), dtype=float).reshape(-1),
            "action_probabilities": np.asarray(pred.get("action_probabilities", []), dtype=float),
            "predict_performance": dict(pred.get("performance", {})),
        }

    def _build_context(self, model: Any, observations: list[dict[str, np.ndarray]] | np.ndarray) -> dict[str, Any]:
        pre = model.preprocess_ppo_data(observations, use_training_stats=True)
        x_raw = np.asarray(pre["raw_features"], dtype=float)
        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        feature_names = list(pre["feature_names"])

        pred = self._predict_from_raw(model, x_raw)
        actions = np.asarray(pred["actions"], dtype=int)
        selected_probs = np.asarray(pred["selected_probs"], dtype=float)
        values = np.asarray(pred["state_values"], dtype=float)
        policy_entropy = np.asarray(pred["policy_entropy"], dtype=float)
        action_probabilities = np.asarray(pred["action_probabilities"], dtype=float)
        predict_performance = dict(pred.get("predict_performance", {}))

        policy_surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        policy_surrogate.fit(x_scaled, selected_probs)
        value_surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        value_surrogate.fit(x_scaled, values)
        baseline = np.mean(x_scaled, axis=0)

        return {
            "raw_x": x_raw,
            "scaled_x": x_scaled,
            "feature_names": feature_names,
            "actions": actions,
            "target_probs": selected_probs,
            "state_values": values,
            "policy_entropy": policy_entropy,
            "action_probabilities": action_probabilities,
            "policy_surrogate": policy_surrogate,
            "value_surrogate": value_surrogate,
            "baseline": baseline,
            "preprocess": {
                "scaler": pre["scaler"],
                "validation": pre["validation"],
            },
            "predict_performance": predict_performance,
        }

    def _build_policy_network_explanation(self, context: dict[str, Any], *, top_k: int) -> dict[str, Any]:
        feature_names = list(context["feature_names"])
        surrogate: Ridge = context["policy_surrogate"]
        feature_scores = np.asarray(surrogate.coef_, dtype=float).reshape(-1)
        probs = np.asarray(context["target_probs"], dtype=float).reshape(-1)
        entropy = np.asarray(context["policy_entropy"], dtype=float).reshape(-1)
        actions = np.asarray(context["actions"], dtype=int).reshape(-1)
        action_probs = np.asarray(context["action_probabilities"], dtype=float)

        action_hist: dict[int, int] = {}
        for a in actions.tolist():
            action_hist[int(a)] = int(action_hist.get(int(a), 0) + 1)
        top_actions = sorted(action_hist.items(), key=lambda item: item[1], reverse=True)[: max(1, int(top_k))]

        return {
            "summary": {
                "network": "policy",
                "explained_samples": int(actions.shape[0]),
                "probability_mean": float(np.mean(probs)) if probs.size else 0.0,
                "probability_std": float(np.std(probs)) if probs.size else 0.0,
                "entropy_mean": float(np.mean(entropy)) if entropy.size else 0.0,
                "entropy_std": float(np.std(entropy)) if entropy.size else 0.0,
                "top_actions": [{"action_index": int(i), "count": int(c)} for i, c in top_actions],
                "top_features": self._top_features(feature_names, feature_scores, int(top_k)),
            },
            "feature_importance": self._top_features(feature_names, feature_scores, len(feature_names)),
            "action_distribution": {
                "total_actions": int(actions.shape[0]),
                "distinct_actions": int(len(action_hist)),
                "histogram": [{"action_index": int(i), "count": int(c)} for i, c in sorted(action_hist.items())],
            },
            "policy_confidence": {
                "selected_probabilities": [float(x) for x in probs.tolist()],
                "entropy": [float(x) for x in entropy.tolist()] if entropy.size else [],
                "max_action_probability_mean": float(np.mean(np.max(action_probs, axis=1))) if action_probs.ndim == 2 and action_probs.size else 0.0,
            },
        }

    def _build_value_network_explanation(
        self,
        context: dict[str, Any],
        *,
        top_k: int,
        explained_nodes: np.ndarray,
    ) -> dict[str, Any]:
        feature_names = list(context["feature_names"])
        surrogate: Ridge = context["value_surrogate"]
        baseline = np.asarray(context["baseline"], dtype=float).reshape(-1)
        scaled_x = np.asarray(context["scaled_x"], dtype=float)
        values = np.asarray(context["state_values"], dtype=float).reshape(-1)
        feature_scores = np.asarray(surrogate.coef_, dtype=float).reshape(-1)

        node_value_details: list[dict[str, Any]] = []
        for idx in np.asarray(explained_nodes, dtype=int).tolist():
            instance = np.asarray(scaled_x[idx], dtype=float)
            local_scores = feature_scores * (instance - baseline)
            top_contrib = self._top_features(feature_names, local_scores, int(top_k))
            node_value_details.append(
                {
                    "node_index": int(idx),
                    "state_value": float(values[idx]),
                    "value_prediction": float(surrogate.predict(instance.reshape(1, -1))[0]),
                    "top_contributions": top_contrib,
                }
            )

        sorted_idx = np.argsort(values)[::-1][: max(1, int(top_k))]
        return {
            "summary": {
                "network": "value",
                "explained_samples": int(values.shape[0]),
                "state_value_mean": float(np.mean(values)) if values.size else 0.0,
                "state_value_std": float(np.std(values)) if values.size else 0.0,
                "state_value_min": float(np.min(values)) if values.size else 0.0,
                "state_value_max": float(np.max(values)) if values.size else 0.0,
                "top_features": self._top_features(feature_names, feature_scores, int(top_k)),
            },
            "feature_importance": self._top_features(feature_names, feature_scores, len(feature_names)),
            "high_value_states": [{"node_index": int(i), "state_value": float(values[int(i)])} for i in sorted_idx.tolist()],
            "node_value_analysis": node_value_details,
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


class PPOLIMEAdapter(_PPOBaseAdapter):
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
        target = np.asarray(context["target_probs"], dtype=float)
        explained_nodes = np.argsort(target)[::-1][: max(1, min(int(max_explain_nodes), len(target)))].astype(int)
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
        baseline = np.asarray(context["baseline"], dtype=float)

        for node_idx in explained_nodes.tolist():
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
                local_weights = np.asarray(surrogate.coef_, dtype=float) * (instance - baseline)
                local_pairs = [(int(i), float(local_weights[i])) for i in range(local_weights.shape[0])]
            else:
                local_weights = np.zeros((len(context["feature_names"]),), dtype=float)
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
                    "prediction": float(context["target_probs"][node_idx]),
                    "state_value": float(context["state_values"][node_idx]),
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

        raw_matrix = np.asarray(raw_weight_rows, dtype=float) if raw_weight_rows else np.zeros((0, len(context["feature_names"])))
        global_scores = np.mean(np.abs(raw_matrix), axis=0) if raw_matrix.size > 0 else np.zeros((len(context["feature_names"]),), dtype=float)
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
            "policy_network_explanation": self._build_policy_network_explanation(context, top_k=int(top_k)),
            "value_network_explanation": self._build_value_network_explanation(
                context,
                top_k=int(top_k),
                explained_nodes=explained_nodes,
            ),
            "preprocess": context["preprocess"],
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - start) * 1000.0),
                "policy_inference_ms": _safe_float(context.get("predict_performance", {}).get("policy_inference_ms", 0.0)),
                "value_inference_ms": _safe_float(context.get("predict_performance", {}).get("value_inference_ms", 0.0)),
                "model_predict_cache_hit": bool(context.get("predict_performance", {}).get("cache_hit", False)),
                "latency_target_ms": 15000.0,
                "meets_latency_target": float((time.perf_counter() - start) * 1000.0) < 15000.0,
            },
        }
        self._cache_set(cache_key, result)
        return result


class PPOSHAPAdapter(_PPOBaseAdapter):
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
        target = np.asarray(context["target_probs"], dtype=float)
        explained_nodes = np.argsort(target)[::-1][: max(1, min(int(max_explain_nodes), len(target)))].astype(int)
        selected_nsamples = int(nsamples or self.config.shap_nsamples)

        shap_module = self._load_shap()
        shap_backend = "surrogate_linear"
        surrogate: Ridge = context["policy_surrogate"]
        background = np.asarray(context["scaled_x"], dtype=float)
        background = background[: max(1, min(32, background.shape[0]))]
        baseline = np.asarray(context["baseline"], dtype=float)
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

        for node_idx in explained_nodes.tolist():
            instance = np.asarray(context["scaled_x"][node_idx], dtype=float)
            expected_value = float(surrogate.predict(baseline.reshape(1, -1))[0])

            if kernel_explainer is not None:
                try:
                    shap_arr = kernel_explainer.shap_values(instance.reshape(1, -1), nsamples=selected_nsamples, silent=True)
                    if isinstance(shap_arr, list):
                        shap_arr = shap_arr[0]
                    shap_values = np.asarray(shap_arr, dtype=float).reshape(-1)
                    ev = getattr(kernel_explainer, "expected_value", expected_value)
                    if np.asarray(ev).reshape(-1).size > 0:
                        expected_value = _safe_float(np.asarray(ev).reshape(-1)[0], expected_value)
                except Exception:
                    shap_values = np.asarray(surrogate.coef_, dtype=float) * (instance - baseline)
            else:
                shap_values = np.asarray(surrogate.coef_, dtype=float) * (instance - baseline)

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
                    "target_prediction": float(context["target_probs"][node_idx]),
                    "state_value": float(context["state_values"][node_idx]),
                    "expected_value": expected_value,
                    "backend": shap_backend,
                    "contributions": contributions,
                    "raw_shap_values": [float(x) for x in shap_values.tolist()],
                }
            )

        raw_matrix = np.asarray(raw_rows, dtype=float) if raw_rows else np.zeros((0, len(context["feature_names"])))
        global_scores = np.mean(np.abs(raw_matrix), axis=0) if raw_matrix.size > 0 else np.zeros((len(context["feature_names"]),), dtype=float)
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
            "policy_network_explanation": self._build_policy_network_explanation(context, top_k=int(top_k)),
            "value_network_explanation": self._build_value_network_explanation(
                context,
                top_k=int(top_k),
                explained_nodes=explained_nodes,
            ),
            "preprocess": context["preprocess"],
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - start) * 1000.0),
                "policy_inference_ms": _safe_float(context.get("predict_performance", {}).get("policy_inference_ms", 0.0)),
                "value_inference_ms": _safe_float(context.get("predict_performance", {}).get("value_inference_ms", 0.0)),
                "model_predict_cache_hit": bool(context.get("predict_performance", {}).get("cache_hit", False)),
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
