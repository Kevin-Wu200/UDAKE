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
            "generator_artifacts": {
                "generated_values": self._to_float32(np.asarray(pre_info.get("generated_values", []), dtype=float)),
                "latent_projection": self._to_float32(np.asarray(pre_info.get("latent_projection", []), dtype=float)),
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
            disc_weighted = float(0.50 * disc[i])
            recon_weighted = float(0.35 * recon[i])
            grad_weighted = float(0.15 * grad[i])
            generator_weighted = float(recon_weighted + grad_weighted)
            total = float(disc_weighted + generator_weighted)
            rows.append(
                {
                    "node_index": int(i),
                    "discriminator_component": float(disc[i]),
                    "reconstruction_component": float(recon[i]),
                    "gradient_component": float(grad[i]),
                    "discriminator_weighted_component": disc_weighted,
                    "generator_reconstruction_component": recon_weighted,
                    "generator_gradient_component": grad_weighted,
                    "generator_weighted_component": generator_weighted,
                    "decomposed_score": total,
                }
            )
        rows.sort(key=lambda item: float(item["decomposed_score"]), reverse=True)
        return {
            "decomposition": rows,
            "top_anomaly_nodes": [int(item["node_index"]) for item in rows[: max(1, min(10, n))]],
        }

    def _component_contribution_analysis(
        self,
        *,
        decomposition: list[dict[str, Any]],
        explained_nodes: list[int],
    ) -> dict[str, Any]:
        if len(decomposition) == 0:
            return {
                "discriminator_total": 0.0,
                "generator_total": 0.0,
                "discriminator_ratio": 0.0,
                "generator_ratio": 0.0,
                "explained_node_breakdown": [],
            }

        disc_total = float(np.sum([float(item.get("discriminator_weighted_component", 0.0)) for item in decomposition]))
        gen_total = float(np.sum([float(item.get("generator_weighted_component", 0.0)) for item in decomposition]))
        total = disc_total + gen_total + 1e-9
        node_set = set(int(i) for i in explained_nodes)
        node_rows = [item for item in decomposition if int(item.get("node_index", -1)) in node_set]
        node_rows.sort(key=lambda item: float(item.get("decomposed_score", 0.0)), reverse=True)
        breakdown = [
            {
                "node_index": int(item["node_index"]),
                "discriminator_weighted_component": float(item.get("discriminator_weighted_component", 0.0)),
                "generator_weighted_component": float(item.get("generator_weighted_component", 0.0)),
                "generator_reconstruction_component": float(item.get("generator_reconstruction_component", 0.0)),
                "generator_gradient_component": float(item.get("generator_gradient_component", 0.0)),
                "decomposed_score": float(item.get("decomposed_score", 0.0)),
            }
            for item in node_rows
        ]
        return {
            "discriminator_total": disc_total,
            "generator_total": gen_total,
            "discriminator_ratio": float(disc_total / total),
            "generator_ratio": float(gen_total / total),
            "explained_node_breakdown": breakdown,
        }

    def _extract_key_anomaly_features(self, *, batch_explanations: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        if len(batch_explanations) == 0:
            return []
        feature_agg: dict[str, dict[str, Any]] = {}
        for item in batch_explanations:
            node_idx = int(item.get("node_index", -1))
            for contrib in item.get("top_contributions", []):
                name = str(contrib.get("feature_name", ""))
                alias = str(contrib.get("feature_alias", name))
                category = str(contrib.get("category", "unknown"))
                score = float(
                    contrib.get(
                        "abs_weight",
                        contrib.get("abs_shap", abs(float(contrib.get("weight", contrib.get("shap_value", 0.0))))),
                    )
                )
                if name not in feature_agg:
                    feature_agg[name] = {
                        "feature_name": name,
                        "feature_alias": alias,
                        "category": category,
                        "importance_sum": 0.0,
                        "mention_count": 0,
                        "nodes": set(),
                    }
                feature_agg[name]["importance_sum"] = float(feature_agg[name]["importance_sum"] + score)
                feature_agg[name]["mention_count"] = int(feature_agg[name]["mention_count"] + 1)
                feature_agg[name]["nodes"].add(node_idx)

        size = float(max(1, len(batch_explanations)))
        rows = []
        for item in feature_agg.values():
            rows.append(
                {
                    "feature_name": str(item["feature_name"]),
                    "feature_alias": str(item["feature_alias"]),
                    "category": str(item["category"]),
                    "importance": float(item["importance_sum"] / size),
                    "mention_count": int(item["mention_count"]),
                    "covered_nodes": sorted(int(i) for i in item["nodes"]),
                }
            )
        rows.sort(key=lambda x: float(x["importance"]), reverse=True)
        return rows[: max(1, int(top_k))]

    def _collect_anomaly_reasons(self, *, batch_explanations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = [
            {
                "node_index": int(item.get("node_index", -1)),
                "reason": str(item.get("reason", "")),
                "confidence": float(item.get("confidence", 0.0)),
            }
            for item in batch_explanations
        ]
        rows.sort(key=lambda x: float(x.get("confidence", 0.0)), reverse=True)
        return rows

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

    def _generator_analysis(
        self,
        *,
        model: Any,
        coords: np.ndarray,
        values: np.ndarray,
        score_bundle: Optional[dict[str, np.ndarray]] = None,
        generator_artifacts: Optional[dict[str, np.ndarray]] = None,
    ) -> dict[str, Any]:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        if generator_artifacts is not None and "generated_values" in generator_artifacts:
            generated = np.asarray(generator_artifacts.get("generated_values", []), dtype=float).reshape(-1)
            if len(generated) != len(v):
                generated = np.asarray(model.generator(np.zeros_like(v), c), dtype=float).reshape(-1)
        else:
            generated = np.asarray(model.generator(np.zeros_like(v), c), dtype=float).reshape(-1)

        if generator_artifacts is not None and "latent_projection" in generator_artifacts:
            latent = np.asarray(generator_artifacts.get("latent_projection", []), dtype=float).reshape(-1)
            if len(latent) != len(v):
                pre = model.preprocess_gan_data(c, v, batch_size=32, use_training_stats=True)
                latent = np.asarray(pre.get("latent_projection", []), dtype=float).reshape(-1)
        else:
            pre = model.preprocess_gan_data(c, v, batch_size=32, use_training_stats=True)
            latent = np.asarray(pre.get("latent_projection", []), dtype=float).reshape(-1)

        bundle = score_bundle or self._predict_scores(model=model, coords=c, values=v)
        disc = np.asarray(bundle.get("discriminator", []), dtype=float).reshape(-1)
        recon = np.asarray(bundle.get("reconstruction", []), dtype=float).reshape(-1)
        grad = np.asarray(bundle.get("gradient", []), dtype=float).reshape(-1)
        combined = np.asarray(bundle.get("combined", []), dtype=float).reshape(-1)
        residual = v - generated
        abs_residual = np.abs(residual)
        residual_z = robust_zscore(residual) if len(residual) else np.array([], dtype=float)

        real_mean = float(np.mean(v)) if len(v) else 0.0
        real_std = float(np.std(v)) if len(v) else 0.0
        gen_mean = float(np.mean(generated)) if len(generated) else 0.0
        gen_std = float(np.std(generated)) if len(generated) else 0.0
        corr = 0.0
        if len(v) >= 2 and real_std > 1e-9 and gen_std > 1e-9:
            corr = float(np.corrcoef(v, generated)[0, 1])
        mae = float(np.mean(abs_residual)) if len(abs_residual) else 0.0
        rmse = float(np.sqrt(np.mean(residual**2))) if len(residual) else 0.0
        mape = float(np.mean(abs_residual / (np.abs(v) + 1e-6))) if len(v) else 0.0
        value_span = float(np.max(v) - np.min(v)) if len(v) else 0.0
        nrmse = float(rmse / (value_span + 1e-6))
        ss_res = float(np.sum(residual**2)) if len(residual) else 0.0
        ss_tot = float(np.sum((v - np.mean(v)) ** 2)) if len(v) else 0.0
        r2 = float(1.0 - ss_res / (ss_tot + 1e-9)) if len(v) else 0.0

        latent_mean = float(np.mean(latent)) if len(latent) else 0.0
        latent_std = float(np.std(latent)) if len(latent) else 0.0
        latent_centered = latent - latent_mean if len(latent) else np.array([], dtype=float)
        latent_skew = float(np.mean((latent_centered / (latent_std + 1e-6)) ** 3)) if len(latent) else 0.0
        latent_kurt = float(np.mean((latent_centered / (latent_std + 1e-6)) ** 4) - 3.0) if len(latent) else 0.0
        latent_q = np.percentile(latent, [5, 25, 50, 75, 95]).astype(float).tolist() if len(latent) else [0.0] * 5
        hist_values: list[float]
        if len(latent):
            hist, _ = np.histogram(latent, bins=min(10, max(4, len(latent) // 4)), density=False)
            hist_values = hist.astype(float).tolist()
        else:
            hist_values = []
        hist_sum = float(np.sum(hist_values)) if hist_values else 0.0
        prob = np.asarray(hist_values, dtype=float) / (hist_sum + 1e-9) if hist_values else np.array([], dtype=float)
        entropy = float(-np.sum(prob * np.log(prob + 1e-9))) if len(prob) else 0.0
        active_bin_ratio = float(np.mean(prob > 0.05)) if len(prob) else 0.0
        latent_outlier_ratio = float(np.mean(np.abs(robust_zscore(latent)) >= 2.5)) if len(latent) else 0.0

        mode_collapse_from_history = bool(any(float(item.get("mode_collapse", 0.0)) > 0.0 for item in getattr(model, "history", [])))
        mode_collapse_risk = bool(mode_collapse_from_history or latent_std <= 0.03 or entropy < 0.8 or active_bin_ratio < 0.3)

        residual_thr = float(np.percentile(abs_residual, 90)) if len(abs_residual) else 0.0
        recon_thr = float(np.percentile(recon, 85)) if len(recon) else 0.0
        grad_thr = float(np.percentile(grad, 85)) if len(grad) else 0.0
        candidates = []
        for i in range(len(v)):
            recon_hit = bool(i < len(recon) and recon[i] >= recon_thr)
            grad_hit = bool(i < len(grad) and grad[i] >= grad_thr)
            resid_hit = bool(abs_residual[i] >= residual_thr)
            if not (recon_hit or grad_hit or resid_hit):
                continue
            pattern_type = "under_generation" if residual[i] > 0 else "over_generation"
            if recon_hit and grad_hit:
                pattern_type = "structural_shift"
            severity = float(
                abs_residual[i] / (residual_thr + 1e-6)
                + (float(recon[i]) if i < len(recon) else 0.0)
                + (float(grad[i]) if i < len(grad) else 0.0)
            )
            candidates.append(
                {
                    "node_index": int(i),
                    "pattern_type": pattern_type,
                    "real_value": float(v[i]),
                    "generated_value": float(generated[i]),
                    "residual": float(residual[i]),
                    "abs_residual": float(abs_residual[i]),
                    "residual_zscore": float(residual_z[i]) if i < len(residual_z) else 0.0,
                    "reconstruction_score": float(recon[i]) if i < len(recon) else 0.0,
                    "gradient_score": float(grad[i]) if i < len(grad) else 0.0,
                    "discriminator_score": float(disc[i]) if i < len(disc) else 0.0,
                    "combined_score": float(combined[i]) if i < len(combined) else 0.0,
                    "severity": severity,
                }
            )
        candidates.sort(key=lambda x: float(x["severity"]), reverse=True)
        top_patterns = candidates[: max(1, min(8, len(candidates)))] if candidates else []

        high_residual_idx = np.argsort(-abs_residual).astype(int).tolist()[: max(1, min(6, len(v)))] if len(v) else []
        low_residual_idx = np.argsort(abs_residual).astype(int).tolist()[: max(1, min(6, len(v)))] if len(v) else []
        comparison_anomalous = [
            {
                "node_index": int(i),
                "real_value": float(v[i]),
                "generated_value": float(generated[i]),
                "residual": float(residual[i]),
                "abs_residual": float(abs_residual[i]),
                "residual_ratio": float(abs_residual[i] / (abs(v[i]) + 1e-6)),
                "pattern_type": next((str(item["pattern_type"]) for item in top_patterns if int(item["node_index"]) == int(i)), "under_generation" if residual[i] > 0 else "over_generation"),
                "combined_score": float(combined[i]) if i < len(combined) else 0.0,
            }
            for i in high_residual_idx
        ]
        comparison_reference = [
            {
                "node_index": int(i),
                "real_value": float(v[i]),
                "generated_value": float(generated[i]),
                "residual": float(residual[i]),
                "abs_residual": float(abs_residual[i]),
                "residual_ratio": float(abs_residual[i] / (abs(v[i]) + 1e-6)),
                "combined_score": float(combined[i]) if i < len(combined) else 0.0,
            }
            for i in low_residual_idx
        ]

        pattern_counts = {"under_generation": 0, "over_generation": 0, "structural_shift": 0}
        for item in top_patterns:
            key = str(item["pattern_type"])
            if key in pattern_counts:
                pattern_counts[key] += 1

        return {
            "output_analysis": {
                "real_stats": {
                    "mean": real_mean,
                    "std": real_std,
                    "min": float(np.min(v)) if len(v) else 0.0,
                    "max": float(np.max(v)) if len(v) else 0.0,
                },
                "generated_stats": {
                    "mean": gen_mean,
                    "std": gen_std,
                    "min": float(np.min(generated)) if len(generated) else 0.0,
                    "max": float(np.max(generated)) if len(generated) else 0.0,
                },
                "residual_stats": {
                    "mean": float(np.mean(residual)) if len(residual) else 0.0,
                    "std": float(np.std(residual)) if len(residual) else 0.0,
                    "mae": mae,
                    "max_abs": float(np.max(abs_residual)) if len(abs_residual) else 0.0,
                    "p95_abs": float(np.percentile(abs_residual, 95)) if len(abs_residual) else 0.0,
                },
                "distribution_match": {
                    "pearson_corr": corr,
                    "mean_gap": float(abs(real_mean - gen_mean)),
                    "std_ratio": float(gen_std / (real_std + 1e-6)),
                },
            },
            "quality_metrics": {
                "mae": mae,
                "rmse": rmse,
                "nrmse": nrmse,
                "mape": mape,
                "r2_score": r2,
                "residual_energy": ss_res,
            },
            "latent_space_distribution": {
                "stats": {
                    "mean": latent_mean,
                    "std": latent_std,
                    "min": float(np.min(latent)) if len(latent) else 0.0,
                    "max": float(np.max(latent)) if len(latent) else 0.0,
                    "skewness": latent_skew,
                    "kurtosis": latent_kurt,
                },
                "quantiles": {"p05": latent_q[0], "p25": latent_q[1], "p50": latent_q[2], "p75": latent_q[3], "p95": latent_q[4]},
                "histogram": hist_values,
                "distribution_health": {
                    "entropy": entropy,
                    "active_bin_ratio": active_bin_ratio,
                    "outlier_ratio": latent_outlier_ratio,
                    "mode_collapse_risk": mode_collapse_risk,
                    "mode_collapse_from_training": mode_collapse_from_history,
                },
            },
            "anomaly_patterns": {
                "residual_threshold": residual_thr,
                "reconstruction_threshold": recon_thr,
                "gradient_threshold": grad_thr,
                "pattern_counts": pattern_counts,
                "detected_patterns": top_patterns,
            },
            "sample_comparison": {
                "anomalous_samples": comparison_anomalous,
                "reference_samples": comparison_reference,
                "mean_abs_residual_gap": float(
                    np.mean([item["abs_residual"] for item in comparison_anomalous]) - np.mean([item["abs_residual"] for item in comparison_reference])
                )
                if comparison_anomalous and comparison_reference
                else 0.0,
            },
            "stats": {
                "mean_residual": float(np.mean(residual)) if len(residual) else 0.0,
                "std_residual": float(np.std(residual)) if len(residual) else 0.0,
                "max_abs_residual": float(np.max(abs_residual)) if len(abs_residual) else 0.0,
            },
            "node_analysis": [
                {
                    "node_index": int(i),
                    "real_value": float(v[i]),
                    "generated_value": float(generated[i]),
                    "residual": float(residual[i]),
                    "abs_residual": float(abs_residual[i]),
                    "residual_ratio": float(abs_residual[i] / (abs(v[i]) + 1e-6)),
                    "residual_zscore": float(z_i) if i < len(residual_z) else 0.0,
                    "discriminator_score": float(disc[i]) if i < len(disc) else 0.0,
                    "reconstruction_score": float(recon[i]) if i < len(recon) else 0.0,
                    "gradient_score": float(grad[i]) if i < len(grad) else 0.0,
                    "combined_score": float(combined[i]) if i < len(combined) else 0.0,
                }
                for i, z_i in enumerate(residual_z.tolist() if len(residual_z) else np.zeros_like(v).tolist())
            ],
        }

    def _discriminator_analysis(
        self,
        *,
        model: Any,
        coords: np.ndarray,
        values: np.ndarray,
        feature_names: list[str],
        feature_matrix: np.ndarray,
        score_bundle: Optional[dict[str, np.ndarray]] = None,
        batch_explanations: Optional[list[dict[str, Any]]] = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        bundle = score_bundle or self._predict_scores(model=model, coords=c, values=v)
        disc = np.asarray(bundle.get("discriminator", []), dtype=float).reshape(-1)
        recon = np.asarray(bundle.get("reconstruction", []), dtype=float).reshape(-1)
        grad = np.asarray(bundle.get("gradient", []), dtype=float).reshape(-1)
        combined = np.asarray(bundle.get("combined", []), dtype=float).reshape(-1)
        x = np.asarray(feature_matrix, dtype=float)
        n = int(min(len(v), len(disc), x.shape[0] if x.ndim == 2 else 0))
        if n <= 0:
            return {
                "decision_analysis": {"threshold": 0.0, "stats": {}, "node_decisions": [], "decision_counts": {}},
                "confidence_scores": {"mean_confidence": 0.0, "high_confidence_ratio": 0.0, "node_confidence": []},
                "decision_boundary": {
                    "lower_margin_threshold": 0.0,
                    "upper_margin_threshold": 0.0,
                    "boundary_sample_ratio": 0.0,
                    "separation_gap": 0.0,
                    "boundary_sharpness": 0.0,
                    "samples": [],
                },
                "key_discriminator_features": [],
                "adversarial_detection": {"risk_ratio": 0.0, "risk_threshold": 0.0, "candidates": []},
            }

        disc = disc[:n]
        recon = recon[:n] if len(recon) >= n else np.pad(recon, (0, n - len(recon)))
        grad = grad[:n] if len(grad) >= n else np.pad(grad, (0, n - len(grad)))
        combined = combined[:n] if len(combined) >= n else np.pad(combined, (0, n - len(combined)))
        x = x[:n]

        disc_thr = float(np.percentile(disc, 85))
        disc_z = robust_zscore(disc) if n > 1 else np.zeros_like(disc)
        margin = disc - disc_thr
        margin_norm = margin / (float(np.std(disc)) + 1e-6)
        confidence = 1.0 / (1.0 + np.exp(-3.0 * margin_norm))
        decision_labels: list[str] = []
        for i in range(n):
            if disc[i] >= disc_thr and confidence[i] >= 0.75:
                decision_labels.append("high_confidence_anomaly")
            elif disc[i] >= disc_thr:
                decision_labels.append("boundary_anomaly")
            elif confidence[i] <= 0.25:
                decision_labels.append("high_confidence_normal")
            else:
                decision_labels.append("boundary_normal")
        decision_counts: dict[str, int] = {}
        for lb in decision_labels:
            decision_counts[lb] = decision_counts.get(lb, 0) + 1
        node_decisions = [
            {
                "node_index": int(i),
                "discriminator_score": float(disc[i]),
                "discriminator_zscore": float(disc_z[i]) if i < len(disc_z) else 0.0,
                "margin_to_threshold": float(margin[i]),
                "confidence": float(confidence[i]),
                "label": decision_labels[i],
            }
            for i in range(n)
        ]

        low_thr = float(np.percentile(disc, 45))
        high_thr = float(np.percentile(disc, 55))
        boundary_mask = (disc >= low_thr) & (disc <= high_thr)
        boundary_indices = np.where(boundary_mask)[0]
        anom_scores = disc[disc >= disc_thr]
        norm_scores = disc[disc < disc_thr]
        anom_mean = float(np.mean(anom_scores)) if len(anom_scores) else disc_thr
        norm_mean = float(np.mean(norm_scores)) if len(norm_scores) else disc_thr
        separation_gap = float(anom_mean - norm_mean)
        boundary_sharpness = float(separation_gap / (float(np.std(disc)) + 1e-6))
        boundary_samples = [
            {
                "node_index": int(i),
                "discriminator_score": float(disc[i]),
                "margin_to_threshold": float(margin[i]),
                "confidence": float(confidence[i]),
            }
            for i in boundary_indices[: max(1, min(8, len(boundary_indices)))]
        ]

        feature_rows: list[dict[str, Any]] = []
        for idx, name in enumerate(feature_names[: x.shape[1]]):
            col = np.asarray(x[:, idx], dtype=float)
            corr = 0.0
            if n >= 2 and np.std(col) > 1e-9 and np.std(disc) > 1e-9:
                corr = float(np.corrcoef(col, disc)[0, 1])
            feature_rows.append(
                {
                    "feature_index": int(idx),
                    "feature_name": str(name),
                    "feature_alias": self._feature_display(str(name)),
                    "category": self._feature_category(str(name)),
                    "corr_with_discriminator": corr,
                    "importance": float(abs(corr)),
                }
            )

        expl_weight: dict[str, float] = {}
        for item in batch_explanations or []:
            for contrib in item.get("top_contributions", []):
                fname = str(contrib.get("feature_name", ""))
                w = float(
                    abs(
                        contrib.get(
                            "abs_weight",
                            contrib.get("abs_shap", contrib.get("weight", contrib.get("shap_value", 0.0))),
                        )
                    )
                )
                expl_weight[fname] = expl_weight.get(fname, 0.0) + w
        explained_nodes = float(max(1, len(batch_explanations or [])))
        for row in feature_rows:
            name = str(row["feature_name"])
            explain_boost = float(expl_weight.get(name, 0.0) / explained_nodes)
            row["explain_importance"] = explain_boost
            row["importance"] = float(0.65 * float(row["importance"]) + 0.35 * explain_boost)
        feature_rows.sort(key=lambda item: float(item["importance"]), reverse=True)
        key_features = feature_rows[: max(1, int(top_k))]

        scale = max(1e-6, float(np.std(v)))
        delta = 0.05 * scale
        perturbed_v = v.copy()
        if len(perturbed_v):
            perturbed_v = perturbed_v + delta * np.sign(v - float(np.mean(v)))
        perturbed_disc = np.asarray(model.discriminator(c, perturbed_v), dtype=float).reshape(-1)
        if len(perturbed_disc) < n:
            perturbed_disc = np.pad(perturbed_disc, (0, n - len(perturbed_disc)))
        perturbed_disc = perturbed_disc[:n]
        sensitivity = np.abs(perturbed_disc - disc) / (abs(delta) + 1e-6)
        sensitivity_thr = float(np.percentile(sensitivity, 90)) if len(sensitivity) else 0.0
        low_recon = recon <= float(np.percentile(recon, 50))
        low_grad = grad <= float(np.percentile(grad, 50))
        high_disc = disc >= disc_thr
        suspicious_mask = (sensitivity >= sensitivity_thr) | (high_disc & low_recon & low_grad)
        adv_candidates = [
            {
                "node_index": int(i),
                "discriminator_score": float(disc[i]),
                "perturbed_discriminator_score": float(perturbed_disc[i]),
                "sensitivity": float(sensitivity[i]),
                "reconstruction_score": float(recon[i]),
                "gradient_score": float(grad[i]),
                "combined_score": float(combined[i]),
                "risk_score": float(
                    (sensitivity[i] / (sensitivity_thr + 1e-6))
                    + (1.0 if high_disc[i] else 0.0)
                    + (1.0 if low_recon[i] else 0.0)
                    + (1.0 if low_grad[i] else 0.0)
                ),
            }
            for i in np.where(suspicious_mask)[0].tolist()
        ]
        adv_candidates.sort(key=lambda item: float(item["risk_score"]), reverse=True)
        adv_candidates = adv_candidates[: max(1, min(8, len(adv_candidates)))] if adv_candidates else []

        return {
            "decision_analysis": {
                "threshold": disc_thr,
                "stats": {
                    "mean": float(np.mean(disc)),
                    "std": float(np.std(disc)),
                    "p95": float(np.percentile(disc, 95)),
                },
                "node_decisions": node_decisions,
                "decision_counts": decision_counts,
            },
            "confidence_scores": {
                "mean_confidence": float(np.mean(confidence)),
                "high_confidence_ratio": float(np.mean(confidence >= 0.75)),
                "node_confidence": [
                    {
                        "node_index": int(i),
                        "confidence": float(confidence[i]),
                        "margin_to_threshold": float(margin[i]),
                        "discriminator_zscore": float(disc_z[i]) if i < len(disc_z) else 0.0,
                    }
                    for i in range(n)
                ],
            },
            "decision_boundary": {
                "lower_margin_threshold": low_thr,
                "upper_margin_threshold": high_thr,
                "boundary_sample_ratio": float(np.mean(boundary_mask)),
                "separation_gap": separation_gap,
                "boundary_sharpness": boundary_sharpness,
                "samples": boundary_samples,
            },
            "key_discriminator_features": key_features,
            "adversarial_detection": {
                "risk_ratio": float(len(adv_candidates) / max(1, n)),
                "risk_threshold": sensitivity_thr,
                "candidates": adv_candidates,
            },
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
        component_summary = self._component_contribution_analysis(
            decomposition=decomposition_payload["decomposition"],
            explained_nodes=explained_nodes,
        )
        key_anomaly_features = self._extract_key_anomaly_features(batch_explanations=batch_explanations, top_k=int(top_k))
        anomaly_reasons = self._collect_anomaly_reasons(batch_explanations=batch_explanations)
        generator_info = self._generator_analysis(
            model=model,
            coords=c,
            values=v,
            score_bundle=context["score_bundle"],
            generator_artifacts=context.get("generator_artifacts"),
        )
        discriminator = np.asarray(context["score_bundle"]["discriminator"], dtype=float)
        reconstruction = np.asarray(context["score_bundle"]["reconstruction"], dtype=float)
        gradient = np.asarray(context["score_bundle"]["gradient"], dtype=float)
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
                "component_contribution": component_summary,
                "key_anomaly_features": key_anomaly_features,
                "anomaly_reasons": anomaly_reasons,
                "consistency_validation": consistency,
            },
            "score_components": {
                "discriminator": discriminator.astype(float).tolist(),
                "discriminator_weighted": (0.50 * discriminator).astype(float).tolist(),
                "reconstruction": reconstruction.astype(float).tolist(),
                "gradient": gradient.astype(float).tolist(),
                "generator_weighted": (0.35 * reconstruction + 0.15 * gradient).astype(float).tolist(),
                "combined": combined.astype(float).tolist(),
            },
            "generator_analysis": generator_info,
            "discriminator_analysis": self._discriminator_analysis(
                model=model,
                coords=c,
                values=v,
                feature_names=feature_names,
                feature_matrix=np.asarray(context["feature_matrix"], dtype=float),
                score_bundle=context["score_bundle"],
                batch_explanations=batch_explanations,
                top_k=int(top_k),
            ),
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

        workers = self._effective_workers(len(explained_nodes))
        if workers == 1:
            batch_explanations = [_explain_one(idx) for idx in explained_nodes]
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                batch_explanations = list(executor.map(_explain_one, explained_nodes))

        mean_abs = np.mean(np.abs(np.asarray([item["raw_shap_values"] for item in batch_explanations], dtype=float)), axis=0)
        ranking = np.argsort(-mean_abs).astype(int).tolist()
        top_features = [
            {
                "feature_index": int(idx),
                "feature_name": feature_names[idx],
                "feature_alias": self._feature_display(feature_names[idx]),
                "importance": float(mean_abs[idx]),
                "category": self._feature_category(feature_names[idx]),
            }
            for idx in ranking[: max(1, int(top_k))]
        ]

        combined = np.asarray(context["score_bundle"]["combined"], dtype=float)
        consistency = self._validate_explanation_consistency(
            decomposition=decomposition_payload["decomposition"],
            combined_scores=combined,
            explained_nodes=explained_nodes,
        )
        component_summary = self._component_contribution_analysis(
            decomposition=decomposition_payload["decomposition"],
            explained_nodes=explained_nodes,
        )
        key_anomaly_features = self._extract_key_anomaly_features(batch_explanations=batch_explanations, top_k=int(top_k))
        anomaly_reasons = self._collect_anomaly_reasons(batch_explanations=batch_explanations)
        generator_info = self._generator_analysis(
            model=model,
            coords=c,
            values=v,
            score_bundle=context["score_bundle"],
            generator_artifacts=context.get("generator_artifacts"),
        )
        discriminator = np.asarray(context["score_bundle"]["discriminator"], dtype=float)
        reconstruction = np.asarray(context["score_bundle"]["reconstruction"], dtype=float)
        gradient = np.asarray(context["score_bundle"]["gradient"], dtype=float)
        payload = {
            "summary": {
                "method": "shap",
                "explainer": "KernelExplainer",
                "explained_nodes": len(explained_nodes),
                "num_features": len(feature_names),
                "background_size": int(background.shape[0]),
                "nsamples": effective_nsamples,
                "top_features": top_features,
                "average_confidence": float(np.mean([item["confidence"] for item in batch_explanations])) if batch_explanations else 0.0,
                "surrogate_fidelity": float(context["surrogate_metrics"]["fidelity"]),
            },
            "feature_importance": mean_abs.astype(float).tolist(),
            "batch_explanations": batch_explanations,
            "global_feature_importance": top_features,
            "anomaly_score_explanation": {
                "decomposition": decomposition_payload["decomposition"],
                "key_anomaly_nodes": decomposition_payload["top_anomaly_nodes"],
                "component_contribution": component_summary,
                "key_anomaly_features": key_anomaly_features,
                "anomaly_reasons": anomaly_reasons,
                "consistency_validation": consistency,
            },
            "score_components": {
                "discriminator": discriminator.astype(float).tolist(),
                "discriminator_weighted": (0.50 * discriminator).astype(float).tolist(),
                "reconstruction": reconstruction.astype(float).tolist(),
                "gradient": gradient.astype(float).tolist(),
                "generator_weighted": (0.35 * reconstruction + 0.15 * gradient).astype(float).tolist(),
                "combined": combined.astype(float).tolist(),
            },
            "generator_analysis": generator_info,
            "discriminator_analysis": self._discriminator_analysis(
                model=model,
                coords=c,
                values=v,
                feature_names=feature_names,
                feature_matrix=np.asarray(context["feature_matrix"], dtype=float),
                score_bundle=context["score_bundle"],
                batch_explanations=batch_explanations,
                top_k=int(top_k),
            ),
            "anomaly_analysis": self._anomaly_profile(combined, explained_nodes),
            "preprocess": dict(context["preprocess"]),
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "backend": "shap" if shap_module is not None else "surrogate_linear",
                "parallel_workers": int(workers),
            },
        }
        self._cache_set(cache_key, payload)
        return payload
