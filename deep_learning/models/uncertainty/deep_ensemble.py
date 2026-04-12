"""Deep Ensemble 不确定性量化实现。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import copy
import hashlib
import json
import threading
from typing import Any, Literal

import numpy as np

from .common import PredictiveMoments, confidence_interval, decompose_uncertainty, ensure_1d, ensure_2d

EnsembleAgg = Literal["mean", "weighted", "median"]
SelectMethod = Literal["validation", "diversity", "adaptive"]


@dataclass
class EnsembleMemberMetadata:
    model_id: str
    version: str
    random_seed: int
    hidden_dim: int
    learning_rate: float
    train_size: int
    val_nll: float


class _DeterministicRegressor:
    def __init__(self, in_dim: int, hidden_dim: int, seed: int) -> None:
        self.rng = np.random.default_rng(seed)
        h = int(max(4, hidden_dim))
        self.w1 = self.rng.normal(0.0, 0.12, size=(in_dim, h))
        self.b1 = np.zeros(h, dtype=float)
        self.wm = self.rng.normal(0.0, 0.12, size=(h, 1))
        self.bm = np.zeros(1, dtype=float)
        self.wv = self.rng.normal(0.0, 0.12, size=(h, 1))
        self.bv = np.zeros(1, dtype=float)

    def _forward(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        z1 = x @ self.w1 + self.b1
        h = np.tanh(z1)
        mean = (h @ self.wm + self.bm).reshape(-1)
        logvar = np.clip((h @ self.wv + self.bv).reshape(-1), -8.0, 5.0)
        var = np.exp(logvar) + 1e-6
        return h, mean, logvar, var

    def fit(self, x: np.ndarray, y: np.ndarray, epochs: int = 180, lr: float = 8e-3) -> None:
        n = float(len(y))
        for _ in range(int(max(1, epochs))):
            h, mean, _, var = self._forward(x)
            err = mean - y

            d_mean = err / var / n
            d_logvar = 0.5 * (1.0 - (err ** 2) / var) / n

            grad_wm = h.T @ d_mean[:, None]
            grad_bm = np.sum(d_mean)
            grad_wv = h.T @ d_logvar[:, None]
            grad_bv = np.sum(d_logvar)

            dh = d_mean[:, None] @ self.wm.T + d_logvar[:, None] @ self.wv.T
            dz1 = dh * (1.0 - h ** 2)
            grad_w1 = x.T @ dz1
            grad_b1 = np.sum(dz1, axis=0)

            self.wm -= lr * grad_wm
            self.bm -= lr * grad_bm
            self.wv -= lr * grad_wv
            self.bv -= lr * grad_bv
            self.w1 -= lr * grad_w1
            self.b1 -= lr * grad_b1

    def predict(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        _, mean, _, var = self._forward(x)
        return mean, var


class DeepEnsembleRegressor:
    """多模型训练、注册与集成推理。"""

    def __init__(self, in_dim: int, n_members: int = 5, seed: int = 42) -> None:
        self.in_dim = int(in_dim)
        self.n_members = int(max(2, n_members))
        self.seed = int(seed)

        self.members: dict[str, _DeterministicRegressor] = {}
        self.metadata: dict[str, EnsembleMemberMetadata] = {}
        self.active_member_ids: list[str] = []
        self.feature_names: list[str] = [f"feature_{i}" for i in range(self.in_dim)]
        self._runtime_feature_mean = np.zeros(self.in_dim, dtype=float)
        self._runtime_feature_std = np.ones(self.in_dim, dtype=float)
        self._has_runtime_stats = False
        self._predict_cache_lock = threading.Lock()
        self._predict_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._predict_cache_size = 24
        self._predict_cache_hits = 0
        self._predict_cache_misses = 0

    def _split_train_val(self, x: np.ndarray, y: np.ndarray, ratio: float = 0.2) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        n = len(y)
        val_n = int(max(1, min(n - 1, round(n * ratio))))
        idx = np.arange(n)
        np.random.default_rng(self.seed).shuffle(idx)
        val_idx = idx[:val_n]
        train_idx = idx[val_n:]
        return x[train_idx], y[train_idx], x[val_idx], y[val_idx]

    def _sample_member_data(self, x: np.ndarray, y: np.ndarray, member_idx: int, mode: str = "bootstrap") -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(self.seed + member_idx * 17)
        n = len(y)
        if mode == "subsample":
            k = max(2, int(0.8 * n))
            idx = rng.choice(n, size=k, replace=False)
            return x[idx], y[idx]
        idx = rng.choice(n, size=n, replace=True)
        return x[idx], y[idx]

    def fit(
        self,
        x: np.ndarray,
        y: np.ndarray,
        epochs: int = 180,
        data_mode: str = "bootstrap",
        hidden_dims: list[int] | None = None,
        learning_rates: list[float] | None = None,
    ) -> dict[str, Any]:
        features = ensure_2d(x)
        target = ensure_1d(y)

        x_train, y_train, x_val, y_val = self._split_train_val(features, target)
        hidden_dims = hidden_dims or [24, 32, 40]
        learning_rates = learning_rates or [8e-3, 6e-3, 1e-2]

        self.members.clear()
        self.metadata.clear()

        for i in range(self.n_members):
            member_id = f"member_{i}"
            version = f"v{i + 1}"
            hidden = int(hidden_dims[i % len(hidden_dims)])
            lr = float(learning_rates[i % len(learning_rates)])

            sub_x, sub_y = self._sample_member_data(x_train, y_train, i, mode=data_mode)
            model = _DeterministicRegressor(self.in_dim, hidden_dim=hidden, seed=self.seed + i)
            model.fit(sub_x, sub_y, epochs=epochs, lr=lr)
            pred_mean, pred_var = model.predict(x_val)
            val_nll = float(np.mean(0.5 * np.log(2.0 * np.pi * pred_var) + 0.5 * ((y_val - pred_mean) ** 2) / pred_var))

            self.members[member_id] = model
            self.metadata[member_id] = EnsembleMemberMetadata(
                model_id=member_id,
                version=version,
                random_seed=self.seed + i,
                hidden_dim=hidden,
                learning_rate=lr,
                train_size=int(len(sub_y)),
                val_nll=val_nll,
            )

        self.active_member_ids = sorted(self.members.keys())
        return {
            "n_members": len(self.members),
            "active_members": list(self.active_member_ids),
            "best_val_nll": float(min(meta.val_nll for meta in self.metadata.values())),
            "avg_val_nll": float(np.mean([meta.val_nll for meta in self.metadata.values()])),
        }

    def _collect_predictions(self, x: np.ndarray, member_ids: list[str] | None = None) -> tuple[np.ndarray, np.ndarray, list[str]]:
        features = ensure_2d(x)
        ids = member_ids or self.active_member_ids or sorted(self.members.keys())
        if not ids:
            raise ValueError("ensemble 尚未训练")

        means: list[np.ndarray] = []
        vars_: list[np.ndarray] = []
        for model_id in ids:
            pred_mean, pred_var = self.members[model_id].predict(features)
            means.append(pred_mean)
            vars_.append(pred_var)

        return np.vstack(means), np.vstack(vars_), ids

    def predict(
        self,
        x: np.ndarray,
        aggregation: EnsembleAgg = "mean",
        member_weights: dict[str, float] | None = None,
        confidence: float = 0.95,
    ) -> dict[str, Any]:
        features = ensure_2d(x)
        conf = float(confidence)
        cache_key = self._predict_cache_key(
            features,
            aggregation=aggregation,
            confidence=conf,
            member_weights=member_weights,
        )
        cached = self._predict_cache_get(cache_key)
        if cached is not None:
            result = dict(cached)
            result["performance"] = {
                **dict(result.get("performance", {})),
                "cache_hit": True,
                "cache_metrics": self._predict_cache_metrics(),
            }
            return result

        means, vars_, ids = self._collect_predictions(features)

        if aggregation == "weighted":
            if not member_weights:
                weights = np.ones(len(ids), dtype=float) / len(ids)
            else:
                weights = np.asarray([float(member_weights.get(mid, 0.0)) for mid in ids], dtype=float)
                weights = np.maximum(weights, 1e-8)
                weights = weights / np.sum(weights)
            mean_pred = np.sum(means * weights[:, None], axis=0)
            aleatoric = np.sum(vars_ * weights[:, None], axis=0)
            epistemic = np.sum(((means - mean_pred[None, :]) ** 2) * weights[:, None], axis=0)
            total = np.maximum(aleatoric + epistemic, 1e-8)
            moments = PredictiveMoments(mean=mean_pred, variance=total, aleatoric=aleatoric, epistemic=epistemic)
        elif aggregation == "median":
            mean_pred = np.median(means, axis=0)
            aleatoric = np.median(vars_, axis=0)
            epistemic = np.var(means, axis=0)
            moments = PredictiveMoments(
                mean=mean_pred,
                variance=np.maximum(aleatoric + epistemic, 1e-8),
                aleatoric=aleatoric,
                epistemic=epistemic,
            )
        else:
            moments = decompose_uncertainty(means, vars_)

        lower, upper = confidence_interval(moments.mean, moments.variance, confidence=conf)
        quantiles = {
            "q10": np.percentile(means, 10.0, axis=0),
            "q50": np.percentile(means, 50.0, axis=0),
            "q90": np.percentile(means, 90.0, axis=0),
        }

        result = {
            "mean": moments.mean,
            "variance": moments.variance,
            "aleatoric": moments.aleatoric,
            "epistemic": moments.epistemic,
            "lower": lower,
            "upper": upper,
            "quantiles": quantiles,
            "member_ids": ids,
            "aggregation": aggregation,
            "performance": {
                "cache_hit": False,
                "cache_metrics": self._predict_cache_metrics(),
            },
        }
        self._predict_cache_set(cache_key, result)
        return result

    def preprocess_deep_ensemble_data(
        self,
        features: np.ndarray | list[list[float]],
        *,
        feature_names: list[str] | None = None,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        x_raw = ensure_2d(np.asarray(features, dtype=float))
        expected_dim = int(self.in_dim)
        if x_raw.shape[1] != expected_dim:
            raise ValueError(f"输入维度不匹配：期望 {expected_dim}，实际 {x_raw.shape[1]}")

        names = list(feature_names) if feature_names is not None else [f"feature_{i}" for i in range(x_raw.shape[1])]
        if len(names) != x_raw.shape[1]:
            raise ValueError("feature_names 长度与特征维度不一致")

        if use_training_stats and self._has_runtime_stats:
            mean = np.asarray(self._runtime_feature_mean, dtype=float)
            std = np.asarray(self._runtime_feature_std, dtype=float)
            stats_source = "runtime"
        else:
            mean = np.mean(x_raw, axis=0)
            std = np.std(x_raw, axis=0)
            std = np.where(std > 1e-8, std, 1.0)
            self._runtime_feature_mean = mean.astype(float)
            self._runtime_feature_std = std.astype(float)
            self._has_runtime_stats = True
            stats_source = "batch"

        x_scaled = (x_raw - mean.reshape(1, -1)) / std.reshape(1, -1)
        self.feature_names = list(names)
        return {
            "raw_features": x_raw,
            "processed_features": x_scaled,
            "feature_names": list(names),
            "scaler": {
                "mean": [float(v) for v in mean.tolist()],
                "std": [float(v) for v in std.tolist()],
                "source": stats_source,
            },
            "validation": {
                "is_valid": True,
                "sample_count": int(x_raw.shape[0]),
                "feature_dim": int(x_raw.shape[1]),
                "stats_source": stats_source,
            },
        }

    def predict_deep_ensemble(
        self,
        features: np.ndarray | list[list[float]],
        *,
        aggregation: EnsembleAgg = "mean",
        member_weights: dict[str, float] | None = None,
        confidence: float = 0.95,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_deep_ensemble_data(features, use_training_stats=use_training_stats)
        pred = self.predict(
            np.asarray(pre["processed_features"], dtype=float),
            aggregation=aggregation,
            member_weights=member_weights,
            confidence=confidence,
        )
        pred["member_count"] = int(len(pred.get("member_ids", [])))
        pred["preprocess"] = {
            "scaler": dict(pre["scaler"]),
            "validation": dict(pre["validation"]),
            "feature_names": list(pre["feature_names"]),
        }
        return pred

    def model_diversity(self, x: np.ndarray) -> dict[str, float]:
        means, _, _ = self._collect_predictions(x)
        if means.shape[0] <= 1:
            return {"mean_corr": 1.0, "spread": 0.0}

        corrs: list[float] = []
        for i in range(means.shape[0]):
            for j in range(i + 1, means.shape[0]):
                if np.std(means[i]) < 1e-8 or np.std(means[j]) < 1e-8:
                    corrs.append(1.0)
                else:
                    corrs.append(float(np.corrcoef(means[i], means[j])[0, 1]))

        spread = float(np.mean(np.std(means, axis=0)))
        return {"mean_corr": float(np.mean(corrs)), "spread": spread}

    def select_members(
        self,
        x_val: np.ndarray,
        y_val: np.ndarray,
        method: SelectMethod = "validation",
        top_k: int | None = None,
    ) -> dict[str, Any]:
        features = ensure_2d(x_val)
        target = ensure_1d(y_val)
        ids = sorted(self.members.keys())
        if not ids:
            raise ValueError("ensemble 尚未训练")

        k = int(top_k or max(2, len(ids) // 2))
        k = min(k, len(ids))

        member_scores: dict[str, float] = {}
        preds: dict[str, np.ndarray] = {}
        for mid in ids:
            mean, var = self.members[mid].predict(features)
            nll = float(np.mean(0.5 * np.log(2.0 * np.pi * var) + 0.5 * ((target - mean) ** 2) / var))
            member_scores[mid] = nll
            preds[mid] = mean

        if method == "validation":
            selected = sorted(ids, key=lambda m: member_scores[m])[:k]
        elif method == "diversity":
            selected = [min(ids, key=lambda m: member_scores[m])]
            while len(selected) < k:
                candidates = [m for m in ids if m not in selected]
                best_mid = candidates[0]
                best_gain = -float("inf")
                for mid in candidates:
                    base = preds[mid]
                    gains: list[float] = []
                    for sm in selected:
                        other = preds[sm]
                        if np.std(base) < 1e-8 or np.std(other) < 1e-8:
                            gains.append(0.0)
                        else:
                            gains.append(1.0 - float(np.corrcoef(base, other)[0, 1]))
                    gain = float(np.mean(gains))
                    if gain > best_gain:
                        best_gain = gain
                        best_mid = mid
                selected.append(best_mid)
        else:
            # 自适应选择：验证分数 + 多样性联合排序
            selected = []
            score_norm = np.asarray([member_scores[mid] for mid in ids], dtype=float)
            score_norm = (score_norm - score_norm.min()) / (score_norm.max() - score_norm.min() + 1e-8)
            for _ in range(k):
                best_mid = None
                best_obj = float("inf")
                for idx, mid in enumerate(ids):
                    if mid in selected:
                        continue
                    diversity_penalty = 0.0
                    if selected:
                        cvals: list[float] = []
                        for sm in selected:
                            a = preds[mid]
                            b = preds[sm]
                            if np.std(a) < 1e-8 or np.std(b) < 1e-8:
                                cvals.append(1.0)
                            else:
                                cvals.append(float(np.corrcoef(a, b)[0, 1]))
                        diversity_penalty = float(np.mean(cvals))
                    objective = 0.7 * score_norm[idx] + 0.3 * diversity_penalty
                    if objective < best_obj:
                        best_obj = objective
                        best_mid = mid
                if best_mid is not None:
                    selected.append(best_mid)

        self.active_member_ids = selected
        return {
            "method": method,
            "selected": list(selected),
            "k": k,
            "scores": member_scores,
        }

    def registry_snapshot(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for mid in sorted(self.metadata.keys()):
            meta = self.metadata[mid]
            records.append(
                {
                    "model_id": meta.model_id,
                    "version": meta.version,
                    "seed": meta.random_seed,
                    "hidden_dim": meta.hidden_dim,
                    "learning_rate": meta.learning_rate,
                    "train_size": meta.train_size,
                    "val_nll": meta.val_nll,
                    "active": mid in self.active_member_ids,
                }
            )
        return records

    @staticmethod
    def _normalized_member_weights(
        ids: list[str],
        member_weights: dict[str, float] | None = None,
    ) -> np.ndarray:
        if not ids:
            return np.zeros(0, dtype=float)
        if not member_weights:
            return np.ones(len(ids), dtype=float) / float(len(ids))
        raw = np.asarray([float(member_weights.get(mid, 0.0)) for mid in ids], dtype=float)
        raw = np.maximum(raw, 1e-8)
        return raw / np.sum(raw)

    def explain_member_contributions(
        self,
        features: np.ndarray | list[list[float]],
        *,
        aggregation: EnsembleAgg = "mean",
        member_weights: dict[str, float] | None = None,
        top_k: int = 6,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_deep_ensemble_data(features, use_training_stats=use_training_stats)
        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        means, vars_, ids = self._collect_predictions(x_scaled)
        weights = self._normalized_member_weights(ids, member_weights if aggregation == "weighted" else None)
        ensemble_mean = np.sum(means * weights[:, None], axis=0)

        summaries: list[dict[str, Any]] = []
        member_pool: list[tuple[float, str, float, float]] = []
        for i, mid in enumerate(ids):
            pred = np.asarray(means[i], dtype=float)
            var = np.asarray(vars_[i], dtype=float)
            deviation = pred - ensemble_mean
            abs_dev = np.abs(deviation)
            mean_abs_dev = float(np.mean(abs_dev)) if abs_dev.size else 0.0
            rmse_to_ensemble = float(np.sqrt(np.mean(deviation ** 2))) if deviation.size else 0.0
            pred_std = float(np.std(pred)) if pred.size else 0.0
            weight = float(weights[i])
            contribution_score = float(weight * mean_abs_dev)
            member_pool.append((contribution_score, str(mid), weight, mean_abs_dev))
            summaries.append(
                {
                    "member_id": str(mid),
                    "weight": weight,
                    "prediction_mean": float(np.mean(pred)) if pred.size else 0.0,
                    "prediction_std": pred_std,
                    "mean_aleatoric": float(np.mean(var)) if var.size else 0.0,
                    "mean_abs_deviation_to_ensemble": mean_abs_dev,
                    "rmse_to_ensemble": rmse_to_ensemble,
                    "contribution_score": contribution_score,
                }
            )

        member_pool.sort(key=lambda item: item[0], reverse=True)
        k = max(1, min(int(top_k), len(member_pool))) if member_pool else 0
        top_members = [
            {
                "member_id": mid,
                "weight": float(weight),
                "mean_abs_deviation_to_ensemble": float(dev),
                "contribution_score": float(score),
            }
            for score, mid, weight, dev in member_pool[:k]
        ]

        return {
            "summary": {
                "sample_count": int(x_scaled.shape[0]),
                "member_count": int(len(ids)),
                "aggregation": str(aggregation),
                "mean_epistemic_from_members": float(np.mean(np.var(means, axis=0))) if means.size else 0.0,
                "mean_aleatoric_from_members": float(np.mean(np.mean(vars_, axis=0))) if vars_.size else 0.0,
            },
            "member_summaries": summaries,
            "top_contributing_members": top_members,
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
                "feature_names": list(pre["feature_names"]),
            },
        }

    def _model_signature(self) -> str:
        stats: list[float] = [float(self.n_members), float(self.seed), float(len(self.members))]
        for mid in sorted(self.metadata.keys()):
            meta = self.metadata[mid]
            stats.extend(
                [
                    float(meta.val_nll),
                    float(meta.hidden_dim),
                    float(meta.learning_rate),
                    float(meta.train_size),
                ]
            )
        normalized = ",".join(f"{v:.8f}" for v in stats)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _feature_fingerprint(self, x: np.ndarray) -> str:
        arr = np.ascontiguousarray(np.asarray(x, dtype=float))
        h = hashlib.sha256()
        h.update(str(tuple(int(v) for v in arr.shape)).encode("utf-8"))
        h.update(arr.tobytes())
        return h.hexdigest()

    def _predict_cache_key(
        self,
        features: np.ndarray,
        *,
        aggregation: EnsembleAgg,
        confidence: float,
        member_weights: dict[str, float] | None,
    ) -> str:
        payload = {
            "feature_hash": self._feature_fingerprint(features),
            "shape": [int(features.shape[0]), int(features.shape[1]) if features.ndim == 2 else 0],
            "aggregation": str(aggregation),
            "confidence": float(confidence),
            "active_member_ids": list(self.active_member_ids),
            "member_weights": {str(k): float(v) for k, v in sorted((member_weights or {}).items())},
            "model_hash": self._model_signature(),
        }
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _predict_cache_get(self, key: str) -> dict[str, Any] | None:
        with self._predict_cache_lock:
            cached = self._predict_cache.get(key)
            if cached is None:
                self._predict_cache_misses += 1
                return None
            self._predict_cache_hits += 1
            self._predict_cache.move_to_end(key)
            return copy.deepcopy(cached)

    def _predict_cache_set(self, key: str, value: dict[str, Any]) -> None:
        with self._predict_cache_lock:
            cached = copy.deepcopy(value)
            perf = dict(cached.get("performance", {}))
            perf.pop("cache_hit", None)
            cached["performance"] = perf
            self._predict_cache[key] = cached
            self._predict_cache.move_to_end(key)
            while len(self._predict_cache) > self._predict_cache_size:
                self._predict_cache.popitem(last=False)

    def _predict_cache_metrics(self) -> dict[str, float | int]:
        with self._predict_cache_lock:
            total = self._predict_cache_hits + self._predict_cache_misses
            return {
                "hits": int(self._predict_cache_hits),
                "misses": int(self._predict_cache_misses),
                "hit_rate": float(self._predict_cache_hits / max(1, total)),
            }

    def explain_ensemble_weights(
        self,
        *,
        strategy: str = "validation_softmax",
        temperature: float = 1.0,
    ) -> dict[str, Any]:
        ids = sorted(self.metadata.keys())
        if not ids:
            raise ValueError("ensemble 尚未训练")

        t = float(max(1e-6, temperature))
        val_nll = np.asarray([float(self.metadata[mid].val_nll) for mid in ids], dtype=float)
        if strategy == "uniform":
            weights = np.ones_like(val_nll, dtype=float) / float(len(ids))
        else:
            centered = (val_nll - np.min(val_nll)) / t
            logits = -centered
            logits = logits - np.max(logits)
            exp_w = np.exp(logits)
            weights = exp_w / np.sum(exp_w)

        entropy = float(-np.sum(weights * np.log(np.maximum(weights, 1e-12))))
        effective_members = float(1.0 / np.sum(np.maximum(weights, 1e-12) ** 2))
        records = [
            {
                "member_id": str(mid),
                "val_nll": float(self.metadata[mid].val_nll),
                "weight": float(weights[i]),
                "rank": int(i + 1),
            }
            for i, mid in enumerate([m for _, m in sorted(zip(weights, ids), key=lambda item: item[0], reverse=True)])
        ]
        return {
            "summary": {
                "strategy": str(strategy),
                "temperature": t,
                "member_count": int(len(ids)),
                "weight_entropy": entropy,
                "effective_member_count": effective_members,
                "max_weight": float(np.max(weights)),
                "min_weight": float(np.min(weights)),
            },
            "weight_distribution": records,
        }

    def analyze_model_diversity(
        self,
        features: np.ndarray | list[list[float]],
        *,
        top_k_pairs: int = 6,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_deep_ensemble_data(features, use_training_stats=use_training_stats)
        x_scaled = np.asarray(pre["processed_features"], dtype=float)
        means, _, ids = self._collect_predictions(x_scaled)
        if means.shape[0] <= 1:
            return {
                "summary": {
                    "member_count": int(means.shape[0]),
                    "sample_count": int(x_scaled.shape[0]),
                    "mean_pair_corr": 1.0,
                    "mean_pair_disagreement": 0.0,
                    "prediction_spread": 0.0,
                },
                "pairwise_diversity": [],
                "top_diverse_pairs": [],
            }

        pairs: list[dict[str, Any]] = []
        for i in range(means.shape[0]):
            for j in range(i + 1, means.shape[0]):
                a = np.asarray(means[i], dtype=float)
                b = np.asarray(means[j], dtype=float)
                if np.std(a) < 1e-8 or np.std(b) < 1e-8:
                    corr = 1.0
                else:
                    corr = float(np.corrcoef(a, b)[0, 1])
                    if not np.isfinite(corr):
                        corr = 1.0
                disagreement = float(np.mean(np.abs(a - b))) if a.size else 0.0
                diversity_score = float((1.0 - corr) * 0.5 + disagreement)
                pairs.append(
                    {
                        "member_a": str(ids[i]),
                        "member_b": str(ids[j]),
                        "correlation": corr,
                        "mean_absolute_disagreement": disagreement,
                        "diversity_score": diversity_score,
                    }
                )

        pair_corr = np.asarray([float(item["correlation"]) for item in pairs], dtype=float)
        pair_disagreement = np.asarray([float(item["mean_absolute_disagreement"]) for item in pairs], dtype=float)
        sorted_pairs = sorted(pairs, key=lambda item: float(item["diversity_score"]), reverse=True)
        k = max(1, min(int(top_k_pairs), len(sorted_pairs)))
        return {
            "summary": {
                "member_count": int(means.shape[0]),
                "sample_count": int(x_scaled.shape[0]),
                "mean_pair_corr": float(np.mean(pair_corr)) if pair_corr.size else 1.0,
                "mean_pair_disagreement": float(np.mean(pair_disagreement)) if pair_disagreement.size else 0.0,
                "prediction_spread": float(np.mean(np.std(means, axis=0))),
            },
            "pairwise_diversity": pairs,
            "top_diverse_pairs": sorted_pairs[:k],
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
                "feature_names": list(pre["feature_names"]),
            },
        }
