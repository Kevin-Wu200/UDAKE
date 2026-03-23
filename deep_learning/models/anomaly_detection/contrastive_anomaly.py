"""对比学习异常检测（轻量 numpy 实现）。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import ThresholdMethod, compute_threshold, safe_minmax


@dataclass
class ContrastiveConfig:
    feature_dim: int = 12
    projection_dim: int = 8
    temperature: float = 0.2
    queue_size: int = 256
    random_state: int = 42


class ContrastiveAnomalyDetector:
    """支持 SimCLR/MoCo/BYOL 风格损失近似与在线更新。"""

    def __init__(self, config: ContrastiveConfig | None = None) -> None:
        self.config = config or ContrastiveConfig()
        self.rng = np.random.default_rng(self.config.random_state)
        self.encoder_weight: np.ndarray | None = None
        self.projector_weight: np.ndarray | None = None
        self.feature_bank: np.ndarray = np.zeros((0, self.config.projection_dim), dtype=float)
        self.history: list[dict[str, float]] = []

    def _build_features(self, coords: np.ndarray, values: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1, 1)
        radius = np.linalg.norm(c, axis=1, keepdims=True)
        angle = np.arctan2(c[:, 1], c[:, 0]).reshape(-1, 1)
        centered_v = v - v.mean(axis=0, keepdims=True)
        return np.concatenate([c, radius, angle, v, centered_v], axis=1)

    def _spatial_augment(self, coords: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        theta = self.rng.uniform(-0.2, 0.2)
        scale = self.rng.uniform(0.9, 1.1)
        rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]], dtype=float)
        return (c @ rot.T) * scale

    def _value_perturb(self, values: np.ndarray) -> np.ndarray:
        v = np.asarray(values, dtype=float).reshape(-1)
        noise = self.rng.normal(0.0, 0.05 * (v.std() + 1e-6), size=len(v))
        return v + noise

    def _mask_strategy(self, values: np.ndarray, mask_ratio: float = 0.1) -> np.ndarray:
        v = np.asarray(values, dtype=float).reshape(-1).copy()
        n_mask = int(max(1, len(v) * mask_ratio)) if len(v) else 0
        if n_mask > 0:
            idx = self.rng.choice(len(v), size=n_mask, replace=False)
            v[idx] = np.median(v)
        return v

    def _encode(self, features: np.ndarray) -> np.ndarray:
        if self.encoder_weight is None:
            feat_dim = features.shape[1]
            self.encoder_weight = self.rng.normal(0.0, 1.0 / np.sqrt(feat_dim), size=(feat_dim, self.config.feature_dim))
        hidden = np.tanh(features @ self.encoder_weight)
        return hidden

    def _project(self, encoded: np.ndarray) -> np.ndarray:
        if self.projector_weight is None:
            dim = encoded.shape[1]
            self.projector_weight = self.rng.normal(0.0, 1.0 / np.sqrt(dim), size=(dim, self.config.projection_dim))
        proj = encoded @ self.projector_weight
        norm = np.linalg.norm(proj, axis=1, keepdims=True) + 1e-9
        return proj / norm

    def _simclr_loss(self, z1: np.ndarray, z2: np.ndarray) -> float:
        sim = z1 @ z2.T / max(self.config.temperature, 1e-6)
        pos = np.diag(sim)
        denom = np.log(np.exp(sim).sum(axis=1) + 1e-9)
        return float(np.mean(-(pos - denom)))

    def _moco_loss(self, z1: np.ndarray, z2: np.ndarray) -> float:
        if len(self.feature_bank) == 0:
            negatives = z2
        else:
            negatives = self.feature_bank
        pos = np.sum(z1 * z2, axis=1)
        neg = z1 @ negatives.T
        logits = np.concatenate([pos.reshape(-1, 1), neg], axis=1) / max(self.config.temperature, 1e-6)
        loss = -np.mean(logits[:, 0] - np.log(np.exp(logits).sum(axis=1) + 1e-9))
        return float(loss)

    def _byol_loss(self, z1: np.ndarray, z2: np.ndarray) -> float:
        return float(np.mean((z1 - z2) ** 2))

    def _update_feature_bank(self, projected: np.ndarray) -> None:
        if len(projected) == 0:
            return
        bank = np.concatenate([self.feature_bank, projected], axis=0)
        if len(bank) > self.config.queue_size:
            bank = bank[-self.config.queue_size :]
        self.feature_bank = bank

    def fit(self, coords: np.ndarray, values: np.ndarray, epochs: int = 30) -> dict[str, float]:
        self.history = []
        for epoch in range(max(1, epochs)):
            aug_coords = self._spatial_augment(coords)
            aug_values = self._value_perturb(values)
            mask_values = self._mask_strategy(values)

            x1 = self._build_features(aug_coords, aug_values)
            x2 = self._build_features(coords, mask_values)

            z1 = self._project(self._encode(x1))
            z2 = self._project(self._encode(x2))

            simclr = self._simclr_loss(z1, z2)
            moco = self._moco_loss(z1, z2)
            byol = self._byol_loss(z1, z2)
            total = 0.4 * simclr + 0.35 * moco + 0.25 * byol

            self._update_feature_bank(z2)
            self.history.append(
                {
                    "epoch": float(epoch),
                    "simclr_loss": float(simclr),
                    "moco_loss": float(moco),
                    "byol_loss": float(byol),
                    "total_loss": float(total),
                    "feature_bank_size": float(len(self.feature_bank)),
                }
            )

        return {
            "final_loss": float(self.history[-1]["total_loss"]),
            "best_loss": float(min(item["total_loss"] for item in self.history)),
            "feature_bank_size": float(len(self.feature_bank)),
        }

    def encode(self, coords: np.ndarray, values: np.ndarray) -> np.ndarray:
        features = self._build_features(coords, values)
        return self._project(self._encode(features))

    def online_update(self, coords: np.ndarray, values: np.ndarray) -> dict[str, float]:
        emb = self.encode(coords, values)
        self._update_feature_bank(emb)
        return {"feature_bank_size": float(len(self.feature_bank))}

    def anomaly_scores(self, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        emb = self.encode(coords, values)
        if len(self.feature_bank) == 0:
            self._update_feature_bank(emb)

        # 特征空间距离
        center = self.feature_bank.mean(axis=0, keepdims=True)
        feat_dist = np.linalg.norm(emb - center, axis=1)

        # 密度估计（kNN 距离）
        sim = emb @ self.feature_bank.T
        order = np.sort(sim, axis=1)
        k = min(5, order.shape[1])
        density = 1.0 - np.mean(order[:, -k:], axis=1)

        # 最近邻分析
        nearest = 1.0 - np.max(sim, axis=1)

        combined = 0.45 * safe_minmax(feat_dist) + 0.35 * safe_minmax(density) + 0.2 * safe_minmax(nearest)

        return {
            "feature_distance": feat_dist,
            "density": density,
            "nearest_neighbor": nearest,
            "combined": combined,
        }

    def predict(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        threshold_method: ThresholdMethod = "percentile",
        percentile: float = 95.0,
        k: float = 2.5,
    ) -> dict[str, object]:
        bundle = self.anomaly_scores(coords, values)
        combined = bundle["combined"]
        threshold = compute_threshold(combined, method=threshold_method, percentile=percentile, k=k)
        idx = np.where(combined >= threshold.value)[0]

        return {
            "anomaly_indices": idx.tolist(),
            "anomaly_count": int(len(idx)),
            "threshold": threshold.value,
            "threshold_method": threshold.method,
            "scores": combined.tolist(),
            "score_components": {
                "feature_distance": bundle["feature_distance"].tolist(),
                "density": bundle["density"].tolist(),
                "nearest_neighbor": bundle["nearest_neighbor"].tolist(),
            },
            "online_feature_bank_size": int(len(self.feature_bank)),
        }
