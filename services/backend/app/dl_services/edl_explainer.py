"""EDL 模型解释适配器（LIME/SHAP）。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import copy
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
class EDLExplanationConfig:
    lime_num_samples: int = 160
    shap_nsamples: int = 100
    max_explain_nodes: int = 8
    cache_size: int = 16
    random_state: int = 42


class _BaseEDLAdapter:
    def __init__(self, config: Optional[EDLExplanationConfig] = None) -> None:
        self.config = config or EDLExplanationConfig()
        self._lock = threading.Lock()
        self._result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._context_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._cache_hits = 0
        self._cache_misses = 0
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

    def _stable_hash(self, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            cached = self._result_cache.get(key)
            if cached is None:
                self._cache_misses += 1
                return None
            self._cache_hits += 1
            self._result_cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._result_cache[key] = copy.deepcopy(value)
            self._result_cache.move_to_end(key)
            while len(self._result_cache) > max(1, int(self.config.cache_size)):
                self._result_cache.popitem(last=False)

    def _context_cache_get(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            cached = self._context_cache.get(key)
            if cached is None:
                self._context_cache_misses += 1
                return None
            self._context_cache_hits += 1
            self._context_cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _context_cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._context_cache[key] = copy.deepcopy(value)
            self._context_cache.move_to_end(key)
            while len(self._context_cache) > max(1, int(self.config.cache_size)):
                self._context_cache.popitem(last=False)

    def _cache_metrics(self) -> dict[str, float | int]:
        with self._lock:
            total = self._cache_hits + self._cache_misses
            ctx_total = self._context_cache_hits + self._context_cache_misses
            return {
                "result_cache_hits": int(self._cache_hits),
                "result_cache_misses": int(self._cache_misses),
                "result_cache_hit_rate": float(self._cache_hits / max(1, total)),
                "context_cache_hits": int(self._context_cache_hits),
                "context_cache_misses": int(self._context_cache_misses),
                "context_cache_hit_rate": float(self._context_cache_hits / max(1, ctx_total)),
            }

    @staticmethod
    def _array_bytes(*arrays: np.ndarray) -> int:
        total = 0
        for arr in arrays:
            try:
                total += int(np.asarray(arr).nbytes)
            except Exception:
                continue
        return int(total)

    @staticmethod
    def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
        x = np.asarray(a, dtype=float).reshape(-1)
        y = np.asarray(b, dtype=float).reshape(-1)
        if x.size < 2 or y.size < 2:
            return 0.0
        if float(np.std(x)) < 1e-8 or float(np.std(y)) < 1e-8:
            return 0.0
        corr = float(np.corrcoef(x, y)[0, 1])
        return corr if np.isfinite(corr) else 0.0

    def _feature_fingerprint(self, x: np.ndarray) -> str:
        arr = np.ascontiguousarray(np.asarray(x, dtype=float))
        h = hashlib.sha256()
        h.update(str(tuple(int(v) for v in arr.shape)).encode("utf-8"))
        h.update(arr.tobytes())
        return h.hexdigest()

    def _model_fingerprint(self, model: Any) -> str:
        parts: list[float] = [float(len(getattr(model, "history", [])))]
        for attr in ("w1", "b1", "w2", "b2"):
            arr = np.asarray(getattr(model, attr, np.array([0.0])), dtype=float).reshape(-1)
            if arr.size == 0:
                continue
            parts.extend([float(np.mean(arr)), float(np.std(arr)), float(np.mean(np.abs(arr)))])
        normalized = ",".join(f"{v:.8f}" for v in parts)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _build_context(self, model: Any, features: np.ndarray) -> dict[str, Any]:
        x = np.asarray(features, dtype=float)
        pre = model.preprocess_edl_data(x, use_training_stats=True)
        pred = model.predict_edl(x, confidence=0.95, use_training_stats=True)

        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        evidence = np.asarray(pred["evidence"], dtype=float)
        alpha = np.asarray(pred["alpha"], dtype=float)
        probs = np.asarray(pred["probabilities"], dtype=float)
        labels = np.asarray(pred["prediction"], dtype=int).reshape(-1)
        confidence = np.asarray(pred["confidence"], dtype=float).reshape(-1)
        uncertainty_total = np.asarray(pred["uncertainty"]["total"], dtype=float).reshape(-1)
        uncertainty_data = np.asarray(pred["uncertainty"]["data"], dtype=float).reshape(-1)
        uncertainty_knowledge = np.asarray(pred["uncertainty"]["knowledge"], dtype=float).reshape(-1)

        if x_scaled.shape[0] != uncertainty_total.shape[0]:
            raise ValueError("EDL 预处理与预测样本数量不一致")

        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(x_scaled, uncertainty_total)
        baseline = np.mean(x_scaled, axis=0)
        background = x_scaled if x_scaled.shape[0] <= 24 else x_scaled[np.linspace(0, x_scaled.shape[0] - 1, 24, dtype=int)]
        return {
            "scaled_x": x_scaled,
            "evidence": evidence,
            "alpha": alpha,
            "feature_names": list(pre["feature_names"]),
            "probabilities": probs,
            "prediction_label": labels,
            "confidence": confidence,
            "uncertainty_total": uncertainty_total,
            "uncertainty_data": uncertainty_data,
            "uncertainty_knowledge": uncertainty_knowledge,
            "surrogate": surrogate,
            "baseline": np.asarray(baseline, dtype=float),
            "background": np.asarray(background, dtype=float),
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
            },
        }

    def _build_context_cached(self, model: Any, features: np.ndarray) -> tuple[dict[str, Any], bool, float]:
        x = np.asarray(features, dtype=float)
        context_key = self._stable_hash(
            {
                "feature_hash": self._feature_fingerprint(x),
                "shape": [int(x.shape[0]), int(x.shape[1]) if x.ndim == 2 else 0],
                "model_hash": self._model_fingerprint(model),
                "shap_nsamples": int(self.config.shap_nsamples),
            }
        )
        started = time.perf_counter()
        cached = self._context_cache_get(context_key)
        if cached is not None:
            return cached, True, float((time.perf_counter() - started) * 1000.0)

        built = self._build_context(model=model, features=x)
        self._context_cache_set(context_key, built)
        return built, False, float((time.perf_counter() - started) * 1000.0)

    @staticmethod
    def _top_features(feature_names: list[str], scores: np.ndarray, top_k: int) -> list[dict[str, float | str]]:
        arr = np.asarray(scores, dtype=float).reshape(-1)
        if arr.size == 0:
            return []
        k = max(1, min(int(top_k), arr.shape[0]))
        order = np.argsort(np.abs(arr))[::-1][:k]
        return [
            {
                "feature": str(feature_names[int(i)] if int(i) < len(feature_names) else f"feature_{int(i)}"),
                "score": float(arr[int(i)]),
                "abs_score": float(abs(arr[int(i)])),
            }
            for i in order.tolist()
        ]

    @staticmethod
    def _select_explained_nodes(total_uncertainty: np.ndarray, max_explain_nodes: int) -> list[int]:
        values = np.asarray(total_uncertainty, dtype=float).reshape(-1)
        if values.size == 0:
            return []
        n = max(1, min(int(max_explain_nodes), int(values.size)))
        return np.argsort(values)[::-1][:n].astype(int).tolist()

    def _predict_surrogate(self, context: dict[str, Any]) -> Callable[[np.ndarray], np.ndarray]:
        surrogate: Ridge = context["surrogate"]
        return lambda x: surrogate.predict(np.asarray(x, dtype=float))

    def _edl_advanced_analysis(self, context: dict[str, Any], *, top_k: int) -> dict[str, Any]:
        evidence = np.asarray(context.get("evidence", np.array([])), dtype=float)
        alpha = np.asarray(context.get("alpha", np.array([])), dtype=float)
        probs = np.asarray(context.get("probabilities", np.array([])), dtype=float)
        labels = np.asarray(context.get("prediction_label", np.array([])), dtype=int).reshape(-1)
        confidence = np.asarray(context.get("confidence", np.array([])), dtype=float).reshape(-1)
        total_unc = np.asarray(context.get("uncertainty_total", np.array([])), dtype=float).reshape(-1)
        data_unc = np.asarray(context.get("uncertainty_data", np.array([])), dtype=float).reshape(-1)
        knowledge_unc = np.asarray(context.get("uncertainty_knowledge", np.array([])), dtype=float).reshape(-1)
        total_evidence = np.sum(evidence, axis=1) if evidence.ndim == 2 else np.zeros_like(total_unc)
        dirichlet_strength = np.sum(alpha, axis=1) if alpha.ndim == 2 else np.zeros_like(total_unc)
        n = int(total_unc.size)
        c = int(evidence.shape[1]) if evidence.ndim == 2 else 0
        if n == 0:
            empty = {"summary": {"sample_count": 0}}
            return {
                "evidence_explanation": empty,
                "uncertainty_evidence_analysis": empty,
                "confidence_distribution_analysis": empty,
            }

        k = min(max(1, int(top_k)), n)
        high_evi_idx = np.argsort(total_evidence)[::-1][:k]
        low_evi_idx = np.argsort(total_evidence)[:k]
        high_unc_idx = np.argsort(total_unc)[::-1][:k]
        low_conf_idx = np.argsort(confidence)[:k]

        class_stats: list[dict[str, float | int]] = []
        mean_total = float(np.mean(total_evidence))
        for cls in range(c):
            cls_e = evidence[:, cls]
            class_stats.append(
                {
                    "class_index": int(cls),
                    "mean_evidence": float(np.mean(cls_e)),
                    "std_evidence": float(np.std(cls_e)),
                    "p90_evidence": float(np.quantile(cls_e, 0.9)),
                    "support_ratio_over_mean_total_per_class": float(np.mean(cls_e > (mean_total / float(max(c, 1))))),
                }
            )

        q_edges = np.quantile(total_evidence, [0.0, 0.33, 0.66, 1.0])
        bins = [("low", q_edges[0], q_edges[1]), ("medium", q_edges[1], q_edges[2]), ("high", q_edges[2], q_edges[3])]
        profile: list[dict[str, float | int | str]] = []
        for label, left, right in bins:
            if label == "high":
                mask = (total_evidence >= left) & (total_evidence <= right)
            else:
                mask = (total_evidence >= left) & (total_evidence < right)
            if not np.any(mask):
                profile.append(
                    {
                        "evidence_level": label,
                        "sample_count": 0,
                        "mean_total_evidence": 0.0,
                        "mean_total_uncertainty": 0.0,
                        "mean_knowledge_uncertainty": 0.0,
                        "mean_data_uncertainty": 0.0,
                        "mean_confidence": 0.0,
                    }
                )
                continue
            profile.append(
                {
                    "evidence_level": label,
                    "sample_count": int(np.sum(mask)),
                    "mean_total_evidence": float(np.mean(total_evidence[mask])),
                    "mean_total_uncertainty": float(np.mean(total_unc[mask])),
                    "mean_knowledge_uncertainty": float(np.mean(knowledge_unc[mask])),
                    "mean_data_uncertainty": float(np.mean(data_unc[mask])),
                    "mean_confidence": float(np.mean(confidence[mask])),
                }
            )

        conf_quantiles = np.quantile(confidence, [0.05, 0.25, 0.5, 0.75, 0.95])
        unc_quantiles = np.quantile(total_unc, [0.05, 0.25, 0.5, 0.75, 0.95])
        pred_entropy = -np.sum(probs * np.log(np.maximum(probs, 1e-8)), axis=1) if probs.ndim == 2 else np.zeros(n, dtype=float)
        centered = confidence - np.mean(confidence)
        conf_std = float(np.std(confidence))
        skew = float(np.mean(centered ** 3) / (max(conf_std, 1e-8) ** 3)) if n > 0 else 0.0
        kurt = float(np.mean(centered ** 4) / (max(conf_std, 1e-8) ** 4) - 3.0) if n > 0 else 0.0
        if not np.isfinite(skew):
            skew = 0.0
        if not np.isfinite(kurt):
            kurt = 0.0

        evidence_explanation = {
            "summary": {
                "sample_count": int(n),
                "num_classes": int(c),
                "mean_total_evidence": float(np.mean(total_evidence)),
                "p90_total_evidence": float(np.quantile(total_evidence, 0.9)),
                "mean_dirichlet_strength": float(np.mean(dirichlet_strength)),
                "mean_confidence": float(np.mean(confidence)),
                "mean_total_uncertainty": float(np.mean(total_unc)),
            },
            "class_evidence_statistics": class_stats,
            "top_high_evidence_samples": [
                {
                    "sample_index": int(i),
                    "prediction_label": int(labels[int(i)] if int(i) < labels.size else int(np.argmax(probs[int(i)]))),
                    "total_evidence": float(total_evidence[int(i)]),
                    "dirichlet_strength": float(dirichlet_strength[int(i)]),
                    "confidence": float(confidence[int(i)]),
                    "total_uncertainty": float(total_unc[int(i)]),
                }
                for i in high_evi_idx.tolist()
            ],
            "top_low_evidence_samples": [
                {
                    "sample_index": int(i),
                    "prediction_label": int(labels[int(i)] if int(i) < labels.size else int(np.argmax(probs[int(i)]))),
                    "total_evidence": float(total_evidence[int(i)]),
                    "dirichlet_strength": float(dirichlet_strength[int(i)]),
                    "confidence": float(confidence[int(i)]),
                    "total_uncertainty": float(total_unc[int(i)]),
                }
                for i in low_evi_idx.tolist()
            ],
        }

        uncertainty_evidence_analysis = {
            "summary": {
                "sample_count": int(n),
                "mean_total_evidence": float(np.mean(total_evidence)),
                "mean_total_uncertainty": float(np.mean(total_unc)),
                "corr_total_uncertainty_total_evidence": self._safe_corr(total_unc, total_evidence),
                "corr_knowledge_uncertainty_total_evidence": self._safe_corr(knowledge_unc, total_evidence),
                "corr_data_uncertainty_total_evidence": self._safe_corr(data_unc, total_evidence),
                "corr_confidence_total_evidence": self._safe_corr(confidence, total_evidence),
            },
            "evidence_uncertainty_profile": profile,
            "top_high_uncertainty_samples": [
                {
                    "sample_index": int(i),
                    "prediction_label": int(labels[int(i)] if int(i) < labels.size else int(np.argmax(probs[int(i)]))),
                    "total_uncertainty": float(total_unc[int(i)]),
                    "knowledge_uncertainty": float(knowledge_unc[int(i)]),
                    "data_uncertainty": float(data_unc[int(i)]),
                    "total_evidence": float(total_evidence[int(i)]),
                    "confidence": float(confidence[int(i)]),
                }
                for i in high_unc_idx.tolist()
            ],
        }

        confidence_distribution_analysis = {
            "summary": {
                "sample_count": int(n),
                "mean_confidence": float(np.mean(confidence)),
                "std_confidence": float(np.std(confidence)),
                "p10_confidence": float(np.quantile(confidence, 0.1)),
                "p90_confidence": float(np.quantile(confidence, 0.9)),
                "mean_total_uncertainty": float(np.mean(total_unc)),
                "mean_prediction_entropy": float(np.mean(pred_entropy)),
                "mean_knowledge_uncertainty": float(np.mean(knowledge_unc)),
                "mean_data_uncertainty": float(np.mean(data_unc)),
                "corr_confidence_total_uncertainty": self._safe_corr(confidence, total_unc),
                "corr_confidence_entropy": self._safe_corr(confidence, pred_entropy),
                "confidence_skewness": skew,
                "confidence_excess_kurtosis": kurt,
            },
            "quantiles": {
                "q05": {"confidence": float(conf_quantiles[0]), "total_uncertainty": float(unc_quantiles[0])},
                "q25": {"confidence": float(conf_quantiles[1]), "total_uncertainty": float(unc_quantiles[1])},
                "q50": {"confidence": float(conf_quantiles[2]), "total_uncertainty": float(unc_quantiles[2])},
                "q75": {"confidence": float(conf_quantiles[3]), "total_uncertainty": float(unc_quantiles[3])},
                "q95": {"confidence": float(conf_quantiles[4]), "total_uncertainty": float(unc_quantiles[4])},
            },
            "top_low_confidence_samples": [
                {
                    "sample_index": int(i),
                    "prediction_label": int(labels[int(i)] if int(i) < labels.size else int(np.argmax(probs[int(i)]))),
                    "confidence": float(confidence[int(i)]),
                    "total_uncertainty": float(total_unc[int(i)]),
                    "knowledge_uncertainty": float(knowledge_unc[int(i)]),
                    "data_uncertainty": float(data_unc[int(i)]),
                    "prediction_entropy": float(pred_entropy[int(i)]),
                }
                for i in low_conf_idx.tolist()
            ],
        }
        return {
            "evidence_explanation": evidence_explanation,
            "uncertainty_evidence_analysis": uncertainty_evidence_analysis,
            "confidence_distribution_analysis": confidence_distribution_analysis,
        }

    def _fallback_local_pairs(self, context: dict[str, Any], node_index: int) -> tuple[list[tuple[int, float]], float]:
        surrogate: Ridge = context["surrogate"]
        instance = np.asarray(context["scaled_x"][node_index], dtype=float)
        local = np.asarray(surrogate.coef_, dtype=float).reshape(-1) * instance
        pred = float(surrogate.predict(instance.reshape(1, -1))[0])
        pairs = [(int(i), float(local[i])) for i in range(local.shape[0])]
        return pairs, pred


class EDLLIMEAdapter(_BaseEDLAdapter):
    """EDL 的 LIME 解释适配器。"""

    def explain(
        self,
        *,
        model: Any,
        features: np.ndarray | list[list[float]],
        top_k: int = 5,
        max_explain_nodes: int | None = None,
        num_samples: int | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        x = np.asarray(features, dtype=float)
        explain_nodes = int(max_explain_nodes or self.config.max_explain_nodes)
        effective_samples = int(num_samples or self.config.lime_num_samples)
        cache_key = self._stable_hash(
            {
                "method": "lime",
                "shape": [int(x.shape[0]), int(x.shape[1]) if x.ndim == 2 else 0],
                "feature_hash": hashlib.md5(np.ascontiguousarray(x).tobytes()).hexdigest(),
                "top_k": int(top_k),
                "max_explain_nodes": int(explain_nodes),
                "num_samples": int(effective_samples),
            }
        )

        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["performance"] = {
                **dict(cached.get("performance", {})),
                "cache_hit": True,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                **self._cache_metrics(),
            }
            return cached

        context, context_cache_hit, context_build_ms = self._build_context_cached(model=model, features=x)
        node_indices = self._select_explained_nodes(context["uncertainty_total"], explain_nodes)
        predict_fn = self._predict_surrogate(context)
        lime_module = self._load_lime_tabular()
        lime_explainer = None
        if lime_module is not None:
            try:
                lime_explainer = lime_module.LimeTabularExplainer(
                    training_data=np.asarray(context["scaled_x"], dtype=float),
                    feature_names=list(context["feature_names"]),
                    mode="regression",
                    random_state=int(self.config.random_state),
                )
            except Exception:
                lime_explainer = None

        batch_explanations: list[dict[str, Any]] = []
        raw_local: list[list[float]] = []
        for idx in node_indices:
            pairs: list[tuple[int, float]]
            local_pred: float
            if lime_explainer is not None:
                try:
                    instance = np.asarray(context["scaled_x"][idx], dtype=float)
                    exp = lime_explainer.explain_instance(
                        instance,
                        predict_fn=predict_fn,
                        num_features=int(np.asarray(instance).shape[0]),
                        num_samples=max(40, int(effective_samples)),
                    )
                    pairs = [(int(i), float(v)) for i, v in exp.local_exp.get(1, [])]
                    local_pred = _safe_float(
                        getattr(exp, "predicted_value", [0.0])[0],
                        float(predict_fn(instance.reshape(1, -1))[0]),
                    )
                except Exception:
                    pairs, local_pred = self._fallback_local_pairs(context, idx)
            else:
                pairs, local_pred = self._fallback_local_pairs(context, idx)

            local_arr = np.zeros(len(context["feature_names"]), dtype=float)
            for f_idx, score in pairs:
                if 0 <= int(f_idx) < local_arr.shape[0]:
                    local_arr[int(f_idx)] = float(score)
            raw_local.append([float(v) for v in local_arr.tolist()])
            batch_explanations.append(
                {
                    "node_index": int(idx),
                    "prediction_label": int(context["prediction_label"][idx]),
                    "confidence": float(context["confidence"][idx]),
                    "uncertainty_total": float(context["uncertainty_total"][idx]),
                    "uncertainty_data": float(context["uncertainty_data"][idx]),
                    "uncertainty_knowledge": float(context["uncertainty_knowledge"][idx]),
                    "surrogate_prediction": float(local_pred),
                    "top_contributions": self._top_features(context["feature_names"], local_arr, int(top_k)),
                    "raw_local_weights": [float(v) for v in local_arr.tolist()],
                }
            )

        global_importance = np.mean(np.abs(np.asarray(raw_local, dtype=float)), axis=0) if raw_local else np.zeros(0, dtype=float)
        advanced = self._edl_advanced_analysis(context, top_k=int(top_k))
        context_memory_bytes = self._array_bytes(
            np.asarray(context.get("scaled_x", np.array([])), dtype=np.float32),
            np.asarray(context.get("evidence", np.array([])), dtype=np.float32),
            np.asarray(context.get("alpha", np.array([])), dtype=np.float32),
            np.asarray(context.get("probabilities", np.array([])), dtype=np.float32),
            np.asarray(context.get("uncertainty_total", np.array([])), dtype=np.float32),
            np.asarray(context.get("uncertainty_data", np.array([])), dtype=np.float32),
            np.asarray(context.get("uncertainty_knowledge", np.array([])), dtype=np.float32),
            np.asarray(context.get("background", np.array([])), dtype=np.float32),
        )
        result_memory_bytes = self._array_bytes(np.asarray(raw_local, dtype=np.float32))
        payload = {
            "summary": {
                "method": "lime",
                "explained_nodes": int(len(node_indices)),
                "num_features": int(len(context["feature_names"])),
                "num_samples": int(effective_samples),
                "sample_count": int(np.asarray(context["scaled_x"]).shape[0]),
            },
            "batch_explanations": batch_explanations,
            "global_feature_importance": self._top_features(context["feature_names"], global_importance, len(context["feature_names"])),
            "evidence_explanation": advanced["evidence_explanation"],
            "uncertainty_evidence_analysis": advanced["uncertainty_evidence_analysis"],
            "confidence_distribution_analysis": advanced["confidence_distribution_analysis"],
            "preprocess": dict(context["preprocess"]),
            "explainer": {
                "backend": "lime_tabular" if lime_module is not None else "surrogate_linear",
            },
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                "context_cache_hit": bool(context_cache_hit),
                "context_build_ms": float(context_build_ms),
                "sample_count": int(np.asarray(context["scaled_x"]).shape[0]),
                "feature_dim": int(np.asarray(context["scaled_x"]).shape[1]) if np.asarray(context["scaled_x"]).ndim == 2 else 0,
                "context_memory_bytes": int(context_memory_bytes),
                "result_memory_bytes": int(result_memory_bytes),
                "latency_target_ms": 6000.0,
                "meets_latency_target": float((time.perf_counter() - started) * 1000.0) < 6000.0,
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, payload)
        return payload


class EDLSHAPAdapter(_BaseEDLAdapter):
    """EDL 的 SHAP 解释适配器。"""

    def explain(
        self,
        *,
        model: Any,
        features: np.ndarray | list[list[float]],
        top_k: int = 5,
        max_explain_nodes: int | None = None,
        nsamples: int | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        x = np.asarray(features, dtype=float)
        explain_nodes = int(max_explain_nodes or self.config.max_explain_nodes)
        effective_nsamples = int(nsamples or self.config.shap_nsamples)
        cache_key = self._stable_hash(
            {
                "method": "shap",
                "shape": [int(x.shape[0]), int(x.shape[1]) if x.ndim == 2 else 0],
                "feature_hash": hashlib.md5(np.ascontiguousarray(x).tobytes()).hexdigest(),
                "top_k": int(top_k),
                "max_explain_nodes": int(explain_nodes),
                "nsamples": int(effective_nsamples),
            }
        )

        cached = self._cache_get(cache_key)
        if cached is not None:
            cached["performance"] = {
                **dict(cached.get("performance", {})),
                "cache_hit": True,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                **self._cache_metrics(),
            }
            return cached

        context, context_cache_hit, context_build_ms = self._build_context_cached(model=model, features=x)
        node_indices = self._select_explained_nodes(context["uncertainty_total"], explain_nodes)
        surrogate: Ridge = context["surrogate"]
        baseline = np.asarray(context["baseline"], dtype=float).reshape(-1)
        shap_module = self._load_shap()
        shap_explainer = None
        if shap_module is not None:
            try:
                shap_explainer = shap_module.KernelExplainer(
                    lambda data: surrogate.predict(np.asarray(data, dtype=float)),
                    np.asarray(context["background"], dtype=float),
                )
            except Exception:
                shap_explainer = None

        batch_explanations: list[dict[str, Any]] = []
        raw_values: list[list[float]] = []
        for idx in node_indices:
            instance = np.asarray(context["scaled_x"][idx], dtype=float).reshape(-1)
            expected_value = float(surrogate.predict(baseline.reshape(1, -1))[0])
            backend = "surrogate_linear"
            if shap_explainer is not None:
                try:
                    shap_arr = shap_explainer.shap_values(instance.reshape(1, -1), nsamples=max(20, int(effective_nsamples)))
                    if isinstance(shap_arr, list):
                        shap_arr = shap_arr[0]
                    shap_values = np.asarray(shap_arr, dtype=float).reshape(-1)
                    ev = getattr(shap_explainer, "expected_value", expected_value)
                    if isinstance(ev, (list, tuple, np.ndarray)):
                        expected_value = _safe_float(np.asarray(ev).reshape(-1)[0], expected_value)
                    else:
                        expected_value = _safe_float(ev, expected_value)
                    backend = "shap_kernel"
                except Exception:
                    shap_values = np.asarray(surrogate.coef_, dtype=float).reshape(-1) * (instance - baseline)
            else:
                shap_values = np.asarray(surrogate.coef_, dtype=float).reshape(-1) * (instance - baseline)

            pred_value = float(surrogate.predict(instance.reshape(1, -1))[0])
            raw_values.append([float(v) for v in shap_values.tolist()])
            batch_explanations.append(
                {
                    "node_index": int(idx),
                    "prediction_label": int(context["prediction_label"][idx]),
                    "confidence": float(context["confidence"][idx]),
                    "uncertainty_total": float(context["uncertainty_total"][idx]),
                    "uncertainty_data": float(context["uncertainty_data"][idx]),
                    "uncertainty_knowledge": float(context["uncertainty_knowledge"][idx]),
                    "surrogate_prediction": pred_value,
                    "expected_value": float(expected_value),
                    "top_contributions": self._top_features(context["feature_names"], shap_values, int(top_k)),
                    "raw_shap_values": [float(v) for v in shap_values.tolist()],
                    "backend": backend,
                }
            )

        global_importance = np.mean(np.abs(np.asarray(raw_values, dtype=float)), axis=0) if raw_values else np.zeros(0, dtype=float)
        advanced = self._edl_advanced_analysis(context, top_k=int(top_k))
        context_memory_bytes = self._array_bytes(
            np.asarray(context.get("scaled_x", np.array([])), dtype=np.float32),
            np.asarray(context.get("evidence", np.array([])), dtype=np.float32),
            np.asarray(context.get("alpha", np.array([])), dtype=np.float32),
            np.asarray(context.get("probabilities", np.array([])), dtype=np.float32),
            np.asarray(context.get("uncertainty_total", np.array([])), dtype=np.float32),
            np.asarray(context.get("uncertainty_data", np.array([])), dtype=np.float32),
            np.asarray(context.get("uncertainty_knowledge", np.array([])), dtype=np.float32),
            np.asarray(context.get("background", np.array([])), dtype=np.float32),
        )
        result_memory_bytes = self._array_bytes(np.asarray(raw_values, dtype=np.float32))
        payload = {
            "summary": {
                "method": "shap",
                "explained_nodes": int(len(node_indices)),
                "num_features": int(len(context["feature_names"])),
                "nsamples": int(effective_nsamples),
                "sample_count": int(np.asarray(context["scaled_x"]).shape[0]),
            },
            "batch_explanations": batch_explanations,
            "global_feature_importance": self._top_features(context["feature_names"], global_importance, len(context["feature_names"])),
            "evidence_explanation": advanced["evidence_explanation"],
            "uncertainty_evidence_analysis": advanced["uncertainty_evidence_analysis"],
            "confidence_distribution_analysis": advanced["confidence_distribution_analysis"],
            "preprocess": dict(context["preprocess"]),
            "explainer": {
                "backend": "shap" if shap_module is not None else "surrogate_linear",
                "background_size": int(np.asarray(context["background"]).shape[0]),
            },
            "performance": {
                "cache_hit": False,
                "latency_ms": float((time.perf_counter() - started) * 1000.0),
                "context_cache_hit": bool(context_cache_hit),
                "context_build_ms": float(context_build_ms),
                "sample_count": int(np.asarray(context["scaled_x"]).shape[0]),
                "feature_dim": int(np.asarray(context["scaled_x"]).shape[1]) if np.asarray(context["scaled_x"]).ndim == 2 else 0,
                "context_memory_bytes": int(context_memory_bytes),
                "result_memory_bytes": int(result_memory_bytes),
                "latency_target_ms": 6000.0,
                "meets_latency_target": float((time.perf_counter() - started) * 1000.0) < 6000.0,
                **self._cache_metrics(),
            },
        }
        self._cache_set(cache_key, payload)
        return payload
