"""证据深度学习（EDL）不确定性量化实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from .common import ActivationType, ensure_1d, ensure_2d


@dataclass
class EDLConfig:
    in_dim: int
    num_classes: int
    hidden_dim: int = 32
    evidence_activation: ActivationType = "softplus"
    seed: int = 42


def _one_hot(labels: np.ndarray, num_classes: int) -> np.ndarray:
    y = np.asarray(labels, dtype=int).reshape(-1)
    out = np.zeros((len(y), num_classes), dtype=float)
    out[np.arange(len(y)), y] = 1.0
    return out


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - np.max(logits, axis=1, keepdims=True)
    e = np.exp(z)
    return e / np.maximum(np.sum(e, axis=1, keepdims=True), 1e-8)


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, x)


def _softplus(x: np.ndarray) -> np.ndarray:
    return np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0.0)


class EDLClassifier:
    """轻量 EDL 分类器。"""

    def __init__(self, config: EDLConfig) -> None:
        self.config = config
        rng = np.random.default_rng(config.seed)

        d = int(config.in_dim)
        h = int(max(4, config.hidden_dim))
        c = int(max(2, config.num_classes))

        self.w1 = rng.normal(0.0, 0.12, size=(d, h))
        self.b1 = np.zeros(h, dtype=float)
        self.w2 = rng.normal(0.0, 0.12, size=(h, c))
        self.b2 = np.zeros(c, dtype=float)

        self.history: list[dict[str, float]] = []
        self.feature_names: list[str] = [f"feature_{i}" for i in range(int(config.in_dim))]
        self._runtime_feature_mean = np.zeros(int(config.in_dim), dtype=float)
        self._runtime_feature_std = np.ones(int(config.in_dim), dtype=float)
        self._has_runtime_stats = False

    def _activate_evidence(self, logits: np.ndarray) -> np.ndarray:
        if self.config.evidence_activation == "relu":
            return _relu(logits)
        return _softplus(logits)

    def _forward(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        z1 = x @ self.w1 + self.b1
        h = np.tanh(z1)
        logits = h @ self.w2 + self.b2
        evidence = self._activate_evidence(logits)
        alpha = evidence + 1.0
        probs = alpha / np.maximum(np.sum(alpha, axis=1, keepdims=True), 1e-8)
        return h, logits, evidence, alpha, probs

    def loss_cross_entropy(self, probs: np.ndarray, labels: np.ndarray) -> float:
        y = ensure_1d(labels).astype(int)
        one_hot = _one_hot(y, self.config.num_classes)
        ce = -np.sum(one_hot * np.log(np.maximum(probs, 1e-8)), axis=1)
        return float(np.mean(ce))

    def loss_evidential_mse(self, alpha: np.ndarray, labels: np.ndarray) -> float:
        y = ensure_1d(labels).astype(int)
        target = _one_hot(y, self.config.num_classes)
        s = np.sum(alpha, axis=1, keepdims=True)
        mean = alpha / np.maximum(s, 1e-8)
        err = np.sum((target - mean) ** 2, axis=1)
        var = np.sum(alpha * (s - alpha) / (np.maximum(s, 1e-8) ** 2 * np.maximum(s + 1.0, 1e-8)), axis=1)
        return float(np.mean(err + var))

    def loss_kl_regularization(self, alpha: np.ndarray) -> float:
        c = float(self.config.num_classes)
        s = np.sum(alpha, axis=1, keepdims=True)
        probs = alpha / np.maximum(s, 1e-8)
        uniform = 1.0 / c
        kl = np.sum(probs * np.log(np.maximum(probs / uniform, 1e-8)), axis=1)
        return float(np.mean(kl))

    def fit(
        self,
        x: np.ndarray,
        y: np.ndarray,
        epochs: int = 220,
        lr: float = 8e-3,
        evidence_weight: float = 0.4,
        kl_weight: float = 0.05,
    ) -> dict[str, Any]:
        features = ensure_2d(x)
        labels = ensure_1d(y).astype(int)
        n = float(len(labels))

        for epoch in range(int(max(1, epochs))):
            h, logits, evidence, alpha, probs = self._forward(features)
            target = _one_hot(labels, self.config.num_classes)

            # 主梯度按 softmax CE 计算，EDL 正则用于稳定输出不确定性。
            d_logits = (probs - target) / n
            if self.config.evidence_activation == "relu":
                grad_evidence = (logits > 0.0).astype(float)
            else:
                grad_evidence = 1.0 / (1.0 + np.exp(-logits))
            d_logits = d_logits * (1.0 + evidence_weight * grad_evidence)

            grad_w2 = h.T @ d_logits
            grad_b2 = np.sum(d_logits, axis=0)

            dh = d_logits @ self.w2.T
            dz1 = dh * (1.0 - h ** 2)
            grad_w1 = features.T @ dz1
            grad_b1 = np.sum(dz1, axis=0)

            # 简单 L2 正则作为稳定器
            grad_w2 += kl_weight * self.w2
            grad_w1 += kl_weight * self.w1

            self.w2 -= lr * grad_w2
            self.b2 -= lr * grad_b2
            self.w1 -= lr * grad_w1
            self.b1 -= lr * grad_b1

            ce = self.loss_cross_entropy(probs, labels)
            mse = self.loss_evidential_mse(alpha, labels)
            kl = self.loss_kl_regularization(alpha)
            total = ce + evidence_weight * mse + kl_weight * kl
            self.history.append(
                {
                    "epoch": float(epoch + 1),
                    "cross_entropy": float(ce),
                    "evidence_mse": float(mse),
                    "kl": float(kl),
                    "total": float(total),
                }
            )

        return {
            "epochs": int(max(1, epochs)),
            "final_loss": float(self.history[-1]["total"]),
            "best_total_loss": float(min(r["total"] for r in self.history)),
            "final_cross_entropy": float(self.history[-1]["cross_entropy"]),
        }

    def predict(self, x: np.ndarray, confidence: float = 0.95) -> dict[str, Any]:
        features = ensure_2d(x)
        _, logits, evidence, alpha, probs = self._forward(features)
        s = np.sum(alpha, axis=1)
        num_classes = float(self.config.num_classes)

        # 知识不确定性：总证据越低，不确定性越高。
        knowledge_uncertainty = num_classes / np.maximum(s, 1e-8)
        # 数据不确定性：类别概率越分散越高。
        data_uncertainty = np.sum(probs * (1.0 - probs), axis=1)
        total_uncertainty = np.maximum(knowledge_uncertainty + data_uncertainty, 1e-8)

        confidence_score = 1.0 / (1.0 + total_uncertainty)
        pred_label = np.argmax(probs, axis=1)

        return {
            "logits": logits,
            "evidence": evidence,
            "alpha": alpha,
            "probabilities": probs,
            "prediction": pred_label,
            "confidence": confidence_score,
            "uncertainty": {
                "total": total_uncertainty,
                "data": data_uncertainty,
                "knowledge": knowledge_uncertainty,
                "threshold": float(confidence),
            },
        }

    def preprocess_edl_data(
        self,
        features: np.ndarray | list[list[float]],
        *,
        feature_names: list[str] | None = None,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        x_raw = ensure_2d(np.asarray(features, dtype=float))
        expected_dim = int(self.config.in_dim)
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

    def predict_edl(
        self,
        features: np.ndarray | list[list[float]],
        *,
        confidence: float = 0.95,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_edl_data(features, use_training_stats=use_training_stats)
        pred = self.predict(
            np.asarray(pre["processed_features"], dtype=float),
            confidence=confidence,
        )
        pred["preprocess"] = {
            "scaler": dict(pre["scaler"]),
            "validation": dict(pre["validation"]),
            "feature_names": list(pre["feature_names"]),
        }
        return pred

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

    @staticmethod
    def _moment_skew_kurt(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        arr = np.asarray(values, dtype=float)
        mean = np.mean(arr, axis=0)
        centered = arr - mean.reshape(1, -1)
        std = np.std(arr, axis=0)
        denom3 = np.maximum(std, 1e-8) ** 3
        denom4 = np.maximum(std, 1e-8) ** 4
        skew = np.mean(centered ** 3, axis=0) / denom3
        kurt = np.mean(centered ** 4, axis=0) / denom4 - 3.0
        skew = np.where(np.isfinite(skew), skew, 0.0)
        kurt = np.where(np.isfinite(kurt), kurt, 0.0)
        return skew.astype(float), kurt.astype(float)

    def explain_evidence(
        self,
        features: np.ndarray | list[list[float]],
        *,
        top_k: int = 8,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_edl_data(features, use_training_stats=use_training_stats)
        pred = self.predict_edl(features, use_training_stats=use_training_stats)

        evidence = np.asarray(pred["evidence"], dtype=float)
        alpha = np.asarray(pred["alpha"], dtype=float)
        probs = np.asarray(pred["probabilities"], dtype=float)
        confidence = np.asarray(pred["confidence"], dtype=float).reshape(-1)
        total_uncertainty = np.asarray(pred["uncertainty"]["total"], dtype=float).reshape(-1)
        n, c = evidence.shape if evidence.ndim == 2 else (0, int(self.config.num_classes))
        if n == 0:
            return {
                "summary": {
                    "sample_count": 0,
                    "num_classes": int(c),
                    "mean_total_evidence": 0.0,
                    "mean_dirichlet_strength": 0.0,
                    "mean_confidence": 0.0,
                },
                "class_evidence_statistics": [],
                "top_high_evidence_samples": [],
                "top_low_evidence_samples": [],
            }

        total_evidence = np.sum(evidence, axis=1)
        dirichlet_strength = np.sum(alpha, axis=1)
        mean_total = float(np.mean(total_evidence))
        k = min(max(1, int(top_k)), n)
        high_idx = np.argsort(total_evidence)[::-1][:k]
        low_idx = np.argsort(total_evidence)[:k]

        class_stats = []
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

        return {
            "summary": {
                "sample_count": int(n),
                "num_classes": int(c),
                "mean_total_evidence": mean_total,
                "p90_total_evidence": float(np.quantile(total_evidence, 0.9)),
                "mean_dirichlet_strength": float(np.mean(dirichlet_strength)),
                "mean_confidence": float(np.mean(confidence)),
                "mean_total_uncertainty": float(np.mean(total_uncertainty)),
            },
            "class_evidence_statistics": class_stats,
            "top_high_evidence_samples": [
                {
                    "sample_index": int(i),
                    "prediction_label": int(np.argmax(probs[int(i)])),
                    "total_evidence": float(total_evidence[int(i)]),
                    "dirichlet_strength": float(dirichlet_strength[int(i)]),
                    "confidence": float(confidence[int(i)]),
                    "total_uncertainty": float(total_uncertainty[int(i)]),
                }
                for i in high_idx.tolist()
            ],
            "top_low_evidence_samples": [
                {
                    "sample_index": int(i),
                    "prediction_label": int(np.argmax(probs[int(i)])),
                    "total_evidence": float(total_evidence[int(i)]),
                    "dirichlet_strength": float(dirichlet_strength[int(i)]),
                    "confidence": float(confidence[int(i)]),
                    "total_uncertainty": float(total_uncertainty[int(i)]),
                }
                for i in low_idx.tolist()
            ],
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
                "feature_names": list(pre["feature_names"]),
            },
        }

    def analyze_uncertainty_evidence(
        self,
        features: np.ndarray | list[list[float]],
        *,
        top_k: int = 8,
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_edl_data(features, use_training_stats=use_training_stats)
        pred = self.predict_edl(features, use_training_stats=use_training_stats)

        evidence = np.asarray(pred["evidence"], dtype=float)
        probs = np.asarray(pred["probabilities"], dtype=float)
        confidence = np.asarray(pred["confidence"], dtype=float).reshape(-1)
        total_uncertainty = np.asarray(pred["uncertainty"]["total"], dtype=float).reshape(-1)
        data_uncertainty = np.asarray(pred["uncertainty"]["data"], dtype=float).reshape(-1)
        knowledge_uncertainty = np.asarray(pred["uncertainty"]["knowledge"], dtype=float).reshape(-1)
        total_evidence = np.sum(evidence, axis=1) if evidence.ndim == 2 else np.zeros_like(total_uncertainty)

        n = int(total_uncertainty.size)
        if n == 0:
            return {
                "summary": {
                    "sample_count": 0,
                    "corr_total_uncertainty_total_evidence": 0.0,
                    "corr_knowledge_uncertainty_total_evidence": 0.0,
                    "corr_confidence_total_evidence": 0.0,
                },
                "evidence_uncertainty_profile": [],
                "top_high_uncertainty_samples": [],
            }

        k = min(max(1, int(top_k)), n)
        high_unc_idx = np.argsort(total_uncertainty)[::-1][:k]
        q_edges = np.quantile(total_evidence, [0.0, 0.33, 0.66, 1.0]) if n > 0 else np.zeros(4, dtype=float)
        bins = [("low", q_edges[0], q_edges[1]), ("medium", q_edges[1], q_edges[2]), ("high", q_edges[2], q_edges[3])]
        profile: list[dict[str, Any]] = []
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
                    "mean_total_uncertainty": float(np.mean(total_uncertainty[mask])),
                    "mean_knowledge_uncertainty": float(np.mean(knowledge_uncertainty[mask])),
                    "mean_data_uncertainty": float(np.mean(data_uncertainty[mask])),
                    "mean_confidence": float(np.mean(confidence[mask])),
                }
            )

        return {
            "summary": {
                "sample_count": int(n),
                "mean_total_evidence": float(np.mean(total_evidence)),
                "mean_total_uncertainty": float(np.mean(total_uncertainty)),
                "corr_total_uncertainty_total_evidence": self._safe_corr(total_uncertainty, total_evidence),
                "corr_knowledge_uncertainty_total_evidence": self._safe_corr(knowledge_uncertainty, total_evidence),
                "corr_data_uncertainty_total_evidence": self._safe_corr(data_uncertainty, total_evidence),
                "corr_confidence_total_evidence": self._safe_corr(confidence, total_evidence),
            },
            "evidence_uncertainty_profile": profile,
            "top_high_uncertainty_samples": [
                {
                    "sample_index": int(i),
                    "prediction_label": int(np.argmax(probs[int(i)])),
                    "total_uncertainty": float(total_uncertainty[int(i)]),
                    "knowledge_uncertainty": float(knowledge_uncertainty[int(i)]),
                    "data_uncertainty": float(data_uncertainty[int(i)]),
                    "total_evidence": float(total_evidence[int(i)]),
                    "confidence": float(confidence[int(i)]),
                }
                for i in high_unc_idx.tolist()
            ],
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
                "feature_names": list(pre["feature_names"]),
            },
        }

    def analyze_confidence_distribution(
        self,
        features: np.ndarray | list[list[float]],
        *,
        top_k: int = 8,
        quantiles: Sequence[float] = (0.05, 0.25, 0.5, 0.75, 0.95),
        use_training_stats: bool = True,
    ) -> dict[str, Any]:
        pre = self.preprocess_edl_data(features, use_training_stats=use_training_stats)
        pred = self.predict_edl(features, use_training_stats=use_training_stats)

        probs = np.asarray(pred["probabilities"], dtype=float)
        confidence = np.asarray(pred["confidence"], dtype=float).reshape(-1)
        total_uncertainty = np.asarray(pred["uncertainty"]["total"], dtype=float).reshape(-1)
        knowledge_uncertainty = np.asarray(pred["uncertainty"]["knowledge"], dtype=float).reshape(-1)
        data_uncertainty = np.asarray(pred["uncertainty"]["data"], dtype=float).reshape(-1)
        entropy = -np.sum(probs * np.log(np.maximum(probs, 1e-8)), axis=1) if probs.ndim == 2 else np.zeros_like(confidence)

        n = int(confidence.size)
        if n == 0:
            return {
                "summary": {
                    "sample_count": 0,
                    "mean_confidence": 0.0,
                    "std_confidence": 0.0,
                    "corr_confidence_total_uncertainty": 0.0,
                },
                "quantiles": {},
                "top_low_confidence_samples": [],
            }

        q = np.asarray(list(quantiles), dtype=float)
        q = np.clip(q, 0.0, 1.0)
        if q.size == 0:
            q = np.asarray([0.5], dtype=float)
        q_conf = np.quantile(confidence, q)
        q_unc = np.quantile(total_uncertainty, q)
        k = min(max(1, int(top_k)), n)
        low_conf_idx = np.argsort(confidence)[:k]
        skew, kurt = self._moment_skew_kurt(confidence.reshape(-1, 1))

        return {
            "summary": {
                "sample_count": int(n),
                "mean_confidence": float(np.mean(confidence)),
                "std_confidence": float(np.std(confidence)),
                "p10_confidence": float(np.quantile(confidence, 0.1)),
                "p90_confidence": float(np.quantile(confidence, 0.9)),
                "mean_total_uncertainty": float(np.mean(total_uncertainty)),
                "mean_prediction_entropy": float(np.mean(entropy)),
                "mean_knowledge_uncertainty": float(np.mean(knowledge_uncertainty)),
                "mean_data_uncertainty": float(np.mean(data_uncertainty)),
                "corr_confidence_total_uncertainty": self._safe_corr(confidence, total_uncertainty),
                "corr_confidence_entropy": self._safe_corr(confidence, entropy),
                "confidence_skewness": float(skew[0]),
                "confidence_excess_kurtosis": float(kurt[0]),
            },
            "quantiles": {
                f"q{int(v * 100):02d}": {
                    "confidence": float(q_conf[i]),
                    "total_uncertainty": float(q_unc[i]),
                }
                for i, v in enumerate(q.tolist())
            },
            "top_low_confidence_samples": [
                {
                    "sample_index": int(i),
                    "confidence": float(confidence[int(i)]),
                    "total_uncertainty": float(total_uncertainty[int(i)]),
                    "knowledge_uncertainty": float(knowledge_uncertainty[int(i)]),
                    "data_uncertainty": float(data_uncertainty[int(i)]),
                    "prediction_entropy": float(entropy[int(i)]),
                }
                for i in low_conf_idx.tolist()
            ],
            "preprocess": {
                "scaler": dict(pre["scaler"]),
                "validation": dict(pre["validation"]),
                "feature_names": list(pre["feature_names"]),
            },
        }

    def reliability_diagram(self, probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> dict[str, np.ndarray]:
        p = np.asarray(probs, dtype=float)
        y = ensure_1d(labels).astype(int)
        conf = np.max(p, axis=1)
        pred = np.argmax(p, axis=1)
        correct = (pred == y).astype(float)

        bins = np.linspace(0.0, 1.0, int(max(2, n_bins)) + 1)
        bin_acc = np.zeros(len(bins) - 1, dtype=float)
        bin_conf = np.zeros(len(bins) - 1, dtype=float)
        bin_count = np.zeros(len(bins) - 1, dtype=float)

        for i in range(len(bins) - 1):
            left, right = bins[i], bins[i + 1]
            mask = (conf >= left) & (conf < right if i < len(bins) - 2 else conf <= right)
            if np.any(mask):
                bin_acc[i] = float(np.mean(correct[mask]))
                bin_conf[i] = float(np.mean(conf[mask]))
                bin_count[i] = float(np.sum(mask))

        return {
            "bins": bins,
            "accuracy": bin_acc,
            "confidence": bin_conf,
            "count": bin_count,
        }

    def expected_calibration_error(self, probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
        rel = self.reliability_diagram(probs, labels, n_bins=n_bins)
        total = np.sum(rel["count"])
        if total <= 0:
            return 0.0
        gap = np.abs(rel["accuracy"] - rel["confidence"])
        return float(np.sum(gap * rel["count"]) / total)

    def temperature_scaling(
        self,
        x: np.ndarray,
        y: np.ndarray,
        candidates: list[float] | None = None,
    ) -> dict[str, float]:
        features = ensure_2d(x)
        labels = ensure_1d(y).astype(int)
        _, logits, _, _, _ = self._forward(features)

        candidates = candidates or [0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0]
        best_t = 1.0
        best_ce = float("inf")

        for t in candidates:
            scaled = logits / float(max(t, 1e-4))
            probs = _softmax(scaled)
            ce = self.loss_cross_entropy(probs, labels)
            if ce < best_ce:
                best_ce = ce
                best_t = float(t)

        return {"temperature": best_t, "cross_entropy": float(best_ce)}
