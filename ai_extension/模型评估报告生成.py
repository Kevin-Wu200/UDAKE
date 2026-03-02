"""
模型评估报告生成
"""
import numpy as np
from typing import Dict, List
from datetime import datetime

class ModelEvaluator:
    """模型评估报告生成器"""

    def generate_evaluation_report(
        self,
        actual_values: np.ndarray,
        predicted_values: np.ndarray,
        variance: np.ndarray,
        model_params: Dict
    ) -> Dict[str, any]:
        """
        生成模型评估报告
        """
        # 计算误差指标
        errors = actual_values - predicted_values
        abs_errors = np.abs(errors)

        mae = np.mean(abs_errors)
        rmse = np.sqrt(np.mean(errors ** 2))
        mape = np.mean(abs_errors / (np.abs(actual_values) + 1e-10)) * 100

        # 相关性分析
        correlation = np.corrcoef(actual_values, predicted_values)[0, 1]

        # 方差分析
        variance_stats = {
            "mean": float(np.mean(variance)),
            "std": float(np.std(variance)),
            "min": float(np.min(variance)),
            "max": float(np.max(variance))
        }

        # 预测质量评估
        quality_score = self._calculate_quality_score(
            mae, rmse, correlation, variance
        )

        report = {
            "timestamp": datetime.now().isoformat(),
            "model_parameters": model_params,
            "error_metrics": {
                "mae": float(mae),
                "rmse": float(rmse),
                "mape": float(mape)
            },
            "correlation": float(correlation),
            "variance_statistics": variance_stats,
            "quality_score": float(quality_score),
            "sample_size": len(actual_values),
            "recommendations": self._generate_recommendations(
                mae, rmse, correlation, variance
            )
        }

        return report

    def _calculate_quality_score(
        self,
        mae: float,
        rmse: float,
        correlation: float,
        variance: np.ndarray
    ) -> float:
        """
        计算综合质量分数 (0-100)
        """
        # 归一化指标
        correlation_score = max(0, correlation) * 40
        error_score = max(0, 1 - mae / (np.mean(variance) + 1e-10)) * 30
        variance_score = max(0, 1 - np.std(variance) / (np.mean(variance) + 1e-10)) * 30

        total_score = correlation_score + error_score + variance_score
        return min(100, max(0, total_score))

    def _generate_recommendations(
        self,
        mae: float,
        rmse: float,
        correlation: float,
        variance: np.ndarray
    ) -> List[str]:
        """
        生成改进建议
        """
        recommendations = []

        if correlation < 0.7:
            recommendations.append("相关性较低，建议增加采样点数量")

        if mae > np.mean(variance):
            recommendations.append("误差较大，建议优化变异函数模型")

        if np.std(variance) / np.mean(variance) > 0.5:
            recommendations.append("方差波动较大，建议在高不确定性区域增加采样")

        if len(recommendations) == 0:
            recommendations.append("模型表现良好，可以投入使用")

        return recommendations
