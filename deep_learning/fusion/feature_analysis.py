"""阶段7：融合模型特征分析。"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .common import EPS, FusionStrategy, ModelPrediction, ensure_prediction_matrix, normalize_weights


class FusionFeatureAnalyzer:
    """融合模型特征分析器。"""

    _FEATURE_NAME_BASE: dict[str, dict[str, str]] = {
        "model_count": {"zh": "子模型数量", "group": "basic"},
        "prediction_horizon": {"zh": "预测步长", "group": "basic"},
        "disagreement_mean": {"zh": "模型分歧均值", "group": "basic"},
        "disagreement_std": {"zh": "模型分歧标准差", "group": "basic"},
        "weight_entropy": {"zh": "权重熵", "group": "weight"},
        "weight_gini": {"zh": "权重基尼系数", "group": "weight"},
        "weight_top1_ratio": {"zh": "最大权重占比", "group": "weight"},
        "weight_effective_models": {"zh": "有效模型数", "group": "weight"},
    }

    _STRATEGY_FEATURES: dict[str, dict[str, Any]] = {
        FusionStrategy.SIMPLE_AVERAGE.value: {
            "fusion_level": "decision",
            "complexity": "low",
            "supports_dynamic_weight": False,
            "requires_true_values": False,
        },
        FusionStrategy.WEIGHTED_AVERAGE.value: {
            "fusion_level": "decision",
            "complexity": "low",
            "supports_dynamic_weight": False,
            "requires_true_values": False,
        },
        FusionStrategy.MEDIAN.value: {
            "fusion_level": "decision",
            "complexity": "low",
            "supports_dynamic_weight": False,
            "requires_true_values": False,
        },
        FusionStrategy.MAX_MIN.value: {
            "fusion_level": "decision",
            "complexity": "low",
            "supports_dynamic_weight": False,
            "requires_true_values": False,
        },
        FusionStrategy.STACKING.value: {
            "fusion_level": "meta_learning",
            "complexity": "medium",
            "supports_dynamic_weight": False,
            "requires_true_values": True,
        },
        FusionStrategy.BAYESIAN_MODEL_AVERAGE.value: {
            "fusion_level": "probabilistic",
            "complexity": "medium",
            "supports_dynamic_weight": False,
            "requires_true_values": False,
        },
        FusionStrategy.VARIANCE_WEIGHTED.value: {
            "fusion_level": "uncertainty_aware",
            "complexity": "medium",
            "supports_dynamic_weight": True,
            "requires_true_values": False,
        },
        FusionStrategy.DYNAMIC.value: {
            "fusion_level": "adaptive",
            "complexity": "high",
            "supports_dynamic_weight": True,
            "requires_true_values": False,
        },
    }

    def feature_name_mapping(self, models: list[ModelPrediction]) -> dict[str, dict[str, str]]:
        mapping = dict(self._FEATURE_NAME_BASE)
        for model in models:
            model_id = str(model.model_id)
            mapping[f"weight.{model_id}"] = {"zh": f"{model_id}模型权重", "group": "weight"}
            mapping[f"contribution.{model_id}.marginal_gain"] = {"zh": f"{model_id}边际收益", "group": "contribution"}
            mapping[f"contribution.{model_id}.stability"] = {"zh": f"{model_id}贡献稳定性", "group": "contribution"}
        mapping["strategy.fusion_level"] = {"zh": "融合层级", "group": "strategy"}
        mapping["strategy.complexity"] = {"zh": "策略复杂度", "group": "strategy"}
        return mapping

    def analyze(
        self,
        models: list[ModelPrediction],
        weights: dict[str, float],
        strategy: str,
        weight_method: str,
        fused_predictions: list[float],
        true_values: list[float] | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        matrix = ensure_prediction_matrix(models)
        model_ids = [m.model_id for m in models]
        norm_weights = normalize_weights(weights, default_keys=model_ids)
        weight_arr = np.asarray([norm_weights[mid] for mid in model_ids], dtype=float)
        fused = np.asarray(fused_predictions, dtype=float).reshape(-1)
        if fused.shape[0] != matrix.shape[1]:
            raise ValueError("fused_predictions 长度与模型预测长度不一致")

        disagreement = np.std(matrix, axis=0, ddof=0)
        entropy = self._weight_entropy(weight_arr)
        gini = self._weight_gini(weight_arr)
        effective_models = float(1.0 / np.clip(np.sum(weight_arr * weight_arr), EPS, None))

        model_contrib = self._contribution_features(
            models=models,
            norm_weights=norm_weights,
            fused=fused,
            true_values=true_values,
        )

        strategy_features = self._strategy_features(strategy=strategy, diagnostics=diagnostics)

        return {
            "feature_mapping": self.feature_name_mapping(models),
            "basic_features": {
                "model_count": int(matrix.shape[0]),
                "prediction_horizon": int(matrix.shape[1]),
                "disagreement_mean": float(np.mean(disagreement)),
                "disagreement_std": float(np.std(disagreement)),
            },
            "weight_features": {
                "weight_entropy": float(entropy),
                "weight_gini": float(gini),
                "weight_top1_ratio": float(np.max(weight_arr)),
                "weight_effective_models": effective_models,
                "weights": {k: float(v) for k, v in norm_weights.items()},
                "weight_method": weight_method,
            },
            "model_contributions": model_contrib,
            "strategy_features": strategy_features,
            "weight_scheme": self._weight_scheme(weight_method),
            "contribution_scheme": self._contribution_scheme(),
        }

    @staticmethod
    def _weight_entropy(weight_arr: np.ndarray) -> float:
        arr = np.clip(np.asarray(weight_arr, dtype=float).reshape(-1), EPS, 1.0)
        if arr.size <= 1:
            return 0.0
        entropy = float(-np.sum(arr * np.log(arr)))
        return entropy / float(np.log(arr.size))

    @staticmethod
    def _weight_gini(weight_arr: np.ndarray) -> float:
        arr = np.asarray(weight_arr, dtype=float).reshape(-1)
        if arr.size == 0:
            return 0.0
        sorted_arr = np.sort(np.clip(arr, 0.0, 1.0))
        n = sorted_arr.size
        idx = np.arange(1, n + 1, dtype=float)
        return float((2.0 * np.sum(idx * sorted_arr) / np.clip(n * np.sum(sorted_arr), EPS, None)) - (n + 1.0) / n)

    def _contribution_features(
        self,
        models: list[ModelPrediction],
        norm_weights: dict[str, float],
        fused: np.ndarray,
        true_values: list[float] | None,
    ) -> list[dict[str, Any]]:
        matrix = ensure_prediction_matrix(models)
        y_true = None if true_values is None else np.asarray(true_values, dtype=float).reshape(-1)
        if y_true is not None and y_true.shape[0] != matrix.shape[1]:
            y_true = None

        base_error = None
        if y_true is not None:
            base_error = np.abs(fused - y_true)

        rows: list[dict[str, Any]] = []
        model_ids = [m.model_id for m in models]
        for idx, model in enumerate(models):
            model_id = model.model_id
            pred = matrix[idx, :]
            weight = float(norm_weights.get(model_id, 0.0))
            signed_component = weight * (pred - fused)
            abs_component = np.abs(signed_component)

            marginal_gain = 0.0
            if base_error is not None:
                others = {k: v for k, v in norm_weights.items() if k != model_id}
                others = normalize_weights(others, default_keys=[mid for mid in model_ids if mid != model_id])
                if others:
                    other_weight_arr = np.asarray([others[mid] for mid in model_ids if mid != model_id], dtype=float)
                    other_matrix = np.vstack([matrix[j, :] for j, mid in enumerate(model_ids) if mid != model_id])
                    fused_wo = np.sum(other_weight_arr[:, None] * other_matrix, axis=0)
                    marginal_gain = float(np.mean(np.abs(fused_wo - y_true) - base_error))

            corr = 0.0
            if np.std(pred) > EPS and np.std(fused) > EPS:
                corr = float(np.corrcoef(pred, fused)[0, 1])
                if math.isnan(corr):
                    corr = 0.0

            rows.append(
                {
                    "model_id": model_id,
                    "weight": weight,
                    "mean_abs_contribution": float(np.mean(abs_component)),
                    "mean_signed_contribution": float(np.mean(signed_component)),
                    "stability": float(1.0 / (1.0 + np.std(abs_component))),
                    "agreement_with_fusion": corr,
                    "marginal_gain": float(marginal_gain),
                }
            )
        return rows

    def _strategy_features(self, strategy: str, diagnostics: dict[str, Any] | None) -> dict[str, Any]:
        base = dict(self._STRATEGY_FEATURES.get(strategy, {}))
        if not base:
            base = {
                "fusion_level": "unknown",
                "complexity": "unknown",
                "supports_dynamic_weight": False,
                "requires_true_values": False,
            }
        base["strategy"] = strategy
        dynamic = (diagnostics or {}).get("dynamic_weights", {})
        if isinstance(dynamic, dict) and dynamic:
            volatility: dict[str, float] = {}
            for model_id, series in dynamic.items():
                arr = np.asarray(series, dtype=float).reshape(-1)
                volatility[str(model_id)] = float(np.std(arr)) if arr.size > 0 else 0.0
            base["dynamic_weight_volatility"] = volatility
            base["has_dynamic_weight_trace"] = True
        else:
            base["dynamic_weight_volatility"] = {}
            base["has_dynamic_weight_trace"] = False
        return base

    @staticmethod
    def _weight_scheme(weight_method: str) -> dict[str, Any]:
        return {
            "selected_method": weight_method,
            "pipeline": [
                "1) 先评估每个子模型的误差、稳定性与不确定性指标",
                "2) 按权重方法生成原始分数（如 1/rmse^2、BMA 后验、注意力得分）",
                "3) 应用约束并归一化为最终权重",
            ],
            "core_formulas": {
                "rmse_based": "w_i ∝ 1 / (rmse_i^2 + eps)",
                "mae_based": "w_i ∝ 1 / (mae_i + eps)",
                "bma": "w_i ∝ exp(-0.5 * (bic_i - bic_min))",
                "uncertainty_based": "w_i ∝ 1 / (uncertainty_i + eps)",
                "adaptive": "w = softmax(f(metrics))",
            },
        }

    @staticmethod
    def _contribution_scheme() -> dict[str, Any]:
        return {
            "indicators": [
                "mean_abs_contribution: 子模型对融合输出的平均绝对贡献",
                "stability: 子模型贡献时序稳定性",
                "agreement_with_fusion: 子模型输出与融合输出的一致性",
                "marginal_gain: 去掉该模型后误差变化（有真值时）",
            ],
            "decision_rule": "优先保留 marginal_gain>0 且 stability 高的模型；对 marginal_gain<=0 的模型降权或剔除。",
        }
