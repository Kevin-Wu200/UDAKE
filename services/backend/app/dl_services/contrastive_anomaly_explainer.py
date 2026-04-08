"""对比学习异常检测模型 LIME 解释适配器。"""

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

from deep_learning.models.anomaly_detection.common import safe_minmax

from .anomaly_features import AnomalyFeatureRegistry


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


@dataclass
class ContrastiveExplanationConfig:
    lime_num_samples: int = 240
    shap_nsamples: int = 140
    shap_background_size: int = 64
    shap_l1_reg_num_features: int = 10
    max_explain_nodes: int = 8
    cache_size: int = 32
    random_state: int = 42


class ContrastiveLimeAdapter:
    """对比学习模型的 LIME 解释适配器。"""

    def __init__(self, config: Optional[ContrastiveExplanationConfig] = None) -> None:
        self.config = config or ContrastiveExplanationConfig()
        self._lock = threading.Lock()
        self._result_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._context_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._feature_registry = AnomalyFeatureRegistry()
        self._score_weights = {
            "feature_distance": 0.40,
            "density": 0.30,
            "nearest_neighbor": 0.20,
            "bank_similarity_inverse": 0.10,
        }

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

    def _feature_category(self, name: str) -> str:
        item = self._feature_registry._COMMON_DEFINITIONS.get(name)
        return item.category if item is not None else "unknown"

    def _feature_display(self, name: str) -> str:
        if name in self._feature_registry._COMMON_DEFINITIONS:
            return self._feature_registry._COMMON_DEFINITIONS[name].display_name
        return name

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
            scaled = (v - median) / (1.4826 * mad + 1e-9)
            return scaled, {"strategy": 1.0, "shift": median, "scale": mad}

        mean = float(np.mean(v))
        std = float(np.std(v))
        std = std if std > 1e-9 else 1.0
        return (v - mean) / std, {"strategy": 0.0, "shift": mean, "scale": std}

    def _preprocess(self, matrix: np.ndarray, feature_names: list[str]) -> tuple[np.ndarray, dict[str, dict[str, float]]]:
        plan = self._feature_registry.standardization_plan("contrastive")
        scaled = np.zeros_like(matrix, dtype=float)
        stats: dict[str, dict[str, float]] = {}
        for idx, name in enumerate(feature_names):
            strategy = plan.get(name, "zscore")
            scaled_col, st = self._standardize_column(matrix[:, idx], strategy)
            scaled[:, idx] = scaled_col
            stats[name] = st
        return scaled, stats

    def _build_feature_matrix(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, list[str], dict[str, Any]]:
        pre = model.preprocess_contrastive_data(
            np.asarray(coords, dtype=float),
            np.asarray(values, dtype=float),
            use_training_stats=True,
            augmentation=False,
        )
        matrix = np.asarray(pre["processed_features"], dtype=float)
        names = [str(x) for x in pre["feature_names"]]
        return matrix, names, pre

    def _predict_encoder_response(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        emb = np.asarray(model.encode(np.asarray(coords, dtype=float), np.asarray(values, dtype=float)), dtype=float)
        if emb.ndim != 2 or emb.shape[0] == 0:
            return {
                "embedding": np.zeros((0, 0), dtype=float),
                "embedding_norm": np.zeros((0,), dtype=float),
                "embedding_cos_center": np.zeros((0,), dtype=float),
            }
        norm = np.linalg.norm(emb, axis=1)
        center = np.mean(emb, axis=0, keepdims=True)
        center_norm = np.linalg.norm(center, axis=1).reshape(-1)[0] + 1e-9
        emb_norm = np.linalg.norm(emb, axis=1) + 1e-9
        cos_center = np.sum(emb * center, axis=1) / (emb_norm * center_norm)
        return {
            "embedding": emb.astype(float),
            "embedding_norm": norm.astype(float),
            "embedding_cos_center": cos_center.astype(float),
        }

    def _predict_contrastive_scores(self, *, model: Any, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        bundle = model.anomaly_scores(np.asarray(coords, dtype=float), np.asarray(values, dtype=float))
        return {
            "feature_distance": np.asarray(bundle.get("feature_distance", []), dtype=float),
            "density": np.asarray(bundle.get("density", []), dtype=float),
            "nearest_neighbor": np.asarray(bundle.get("nearest_neighbor", []), dtype=float),
            "bank_similarity": np.asarray(bundle.get("bank_similarity", []), dtype=float),
            "combined": np.asarray(bundle.get("combined", []), dtype=float),
        }

    def _dynamic_lime_samples(self, n_features: int, n_points: int) -> int:
        base = max(80, int(self.config.lime_num_samples))
        return min(1200, base + n_features * 8 + n_points * 2)

    def _dynamic_shap_samples(self, selected_nsamples: int, n_features: int, n_points: int) -> int:
        base = max(40, int(selected_nsamples))
        return min(1000, base + n_features * 3 + n_points)

    def _select_background(self, x_scaled: np.ndarray, scores: np.ndarray, size: int | None = None) -> np.ndarray:
        n = x_scaled.shape[0]
        k = max(8, min(int(size or self.config.shap_background_size), n))
        if n <= k:
            return np.asarray(x_scaled, dtype=float).copy()
        order = np.argsort(np.asarray(scores, dtype=float).reshape(-1))
        evenly = np.linspace(0, n - 1, k, dtype=int)
        return np.asarray(x_scaled[np.unique(order[evenly])], dtype=float)

    def _top_node_indices(self, scores: np.ndarray, max_explain_nodes: int) -> list[int]:
        n = len(scores)
        explain_count = max(1, min(int(max_explain_nodes), n))
        return np.argsort(-scores)[:explain_count].astype(int).tolist()

    def _select_explained_nodes(self, scores: np.ndarray, max_explain_nodes: int) -> tuple[list[int], float]:
        s = np.asarray(scores, dtype=float).reshape(-1)
        if s.size == 0:
            return [], 0.0
        threshold = float(np.percentile(s, 95))
        anomaly_nodes = np.where(s >= threshold)[0].astype(int).tolist()
        ranked_nodes = self._top_node_indices(s, max_explain_nodes)
        selected: list[int] = []
        for idx in anomaly_nodes + ranked_nodes:
            if idx not in selected:
                selected.append(int(idx))
            if len(selected) >= max(1, int(max_explain_nodes)):
                break
        return selected, threshold

    def _predict_surrogate(self, context: dict[str, Any]) -> Callable[[np.ndarray], np.ndarray]:
        surrogate: Ridge = context["surrogate"]
        return lambda x: surrogate.predict(np.asarray(x, dtype=float))

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

    def _embedding_similarity_analysis(self, embeddings: np.ndarray) -> dict[str, Any]:
        emb = np.asarray(embeddings, dtype=float)
        if emb.ndim != 2 or emb.shape[0] == 0:
            return {
                "mean_cosine_similarity": 0.0,
                "std_cosine_similarity": 0.0,
                "most_similar_pairs": [],
                "most_dissimilar_pairs": [],
                "node_mean_similarity": [],
            }
        norm = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9
        normalized = emb / norm
        sim = np.asarray(normalized @ normalized.T, dtype=float)
        n = sim.shape[0]
        triu = np.triu_indices(n, k=1)
        pair_scores = sim[triu] if len(triu[0]) else np.zeros((0,), dtype=float)
        pair_rows = [
            {"node_i": int(i), "node_j": int(j), "cosine_similarity": float(sim[i, j])}
            for i, j in zip(triu[0].tolist(), triu[1].tolist())
        ]
        pair_rows.sort(key=lambda item: float(item["cosine_similarity"]), reverse=True)
        top_k = max(1, min(8, len(pair_rows)))
        np.fill_diagonal(sim, np.nan)
        node_mean = np.nanmean(sim, axis=1)
        node_mean = np.where(np.isfinite(node_mean), node_mean, 0.0)
        return {
            "mean_cosine_similarity": float(np.mean(pair_scores)) if len(pair_scores) else 1.0,
            "std_cosine_similarity": float(np.std(pair_scores)) if len(pair_scores) else 0.0,
            "most_similar_pairs": pair_rows[:top_k],
            "most_dissimilar_pairs": sorted(pair_rows, key=lambda item: float(item["cosine_similarity"]))[:top_k],
            "node_mean_similarity": [
                {"node_index": int(i), "mean_cosine_similarity": float(node_mean[i])}
                for i in range(len(node_mean))
            ],
        }

    def _embedding_distribution_analysis(self, embeddings: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
        emb = np.asarray(embeddings, dtype=float)
        s = np.asarray(scores, dtype=float).reshape(-1)
        if emb.ndim != 2 or emb.shape[0] == 0:
            return {
                "embedding_dim": 0,
                "center": [],
                "distance_stats": {"mean": 0.0, "std": 0.0, "p90": 0.0, "p95": 0.0},
                "score_distance_correlation": 0.0,
                "distance_to_center": [],
            }
        center = np.mean(emb, axis=0)
        dist = np.linalg.norm(emb - center.reshape(1, -1), axis=1)
        aligned = min(len(dist), len(s))
        corr = 0.0
        if aligned >= 2:
            d = dist[:aligned]
            y = s[:aligned]
            if np.std(d) > 1e-9 and np.std(y) > 1e-9:
                corr = float(np.corrcoef(d, y)[0, 1])
        return {
            "embedding_dim": int(emb.shape[1]),
            "center": [float(x) for x in center.tolist()],
            "distance_stats": {
                "mean": float(np.mean(dist)),
                "std": float(np.std(dist)),
                "p90": float(np.percentile(dist, 90)),
                "p95": float(np.percentile(dist, 95)),
            },
            "score_distance_correlation": corr,
            "distance_to_center": [float(x) for x in dist.tolist()],
        }

    def _embedding_anomaly_patterns(
        self,
        *,
        scores: np.ndarray,
        explained_nodes: list[int],
        similarity: dict[str, Any],
        distribution: dict[str, Any],
    ) -> dict[str, Any]:
        s = np.asarray(scores, dtype=float).reshape(-1)
        dist = np.asarray(distribution.get("distance_to_center", []), dtype=float).reshape(-1)
        mean_similarity = np.asarray(
            [float(item.get("mean_cosine_similarity", 0.0)) for item in similarity.get("node_mean_similarity", [])],
            dtype=float,
        ).reshape(-1)
        if len(s) == 0 or len(dist) == 0 or len(mean_similarity) == 0:
            return {"pattern_name": "none", "matched_nodes": [], "coverage": 0.0}
        aligned = min(len(s), len(dist), len(mean_similarity))
        score_thr = float(np.percentile(s[:aligned], 95))
        dist_thr = float(np.percentile(dist[:aligned], 90))
        sim_thr = float(np.percentile(mean_similarity[:aligned], 15))
        matched = [
            int(i)
            for i in range(aligned)
            if s[i] >= score_thr and dist[i] >= dist_thr and mean_similarity[i] <= sim_thr
        ]
        explain_set = set(int(i) for i in explained_nodes)
        matched_explained = [idx for idx in matched if idx in explain_set]
        return {
            "pattern_name": "high_score_far_center_low_similarity",
            "rule_thresholds": {"score_p95": score_thr, "distance_p90": dist_thr, "similarity_p15": sim_thr},
            "matched_nodes": matched,
            "matched_explained_nodes": matched_explained,
            "coverage": float(len(matched) / max(1, aligned)),
        }

    def _embedding_visualization(self, embeddings: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
        emb = np.asarray(embeddings, dtype=float)
        s = np.asarray(scores, dtype=float).reshape(-1)
        if emb.ndim != 2 or emb.shape[0] == 0:
            return {"method": "pca_svd", "points": []}
        if emb.shape[1] >= 2:
            centered = emb - np.mean(emb, axis=0, keepdims=True)
            try:
                _, _, vh = np.linalg.svd(centered, full_matrices=False)
                components = vh[:2]
                reduced = centered @ components.T
            except Exception:
                reduced = centered[:, :2]
        else:
            reduced = np.concatenate([emb, np.zeros((emb.shape[0], 1), dtype=float)], axis=1)
        threshold = float(np.percentile(s, 95)) if len(s) else 0.0
        points = []
        for idx in range(min(len(reduced), len(s))):
            points.append(
                {
                    "node_index": int(idx),
                    "x": float(reduced[idx, 0]),
                    "y": float(reduced[idx, 1]),
                    "score": float(s[idx]),
                    "is_anomaly": bool(s[idx] >= threshold),
                }
            )
        return {"method": "pca_svd", "anomaly_threshold_p95": threshold, "points": points}

    def _embedding_analysis(self, *, encoder_bundle: dict[str, np.ndarray], scores: np.ndarray, explained_nodes: list[int]) -> dict[str, Any]:
        embeddings = np.asarray(encoder_bundle.get("embedding", []), dtype=float)
        similarity = self._embedding_similarity_analysis(embeddings)
        distribution = self._embedding_distribution_analysis(embeddings, np.asarray(scores, dtype=float))
        patterns = self._embedding_anomaly_patterns(
            scores=np.asarray(scores, dtype=float),
            explained_nodes=explained_nodes,
            similarity=similarity,
            distribution=distribution,
        )
        visualization = self._embedding_visualization(embeddings, np.asarray(scores, dtype=float))
        return {
            "summary": {
                "embedding_count": int(embeddings.shape[0]) if embeddings.ndim == 2 else 0,
                "embedding_dim": int(embeddings.shape[1]) if embeddings.ndim == 2 else 0,
            },
            "similarity": similarity,
            "distribution": distribution,
            "anomaly_patterns": patterns,
            "visualization": visualization,
        }

    def _score_decomposition(
        self,
        *,
        feature_distance: np.ndarray,
        density: np.ndarray,
        nearest_neighbor: np.ndarray,
        bank_similarity: np.ndarray,
        combined: np.ndarray,
    ) -> dict[str, Any]:
        fd = np.asarray(feature_distance, dtype=float).reshape(-1)
        den = np.asarray(density, dtype=float).reshape(-1)
        near = np.asarray(nearest_neighbor, dtype=float).reshape(-1)
        bank = np.asarray(bank_similarity, dtype=float).reshape(-1)
        combo = np.asarray(combined, dtype=float).reshape(-1)
        aligned = min(len(fd), len(den), len(near), len(bank), len(combo))
        if aligned <= 0:
            return {"decomposition": [], "top_anomaly_nodes": []}

        fd = fd[:aligned]
        den = den[:aligned]
        near = near[:aligned]
        bank = bank[:aligned]
        combo = combo[:aligned]
        fd_norm = safe_minmax(fd)
        den_norm = safe_minmax(den)
        near_norm = safe_minmax(near)
        bank_inv_norm = 1.0 - safe_minmax(bank)

        rows: list[dict[str, Any]] = []
        for idx in range(aligned):
            fd_weighted = float(self._score_weights["feature_distance"] * fd_norm[idx])
            den_weighted = float(self._score_weights["density"] * den_norm[idx])
            near_weighted = float(self._score_weights["nearest_neighbor"] * near_norm[idx])
            bank_weighted = float(self._score_weights["bank_similarity_inverse"] * bank_inv_norm[idx])
            total = float(fd_weighted + den_weighted + near_weighted + bank_weighted)
            rows.append(
                {
                    "node_index": int(idx),
                    "feature_distance_component": float(fd[idx]),
                    "density_component": float(den[idx]),
                    "nearest_neighbor_component": float(near[idx]),
                    "bank_similarity_component": float(bank[idx]),
                    "feature_distance_weighted_component": fd_weighted,
                    "density_weighted_component": den_weighted,
                    "nearest_neighbor_weighted_component": near_weighted,
                    "bank_similarity_inverse_weighted_component": bank_weighted,
                    "decomposed_score": total,
                    "combined_score": float(combo[idx]),
                }
            )
        rows.sort(key=lambda item: float(item["decomposed_score"]), reverse=True)
        return {
            "decomposition": rows,
            "top_anomaly_nodes": [int(item["node_index"]) for item in rows[: max(1, min(10, aligned))]],
        }

    def _component_contribution_analysis(
        self,
        *,
        decomposition: list[dict[str, Any]],
        explained_nodes: list[int],
    ) -> dict[str, Any]:
        if len(decomposition) == 0:
            return {
                "encoder_total": 0.0,
                "contrastive_loss_total": 0.0,
                "encoder_ratio": 0.0,
                "contrastive_loss_ratio": 0.0,
                "explained_node_breakdown": [],
            }

        # 近似拆分：编码器主导 embedding 距离与最近邻项；对比损失主导密度与特征库一致性项。
        encoder_total = float(
            np.sum(
                [
                    float(item.get("feature_distance_weighted_component", 0.0))
                    + float(item.get("nearest_neighbor_weighted_component", 0.0))
                    for item in decomposition
                ]
            )
        )
        contrastive_total = float(
            np.sum(
                [
                    float(item.get("density_weighted_component", 0.0))
                    + float(item.get("bank_similarity_inverse_weighted_component", 0.0))
                    for item in decomposition
                ]
            )
        )
        total = encoder_total + contrastive_total + 1e-9
        node_set = set(int(i) for i in explained_nodes)
        node_rows = [item for item in decomposition if int(item.get("node_index", -1)) in node_set]
        node_rows.sort(key=lambda item: float(item.get("decomposed_score", 0.0)), reverse=True)
        breakdown = [
            {
                "node_index": int(item["node_index"]),
                "encoder_weighted_component": float(item.get("feature_distance_weighted_component", 0.0))
                + float(item.get("nearest_neighbor_weighted_component", 0.0)),
                "contrastive_loss_weighted_component": float(item.get("density_weighted_component", 0.0))
                + float(item.get("bank_similarity_inverse_weighted_component", 0.0)),
                "decomposed_score": float(item.get("decomposed_score", 0.0)),
            }
            for item in node_rows
        ]
        return {
            "encoder_total": encoder_total,
            "contrastive_loss_total": contrastive_total,
            "encoder_ratio": float(encoder_total / total),
            "contrastive_loss_ratio": float(contrastive_total / total),
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
            return f"节点{node_idx}异常主要由嵌入偏移与特征库不一致共同触发。"
        top_feat = top_contributions[0]
        return (
            f"节点{node_idx}异常由{top_feat['feature_alias']}驱动，"
            f"特征距离分量{decomposition_row['feature_distance_component']:.3f}、"
            f"密度分量{decomposition_row['density_component']:.3f}、"
            f"最近邻分量{decomposition_row['nearest_neighbor_component']:.3f}、"
            f"特征库相似度分量{decomposition_row['bank_similarity_component']:.3f}共同放大异常。"
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

    def _fallback_local_pairs(self, context: dict[str, Any], node_index: int) -> tuple[list[tuple[int, float]], float]:
        surrogate: Ridge = context["surrogate"]
        instance = np.asarray(context["scaled_x"][node_index], dtype=float)
        coef = np.asarray(surrogate.coef_, dtype=float)
        local = coef * instance
        pairs = [(int(i), float(local[i])) for i in range(local.shape[0])]
        pred = float(surrogate.predict(instance.reshape(1, -1))[0])
        return pairs, pred

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

        matrix, feature_names, pre_info = self._build_feature_matrix(model=model, coords=coords, values=values)
        scaled_x, scaler_stats = self._preprocess(matrix, feature_names)
        score_bundle = self._predict_contrastive_scores(model=model, coords=coords, values=values)
        encoder_bundle = self._predict_encoder_response(model=model, coords=coords, values=values)
        target = np.asarray(score_bundle["combined"], dtype=float)
        surrogate = Ridge(alpha=1.0, random_state=self.config.random_state)
        surrogate.fit(scaled_x, target)

        pred_train = surrogate.predict(scaled_x)
        train_rmse = float(np.sqrt(np.mean((pred_train - target) ** 2))) if len(target) else 0.0
        target_std = float(np.std(target)) if len(target) else 0.0
        fidelity = float(max(0.0, 1.0 - train_rmse / (target_std + 1e-6))) if len(target) else 0.0

        context = {
            "context_key": key,
            "feature_matrix": matrix,
            "scaled_x": scaled_x,
            "feature_names": feature_names,
            "scaler_stats": scaler_stats,
            "score_bundle": score_bundle,
            "encoder_bundle": encoder_bundle,
            "target": target,
            "surrogate": surrogate,
            "surrogate_metrics": {"train_rmse": train_rmse, "fidelity": fidelity},
            "preprocess": {
                "batch_slices": pre_info.get("batch_slices", []),
                "validation": pre_info.get("validation", {}),
                "pair_count": len(pre_info.get("positive_pairs", [])),
            },
        }
        self._context_set(key, context)
        return context

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
        explained_nodes, anomaly_threshold = self._select_explained_nodes(target, int(max_explain_nodes or self.config.max_explain_nodes))
        decomposition_payload = self._score_decomposition(
            feature_distance=np.asarray(context["score_bundle"]["feature_distance"], dtype=float),
            density=np.asarray(context["score_bundle"]["density"], dtype=float),
            nearest_neighbor=np.asarray(context["score_bundle"]["nearest_neighbor"], dtype=float),
            bank_similarity=np.asarray(context["score_bundle"]["bank_similarity"], dtype=float),
            combined=target,
        )
        dec_by_node = {int(item["node_index"]): item for item in decomposition_payload["decomposition"]}
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
        batch_explanations: list[dict[str, Any]] = []
        for node_idx in explained_nodes:
            instance = np.asarray(context["scaled_x"][node_idx], dtype=float)
            local_pairs: list[tuple[int, float]]
            local_pred = float(predict_fn(instance.reshape(1, -1))[0])
            fidelity = _safe_float(context["surrogate_metrics"].get("fidelity", 0.5), 0.5)

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
                except Exception:
                    local_pairs, local_pred = self._fallback_local_pairs(context, node_idx)
            else:
                local_pairs, local_pred = self._fallback_local_pairs(context, node_idx)

            contributions = [
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
            batch_explanations.append(
                {
                    "node_index": int(node_idx),
                    "prediction": local_pred,
                    "target_prediction": float(target[node_idx]),
                    "is_anomaly": bool(target[node_idx] >= anomaly_threshold),
                    "fidelity": float(fidelity),
                    "confidence": float(max(0.0, min(1.0, fidelity * np.exp(-abs(local_pred - target[node_idx]))))),
                    "top_contributions": contributions,
                    "decomposition": dec_by_node.get(
                        int(node_idx),
                        {
                            "feature_distance_component": 0.0,
                            "density_component": 0.0,
                            "nearest_neighbor_component": 0.0,
                            "bank_similarity_component": 0.0,
                        },
                    ),
                    "reason": self._explanation_reason(
                        node_idx=int(node_idx),
                        decomposition_row=dec_by_node.get(
                            int(node_idx),
                            {
                                "feature_distance_component": 0.0,
                                "density_component": 0.0,
                                "nearest_neighbor_component": 0.0,
                                "bank_similarity_component": 0.0,
                            },
                        ),
                        top_contributions=contributions,
                    ),
                }
            )

        global_importance: dict[str, float] = {}
        raw_importance = np.zeros((len(feature_names),), dtype=float)
        for item in batch_explanations:
            for contrib in item["top_contributions"]:
                idx = int(contrib["feature_index"])
                raw_importance[idx] += float(abs(contrib["weight"]))
                name = str(contrib["feature_name"])
                global_importance[name] = global_importance.get(name, 0.0) + float(abs(contrib["weight"]))
        global_items = sorted(global_importance.items(), key=lambda kv: kv[1], reverse=True)
        global_feature_importance = [
            {
                "feature_name": name,
                "feature_alias": self._feature_display(name),
                "importance": float(weight / max(1, len(batch_explanations))),
                "category": self._feature_category(name),
            }
            for name, weight in global_items[: max(1, int(top_k))]
        ]
        consistency = self._validate_explanation_consistency(
            decomposition=decomposition_payload["decomposition"],
            combined_scores=target,
            explained_nodes=explained_nodes,
        )
        component_summary = self._component_contribution_analysis(
            decomposition=decomposition_payload["decomposition"],
            explained_nodes=explained_nodes,
        )
        key_anomaly_features = self._extract_key_anomaly_features(batch_explanations=batch_explanations, top_k=int(top_k))
        anomaly_reasons = self._collect_anomaly_reasons(batch_explanations=batch_explanations)

        payload = {
            "summary": {
                "method": "lime",
                "explained_nodes": len(explained_nodes),
                "num_samples": selected_samples,
                "num_features": len(feature_names),
                "anomaly_threshold_p95": anomaly_threshold,
                "top_features": [
                    {"feature_index": int(idx), "feature_name": item["feature_name"], "importance": item["importance"]}
                    for idx, item in enumerate(global_feature_importance)
                ],
                "average_confidence": float(np.mean([item["confidence"] for item in batch_explanations])) if batch_explanations else 0.0,
            },
            "feature_importance": raw_importance.astype(float).tolist(),
            "batch_explanations": batch_explanations,
            "global_feature_importance": global_feature_importance,
            "anomaly_score_explanation": {
                "decomposition": decomposition_payload["decomposition"],
                "key_anomaly_nodes": decomposition_payload["top_anomaly_nodes"],
                "component_contribution": component_summary,
                "key_anomaly_features": key_anomaly_features,
                "anomaly_reasons": anomaly_reasons,
                "consistency_validation": consistency,
            },
            "score_components": {
                "feature_distance": np.asarray(context["score_bundle"]["feature_distance"], dtype=float).astype(float).tolist(),
                "density": np.asarray(context["score_bundle"]["density"], dtype=float).astype(float).tolist(),
                "nearest_neighbor": np.asarray(context["score_bundle"]["nearest_neighbor"], dtype=float).astype(float).tolist(),
                "bank_similarity": np.asarray(context["score_bundle"]["bank_similarity"], dtype=float).astype(float).tolist(),
                "combined": target.astype(float).tolist(),
            },
            "encoder_components": {
                "embedding_norm": np.asarray(context["encoder_bundle"]["embedding_norm"], dtype=float).astype(float).tolist(),
                "embedding_cos_center": np.asarray(context["encoder_bundle"]["embedding_cos_center"], dtype=float).astype(float).tolist(),
            },
            "embedding_analysis": self._embedding_analysis(
                encoder_bundle=context["encoder_bundle"],
                scores=target,
                explained_nodes=explained_nodes,
            ),
            "surrogate_metrics": context["surrogate_metrics"],
            "preprocess": context["preprocess"],
            "anomaly_analysis": self._anomaly_profile(target, explained_nodes),
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
            },
        }
        self._cache_set(cache_key, payload)
        return payload


class ContrastiveShapAdapter(ContrastiveLimeAdapter):
    """对比学习模型的 SHAP 解释适配器。"""

    _CONTRASTIVE_FEATURE_NAMES = {"feature_distance", "density_score", "nearest_score", "bank_similarity"}

    def _embedding_input_summary(self, encoder_bundle: dict[str, np.ndarray], explained_nodes: list[int]) -> dict[str, Any]:
        embedding_norm = np.asarray(encoder_bundle.get("embedding_norm", []), dtype=float).reshape(-1)
        embedding_cos_center = np.asarray(encoder_bundle.get("embedding_cos_center", []), dtype=float).reshape(-1)
        idx = np.asarray(explained_nodes, dtype=int)
        if len(idx) and len(embedding_norm) >= int(np.max(idx)) + 1:
            explained_norm = embedding_norm[idx]
        else:
            explained_norm = np.zeros((0,), dtype=float)
        if len(idx) and len(embedding_cos_center) >= int(np.max(idx)) + 1:
            explained_cos = embedding_cos_center[idx]
        else:
            explained_cos = np.zeros((0,), dtype=float)

        return {
            "embedding_dim_proxy": int(len(embedding_norm)),
            "explained_nodes": int(len(explained_nodes)),
            "explained_embedding_norm_mean": float(np.mean(explained_norm)) if len(explained_norm) else 0.0,
            "explained_embedding_norm_std": float(np.std(explained_norm)) if len(explained_norm) else 0.0,
            "explained_embedding_cos_center_mean": float(np.mean(explained_cos)) if len(explained_cos) else 0.0,
            "explained_embedding_cos_center_std": float(np.std(explained_cos)) if len(explained_cos) else 0.0,
        }

    def _encoder_shap_analysis(
        self,
        *,
        feature_names: list[str],
        mean_abs: np.ndarray,
        encoder_bundle: dict[str, np.ndarray],
        batch_explanations: list[dict[str, Any]],
        top_k: int,
    ) -> dict[str, Any]:
        encoder_pairs: list[tuple[int, float]] = []
        for idx, name in enumerate(feature_names):
            if name in self._CONTRASTIVE_FEATURE_NAMES:
                continue
            encoder_pairs.append((idx, float(mean_abs[idx])))
        encoder_pairs.sort(key=lambda item: item[1], reverse=True)

        top_encoder_features = [
            {
                "feature_index": int(idx),
                "feature_name": feature_names[idx],
                "feature_alias": self._feature_display(feature_names[idx]),
                "importance": float(score),
                "category": self._feature_category(feature_names[idx]),
            }
            for idx, score in encoder_pairs[: max(1, int(top_k))]
        ]

        embedding_norm = np.asarray(encoder_bundle.get("embedding_norm", []), dtype=float).reshape(-1)
        embedding_cos_center = np.asarray(encoder_bundle.get("embedding_cos_center", []), dtype=float).reshape(-1)
        local_abs = np.asarray([np.sum(np.abs(np.asarray(item["raw_shap_values"], dtype=float))) for item in batch_explanations], dtype=float)
        explain_idx = np.asarray([int(item["node_index"]) for item in batch_explanations], dtype=int)
        emb_slice = embedding_norm[explain_idx] if len(embedding_norm) > 0 and len(explain_idx) > 0 else np.zeros((0,), dtype=float)
        corr = 0.0
        if len(local_abs) > 1 and len(emb_slice) == len(local_abs) and np.std(local_abs) > 1e-9 and np.std(emb_slice) > 1e-9:
            corr = float(np.corrcoef(local_abs, emb_slice)[0, 1])

        return {
            "top_encoder_features": top_encoder_features,
            "embedding_norm_stats": {
                "mean": float(np.mean(embedding_norm)) if len(embedding_norm) else 0.0,
                "std": float(np.std(embedding_norm)) if len(embedding_norm) else 0.0,
            },
            "embedding_cos_center_stats": {
                "mean": float(np.mean(embedding_cos_center)) if len(embedding_cos_center) else 0.0,
                "std": float(np.std(embedding_cos_center)) if len(embedding_cos_center) else 0.0,
            },
            "embedding_shap_alignment": corr,
        }

    def _contrastive_shap_analysis(self, *, feature_names: list[str], mean_abs: np.ndarray, score_bundle: dict[str, np.ndarray], top_k: int) -> dict[str, Any]:
        pairs: list[tuple[str, float]] = []
        for idx, name in enumerate(feature_names):
            if name in self._CONTRASTIVE_FEATURE_NAMES:
                pairs.append((name, float(mean_abs[idx])))
        pairs.sort(key=lambda item: item[1], reverse=True)
        top_contrastive_features = [
            {
                "feature_name": name,
                "feature_alias": self._feature_display(name),
                "importance": float(score),
                "category": self._feature_category(name),
            }
            for name, score in pairs[: max(1, int(top_k))]
        ]
        return {
            "top_contrastive_features": top_contrastive_features,
            "score_component_stats": {
                "feature_distance_mean": float(np.mean(np.asarray(score_bundle.get("feature_distance", []), dtype=float))) if len(np.asarray(score_bundle.get("feature_distance", []), dtype=float)) else 0.0,
                "density_mean": float(np.mean(np.asarray(score_bundle.get("density", []), dtype=float))) if len(np.asarray(score_bundle.get("density", []), dtype=float)) else 0.0,
                "nearest_neighbor_mean": float(np.mean(np.asarray(score_bundle.get("nearest_neighbor", []), dtype=float))) if len(np.asarray(score_bundle.get("nearest_neighbor", []), dtype=float)) else 0.0,
                "bank_similarity_mean": float(np.mean(np.asarray(score_bundle.get("bank_similarity", []), dtype=float))) if len(np.asarray(score_bundle.get("bank_similarity", []), dtype=float)) else 0.0,
            },
        }

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
        explained_nodes, anomaly_threshold = self._select_explained_nodes(target, int(max_explain_nodes or self.config.max_explain_nodes))
        decomposition_payload = self._score_decomposition(
            feature_distance=np.asarray(context["score_bundle"]["feature_distance"], dtype=float),
            density=np.asarray(context["score_bundle"]["density"], dtype=float),
            nearest_neighbor=np.asarray(context["score_bundle"]["nearest_neighbor"], dtype=float),
            bank_similarity=np.asarray(context["score_bundle"]["bank_similarity"], dtype=float),
            combined=target,
        )
        dec_by_node = {int(item["node_index"]): item for item in decomposition_payload["decomposition"]}
        selected_nsamples = int(nsamples or self.config.shap_nsamples)
        effective_nsamples = self._dynamic_shap_samples(selected_nsamples, context["scaled_x"].shape[1], len(v))

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
        background = self._select_background(np.asarray(context["scaled_x"], dtype=float), target)
        baseline = np.mean(background, axis=0)

        batch_explanations: list[dict[str, Any]] = []
        additivity_errors: list[float] = []
        for node_idx in explained_nodes:
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
                        l1_reg=f"num_features({max(4, int(self.config.shap_l1_reg_num_features))})",
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
            additivity_errors.append(float(abs((expected_value + float(np.sum(shap_values))) - pred)))
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
            contributions = contributions[: max(1, int(top_k))]
            batch_explanations.append(
                {
                    "node_index": int(node_idx),
                    "prediction": pred,
                    "target_prediction": float(target[node_idx]),
                    "is_anomaly": bool(target[node_idx] >= anomaly_threshold),
                    "expected_value": expected_value,
                    "backend": backend,
                    "confidence": float(np.exp(-abs(pred - target[node_idx]) / (abs(target[node_idx]) + 1e-6))),
                    "top_contributions": contributions,
                    "raw_shap_values": [float(x) for x in shap_values.tolist()],
                    "decomposition": dec_by_node.get(
                        int(node_idx),
                        {
                            "feature_distance_component": 0.0,
                            "density_component": 0.0,
                            "nearest_neighbor_component": 0.0,
                            "bank_similarity_component": 0.0,
                        },
                    ),
                    "reason": self._explanation_reason(
                        node_idx=int(node_idx),
                        decomposition_row=dec_by_node.get(
                            int(node_idx),
                            {
                                "feature_distance_component": 0.0,
                                "density_component": 0.0,
                                "nearest_neighbor_component": 0.0,
                                "bank_similarity_component": 0.0,
                            },
                        ),
                        top_contributions=contributions,
                    ),
                }
            )

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

        mean_abs_error = float(
            np.mean(
                [
                    abs(float(item["prediction"]) - float(item["target_prediction"]))
                    for item in batch_explanations
                ]
            )
        ) if batch_explanations else 0.0
        score_bundle = context["score_bundle"]
        consistency = self._validate_explanation_consistency(
            decomposition=decomposition_payload["decomposition"],
            combined_scores=target,
            explained_nodes=explained_nodes,
        )
        component_summary = self._component_contribution_analysis(
            decomposition=decomposition_payload["decomposition"],
            explained_nodes=explained_nodes,
        )
        key_anomaly_features = self._extract_key_anomaly_features(batch_explanations=batch_explanations, top_k=int(top_k))
        anomaly_reasons = self._collect_anomaly_reasons(batch_explanations=batch_explanations)

        payload = {
            "summary": {
                "method": "shap",
                "explainer": "KernelExplainer",
                "explained_nodes": len(explained_nodes),
                "num_features": len(feature_names),
                "background_size": int(background.shape[0]),
                "nsamples": int(selected_nsamples),
                "explainer_config": {
                    "background_size": int(background.shape[0]),
                    "effective_nsamples": int(effective_nsamples),
                    "l1_reg_num_features": int(max(4, int(self.config.shap_l1_reg_num_features))),
                },
                "anomaly_threshold_p95": anomaly_threshold,
                "top_features": top_features,
                "average_confidence": float(np.mean([item["confidence"] for item in batch_explanations])) if batch_explanations else 0.0,
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
                "feature_distance": np.asarray(score_bundle["feature_distance"], dtype=float).astype(float).tolist(),
                "density": np.asarray(score_bundle["density"], dtype=float).astype(float).tolist(),
                "nearest_neighbor": np.asarray(score_bundle["nearest_neighbor"], dtype=float).astype(float).tolist(),
                "bank_similarity": np.asarray(score_bundle["bank_similarity"], dtype=float).astype(float).tolist(),
                "combined": target.astype(float).tolist(),
            },
            "encoder_components": {
                "embedding_norm": np.asarray(context["encoder_bundle"]["embedding_norm"], dtype=float).astype(float).tolist(),
                "embedding_cos_center": np.asarray(context["encoder_bundle"]["embedding_cos_center"], dtype=float).astype(float).tolist(),
            },
            "embedding_analysis": self._embedding_analysis(
                encoder_bundle=context["encoder_bundle"],
                scores=target,
                explained_nodes=explained_nodes,
            ),
            "embedding_input": self._embedding_input_summary(context["encoder_bundle"], explained_nodes),
            "encoder_shap_analysis": self._encoder_shap_analysis(
                feature_names=feature_names,
                mean_abs=mean_abs,
                encoder_bundle=context["encoder_bundle"],
                batch_explanations=batch_explanations,
                top_k=top_k,
            ),
            "contrastive_loss_shap_analysis": self._contrastive_shap_analysis(
                feature_names=feature_names,
                mean_abs=mean_abs,
                score_bundle=score_bundle,
                top_k=top_k,
            ),
            "surrogate_metrics": context["surrogate_metrics"],
            "preprocess": context["preprocess"],
            "validation": {
                "mean_abs_error": mean_abs_error,
                "surrogate_fidelity": _safe_float(context.get("surrogate_metrics", {}).get("fidelity", 0.0), 0.0),
                "additivity_mean_abs_error": float(np.mean(additivity_errors)) if additivity_errors else 0.0,
                "additivity_max_abs_error": float(np.max(additivity_errors)) if additivity_errors else 0.0,
            },
            "anomaly_analysis": self._anomaly_profile(target, explained_nodes),
            "performance": {
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "cache_hit": False,
                "backend": "shap" if shap_module is not None else "surrogate_linear",
                "effective_nsamples": int(effective_nsamples),
            },
        }
        self._cache_set(cache_key, payload)
        return payload
