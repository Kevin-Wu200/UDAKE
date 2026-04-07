"""GAN 风格异常检测（轻量 numpy 实现）。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import ThresholdMethod, compute_threshold, safe_minmax


@dataclass
class GANConfig:
    latent_dim: int = 6
    max_epochs: int = 60
    gp_weight: float = 10.0
    random_state: int = 42


class GANAnomalyDetector:
    """生成器+判别器联合分数的异常检测器。"""

    def __init__(self, config: GANConfig | None = None) -> None:
        self.config = config or GANConfig()
        self.rng = np.random.default_rng(self.config.random_state)
        self.generator_coef: np.ndarray | None = None
        self.generator_bias: float = 0.0
        self.feature_mean: np.ndarray | None = None
        self.feature_std: np.ndarray | None = None
        self.normal_stats: dict[str, float] = {}
        self.history: list[dict[str, float]] = []

    def is_trained(self) -> bool:
        return self.generator_coef is not None

    def _validate_inputs(self, coords: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        c = np.asarray(coords, dtype=float)
        v = np.asarray(values, dtype=float).reshape(-1)
        if c.ndim != 2 or c.shape[1] != 2:
            raise ValueError("coords must be [[x, y], ...]")
        if c.shape[0] != v.shape[0]:
            raise ValueError("coords and values length mismatch")
        if c.shape[0] < 2:
            raise ValueError("at least 2 points are required")
        if not np.isfinite(c).all() or not np.isfinite(v).all():
            raise ValueError("coords and values must be finite")
        return c, v

    def _build_design(self, coords: np.ndarray) -> np.ndarray:
        c = np.asarray(coords, dtype=float)
        radius = np.linalg.norm(c, axis=1, keepdims=True)
        angle = np.arctan2(c[:, 1], c[:, 0]).reshape(-1, 1)
        return np.concatenate([np.ones((len(c), 1), dtype=float), c, radius, angle], axis=1)

    def generator(self, noise: np.ndarray, coords: np.ndarray) -> np.ndarray:
        if self.generator_coef is None:
            raise ValueError("模型尚未训练")
        design = self._build_design(coords)
        conditional = design @ self.generator_coef.reshape(-1, 1)
        return conditional.reshape(-1) + self.generator_bias + 0.1 * noise.reshape(-1)

    def discriminator(self, coords: np.ndarray, values: np.ndarray) -> np.ndarray:
        v = np.asarray(values, dtype=float).reshape(-1)
        c = np.asarray(coords, dtype=float)
        mean = self.normal_stats.get("mean", float(v.mean()))
        std = max(self.normal_stats.get("std", float(v.std() + 1e-6)), 1e-6)

        spatial_grad = self._spatial_gradient(c, v)
        value_score = np.abs(v - mean) / std
        spatial_score = np.abs(spatial_grad - spatial_grad.mean()) / (spatial_grad.std() + 1e-6)
        # 输出越大越像异常。
        return 0.7 * safe_minmax(value_score) + 0.3 * safe_minmax(spatial_score)

    def _spatial_gradient(self, coords: np.ndarray, values: np.ndarray) -> np.ndarray:
        if len(values) <= 1:
            return np.zeros_like(values)
        diff_c = coords[:, None, :] - coords[None, :, :]
        dist = np.sqrt((diff_c * diff_c).sum(axis=-1) + 1e-8)
        diff_v = np.abs(values[:, None] - values[None, :])
        grad = diff_v / (dist + 1e-6)
        np.fill_diagonal(grad, 0.0)
        return grad.mean(axis=1)

    def _wgan_gp_penalty(self) -> float:
        if self.generator_coef is None:
            return 0.0
        norm = float(np.linalg.norm(self.generator_coef))
        return self.config.gp_weight * (norm - 1.0) ** 2

    def fit(self, coords: np.ndarray, values: np.ndarray) -> dict[str, float]:
        c, v = self._validate_inputs(coords, values)
        design = self._build_design(c)

        coef, *_ = np.linalg.lstsq(design, v, rcond=None)
        self.generator_coef = coef
        self.generator_bias = float(v.mean() - (design @ coef).mean())

        self.normal_stats = {
            "mean": float(v.mean()),
            "std": float(v.std() + 1e-6),
            "var": float(v.var()),
        }
        pre = self.preprocess_gan_data(c, v, batch_size=64, use_training_stats=False, noise_scale=0.0)
        mat = np.asarray(pre["processed_features"], dtype=float)
        self.feature_mean = mat.mean(axis=0, keepdims=True)
        self.feature_std = mat.std(axis=0, keepdims=True) + 1e-6

        self.history = []
        for epoch in range(self.config.max_epochs):
            noise_scale = max(0.02, 1.0 - epoch / max(1, self.config.max_epochs))
            noise = self.rng.normal(0.0, noise_scale, size=len(v))
            fake = self.generator(noise, c)

            real_disc = self.discriminator(c, v)
            fake_disc = self.discriminator(c, fake)

            disc_loss = float(fake_disc.mean() - real_disc.mean())
            gp_loss = float(self._wgan_gp_penalty())
            gen_loss = float(np.mean(np.abs(fake - v)))
            total_g = gen_loss + 0.1 * gp_loss
            total_d = disc_loss + gp_loss

            # 谱归一化近似：压缩生成器系数范围。
            coef_norm = float(np.linalg.norm(self.generator_coef))
            if coef_norm > 1.0:
                self.generator_coef = self.generator_coef / coef_norm

            mode_collapse_flag = float(np.var(fake) < 0.1 * np.var(v))

            self.history.append(
                {
                    "epoch": float(epoch),
                    "generator_loss": total_g,
                    "discriminator_loss": total_d,
                    "gradient_penalty": gp_loss,
                    "mode_collapse": mode_collapse_flag,
                }
            )

        return {
            "final_generator_loss": float(self.history[-1]["generator_loss"]),
            "final_discriminator_loss": float(self.history[-1]["discriminator_loss"]),
            "mode_collapse_detected": bool(any(item["mode_collapse"] > 0 for item in self.history)),
            "epochs": float(len(self.history)),
        }

    def preprocess_gan_data(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        *,
        batch_size: int | None = None,
        use_training_stats: bool = True,
        noise_scale: float = 0.05,
    ) -> dict[str, object]:
        c, v = self._validate_inputs(coords, values)
        radius = np.linalg.norm(c, axis=1)
        angle = np.arctan2(c[:, 1], c[:, 0])
        noise = self.rng.normal(0.0, max(0.0, float(noise_scale)), size=len(v))

        if self.is_trained():
            generated = self.generator(np.zeros_like(v), c)
            bundle = self.anomaly_scores(c, v)
            disc_score = np.asarray(bundle["discriminator"], dtype=float)
            recon_score = np.asarray(bundle["reconstruction"], dtype=float)
            grad_score = np.asarray(bundle["gradient"], dtype=float)
            latent = (self._build_design(c) @ self.generator_coef.reshape(-1, 1)).reshape(-1)
        else:
            disc_score = safe_minmax(np.abs(v - np.mean(v)))
            recon_score = np.zeros_like(v)
            grad_score = np.zeros_like(v)
            generated = v.copy()
            latent = self._build_design(c)[:, 1]

        matrix = np.column_stack(
            [
                c[:, 0],
                c[:, 1],
                radius,
                angle,
                v,
                disc_score,
                recon_score,
                grad_score,
                noise,
            ]
        )
        names = [
            "coord_x",
            "coord_y",
            "radius",
            "angle",
            "value",
            "disc_score",
            "recon_score",
            "grad_score",
            "noise_level",
        ]
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

        size = int(max(1, batch_size or len(v)))
        slices = [[int(i), int(min(i + size, len(v)))] for i in range(0, len(v), size)]
        return {
            "coords": c,
            "values": v,
            "generated_values": generated.astype(float).tolist(),
            "latent_projection": latent.astype(float).tolist(),
            "processed_features": processed.astype(float),
            "feature_names": names,
            "batch_slices": slices,
            "scaler": scaler,
            "validation": {
                "is_valid": bool(np.isfinite(matrix).all() and len(v) > 0),
                "n_points": int(len(v)),
                "batch_size": size,
            },
        }

    def anomaly_scores(self, coords: np.ndarray, values: np.ndarray) -> dict[str, np.ndarray]:
        if not self.is_trained():
            raise ValueError("模型尚未训练")
        c, v = self._validate_inputs(coords, values)
        noise = np.zeros_like(v)
        generated = self.generator(noise, c)

        disc_score = self.discriminator(c, v)
        recon_score = safe_minmax(np.abs(v - generated))

        gradient_real = self._spatial_gradient(c, v)
        gradient_fake = self._spatial_gradient(c, generated)
        gradient_score = safe_minmax(np.abs(gradient_real - gradient_fake))

        combined = 0.5 * disc_score + 0.35 * recon_score + 0.15 * gradient_score

        return {
            "discriminator": disc_score,
            "reconstruction": recon_score,
            "gradient": gradient_score,
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
        c, v = self._validate_inputs(coords, values)
        bundle = self.anomaly_scores(c, v)
        combined = bundle["combined"]
        threshold = compute_threshold(combined, method=threshold_method, percentile=percentile, k=k)
        hit_idx = np.where(combined >= threshold.value)[0]

        return {
            "anomaly_indices": hit_idx.tolist(),
            "anomaly_count": int(len(hit_idx)),
            "threshold": threshold.value,
            "threshold_method": threshold.method,
            "scores": combined.tolist(),
            "score_components": {
                "discriminator": bundle["discriminator"].tolist(),
                "reconstruction": bundle["reconstruction"].tolist(),
                "gradient": bundle["gradient"].tolist(),
            },
            "training_diagnostics": {
                "generator_loss": [item["generator_loss"] for item in self.history],
                "discriminator_loss": [item["discriminator_loss"] for item in self.history],
                "gradient_penalty": [item["gradient_penalty"] for item in self.history],
            },
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
        payload = self.predict(
            coords=coords,
            values=values,
            threshold_method=threshold_method,
            percentile=percentile,
            k=k,
        )
        scores = np.asarray(payload.get("scores", []), dtype=float)
        labels = (scores >= float(payload.get("threshold", 0.0))).astype(int)
        return {
            "scores": scores.astype(float).tolist(),
            "labels": labels.astype(int).tolist(),
            "anomaly_count": int(labels.sum()),
            "anomaly_indices": np.where(labels > 0)[0].astype(int).tolist(),
            "threshold": float(payload.get("threshold", 0.0)),
            "details": payload,
        }
