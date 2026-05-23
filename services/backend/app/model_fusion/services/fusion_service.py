"""
模型融合服务
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.fusion_engine import FusionEngine
from ..core.fusion_models import (
    FusionConfig,
    FusionStrategy,
    FusionTask,
    ModelPrediction,
    WeightConfig,
    WeightMethod,
)

logger = logging.getLogger(__name__)


class FusionService:
    """模型融合服务"""

    def __init__(self):
        self.fusion_engine = FusionEngine()
        self._tasks: Dict[str, FusionTask] = {}

    def create_fusion_task(
        self,
        models: List[Dict[str, Any]],
        config: Dict[str, Any],
        true_values: Optional[List[float]] = None
    ) -> str:
        """
        创建融合任务

        Args:
            models: 模型预测数据列表
            config: 融合配置
            true_values: 真实值（可选）

        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())

        # 解析模型预测
        model_predictions = [
            ModelPrediction(
                model_id=m.get('model_id', f'model_{i}'),
                model_name=m.get('model_name', f'Model {i}'),
                predictions=m.get('predictions', []),
                variances=m.get('variances'),
                confidence_intervals=m.get('confidence_intervals')
            )
            for i, m in enumerate(models)
        ]

        # 解析融合配置
        fusion_config = FusionConfig(
            strategy=FusionStrategy(config.get('strategy', 'weighted_average')),
            weight_config=WeightConfig(
                method=WeightMethod(config.get('weight_method', 'rmse_based')),
                min_weight=config.get('min_weight', 0.0),
                max_weight=config.get('max_weight', 1.0),
                normalize=config.get('normalize', True),
                smoothing=config.get('smoothing', False),
                smoothing_factor=config.get('smoothing_factor', 0.1)
            ),
            enable_cross_validation=config.get('enable_cross_validation', True),
            enable_stability_check=config.get('enable_stability_check', True),
            enable_uncertainty_propagation=config.get('enable_uncertainty_propagation', True),
            n_folds=config.get('n_folds', 5)
        )

        # 创建任务
        task = FusionTask(
            task_id=task_id,
            config=fusion_config,
            models=model_predictions,
            true_values=true_values,
            status="pending",
            created_at=datetime.now().isoformat()
        )

        self._tasks[task_id] = task

        logger.info(f"创建融合任务: {task_id}")

        # 异步执行
        self._execute_task(task_id)

        return task_id

    def _execute_task(self, task_id: str):
        """执行融合任务"""
        task = self._tasks.get(task_id)

        if task is None:
            logger.error(f"任务不存在: {task_id}")
            return

        try:
            task.status = "running"

            # 执行融合
            result = self.fusion_engine.fuse(
                config=task.config,
                models=task.models,
                true_values=task.true_values
            )

            task.result = result
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()

            logger.info(f"融合任务完成: {task_id}")

        except Exception as e:
            logger.error(f"融合任务失败: {task_id}, 错误: {str(e)}", exc_info=True)
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息
        """
        task = self._tasks.get(task_id)

        if task is None:
            return None

        return {
            'task_id': task.task_id,
            'status': task.status,
            'created_at': task.created_at,
            'completed_at': task.completed_at,
            'error': task.error
        }

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务结果

        Args:
            task_id: 任务ID

        Returns:
            融合结果
        """
        task = self._tasks.get(task_id)

        if task is None or task.result is None:
            return None

        if hasattr(task.result, 'model_dump'):
            return task.result.model_dump()
        return task.result.dict()

    def compare_strategies(
        self,
        models: List[Dict[str, Any]],
        config: Dict[str, Any],
        true_values: Optional[List[float]] = None,
        strategies: Optional[List[str]] = None
    ) -> str:
        """
        比较不同融合策略

        Args:
            models: 模型预测数据
            config: 融合配置
            true_values: 真实值
            strategies: 要比较的策略列表

        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())

        # 解析模型预测
        model_predictions = [
            ModelPrediction(
                model_id=m.get('model_id', f'model_{i}'),
                model_name=m.get('model_name', f'Model {i}'),
                predictions=m.get('predictions', []),
                variances=m.get('variances'),
                confidence_intervals=m.get('confidence_intervals')
            )
            for i, m in enumerate(models)
        ]

        # 解析融合配置
        fusion_config = FusionConfig(
            strategy=FusionStrategy(config.get('strategy', 'weighted_average')),
            weight_config=WeightConfig(
                method=WeightMethod(config.get('weight_method', 'rmse_based')),
                min_weight=config.get('min_weight', 0.0),
                max_weight=config.get('max_weight', 1.0),
                normalize=config.get('normalize', True),
                smoothing=config.get('smoothing', False),
                smoothing_factor=config.get('smoothing_factor', 0.1)
            )
        )

        # 解析策略列表
        strategy_list = None
        if strategies:
            strategy_list = [FusionStrategy(s) for s in strategies]

        # 创建任务
        task = FusionTask(
            task_id=task_id,
            config=fusion_config,
            models=model_predictions,
            true_values=true_values,
            status="pending",
            created_at=datetime.now().isoformat()
        )

        self._tasks[task_id] = task

        # 异步执行
        self._execute_comparison(task_id, strategy_list)

        return task_id

    def _execute_comparison(
        self,
        task_id: str,
        strategies: Optional[List[FusionStrategy]] = None
    ):
        """执行策略比较"""
        task = self._tasks.get(task_id)

        if task is None:
            logger.error(f"任务不存在: {task_id}")
            return

        try:
            task.status = "running"

            # 比较策略
            results = self.fusion_engine.compare_strategies(
                config=task.config,
                models=task.models,
                true_values=task.true_values,
                strategies=strategies
            )

            # 存储结果
            comparison_result = {
                'strategy_results': {
                    strategy: result.dict() for strategy, result in results.items()
                }
            }

            # 创建一个虚拟的融合结果来存储比较结果
            best_strategy = min(
                results.items(),
                key=lambda x: x[1].metrics.get('rmse', float('inf'))
            )[0] if results else None

            # 使用最佳策略的结果作为任务结果
            if best_strategy and best_strategy in results:
                task.result = results[best_strategy]
            else:
                task.result = None

            task.status = "completed"
            task.completed_at = datetime.now().isoformat()

            # 保存比较结果到任务（自定义字段）
            task.comparison_results = comparison_result

            logger.info(f"策略比较完成: {task_id}, 最佳策略: {best_strategy}")

        except Exception as e:
            logger.error(f"策略比较失败: {task_id}, 错误: {str(e)}", exc_info=True)
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()

    def optimize_weights(
        self,
        models: List[Dict[str, Any]],
        config: Dict[str, Any],
        true_values: List[float]
    ) -> str:
        """
        优化权重计算方法

        Args:
            models: 模型预测数据
            config: 融合配置
            true_values: 真实值

        Returns:
            任务ID
        """
        task_id = str(uuid.uuid4())

        # 解析模型预测
        model_predictions = [
            ModelPrediction(
                model_id=m.get('model_id', f'model_{i}'),
                model_name=m.get('model_name', f'Model {i}'),
                predictions=m.get('predictions', []),
                variances=m.get('variances'),
                confidence_intervals=m.get('confidence_intervals')
            )
            for i, m in enumerate(models)
        ]

        # 解析融合配置
        fusion_config = FusionConfig(
            strategy=FusionStrategy(config.get('strategy', 'weighted_average')),
            weight_config=WeightConfig(
                method=WeightMethod(config.get('weight_method', 'rmse_based'))
            )
        )

        # 创建任务
        task = FusionTask(
            task_id=task_id,
            config=fusion_config,
            models=model_predictions,
            true_values=true_values,
            status="pending",
            created_at=datetime.now().isoformat()
        )

        self._tasks[task_id] = task

        # 异步执行
        self._execute_optimization(task_id)

        return task_id

    def _execute_optimization(self, task_id: str):
        """执行权重优化"""
        task = self._tasks.get(task_id)

        if task is None:
            logger.error(f"任务不存在: {task_id}")
            return

        try:
            task.status = "running"

            # 优化权重
            optimization_result = self.fusion_engine.optimize_weights(
                config=task.config,
                models=task.models,
                true_values=task.true_values
            )

            # 使用最佳方法重新融合
            best_method = optimization_result.get('best_method')
            if best_method:
                task.config.weight_config.method = WeightMethod(best_method)
                task.result = self.fusion_engine.fuse(
                    config=task.config,
                    models=task.models,
                    true_values=task.true_values
                )
            else:
                task.result = None

            task.status = "completed"
            task.completed_at = datetime.now().isoformat()

            # 保存优化结果
            task.optimization_results = optimization_result

            logger.info(f"权重优化完成: {task_id}, 最佳方法: {best_method}")

        except Exception as e:
            logger.error(f"权重优化失败: {task_id}, 错误: {str(e)}", exc_info=True)
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()

    def list_tasks(self) -> List[Dict[str, Any]]:
        """
        列出所有任务

        Returns:
            任务列表
        """
        return [
            {
                'task_id': task.task_id,
                'status': task.status,
                'created_at': task.created_at,
                'completed_at': task.completed_at
            }
            for task in self._tasks.values()
        ]


# 全局服务实例
fusion_service = FusionService()
