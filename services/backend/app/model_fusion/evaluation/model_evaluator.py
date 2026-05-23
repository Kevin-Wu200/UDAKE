"""
模型评估器
"""
import logging
from typing import Dict, List, Optional

import numpy as np
from sklearn.model_selection import KFold

from ..core.fusion_models import ModelMetrics, ModelPrediction

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """模型评估器"""

    def __init__(self):
        pass

    def evaluate_models(
        self,
        models: List[ModelPrediction],
        true_values: Optional[List[float]] = None
    ) -> List[ModelMetrics]:
        """
        评估各模型性能

        Args:
            models: 各模型预测
            true_values: 真实值

        Returns:
            模型指标列表
        """
        metrics_list = []

        for model in models:
            if true_values is not None:
                # 计算各项指标
                rmse = self._calculate_rmse(model.predictions, true_values)
                mae = self._calculate_mae(model.predictions, true_values)
                r2 = self._calculate_r2(model.predictions, true_values)
                mape = self._calculate_mape(model.predictions, true_values)
                stability = self._calculate_stability(model.predictions)

                metrics = ModelMetrics(
                    model_id=model.model_id,
                    model_name=model.model_name,
                    rmse=rmse,
                    mae=mae,
                    r2=r2,
                    mape=mape,
                    stability=stability
                )
            else:
                # 如果没有真实值，使用默认值
                metrics = ModelMetrics(
                    model_id=model.model_id,
                    model_name=model.model_name,
                    rmse=0.0,
                    mae=0.0,
                    r2=1.0,
                    mape=0.0,
                    stability=1.0
                )

            metrics_list.append(metrics)

        return metrics_list

    def evaluate_fusion_result(
        self,
        predictions: List[float],
        true_values: List[float]
    ) -> Dict[str, float]:
        """
        评估融合结果

        Args:
            predictions: 融合预测
            true_values: 真实值

        Returns:
            评估指标字典
        """
        metrics = {
            'rmse': self._calculate_rmse(predictions, true_values),
            'mae': self._calculate_mae(predictions, true_values),
            'r2': self._calculate_r2(predictions, true_values),
            'mape': self._calculate_mape(predictions, true_values),
            'max_error': self._calculate_max_error(predictions, true_values),
        }

        return metrics

    def cross_validate(
        self,
        models: List[ModelPrediction],
        true_values: List[float],
        n_folds: int = 5
    ) -> Dict[str, List[float]]:
        """
        交叉验证

        Args:
            models: 各模型预测
            true_values: 真实值
            n_folds: 折数

        Returns:
            各指标在各折上的值
        """
        n_samples = len(true_values)

        if n_samples < n_folds:
            logger.warning(f"样本数({n_samples})小于折数({n_folds}), 使用样本数作为折数")
            n_folds = n_samples

        if n_samples == 0:
            return {}

        kfold = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        results = {m.model_id: [] for m in models}

        for train_idx, test_idx in kfold.split(range(n_samples)):
            # 提取训练集和测试集
            train_true = [true_values[i] for i in train_idx]  # noqa: F841
            test_true = [true_values[i] for i in test_idx]

            for model in models:
                train_pred = [model.predictions[i] for i in train_idx]  # noqa: F841
                test_pred = [model.predictions[i] for i in test_idx]

                # 计算RMSE
                rmse = self._calculate_rmse(test_pred, test_true)
                results[model.model_id].append(rmse)

        return results

    def evaluate_stability(
        self,
        models: List[ModelPrediction],
        true_values: List[float],
        n_bootstrap: int = 100
    ) -> Dict[str, float]:
        """
        评估模型稳定性（Bootstrap）

        Args:
            models: 各模型预测
            true_values: 真实值
            n_bootstrap: Bootstrap次数

        Returns:
            各模型的稳定性指标
        """
        n_samples = len(true_values)

        if n_samples == 0:
            return {m.model_id: 0.0 for m in models}

        stability_scores = {}

        for model in models:
            rmse_list = []

            for _ in range(n_bootstrap):
                # Bootstrap采样
                indices = np.random.choice(n_samples, n_samples, replace=True)
                bootstrap_true = [true_values[i] for i in indices]
                bootstrap_pred = [model.predictions[i] for i in indices]

                # 计算RMSE
                rmse = self._calculate_rmse(bootstrap_pred, bootstrap_true)
                rmse_list.append(rmse)

            # 稳定性：RMSE的变异系数（标准差/均值）
            rmse_mean = np.mean(rmse_list)
            rmse_std = np.std(rmse_list)

            if rmse_mean > 0:
                stability = 1.0 / (1.0 + rmse_std / rmse_mean)
            else:
                stability = 0.0

            stability_scores[model.model_id] = float(stability)

        return stability_scores

    def _calculate_rmse(
        self,
        predictions: List[float],
        true_values: List[float]
    ) -> float:
        """计算均方根误差"""
        if len(predictions) != len(true_values) or len(predictions) == 0:
            return 0.0

        mse = np.mean((np.array(predictions) - np.array(true_values)) ** 2)
        return float(np.sqrt(mse))

    def _calculate_mae(
        self,
        predictions: List[float],
        true_values: List[float]
    ) -> float:
        """计算平均绝对误差"""
        if len(predictions) != len(true_values) or len(predictions) == 0:
            return 0.0

        return float(np.mean(np.abs(np.array(predictions) - np.array(true_values))))

    def _calculate_r2(
        self,
        predictions: List[float],
        true_values: List[float]
    ) -> float:
        """计算R²分数"""
        if len(predictions) != len(true_values) or len(predictions) == 0:
            return 0.0

        ss_res = np.sum((np.array(true_values) - np.array(predictions)) ** 2)
        ss_tot = np.sum((np.array(true_values) - np.mean(true_values)) ** 2)

        if ss_tot == 0:
            return 1.0

        r2 = 1.0 - (ss_res / ss_tot)
        return float(max(0, min(1, r2)))

    def _calculate_mape(
        self,
        predictions: List[float],
        true_values: List[float]
    ) -> float:
        """计算平均绝对百分比误差"""
        if len(predictions) != len(true_values) or len(predictions) == 0:
            return 0.0

        # 避免除零
        epsilon = 1e-6
        mape = np.mean(
            np.abs((np.array(true_values) - np.array(predictions)) /
                   (np.array(true_values) + epsilon))
        ) * 100

        return float(mape)

    def _calculate_max_error(
        self,
        predictions: List[float],
        true_values: List[float]
    ) -> float:
        """计算最大误差"""
        if len(predictions) != len(true_values) or len(predictions) == 0:
            return 0.0

        return float(np.max(np.abs(np.array(predictions) - np.array(true_values))))

    def _calculate_stability(
        self,
        predictions: List[float],
        window_size: int = 5
    ) -> float:
        """
        计算预测稳定性（局部变异性）

        Args:
            predictions: 预测值
            window_size: 窗口大小

        Returns:
            稳定性得分（0-1，越高越稳定）
        """
        if len(predictions) < window_size:
            return 1.0

        # 计算滑动窗口的方差
        variances = []
        for i in range(len(predictions) - window_size + 1):
            window = predictions[i:i + window_size]
            variances.append(np.var(window))

        # 平均方差
        avg_variance = np.mean(variances)

        # 稳定性得分
        stability = 1.0 / (1.0 + avg_variance)

        return float(stability)
