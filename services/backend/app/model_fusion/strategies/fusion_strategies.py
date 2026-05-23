"""
融合策略实现
"""
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core.fusion_models import FusionStrategy, ModelPrediction

logger = logging.getLogger(__name__)


class FusionStrategies:
    """融合策略"""

    def fuse(
        self,
        strategy: FusionStrategy,
        models: List[ModelPrediction],
        weights: Dict[str, float],
        enable_uncertainty: bool = True
    ) -> Tuple[List[float], Optional[List[float]]]:
        """
        执行融合

        Args:
            strategy: 融合策略
            models: 各模型预测
            weights: 模型权重
            enable_uncertainty: 是否计算不确定性

        Returns:
            (融合预测, 融合方差)
        """
        fusion_methods = {
            FusionStrategy.SIMPLE_AVERAGE: self._simple_average,
            FusionStrategy.WEIGHTED_AVERAGE: self._weighted_average,
            FusionStrategy.MEDIAN: self._median_fusion,
            FusionStrategy.STACKING: self._stacking_fusion,
            FusionStrategy.BAYESIAN_MODEL_AVERAGE: self._bma_fusion,
            FusionStrategy.VARIANCE_WEIGHTED: self._variance_weighted,
            FusionStrategy.MAX_MIN: self._max_min_fusion,
        }

        method = fusion_methods.get(strategy)
        if method is None:
            logger.warning(f"未知的融合策略: {strategy}, 使用加权平均")
            method = self._weighted_average

        return method(models, weights, enable_uncertainty)

    def _simple_average(
        self,
        models: List[ModelPrediction],
        weights: Dict[str, float],
        enable_uncertainty: bool
    ) -> Tuple[List[float], Optional[List[float]]]:
        """简单平均融合"""
        predictions = [m.predictions for m in models]
        fused = np.mean(predictions, axis=0).tolist()

        # 计算方差（如果启用）
        variances = None
        if enable_uncertainty:
            variances = np.var(predictions, axis=0, ddof=1).tolist()

        return fused, variances

    def _weighted_average(
        self,
        models: List[ModelPrediction],
        weights: Dict[str, float],
        enable_uncertainty: bool
    ) -> Tuple[List[float], Optional[List[float]]]:
        """加权平均融合"""
        predictions = [m.predictions for m in models]
        weight_values = [weights[m.model_id] for m in models]

        # 归一化权重
        total_weight = sum(weight_values)
        if total_weight > 0:
            weight_values = [w / total_weight for w in weight_values]

        # 加权平均
        fused = np.average(predictions, axis=0, weights=weight_values).tolist()

        # 计算加权方差
        variances = None
        if enable_uncertainty:
            # 使用权重作为不确定性
            weighted_var = np.average(
                [(p - np.array(fused)) ** 2 for p in predictions],
                axis=0,
                weights=weight_values
            )
            variances = weighted_var.tolist()

        return fused, variances

    def _median_fusion(
        self,
        models: List[ModelPrediction],
        weights: Dict[str, float],
        enable_uncertainty: bool
    ) -> Tuple[List[float], Optional[List[float]]]:
        """中位数融合"""
        predictions = [m.predictions for m in models]
        fused = np.median(predictions, axis=0).tolist()

        variances = None
        if enable_uncertainty:
            # 使用IQR（四分位距）作为不确定性
            q25 = np.percentile(predictions, 25, axis=0)
            q75 = np.percentile(predictions, 75, axis=0)
            variances = ((q75 - q25) / 1.35).tolist()

        return fused, variances

    def _stacking_fusion(
        self,
        models: List[ModelPrediction],
        weights: Dict[str, float],
        enable_uncertainty: bool
    ) -> Tuple[List[float], Optional[List[float]]]:
        """堆叠融合（简化版，使用加权平均作为meta-learner）"""
        # 在完整实现中，这里应该使用meta-learner
        # 这里简化为基于权重的融合，但考虑非线性组合

        predictions = [m.predictions for m in models]
        weight_values = [weights[m.model_id] for m in models]

        # 归一化权重
        total_weight = sum(weight_values)
        if total_weight > 0:
            weight_values = [w / total_weight for w in weight_values]

        # 使用加权平均（简化版）
        fused = np.average(predictions, axis=0, weights=weight_values).tolist()

        variances = None
        if enable_uncertainty:
            weighted_var = np.average(
                [(p - np.array(fused)) ** 2 for p in predictions],
                axis=0,
                weights=weight_values
            )
            variances = weighted_var.tolist()

        return fused, variances

    def _bma_fusion(
        self,
        models: List[ModelPrediction],
        weights: Dict[str, float],
        enable_uncertainty: bool
    ) -> Tuple[List[float], Optional[List[float]]]:
        """贝叶斯模型平均融合"""
        predictions = [m.predictions for m in models]
        weight_values = [weights[m.model_id] for m in models]

        # BMA预测：加权平均
        fused = np.average(predictions, axis=0, weights=weight_values).tolist()

        # BMA方差：考虑模型方差和模型间方差
        variances = None
        if enable_uncertainty:
            # 如果有模型方差
            if all(m.variances is not None for m in models):
                model_variances = [np.array(m.variances) for m in models]

                # 组合方差
                # Var_total = Σ wi * (μi² + σi²) - μ_total²
                weighted_mean_sq = sum(
                    w * (np.array(p) ** 2) for w, p in zip(weight_values, predictions)
                )
                weighted_var = sum(
                    w * v for w, v in zip(weight_values, model_variances)
                )
                total_mean_sq = np.array(fused) ** 2

                total_var = weighted_mean_sq + weighted_var - total_mean_sq
                variances = total_var.tolist()
            else:
                # 简化版本：使用预测方差
                weighted_var = np.average(
                    [(p - np.array(fused)) ** 2 for p in predictions],
                    axis=0,
                    weights=weight_values
                )
                variances = weighted_var.tolist()

        return fused, variances

    def _variance_weighted(
        self,
        models: List[ModelPrediction],
        weights: Dict[str, float],
        enable_uncertainty: bool
    ) -> Tuple[List[float], Optional[List[float]]]:
        """方差加权融合"""
        predictions = [m.predictions for m in models]

        # 如果有方差信息，使用方差倒数权重
        if all(m.variances is not None for m in models):
            variance_weights = []
            for m in models:
                # 方差倒数
                v = np.array(m.variances)
                v = np.maximum(v, 1e-6)  # 避免除零
                w = 1.0 / v
                variance_weights.append(w)

            # 归一化权重
            total_weight = sum(variance_weights)
            if total_weight.sum() > 0:
                variance_weights = [w / total_weight for w in variance_weights]

            fused = np.average(predictions, axis=0, weights=variance_weights).tolist()

            # 计算组合方差
            combined_var = 1.0 / np.sum(variance_weights, axis=0)
            variances = combined_var.tolist()
        else:
            # 回退到普通加权平均
            return self._weighted_average(models, weights, enable_uncertainty)

        return fused, variances

    def _max_min_fusion(
        self,
        models: List[ModelPrediction],
        weights: Dict[str, float],
        enable_uncertainty: bool
    ) -> Tuple[List[float], Optional[List[float]]]:
        """最大最小融合（鲁棒融合）"""
        predictions = [m.predictions for m in models]

        # 使用最大值和最小值的平均
        max_pred = np.max(predictions, axis=0)
        min_pred = np.min(predictions, axis=0)
        fused = ((max_pred + min_pred) / 2).tolist()

        variances = None
        if enable_uncertainty:
            # 使用最大最小差值作为不确定性
            variances = ((max_pred - min_pred) / 4).tolist()

        return fused, variances

    def dynamic_fusion(
        self,
        models: List[ModelPrediction],
        weights: Dict[str, float],
        spatial_weights: List[Dict[str, float]],
        enable_uncertainty: bool
    ) -> Tuple[List[float], Optional[List[float]]]:
        """
        动态空间融合

        Args:
            models: 各模型预测
            weights: 全局权重
            spatial_weights: 空间变化权重
            enable_uncertainty: 是否计算不确定性

        Returns:
            (融合预测, 融合方差)
        """
        predictions = [m.predictions for m in models]
        n_points = len(predictions[0])

        fused = []
        variances = []

        for i in range(n_points):
            # 获取该点的权重
            point_weights = spatial_weights[i]

            # 提取该点的预测
            point_preds = [p[i] for p in predictions]

            # 使用该点的权重进行融合
            weight_values = [point_weights[m.model_id] for m in models]

            # 归一化
            total_weight = sum(weight_values)
            if total_weight > 0:
                weight_values = [w / total_weight for w in weight_values]

            # 加权平均
            fused_point = np.average(point_preds, weights=weight_values)
            fused.append(fused_point)

            # 计算方差
            if enable_uncertainty:
                point_var = np.average(
                    [(p - fused_point) ** 2 for p in point_preds],
                    weights=weight_values
                )
                variances.append(point_var)

        return fused, variances if enable_uncertainty else None
