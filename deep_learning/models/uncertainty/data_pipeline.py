"""不确定性数据准备与特征工程。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .common import ensure_1d, ensure_2d


@dataclass
class UncertaintyDataset:
    coords: np.ndarray
    values: np.ndarray
    aleatoric_label: np.ndarray
    epistemic_label: np.ndarray
    features: np.ndarray


class UncertaintyDatasetBuilder:
    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)

    def create_uncertainty_dataset(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        noise_scale: float = 0.05,
        multimodal: bool = True,
    ) -> UncertaintyDataset:
        c = ensure_2d(coords)
        v = ensure_1d(values)
        if len(c) != len(v):
            raise ValueError("coords 与 values 长度不一致")

        base_noise = self.rng.normal(0.0, float(max(noise_scale, 1e-4)), size=len(v))
        local_noise = np.abs(base_noise)

        if multimodal:
            mode_flag = self.rng.integers(0, 2, size=len(v))
            extra = self.rng.normal(0.0, noise_scale * 1.8, size=len(v))
            v_aug = v + base_noise + (mode_flag * extra)
        else:
            v_aug = v + base_noise

        # 简化标签：局部噪声代表 aleatoric，空间覆盖密度代表 epistemic
        aleatoric = local_noise
        diff = c[:, None, :] - c[None, :, :]
        dist = np.sqrt(np.sum(diff ** 2, axis=-1) + 1e-12)
        density = np.mean(np.exp(-dist / (np.mean(dist) + 1e-8)), axis=1)
        epistemic = 1.0 - (density - density.min()) / (density.max() - density.min() + 1e-8)

        features = self.feature_engineering(c, v_aug, aleatoric=aleatoric, epistemic=epistemic)
        return UncertaintyDataset(
            coords=c,
            values=v_aug,
            aleatoric_label=aleatoric,
            epistemic_label=epistemic,
            features=features,
        )

    def uncertainty_preserving_augment(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        aleatoric: np.ndarray,
        n_copies: int = 2,
    ) -> tuple[np.ndarray, np.ndarray]:
        c = ensure_2d(coords)
        v = ensure_1d(values)
        a = np.maximum(ensure_1d(aleatoric), 1e-8)
        if len(c) != len(v) or len(c) != len(a):
            raise ValueError("输入长度不一致")

        coords_all = [c]
        values_all = [v]

        for _ in range(int(max(1, n_copies))):
            jitter_c = c + self.rng.normal(0.0, 0.005, size=c.shape)
            jitter_v = v + self.rng.normal(0.0, a)
            coords_all.append(jitter_c)
            values_all.append(jitter_v)

        return np.vstack(coords_all), np.concatenate(values_all)

    def feature_engineering(
        self,
        coords: np.ndarray,
        values: np.ndarray,
        aleatoric: np.ndarray | None = None,
        epistemic: np.ndarray | None = None,
    ) -> np.ndarray:
        c = ensure_2d(coords)
        v = ensure_1d(values)
        if len(c) != len(v):
            raise ValueError("coords 与 values 长度不一致")

        local_mean = np.zeros(len(v), dtype=float)
        local_std = np.zeros(len(v), dtype=float)

        diff = c[:, None, :] - c[None, :, :]
        dist = np.sqrt(np.sum(diff ** 2, axis=-1) + 1e-12)
        order = np.argsort(dist, axis=1)
        k = max(1, min(6, len(v) - 1 if len(v) > 1 else 1))
        idx = order[:, 1 : k + 1] if len(v) > 1 else np.zeros((len(v), 1), dtype=int)

        local_mean = np.mean(v[idx], axis=1)
        local_std = np.std(v[idx], axis=1)

        feats = [c, v.reshape(-1, 1), local_mean.reshape(-1, 1), local_std.reshape(-1, 1)]
        if aleatoric is not None:
            feats.append(ensure_1d(aleatoric).reshape(-1, 1))
        if epistemic is not None:
            feats.append(ensure_1d(epistemic).reshape(-1, 1))
        return np.concatenate(feats, axis=1)
