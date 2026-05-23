"""数据预处理框架。"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

import numpy as np


class BasePreprocessor(ABC):
    """预处理基类。"""

    @abstractmethod
    def fit(self, data: np.ndarray) -> "BasePreprocessor":
        raise NotImplementedError

    @abstractmethod
    def transform(self, data: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def fit_transform(self, data: np.ndarray) -> np.ndarray:
        return self.fit(data).transform(data)


class SpatialNormalizer(BasePreprocessor):
    """空间坐标归一化。"""

    def __init__(self) -> None:
        self.min_: np.ndarray | None = None
        self.max_: np.ndarray | None = None

    def fit(self, data: np.ndarray) -> "SpatialNormalizer":
        self.min_ = data.min(axis=0)
        self.max_ = data.max(axis=0)
        return self

    def transform(self, data: np.ndarray) -> np.ndarray:
        if self.min_ is None or self.max_ is None:
            raise ValueError("SpatialNormalizer 尚未 fit")
        scale = np.where((self.max_ - self.min_) == 0, 1.0, self.max_ - self.min_)
        return (data - self.min_) / scale


class FeatureScaler(BasePreprocessor):
    """特征缩放器，支持 standard/minmax。"""

    def __init__(self, method: str = "standard") -> None:
        if method not in {"standard", "minmax"}:
            raise ValueError("method 仅支持 standard 或 minmax")
        self.method = method
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None
        self.min_: np.ndarray | None = None
        self.max_: np.ndarray | None = None

    def fit(self, data: np.ndarray) -> "FeatureScaler":
        if self.method == "standard":
            self.mean_ = data.mean(axis=0)
            self.std_ = np.where(data.std(axis=0) == 0, 1.0, data.std(axis=0))
        else:
            self.min_ = data.min(axis=0)
            self.max_ = data.max(axis=0)
        return self

    def transform(self, data: np.ndarray) -> np.ndarray:
        if self.method == "standard":
            if self.mean_ is None or self.std_ is None:
                raise ValueError("FeatureScaler 尚未 fit")
            return (data - self.mean_) / self.std_
        if self.min_ is None or self.max_ is None:
            raise ValueError("FeatureScaler 尚未 fit")
        scale = np.where((self.max_ - self.min_) == 0, 1.0, self.max_ - self.min_)
        return (data - self.min_) / scale


class DataAugmentation:
    """基础数据增强：高斯噪声、随机平移。"""

    def __init__(self, noise_std: float = 0.01, jitter_range: float = 0.0, seed: int = 42) -> None:
        self.noise_std = noise_std
        self.jitter_range = jitter_range
        self.rng = np.random.default_rng(seed)

    def apply(self, data: np.ndarray) -> np.ndarray:
        noise = self.rng.normal(0.0, self.noise_std, data.shape)
        augmented = data + noise
        if self.jitter_range > 0:
            jitter = self.rng.uniform(-self.jitter_range, self.jitter_range, data.shape)
            augmented = augmented + jitter
        return augmented


@dataclass
class SplitResult:
    train: np.ndarray
    val: np.ndarray
    test: np.ndarray


class DataSplitter:
    """数据集划分。"""

    def __init__(
        self,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        seed: int = 42,
    ) -> None:
        total = train_ratio + val_ratio + test_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError("train/val/test 比例之和必须为 1")
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.seed = seed

    def split(self, data: np.ndarray, shuffle: bool = True) -> SplitResult:
        idx = list(range(len(data)))
        if shuffle:
            random.Random(self.seed).shuffle(idx)
        shuffled = data[idx]

        n_train = int(len(shuffled) * self.train_ratio)
        n_val = int(len(shuffled) * self.val_ratio)
        train = shuffled[:n_train]
        val = shuffled[n_train:n_train + n_val]
        test = shuffled[n_train + n_val:]
        return SplitResult(train=train, val=val, test=test)


class DataValidatorCleaner:
    """数据校验与清洗。"""

    def __init__(self, clip_quantile: float = 0.99) -> None:
        self.clip_quantile = clip_quantile

    def clean(self, data: np.ndarray) -> np.ndarray:
        if data.size == 0:
            return data
        cleaned = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
        low = np.quantile(cleaned, 1 - self.clip_quantile, axis=0)
        high = np.quantile(cleaned, self.clip_quantile, axis=0)
        return np.clip(cleaned, low, high)

    def validate(self, data: np.ndarray) -> list[str]:
        issues: list[str] = []
        if np.isnan(data).any():
            issues.append("包含 NaN")
        if np.isinf(data).any():
            issues.append("包含无穷值")
        if data.ndim != 2:
            issues.append("数据维度应为二维")
        return issues


def to_numpy(data: Iterable[Iterable[float]]) -> np.ndarray:
    return np.asarray(list(data), dtype=float)
