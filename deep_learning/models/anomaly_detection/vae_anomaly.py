"""VAE 风格异常检测（轻量 numpy 实现）。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import (
    ThresholdMethod,
    compute_threshold,
    multiscale_value_features,
    safe_minmax,
    standardize,
)


@dataclass
class VAETrainConfig:
    latent_dim: int = 4
    beta: float = 0.1
    max_epochs: int = 40
    noise_schedule_start: float = 1.0
    noise_schedule_end: float = 0.05
    random_state: int = 42


class VAEAnomalyDetector:
    """带编码器/潜在空间/解码器结构的异常检测器。"""

    def __init__(self, config: VAETrainConfig | None = None) -> None:
        self.config = config or VAETrainConfig()
        self.feature_mean: np.ndarray | None = None
        self.feature_std: np.ndarray | None = None
        self.feature_center: np.ndarray | None = None
        self.components: np.ndarray | None = None
        self.latent_mu: np.ndarray | None = None
        self.latent_logvar: np.ndarray | None = None
        self.history: list[dict[str, float]] = []
        self.rng = np.random.default_rng(self.config.random_state)

    def _coordinate_encoder(self, coords: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        radius = np.linalg.norm(c, axis=1, keepdims=True)
        angle = np.arctan2(c[:, 1], c[:, 0]).reshape(-1, 1)
        return np.concatenate([c, radius, angle], axis=1)

    def _value_encoder(self, values: np.ndarray) -> np.ndarray:
        v = np.asarray(values, dtype=float).reshape(-1, 1)
        centered = v - v.mean(axis=0, keepdims=True)
        return np.concatenate([v, centered, v * v], axis=1)

    def _spatial_feature_encoder(self, coords: np.ndarray, values: np.ndarray) -> np.ndarray:
        coord_feat = self._coordinate_encoder(coords)
        value_feat = self._value_encoder(values)
        multi_scale = multiscale_value_features(coords, values)
        merged = np.concatenate([coord_feat, value_feat, multi_scale], axis=1)

        # 残差连接：保留原始坐标和值，增强重建稳定性。
        skip = np.concatenate([coords, np.asarray(values, dtype=float).reshape(-1, 1)], axis=1)
        return np.concatenate([merged, skip], axis=1)

    def _latent_projection(self, features: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        centered = features - features.mean(axis=0, keepdims=True)
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        latent_dim = int(max(1, min(self.config.latent_dim, vt.shape[0])))
        components = vt[:latent_dim].T
        mu = centered @ components
        residual = centered - mu @ components.T
        variance = np.var(residual, axis=1, keepdims=True) + 1e-6
        logvar = np.log(np.repeat(variance, latent_dim, axis=1))
        return mu, logvar, components

    def reparameterize(self, mu: np.ndarray, logvar: np.ndarray, noise_scale: float = 1.0) -> np.ndarray:
        eps = self.rng.normal(0.0, 1.0, size=mu.shape)
        return mu + noise_scale * np.exp(0.5 * logvar) * eps

    def _decode(self, z: np.ndarray) -> np.ndarray:
        if self.components is None or self.feature_center is None:
            raise ValueError("模型尚未训练")
        return z @ self.components.T + self.feature_center

    def loss(self, features: np.ndarray, recon: np.ndarray, mu: np.ndarray, logvar: np.ndarray) -> dict[str, float]:
        recon_loss = float(np.mean((features - recon) ** 2))
        kl_loss = float(np.mean(-0.5 * np.sum(1.0 + logvar - mu * mu - np.exp(logvar), axis=1)))
        total = recon_loss + self.config.beta * kl_loss
        return {
            "reconstruction_loss": recon_loss,
            "kl_loss": kl_loss,
            "total_loss": float(total),
        }

    def fit(self, coords: np.ndarray, values: np.ndarray) -> dict[str, float]:
        features = self._spatial_feature_encoder(coords, values)
        normalized, mean, std = standardize(features)
        mu, logvar, components = self._latent_projection(normalized)

        self.feature_mean = mean
        self.feature_std = std
        self.feature_center = normalized.mean(axis=0, keepdims=True)
        self.components = components
        self.latent_mu = mu
        self.latent_logvar = logvar

        self.history = []
        start = self.config.noise_schedule_start
        end = self.config.noise_schedule_end

        for epoch in range(self.config.max_epochs):
            if self.config.max_epochs <= 1:
                noise_scale = end
            else:
                alpha = epoch / (self.config.max_epochs - 1)
                noise_scale = (1.0 - alpha) * start + alpha * end
            z = self.reparameterize(mu, logvar, noise_scale=noise_scale)
            recon = self._decode(z)
            losses = self.loss(normalized, recon, mu, logvar)
            losses["epoch"] = float(epoch)
            losses["noise_scale"] = float(noise_scale)
            self.history.append(losses)

        return {
            "final_total_loss": float(self.history[-1]["total_loss"]),
            "best_total_loss": float(min(x["total_loss"] for x in self.history)),
            "epochs": float(len(self.history)),
        }

    def _encode_for_inference(self, coords: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.components is None or self.feature_mean is None or self.feature_std is None:
            raise ValueError("模型尚未训练")
        features = self._spatial_feature_encoder(coords, values)
        normalized = (features - self.feature_mean) / self.feature_std
        centered = normalized - self.feature_center
        mu = centered @ self.components
        residual = centered - mu @ self.components.T
        variance = np.var(residual, axis=1, keepdims=True) + 1e-6
        logvar = np.log(np.repeat(variance, mu.shape[1], axis=1))
        recon = mu @ self.components.T + self.feature_center
        return normalized, mu, recon

    def latent_visualization(self, coords: np.ndarray, values: np.ndarray) -> list[dict[str, float]]:
        _, mu, _ = self._encode_for_inference(coords, values)
        if mu.shape[1] == 1:
            mu = np.concatenate([mu, np.zeros((len(mu), 1), dtype=float)], axis=1)
        return [{"z1": float(item[0]), "z2": float(item[1])} for item in mu]

    def anomaly_scores(self, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        normalized, mu, recon = self._encode_for_inference(coords, values)
        recon_error = np.mean((normalized - recon) ** 2, axis=1)
        latent_center = mu.mean(axis=0, keepdims=True)
        latent_distance = np.linalg.norm(mu - latent_center, axis=1)
        combined = 0.7 * safe_minmax(recon_error) + 0.3 * safe_minmax(latent_distance)
        return {
            "reconstruction": recon_error,
            "latent_distance": latent_distance,
            "combined": combined,
        }

    def predict(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        threshold_method: ThresholdMethod = "percentile",
        k: float = 2.5,
        percentile: float = 95.0,
    ) -> dict[str, object]:
        score_bundle = self.anomaly_scores(coords, values)
        combined = score_bundle["combined"]
        threshold = compute_threshold(combined, method=threshold_method, k=k, percentile=percentile)
        hit_idx = np.where(combined >= threshold.value)[0]

        return {
            "threshold": threshold.value,
            "threshold_method": threshold.method,
            "threshold_details": threshold.details,
            "anomaly_indices": hit_idx.tolist(),
            "anomaly_count": int(len(hit_idx)),
            "scores": combined.tolist(),
            "score_components": {
                "reconstruction": score_bundle["reconstruction"].tolist(),
                "latent_distance": score_bundle["latent_distance"].tolist(),
            },
        }
