"""
融合引擎
"""
import numpy as np
from typing import List, Dict, Any, Optional
from .fusion_models import (
    FusionConfig, FusionResult, ModelPrediction, FusionStrategy
)
from .weight_calculator import WeightCalculator
from ..strategies.fusion_strategies import FusionStrategies
from ..evaluation.model_evaluator import ModelEvaluator
import logging

logger = logging.getLogger(__name__)


class FusionEngine:
    """融合引擎"""

    def __init__(self):
        self.weight_calculator = WeightCalculator()
        self.fusion_strategies = FusionStrategies()
        self.model_evaluator = ModelEvaluator()

    def fuse(
        self,
        config: FusionConfig,
        models: List[ModelPrediction],
        true_values: Optional[List[float]] = None
    ) -> FusionResult:
        """
        执行模型融合

        Args:
            config: 融合配置
            models: 各模型的预测结果
            true_values: 真实值（用于评估）

        Returns:
            融合结果
        """
        logger.info(f"开始融合 {len(models)} 个模型，策略: {config.strategy}")

        try:
            # 步骤1: 计算模型指标
            model_metrics = self.model_evaluator.evaluate_models(
                models, true_values
            )

            # 步骤2: 计算权重
            weights = self.weight_calculator.calculate_weights(
                method=config.weight_config.method,
                model_metrics=model_metrics,
                predictions=[m.predictions for m in models],
                true_values=true_values,
                min_weight=config.weight_config.min_weight,
                max_weight=config.weight_config.max_weight,
                normalize=config.weight_config.normalize,
                smoothing=config.weight_config.smoothing,
                smoothing_factor=config.weight_config.smoothing_factor
            )

            logger.info(f"计算得到权重: {weights}")

            # 步骤3: 执行融合
            fused_predictions, fused_variances = self.fusion_strategies.fuse(
                strategy=config.strategy,
                models=models,
                weights=weights,
                enable_uncertainty=config.enable_uncertainty_propagation
            )

            # 步骤4: 计算融合指标
            if true_values is not None:
                fused_metrics = self.model_evaluator.evaluate_fusion_result(
                    fused_predictions, true_values
                )
            else:
                fused_metrics = {}

            # 步骤5: 计算改进指标
            improvement = None
            if true_values is not None and model_metrics:
                improvement = self._calculate_improvement(
                    model_metrics, fused_metrics
                )

            # 步骤6: 创建融合结果
            result = FusionResult(
                fused_predictions=fused_predictions,
                fused_variances=fused_variances,
                weights=weights,
                metrics=fused_metrics,
                individual_predictions=models,
                fusion_strategy=config.strategy.value,
                weight_method=config.weight_config.method.value,
                improvement=improvement
            )

            logger.info(f"融合完成，策略: {config.strategy}")
            return result

        except Exception as e:
            logger.error(f"融合失败: {str(e)}", exc_info=True)
            raise

    def _calculate_improvement(
        self,
        model_metrics: List[Any],
        fused_metrics: Dict[str, float]
    ) -> Dict[str, float]:
        """计算融合改进指标"""
        if not model_metrics or not fused_metrics:
            return {}

        # 计算平均指标
        avg_rmse = np.mean([m.rmse for m in model_metrics])
        avg_mae = np.mean([m.mae for m in model_metrics])
        avg_r2 = np.mean([m.r2 for m in model_metrics])

        # 计算改进百分比
        improvement = {}

        if 'rmse' in fused_metrics and avg_rmse > 0:
            improvement['rmse_improvement'] = (
                (avg_rmse - fused_metrics['rmse']) / avg_rmse * 100
            )

        if 'mae' in fused_metrics and avg_mae > 0:
            improvement['mae_improvement'] = (
                (avg_mae - fused_metrics['mae']) / avg_mae * 100
            )

        if 'r2' in fused_metrics:
            improvement['r2_improvement'] = fused_metrics['r2'] - avg_r2

        return improvement

    def compare_strategies(
        self,
        config: FusionConfig,
        models: List[ModelPrediction],
        true_values: Optional[List[float]] = None,
        strategies: Optional[List[FusionStrategy]] = None
    ) -> Dict[str, FusionResult]:
        """
        比较不同融合策略

        Args:
            config: 融合配置
            models: 各模型的预测结果
            true_values: 真实值
            strategies: 要比较的策略列表

        Returns:
            各策略的融合结果字典 {strategy_name: result}
        """
        if strategies is None:
            strategies = [
                FusionStrategy.SIMPLE_AVERAGE,
                FusionStrategy.WEIGHTED_AVERAGE,
                FusionStrategy.MEDIAN,
                FusionStrategy.STACKING,
                FusionStrategy.VARIANCE_WEIGHTED
            ]

        results = {}

        for strategy in strategies:
            try:
                # 更新配置中的策略
                config.strategy = strategy
                result = self.fuse(config, models, true_values)
                results[strategy.value] = result
                logger.info(f"策略 {strategy.value} 完成")
            except Exception as e:
                logger.error(f"策略 {strategy.value} 失败: {str(e)}")

        return results

    def optimize_weights(
        self,
        config: FusionConfig,
        models: List[ModelPrediction],
        true_values: List[float],
        weight_methods: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        优化权重计算方法

        Args:
            config: 融合配置
            models: 各模型的预测结果
            true_values: 真实值
            weight_methods: 要测试的权重方法列表

        Returns:
            优化结果
        """
        if weight_methods is None:
            from .fusion_models import WeightMethod
            weight_methods = [
                WeightMethod.EQUAL,
                WeightMethod.RMSE_BASED,
                WeightMethod.MAE_BASED,
                WeightMethod.R2_BASED,
                WeightMethod.CROSS_VALIDATION,
                WeightMethod.UNCERTAINTY_BASED,
                WeightMethod.ADAPTIVE
            ]

        results = {}
        best_method = None
        best_rmse = float('inf')

        for method in weight_methods:
            try:
                # 更新权重方法
                config.weight_config.method = method
                result = self.fuse(config, models, true_values)

                # 记录结果
                results[method.value] = {
                    'rmse': result.metrics.get('rmse', float('inf')),
                    'mae': result.metrics.get('mae', float('inf')),
                    'r2': result.metrics.get('r2', 0.0),
                    'weights': result.weights
                }

                # 找到最佳方法
                rmse = result.metrics.get('rmse', float('inf'))
                if rmse < best_rmse:
                    best_rmse = rmse
                    best_method = method.value

                logger.info(f"权重方法 {method.value}: RMSE={rmse:.4f}")

            except Exception as e:
                logger.error(f"权重方法 {method.value} 失败: {str(e)}")

        return {
            'results': results,
            'best_method': best_method,
            'best_rmse': best_rmse
        }