"""
权重计算器
"""
import logging
from typing import Dict, List, Optional

import numpy as np

from .fusion_models import ModelMetrics, WeightMethod

logger = logging.getLogger(__name__)


class WeightCalculator:
    """权重计算器"""

    def __init__(self):
        self._calculators = {
            WeightMethod.EQUAL: self._calculate_equal_weights,
            WeightMethod.RMSE_BASED: self._calculate_rmse_weights,
            WeightMethod.MAE_BASED: self._calculate_mae_weights,
            WeightMethod.R2_BASED: self._calculate_r2_weights,
            WeightMethod.CROSS_VALIDATION: self._calculate_cv_weights,
            WeightMethod.BMA: self._calculate_bma_weights,
            WeightMethod.UNCERTAINTY_BASED: self._calculate_uncertainty_weights,
            WeightMethod.ADAPTIVE: self._calculate_adaptive_weights,
        }

    def calculate_weights(
        self,
        method: WeightMethod,
        model_metrics: List[ModelMetrics],
        predictions: Optional[List[List[float]]] = None,
        true_values: Optional[List[float]] = None,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
        normalize: bool = True,
        smoothing: bool = False,
        smoothing_factor: float = 0.1
    ) -> Dict[str, float]:
        """
        计算模型权重

        Args:
            method: 权重计算方法
            model_metrics: 模型评估指标
            predictions: 各模型预测值（用于某些方法）
            true_values: 真实值（用于某些方法）
            min_weight: 最小权重
            max_weight: 最大权重
            normalize: 是否归一化
            smoothing: 是否平滑权重
            smoothing_factor: 平滑因子

        Returns:
            模型权重字典 {model_id: weight}
        """
        calculator = self._calculators.get(method)

        if calculator is None:
            logger.warning(f"未知的权重计算方法: {method}, 使用等权重")
            calculator = self._calculate_equal_weights

        weights = calculator(model_metrics, predictions, true_values)

        # 应用约束
        weights = self._apply_constraints(
            weights, min_weight, max_weight, normalize, smoothing, smoothing_factor
        )

        return weights

    def _calculate_equal_weights(
        self,
        model_metrics: List[ModelMetrics],
        predictions: Optional[List[List[float]]] = None,
        true_values: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """计算等权重"""
        n_models = len(model_metrics)
        weight = 1.0 / n_models if n_models > 0 else 0.0
        return {metric.model_id: weight for metric in model_metrics}

    def _calculate_rmse_weights(
        self,
        model_metrics: List[ModelMetrics],
        predictions: Optional[List[List[float]]] = None,
        true_values: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """基于RMSE计算权重 (RMSE越小，权重越大)"""
        # 使用倒数平方
        rmse_values = [metric.rmse for metric in model_metrics]
        weights = []

        for rmse in rmse_values:
            if rmse > 0:
                weight = 1.0 / (rmse ** 2)
            else:
                weight = 1e6  # 非常大的权重
            weights.append(weight)

        # 归一化
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            n = len(weights)
            weights = [1.0 / n] * n

        return {metric.model_id: weight for metric, weight in zip(model_metrics, weights)}

    def _calculate_mae_weights(
        self,
        model_metrics: List[ModelMetrics],
        predictions: Optional[List[List[float]]] = None,
        true_values: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """基于MAE计算权重"""
        mae_values = [metric.mae for metric in model_metrics]
        weights = []

        for mae in mae_values:
            if mae > 0:
                weight = 1.0 / mae
            else:
                weight = 1e6
            weights.append(weight)

        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            n = len(weights)
            weights = [1.0 / n] * n

        return {metric.model_id: weight for metric, weight in zip(model_metrics, weights)}

    def _calculate_r2_weights(
        self,
        model_metrics: List[ModelMetrics],
        predictions: Optional[List[List[float]]] = None,
        true_values: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """基于R²计算权重 (R²越大，权重越大)"""
        r2_values = [metric.r2 for metric in model_metrics]
        # 将R²转换为正数
        r2_values = [max(0, r2) for r2 in r2_values]

        total = sum(r2_values)
        if total > 0:
            weights = [r2 / total for r2 in r2_values]
        else:
            n = len(r2_values)
            weights = [1.0 / n] * n

        return {metric.model_id: weight for metric, weight in zip(model_metrics, weights)}

    def _calculate_cv_weights(
        self,
        model_metrics: List[ModelMetrics],
        predictions: Optional[List[List[float]]] = None,
        true_values: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """基于交叉验证计算权重"""
        # 结合多个指标
        weights = []

        for metric in model_metrics:
            # 综合得分：R²贡献 + RMSE倒数贡献
            r2_score = max(0, metric.r2)
            rmse_score = 1.0 / (metric.rmse + 1e-6) if metric.rmse > 0 else 1e6
            mae_score = 1.0 / (metric.mae + 1e-6) if metric.mae > 0 else 1e6

            # 加权组合
            weight = 0.5 * r2_score + 0.3 * rmse_score + 0.2 * mae_score
            weights.append(weight)

        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            n = len(weights)
            weights = [1.0 / n] * n

        return {metric.model_id: weight for metric, weight in zip(model_metrics, weights)}

    def _calculate_bma_weights(
        self,
        model_metrics: List[ModelMetrics],
        predictions: Optional[List[List[float]]] = None,
        true_values: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """贝叶斯模型平均权重"""
        # 使用BIC近似计算后验概率
        weights = []

        for metric in model_metrics:
            # 假设样本数量（可以传入参数）
            n_samples = 100  # 默认值

            # BIC = n * ln(RMSE^2) + k * ln(n)
            # k是模型复杂度（这里简化处理）
            rmse2 = metric.rmse ** 2
            if rmse2 > 0:
                bic = n_samples * np.log(rmse2) + 3 * np.log(n_samples)
                # 转换为似然
                likelihood = np.exp(-0.5 * bic)
            else:
                likelihood = 1.0

            weights.append(likelihood)

        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            n = len(weights)
            weights = [1.0 / n] * n

        return {metric.model_id: weight for metric, weight in zip(model_metrics, weights)}

    def _calculate_uncertainty_weights(
        self,
        model_metrics: List[ModelMetrics],
        predictions: Optional[List[List[float]]] = None,
        true_values: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """基于不确定性计算权重"""
        # 使用RMSE作为不确定性的代理
        rmse_values = [metric.rmse for metric in model_metrics]
        weights = []

        for rmse in rmse_values:
            if rmse > 0:
                # 方差倒数加权
                weight = 1.0 / (rmse ** 2)
            else:
                weight = 1e6
            weights.append(weight)

        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            n = len(weights)
            weights = [1.0 / n] * n

        return {metric.model_id: weight for metric, weight in zip(model_metrics, weights)}

    def _calculate_adaptive_weights(
        self,
        model_metrics: List[ModelMetrics],
        predictions: Optional[List[List[float]]] = None,
        true_values: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """自适应权重计算"""
        # 结合稳定性和准确性
        weights = []

        for metric in model_metrics:
            # 准确性得分（RMSE的倒数）
            accuracy_score = 1.0 / (metric.rmse + 1e-6) if metric.rmse > 0 else 1e6

            # 稳定性得分（如果有）
            stability_score = metric.stability if metric.stability is not None else 1.0

            # 自适应组合：稳定性高时更依赖稳定性，稳定性低时更依赖准确性
            alpha = min(1.0, stability_score)
            weight = alpha * stability_score + (1 - alpha) * accuracy_score

            weights.append(weight)

        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]
        else:
            n = len(weights)
            weights = [1.0 / n] * n

        return {metric.model_id: weight for metric, weight in zip(model_metrics, weights)}

    def _apply_constraints(
        self,
        weights: Dict[str, float],
        min_weight: float,
        max_weight: float,
        normalize: bool,
        smoothing: bool,
        smoothing_factor: float
    ) -> Dict[str, float]:
        """应用约束条件"""
        # 最小最大约束
        constrained_weights = {
            k: max(min_weight, min(max_weight, v)) for k, v in weights.items()
        }

        # 归一化
        if normalize:
            total = sum(constrained_weights.values())
            if total > 0:
                constrained_weights = {
                    k: v / total for k, v in constrained_weights.items()
                }

        # 平滑处理
        if smoothing:
            n = len(constrained_weights)
            avg_weight = 1.0 / n
            constrained_weights = {
                k: smoothing_factor * avg_weight + (1 - smoothing_factor) * v
                for k, v in constrained_weights.items()
            }
            # 重新归一化
            total = sum(constrained_weights.values())
            if total > 0:
                constrained_weights = {
                    k: v / total for k, v in constrained_weights.items()
                }

        return constrained_weights

    def calculate_spatial_weights(
        self,
        model_metrics: List[ModelMetrics],
        spatial_predictions: List[np.ndarray],
        spatial_true_values: np.ndarray
    ) -> List[Dict[str, float]]:
        """
        计算空间变化的权重

        Args:
            model_metrics: 模型评估指标
            spatial_predictions: 各模型的空间预测 [n_models, n_points]
            spatial_true_values: 空间真实值 [n_points]

        Returns:
            每个空间点的权重列表 [n_points, {model_id: weight}]
        """
        n_points = len(spatial_true_values)
        n_models = len(model_metrics)

        spatial_weights = []

        for i in range(n_points):
            # 计算每个模型在该点的误差
            point_errors = []
            for j in range(n_models):
                pred = spatial_predictions[j][i]
                true_val = spatial_true_values[i]
                error = abs(pred - true_val)
                point_errors.append(error)

            # 基于误差计算权重（误差越小，权重越大）
            point_weights = []
            for error in point_errors:
                if error > 0:
                    weight = 1.0 / (error ** 2)
                else:
                    weight = 1e6
                point_weights.append(weight)

            # 归一化
            total = sum(point_weights)
            if total > 0:
                point_weights = [w / total for w in point_weights]
            else:
                point_weights = [1.0 / n_models] * n_models

            # 创建权重字典
            weights_dict = {
                model_metrics[j].model_id: point_weights[j]
                for j in range(n_models)
            }
            spatial_weights.append(weights_dict)

        return spatial_weights
