"""GAN 异常检测模型解释适配器。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
import threading
import time
from typing import Any, Callable, Optional

import numpy as np
from sklearn.linear_model import Ridge

from deep_learning.models.anomaly_detection.common import robust_zscore

from .anomaly_features import AnomalyFeatureRegistry


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class GANExplanationConfig:
    lime_num_samples: int = 240
    shap_nsamples: int = 140
    max_explain_nodes: int = 8
    cache_size: int = 32
    parallel_workers: int = 4
    shap_feature_cap: int = 10
    random_state: int = 42


class _BaseGANAdapter:
    def __init__(self, config: Optional[GANExplanationConfig] = None) -> None:
        self.config = config or GANExplanationConfig()
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
        plan = self._feature_registry.standardization_plan("gan")
        scaled = np.zeros_like(matrix, dtype=float)
        stats: dict[str, dict[str, float]] = {}
        for idx, name in enumerate(feature_names):
            strategy = plan.get(name, "zscore")
            scaled_col, st = self._standardize_column(matrix[:, idx], strategy)
            scaled[:, idx] = scaled_col
            stats[name] = st
        return scaled, stats

    def _build_feature_matrix(self, *, model: Any, coords: np.ndarray, values: np.ndarray, batch_size: int | None = None) -> tuple[np.ndarray, list[str], dict[str, Any]]:
        pre = model.preprocess_gan_data(
            np.asarray(coords, dtype=float),
            np.asarray(values, dtype=float),
            batch_size=batch_size,
            use_training_stats=True,
        )
        matrix = np.asarray(pre["processed_features"], dtype=float)
        names = [str(x) for x in pre["feature_names"]]
        return matrix, names, pre

    def _predict_scores(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        bundle = model.anomaly_scores(np.asarray(coords, dtype=float), np.asarray(values, dtype=float))
        discriminator = np.asarray(bundle.get("discriminator", []), dtype=float)
        reconstruction = np.asarray(bundle.get("reconstruction", []), dtype=float)
        gradient = np.asarray(bundle.get("gradient", []), dtype=float)
        combined = np.asarray(bundle.get("combined", []), dtype=float)
        return {
            "discriminator": discriminator,
            "reconstruction": reconstruction,
            "gradient": gradient,
            "combined": combined,
        }

    def _top_node_indices(self, scores: np.ndarray, max_explain_nodes: int) -> list[int]:
        n = len(scores)
        explain_count = max(1, min(int(max_explain_nodes), n))
        return np.argsort(-scores)[:explain_count].astype(int).tolist()

    def _select_background(self, x_scaled: np.ndarray, scores: np.ndarray, size: int = 64) -> np.ndarray:
        n = x_scaled.shape[0]
        k = max(8, min(size, n))
        if n <= k:
            return x_scaled.copy()
        order = np.argsort(scores)
        evenly = np.linspace(0, n - 1, k, dtype=int)
        return x_scaled[np.unique(order[evenly])]

    def _feature_category(self, name: str) -> str:
        item = self._feature_registry._COMMON_DEFINITIONS.get(name)
        return item.category if item is not None else "unknown"

    def _feature_display(self, name: str) -> str:
        if name in self._feature_registry._COMMON_DEFINITIONS:
            return self._feature_registry._COMMON_DEFINITIONS[name].display_name
        return name

    def _dynamic_lime_samples(self, n_features: int, n_points: int) -> int:
        base = max(80, int(self.config.lime_num_samples))
        return min(1200, base + n_features * 10 + n_points * 2)

    def _dynamic_shap_samples(self, selected_nsamples: int, n_features: int, n_points: int) -> int:
        base = max(40, int(selected_nsamples))
        penalty = int(max(0, n_features - 8) * 3 + max(0, n_points - 64) * 0.5)
        return max(40, min(base, base - penalty))

    def _effective_workers(self, n_tasks: int) -> int:
        return max(1, min(int(self.config.parallel_workers), int(n_tasks)))

    @staticmethod
    def _to_float32(arr: np.ndarray) -> np.ndarray:
        x = np.asarray(arr, dtype=float)
        if x.dtype == np.float32:
            return x
        return x.astype(np.float32, copy=False)

    def _predict_surrogate(self, context: dict[str, Any]) -> Callable[[np.ndarray], np.ndarray]:
        model: Ridge = context["surrogate"]
        return lambda x: model.predict(np.asarray(x, dtype=float))

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

        matrix, feature_names, pre_info = self._build_feature_matrix(model=model, coords=coords, values=values, batch_size=32)
        scaled_x, scaler_stats = self._preprocess(matrix, feature_names)
        score_bundle = self._predict_scores(model=model, coords=coords, values=values)
        target = np.asarray(score_bundle["combined"], dtype=float)

        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(scaled_x, target)

        pred_train = surrogate.predict(scaled_x)
        train_rmse = float(np.sqrt(np.mean((pred_train - target) ** 2))) if len(target) else 0.0
        target_std = float(np.std(target)) if len(target) else 0.0
        fidelity = float(max(0.0, 1.0 - train_rmse / (target_std + 1e-6))) if len(target) else 0.0

        context = {
            "context_key": key,
            "feature_matrix": self._to_float32(matrix),
            "scaled_x": self._to_float32(scaled_x),
            "feature_names": feature_names,
            "scaler_stats": scaler_stats,
            "score_bundle": score_bundle,
            "target": target,
            "surrogate": surrogate,
            "background": self._to_float32(self._select_background(scaled_x, target, size=48)),
            "preprocess": {
                "batch_slices": pre_info.get("batch_slices", []),
                "validation": pre_info.get("validation", {}),
            },
            "surrogate_metrics": {"train_rmse": train_rmse, "fidelity": fidelity},
        }
        self._context_set(key, context)
        return context

    def _anomaly_profile(self, scores: np.ndarray, explained_nodes: list[int]) -> dict[str, Any]:
        s = np.asarray(scores, dtype=float).reshape(-1)
        if s.size == 0:
            return {"stats": {"mean": 0.0, "std": 0.0, "p95": 0.0}, "node_labels": []}
        thr = float(np.percentile(s, 95))
        labels = (s >= thr).astype(int)
        return {
            "stats": {"mean": float(np.mean(s)), "std": float(np.std(s)), "p95": thr},
            "node_labels": [
                {"node_index": int(i), "score": float(s[i]), "label": int(labels[i])}
                for i in explained_nodes
                if 0 <= i < len(s)
            ],
        }

    def _score_decomposition(
        self,
        *,
        discriminator_scores: np.ndarray,
        reconstruction_scores: np.ndarray,
        gradient_scores: np.ndarray,
    ) -> dict[str, Any]:
        disc = np.asarray(discriminator_scores, dtype=float).reshape(-1)
        recon = np.asarray(reconstruction_scores, dtype=float).reshape(-1)
        grad = np.asarray(gradient_scores, dtype=float).reshape(-1)
        n = len(disc)
        rows: list[dict[str, Any]] = []
        for i in range(n):
            total = float(0.50 * disc[i] + 0.35 * recon[i] + 0.15 * grad[i])
            rows.append(
                {
                    "node_index": int(i),
                    "discriminator_component": float(disc[i]),
                    "reconstruction_component": float(recon[i]),
                    "gradient_component": float(grad[i]),
                    "decomposed_score": total,
                }
            )
        rows.sort(key=lambda item: float(item["decomposed_score"]), reverse=True)
        return {
            "decomposition": rows,
            "top_anomaly_nodes": [int(item["node_index"]) for item in rows[: max(1, min(10, n))]],
        }

    def _explanation_reason(
        self,
        *,
        node_idx: int,
        decomposition_row: dict[str, Any],
        top_contributions: list[dict[str, Any]],
    ) -> str:
        if not top_contributions:
            return f"节点{node_idx}异常主要由GAN判别器分数触发。"
        top_feat = top_contributions[0]
        return (
            f"节点{node_idx}异常由{top_feat['feature_alias']}驱动，"
            f"判别器分量{decomposition_row['discriminator_component']:.3f}、"
            f"重建分量{decomposition_row['reconstruction_component']:.3f}、"
            f"梯度分量{decomposition_row['gradient_component']:.3f}共同放大异常。"
        )

    def _validate_explanation_consistency(
        self,
        *,
        decomposition: list[dict[str, Any]],
        combined_scores: np.ndarray,
        explained_nodes: list[int],
    ) -> dict[str, Any]:
        if len(decomposition) == 0:
            return {"is_reasonable": False, "score_corr": 0.0, "coverage": 0.0}
        dec = np.asarray([item["decomposed_score"] for item in decomposition], dtype=float)
        node = np.asarray(combined_scores, dtype=float)
        if len(dec) != len(node):
            aligned = min(len(dec), len(node))
            dec = dec[:aligned]
            node = node[:aligned]
        corr = float(np.corrcoef(dec, node)[0, 1]) if len(dec) >= 2 and np.std(dec) > 1e-9 and np.std(node) > 1e-9 else 0.0
        coverage = float(len(explained_nodes) / max(1, len(node)))
        return {
            "is_reasonable": bool(corr >= 0.5),
            "score_corr": corr,
            "coverage": coverage,
        }

    def _generator_analysis(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> dict[str, Any]:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        noise = np.zeros_like(v)
        generated = model.generator(noise, c)
        residual = v - generated
        return {
            "stats": {
                "mean_residual": float(np.mean(residual)),
                "std_residual": float(np.std(residual)),
                "max_abs_residual": float(np.max(np.abs(residual))),
            },
            "node_analysis": [
                {
                    "node_index": int(i),
                    "real_value": float(v[i]),
                    "generated_value": float(generated[i]),
                    "residual": float(residual[i]),
                    "residual_zscore": float(z_i),
                }
                for i, z_i in enumerate(robust_zscore(residual).tolist())
            ],
        }


class GANAnomalyLimeAdapter(_BaseGANAdapter):
    """GAN 的 LIME 解释适配器。"""

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
        decomposition_payload = self._score_decomposition(
            discriminator_scores=np.asarray(context["score_bundle"]["discriminator"], dtype=float),
            reconstruction_scores=np.asarray(context["score_bundle"]["reconstruction"], dtype=float),
            gradient_scores=np.asarray(context["score_bundle"]["gradient"], dtype=float),
        )
        dec_by_node = {int(item["node_index"]): item for item in decomposition_payload["decomposition"]}

        def _explain_one(node_idx: int) -> dict[str, Any]:
            instance = np.asarray(context["scaled_x"][node_idx], dtype=float)
            local_pairs: list[tuple[int, float]]
            local_pred = float(predict_fn(instance.reshape(1, -1))[0])
            fidelity = float(context["surrogate_metrics"]["fidelity"])
            backend = "surrogate_linear"

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
                    backend = "lime_tabular"
                except Exception:
                    local_pairs, local_pred = self._fallback_local_pairs(context, node_idx)
            else:
                local_pairs, local_pred = self._fallback_local_pairs(context, node_idx)

            contributions: list[dict[str, Any]] = [
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
            truth = float(target[node_idx])
            dec_row = dec_by_node.get(int(node_idx), {"discriminator_component": 0.0, "reconstruction_component": 0.0, "gradient_component": 0.0})
            return {
                "node_index": int(node_idx),
                "prediction": local_pred,
                "target_prediction": truth,
                "fidelity": float(fidelity),
                "confidence": float(max(0.0, min(1.0, fidelity * np.exp(-abs(local_pred - truth))))),
                "backend": backend,
                "top_contributions": contributions,
                "decomposition": dec_row,
                "reason": self._explanation_reason(node_idx=int(node_idx), decomposition_row=dec_row, top_contributions=contributions),
            }

        workers = self._effective_workers(len(explained_nodes))
        if workers == 1:
            batch_explanations = [_explain_one(idx) for idx in explained_nodes]
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                batch_explanations = list(executor.map(_explain_one, explained_nodes))

        raw_importance = np.zeros((len(feature_names),), dtype=float)
        for item in batch_explanations:
            for contrib in item["top_contributions"]:
                raw_importance[int(contrib["feature_index"])] += float(abs(contrib["weight"]))
        order = np.argsort(-raw_importance).astype(int).tolist()
        top_features = [
            {
                "feature_index": int(idx),
                "feature_name": feature_names[idx],
                "feature_alias": self._feature_display(feature_names[idx]),
                "importance": float(raw_importance[idx] / max(1, len(batch_explanations))),
                "category": self._feature_category(feature_names[idx]),
            }
            for idx in order[: max(1, int(top_k))]
        ]

        combined = np.asarray(context["score_bundle"]["combined"], dtype=float)
        consistency = self._validate_explanation_consistency(
            decomposition=decomposition_payload["decomposition"],
            combined_scores=combined,
            explained_nodes=explained_nodes,
        )
        generator_info = self._generator_analysis(model=model, coords=c, values=v)
        payload = {
            "summary": {
                "method": "lime",
                "explained_nodes": len(explained_nodes),
                "num_samples": selected_samples,
                "num_features": len(feature_names),
                "top_features": top_features,
                "average_confidence": float(np.mean([item["confidence"] for item in batch_explanations])) if batch_explanations else 0.0,
                "surrogate_fidelity": float(context["surrogate_metrics"]["fidelity"]),
            },
            "feature_importance": raw_importance.astype(float).tolist(),
            "batch_explanations": batch_explanations,
            "global_feature_importance": top_features,
            "anomaly_score_explanation": {
                "decomposition": decomposition_payload["decomposition"],
                "key_anomaly_nodes": decomposition_payload["top_anomaly_nodes"],
                "consistency_validation": consistency,
            },
            "score_components": {
                "discriminator": np.asarray(context["score_bundle"]["discriminator"], dtype=float).astype(float).tolist(),
                "reconstruction": np.asarray(context["score_bundle"]["reconstruction"], dtype=float).astype(float).tolist(),
                "gradient": np.asarray(context["score_bundle"]["gradient"], dtype=float).astype(float).tolist(),
                "combined": combined.astype(float).tolist(),
            },
            "generator_analysis": generator_info,
            "anomaly_analysis": self._anomaly_profile(combined, explained_nodes),
            "preprocess": dict(context["preprocess"]),
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "parallel_workers": int(workers),
            },
        }
        self._cache_set(cache_key, payload)
        return payload


class GANAnomalySHAPAdapter(_BaseGANAdapter):
    """GAN 的 SHAP 解释适配器。"""

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
        effective_nsamples = self._dynamic_shap_samples(selected_nsamples, len(feature_names), len(v))
        decomposition_payload = self._score_decomposition(
            discriminator_scores=np.asarray(context["score_bundle"]["discriminator"], dtype=float),
            reconstruction_scores=np.asarray(context["score_bundle"]["reconstruction"], dtype=float),
            gradient_scores=np.asarray(context["score_bundle"]["gradient"], dtype=float),
        )
        dec_by_node = {int(item["node_index"]): item for item in decomposition_payload["decomposition"]}

        def _explain_one(node_idx: int) -> dict[str, Any]:
            instance = np.asarray(context["scaled_x"][node_idx], dtype=float)
            expected_value = float(surrogate.predict(baseline.reshape(1, -1))[0])
            backend = "surrogate_linear"
            if shap_module is not None:
                try:
                    explainer = shap_module.KernelExplainer(
                        lambda x: surrogate.predict(np.asarray(x, dtype=float)),
                        background,
                    )
                    values_arr = explainer.shap_values(
                        instance.reshape(1, -1),
                        nsamples=max(40, effective_nsamples),
                        l1_reg=f"num_features({max(4, int(self.config.shap_feature_cap))})",
                    )
                    if isinstance(values_arr, list):
                        values_arr = values_arr[0]
                    shap_values = np.asarray(values_arr, dtype=float).reshape(-1)
                    ev = getattr(explainer, "expected_value", expected_value)
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
            truth = float(target[node_idx])
            contributions: list[dict[str, Any]] = []
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
            contributions = contributions[: max(1, int(min(top_k, self.config.shap_feature_cap)))]
            dec_row = dec_by_node.get(int(node_idx), {"discriminator_component": 0.0, "reconstruction_component": 0.0, "gradient_component": 0.0})
            return {
                "node_index": int(node_idx),
                "prediction": pred,
                "target_prediction": truth,
                "expected_value": expected_value,
                "backend": backend,
                "confidence": float(np.exp(-abs(pred - truth) / (abs(truth) + 1e-6))),
                "top_contributions": contributions,
                "raw_shap_values": [float(x) for x in shap_values.tolist()],
                "decomposition": dec_row,
                "reason": self._explanation_reason(node_idx=int(node_idx), decomposition_row=dec_row, top_contributions=contributions),
            }

<!-- PLACEHOLDER_SHAP_AGGREGATE -->
