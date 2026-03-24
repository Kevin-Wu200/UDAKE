"""阶段7：深度学习与传统方法融合、多模态融合。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import EPS, HybridFusionMode, MultiModalStrategy


@dataclass
class HybridFusionResult:
    prediction: list[float]
    variance: list[float]
    metadata: dict[str, Any]


class HybridFusionBridge:
    """传统模型（如克里金）与深度学习预测融合。"""

    def fuse_kriging_and_deep_learning(
        self,
        kriging_prediction: list[float],
        deep_prediction: list[float],
        kriging_variance: list[float] | None = None,
        deep_variance: list[float] | None = None,
        mode: HybridFusionMode = HybridFusionMode.RESIDUAL,
        ratio: float = 0.6,
    ) -> HybridFusionResult:
        k = np.asarray(kriging_prediction, dtype=float)
        d = np.asarray(deep_prediction, dtype=float)
        if len(k) != len(d):
            raise ValueError("克里金和深度学习预测长度不一致")

        r = float(np.clip(ratio, 0.0, 1.0))
        if mode == HybridFusionMode.RESIDUAL:
            # 用深度学习学习残差，强调局部非线性修正。
            residual = d - k
            pred = k + r * residual
        elif mode == HybridFusionMode.FEATURE:
            # 特征级融合：近似为稳定凸组合。
            pred = r * d + (1.0 - r) * k
        else:
            # 决策级融合：保留两类模型独立决策后再加权。
            pred = r * d + (1.0 - r) * k

        k_var = np.asarray(kriging_variance if kriging_variance is not None else np.var(k) * np.ones_like(k), dtype=float)
        d_var = np.asarray(deep_variance if deep_variance is not None else np.var(d) * np.ones_like(d), dtype=float)
        var = np.maximum(r * d_var + (1.0 - r) * k_var, EPS)

        return HybridFusionResult(
            prediction=pred.tolist(),
            variance=var.tolist(),
            metadata={"mode": mode.value, "ratio": r},
        )

    def adaptive_model_selection(
        self,
        performance_scores: dict[str, float] | None = None,
        uncertainty_scores: dict[str, float] | None = None,
        input_score: float | None = None,
    ) -> str:
        if performance_scores:
            best_perf = min(performance_scores.items(), key=lambda item: item[1])
        else:
            best_perf = ("deep_learning", 0.0)

        if uncertainty_scores:
            best_unc = min(uncertainty_scores.items(), key=lambda item: item[1])
        else:
            best_unc = best_perf

        if input_score is not None and input_score > 0.7:
            return best_unc[0]
        if abs(best_perf[1] - best_unc[1]) < 0.02:
            return best_unc[0]
        return best_perf[0]


class MultiModalFusion:
    """数据级、特征级、决策级与混合融合。"""

    def fuse(
        self,
        modalities: list[list[float]],
        strategy: MultiModalStrategy = MultiModalStrategy.HYBRID,
        weights: list[float] | None = None,
    ) -> list[float]:
        if not modalities:
            return []

        arr = [np.asarray(m, dtype=float) for m in modalities]
        lengths = {len(x) for x in arr}
        if len(lengths) != 1:
            raise ValueError("多模态输入长度不一致")

        n = len(arr)
        if weights is None:
            w = np.ones(n, dtype=float) / n
        else:
            w = np.asarray(weights, dtype=float)
            w = np.clip(w, 0.0, None)
            if np.sum(w) <= EPS:
                w = np.ones(n, dtype=float) / n
            else:
                w = w / np.sum(w)

        matrix = np.vstack(arr)
        if strategy == MultiModalStrategy.DATA_LEVEL:
            return np.mean(matrix, axis=0).tolist()
        if strategy == MultiModalStrategy.FEATURE_LEVEL:
            # 早期/中期融合近似：每一维标准化后加权。
            normed = (matrix - np.mean(matrix, axis=1, keepdims=True)) / (
                np.std(matrix, axis=1, keepdims=True) + EPS
            )
            return np.sum(normed * w[:, None], axis=0).tolist()
        if strategy == MultiModalStrategy.DECISION_LEVEL:
            return np.sum(matrix * w[:, None], axis=0).tolist()

        # HYBRID: feature + decision 双路径融合。
        feature_part = self.fuse(modalities, strategy=MultiModalStrategy.FEATURE_LEVEL, weights=w.tolist())
        decision_part = self.fuse(modalities, strategy=MultiModalStrategy.DECISION_LEVEL, weights=w.tolist())
        return (0.5 * np.asarray(feature_part) + 0.5 * np.asarray(decision_part)).tolist()
