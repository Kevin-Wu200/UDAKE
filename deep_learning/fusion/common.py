"""阶段7：模型融合与系统集成通用数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class FusionStrategy(str, Enum):
    SIMPLE_AVERAGE = "simple_average"
    WEIGHTED_AVERAGE = "weighted_average"
    MEDIAN = "median"
    MAX_MIN = "max_min"
    STACKING = "stacking"
    BAYESIAN_MODEL_AVERAGE = "bayesian_model_average"
    VARIANCE_WEIGHTED = "variance_weighted"
    DYNAMIC = "dynamic"


class WeightMethod(str, Enum):
    EQUAL = "equal"
    RMSE_BASED = "rmse_based"
    MAE_BASED = "mae_based"
    R2_BASED = "r2_based"
    CROSS_VALIDATION = "cross_validation"
    BMA = "bma"
    UNCERTAINTY_BASED = "uncertainty_based"
    ADAPTIVE = "adaptive"


class AdaptiveLearningMode(str, Enum):
    NEURAL = "neural"
    ATTENTION = "attention"


class MultiModalStrategy(str, Enum):
    DATA_LEVEL = "data_level"
    FEATURE_LEVEL = "feature_level"
    DECISION_LEVEL = "decision_level"
    HYBRID = "hybrid"


class HybridFusionMode(str, Enum):
    RESIDUAL = "residual"
    FEATURE = "feature"
    DECISION = "decision"


@dataclass
class ModelPrediction:
    model_id: str
    predictions: list[float]
    model_name: str | None = None
    variances: list[float] | None = None
    confidence_intervals: list[dict[str, float]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelMetric:
    model_id: str
    rmse: float
    mae: float
    r2: float
    mape: float
    stability: float
    uncertainty: float


@dataclass
class FusionConfig:
    strategy: FusionStrategy = FusionStrategy.WEIGHTED_AVERAGE
    weight_method: WeightMethod = WeightMethod.RMSE_BASED
    adaptive_mode: AdaptiveLearningMode = AdaptiveLearningMode.NEURAL
    min_weight: float = 0.0
    max_weight: float = 1.0
    normalize: bool = True
    smoothing: bool = False
    smoothing_factor: float = 0.1
    n_folds: int = 5
    enable_uncertainty: bool = True


@dataclass
class FusionResult:
    fused_predictions: list[float]
    fused_variances: list[float] | None
    weights: dict[str, float]
    metrics: dict[str, float]
    strategy: str
    weight_method: str
    improvement: dict[str, float] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class FusionProfile:
    profile_id: str
    strategy: FusionStrategy
    weight_method: WeightMethod
    weights: dict[str, float]
    metrics: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)


EPS = 1e-8


def ensure_prediction_matrix(models: list[ModelPrediction]) -> np.ndarray:
    if not models:
        raise ValueError("至少需要一个模型预测")
    lengths = {len(m.predictions) for m in models}
    if len(lengths) != 1:
        raise ValueError("模型输出长度不一致")
    matrix = np.asarray([m.predictions for m in models], dtype=float)
    if matrix.ndim != 2:
        raise ValueError("预测矩阵维度错误")
    return matrix


def normalize_weights(raw: dict[str, float], default_keys: list[str] | None = None) -> dict[str, float]:
    if not raw:
        keys = default_keys or []
        if not keys:
            return {}
        equal = 1.0 / len(keys)
        return {k: equal for k in keys}

    sanitized = {k: max(0.0, float(v)) for k, v in raw.items()}
    total = sum(sanitized.values())
    if total <= EPS:
        keys = list(sanitized.keys())
        equal = 1.0 / len(keys)
        return {k: equal for k in keys}
    return {k: v / total for k, v in sanitized.items()}
