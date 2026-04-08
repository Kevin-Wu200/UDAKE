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
        self.feature_mean: np.ndarray | None = None
        self.feature_std: np.ndarray | None = None
        self.feature_bank: np.ndarray = np.zeros((0, self.config.projection_dim), dtype=float)
        self.history: list[dict[str, float]] = []

    def is_trained(self) -> bool:
        return self.encoder_weight is not None and self.projector_weight is not None

    def _validate_inputs(self, coords: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be [[x, y], ...]")
        if len(c) != len(v):
            raise ValueError("coords and values length mismatch")
        if len(c) < 2:
            raise ValueError("at least 2 points are required")
        if not np.isfinite(c).all() or not np.isfinite(v).all():
            raise ValueError("coords and values must be finite")
        return c, v

    def _build_features(self, coords: np.ndarray, values: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1, 1)
        radius = np.linalg.norm(c, axis=1, keepdims=True)
        angle = np.arctan2(c[:, 1], c[:, 0]).reshape(-1, 1)
        centered_v = v - v.mean(axis=0, keepdims=True)
        return np.concatenate([c, radius, angle, v, centered_v], axis=1)

    def _pair_indices(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        if n <= 1:
            return np.zeros((0,), dtype=int), np.zeros((0,), dtype=int)
        pos = np.arange(n, dtype=int)
        neg = np.roll(pos, max(1, n // 2))
        if np.any(pos == neg):
            neg = np.roll(pos, 1)
        return pos, neg

    def preprocess_contrastive_data(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        *,
        batch_size: int | None = None,
        use_training_stats: bool = True,
        augmentation: bool = True,
    ) -> dict[str, object]:
        c, v = self._validate_inputs(coords, values)
        base = self._build_features(c, v)
        names = [
            "coord_x",
            "coord_y",
            "radius",
            "angle",
            "value",
            "value_centered",
        ]

        if augmentation:
            aug_coords = self._spatial_augment(c)
            aug_values = self._value_perturb(v)
            mask_values = self._mask_strategy(v)
        else:
            aug_coords = c.copy()
            aug_values = v.copy()
            mask_values = v.copy()

        aug_features = self._build_features(aug_coords, aug_values)
        masked_features = self._build_features(c, mask_values)

        feature_distance = np.linalg.norm(aug_features - base, axis=1, keepdims=True)
        density_score = np.abs(masked_features[:, [5]] - base[:, [5]])
        nearest_score = np.abs(masked_features[:, [4]] - base[:, [4]])
        bank_similarity = 1.0 / (1.0 + feature_distance)
        matrix = np.concatenate([base, feature_distance, density_score, nearest_score, bank_similarity], axis=1)
        names.extend(["feature_distance", "density_score", "nearest_score", "bank_similarity"])

        if use_training_stats and self.feature_mean is not None and self.feature_std is not None:
            processed = (matrix - self.feature_mean) / self.feature_std
            scaler = {
                "mean": np.asarray(self.feature_mean, dtype=float).reshape(-1).tolist(),
                "std": np.asarray(self.feature_std, dtype=float).reshape(-1).tolist(),
                "source": "trained",
            }
        else:
            mean = matrix.mean(axis=0, keepdims=True)
            std = matrix.std(axis=0, keepdims=True) + 1e-6
            processed = (matrix - mean) / std
            scaler = {
                "mean": mean.reshape(-1).tolist(),
                "std": std.reshape(-1).tolist(),
                "source": "runtime",
            }

        pos_idx, neg_idx = self._pair_indices(len(v))
        pair_size = int(len(pos_idx))
        size = int(max(1, batch_size or len(v)))
        slices = [[int(i), int(min(i + size, len(v)))] for i in range(0, len(v), size)]
        return {
            "coords": c,
            "values": v,
            "processed_features": processed.astype(float),
            "feature_names": names,
            "batch_slices": slices,
            "positive_pairs": np.column_stack([pos_idx, pos_idx]).astype(int).tolist() if pair_size else [],
            "negative_pairs": np.column_stack([pos_idx, neg_idx]).astype(int).tolist() if pair_size else [],
            "augmentations": {
                "aug_coords": aug_coords.astype(float).tolist(),
                "aug_values": aug_values.astype(float).tolist(),
                "mask_values": mask_values.astype(float).tolist(),
            },
            "scaler": scaler,
            "validation": {
                "is_valid": bool(np.isfinite(matrix).all() and len(v) > 0 and pair_size > 0),
                "n_points": int(len(v)),
                "pair_count": int(pair_size),
                "batch_size": size,
            },
        }

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
        coords, values = self._validate_inputs(coords, values)
        pre = self.preprocess_contrastive_data(coords, values, batch_size=64, use_training_stats=False, augmentation=True)
        mat = np.asarray(pre["processed_features"], dtype=float)
        self.feature_mean = mat.mean(axis=0, keepdims=True)
        self.feature_std = mat.std(axis=0, keepdims=True) + 1e-6
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
        coords, values = self._validate_inputs(coords, values)
        features = self._build_features(coords, values)
        return self._project(self._encode(features))

    def online_update(self, coords: np.ndarray, values: np.ndarray) -> dict[str, float]:
        emb = self.encode(coords, values)
        self._update_feature_bank(emb)
        return {"feature_bank_size": float(len(self.feature_bank))}

    def anomaly_scores(self, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        coords, values = self._validate_inputs(coords, values)
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
        bank_similarity = np.max(sim, axis=1)

        combined = 0.40 * safe_minmax(feat_dist) + 0.30 * safe_minmax(density) + 0.20 * safe_minmax(nearest) + 0.10 * (1.0 - safe_minmax(bank_similarity))

        return {
            "feature_distance": feat_dist,
            "density": density,
            "nearest_neighbor": nearest,
            "bank_similarity": bank_similarity,
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
        coords, values = self._validate_inputs(coords, values)
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
                "bank_similarity": bundle["bank_similarity"].tolist(),
            },
            "online_feature_bank_size": int(len(self.feature_bank)),
        }

    def predict_standard(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        *,
        threshold_method: ThresholdMethod = "percentile",
        percentile: float = 95.0,
        k: float = 2.5,
    ) -> dict[str, object]:
        if not self.is_trained():
            raise ValueError("模型尚未训练，无法执行标准预测")
        c, v = self._validate_inputs(coords, values)
        payload = self.predict(
            coords=c,
            values=v,
            threshold_method=threshold_method,
            percentile=percentile,
            k=k,
        )
        scores = np.asarray(payload.get("scores", []), dtype=float)
        labels = (scores >= float(payload.get("threshold", 0.0))).astype(int)
        if len(scores) == 0:
            return {
                "scores": [],
                "labels": [],
                "anomaly_count": 0,
                "anomaly_indices": [],
                "threshold": 0.0,
                "details": payload,
            }
        return {
            "scores": scores.astype(float).tolist(),
            "labels": labels.astype(int).tolist(),
            "anomaly_count": int(labels.sum()),
            "anomaly_indices": np.where(labels > 0)[0].astype(int).tolist(),
            "threshold": float(payload.get("threshold", 0.0)),
            "details": payload,
        }
