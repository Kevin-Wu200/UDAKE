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
        if len(actual_values) == 0 or len(predicted_values) == 0 or len(variance) == 0:
            raise ValueError("输入数组不能为空")

        if len(actual_values) != len(predicted_values):
            raise ValueError("actual_values 与 predicted_values 长度必须一致")

        # 计算误差指标
        errors = actual_values - predicted_values
        abs_errors = np.abs(errors)

        mae = np.mean(abs_errors)
        rmse = np.sqrt(np.mean(errors ** 2))
        mape = np.mean(abs_errors / (np.abs(actual_values) + 1e-10)) * 100

        # 相关性分析（安全处理单值/常量输入）
        correlation = self._safe_correlation(actual_values, predicted_values)

        # 方差分析
        variance_stats = {
            "mean": float(np.mean(variance)),
            "std": float(np.std(variance)),
            "median": float(np.median(variance)),
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
        variance_mean = float(np.mean(variance))
        variance_std = float(np.std(variance))

        correlation_score = max(0.0, correlation) * 35.0

        # 用 sqrt(mean(variance)) 作为误差尺度，避免高方差掩盖高误差
        error_scale = max(1.0, np.sqrt(max(variance_mean, 0.0)))
        mae_component = np.exp(-mae / (error_scale + 1e-10))
        rmse_component = np.exp(-rmse / (error_scale + 1e-10))
        error_score = float((mae_component + rmse_component) / 2.0) * 40.0

        variance_cv = variance_std / (variance_mean + 1e-10) if variance_mean > 0 else 1.0
        variance_score = max(0.0, 1.0 - variance_cv) * 25.0

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

        variance_mean = float(np.mean(variance))
        variance_std = float(np.std(variance))
        variance_cv = variance_std / (variance_mean + 1e-10) if variance_mean > 0 else 0.0
        if variance_cv > 0.4:
            recommendations.append("方差波动较大，建议在高不确定性区域增加采样")

        if len(recommendations) == 0:
            recommendations.append("模型表现良好，可以投入使用")

        return recommendations

    def _safe_correlation(self, actual_values: np.ndarray, predicted_values: np.ndarray) -> float:
        """安全计算相关系数，避免空数组/常量数组导致 NaN 和告警。"""
        if len(actual_values) < 2 or len(predicted_values) < 2:
            return 1.0 if np.allclose(actual_values, predicted_values) else 0.0

        actual_std = float(np.std(actual_values))
        predicted_std = float(np.std(predicted_values))
        if actual_std < 1e-12 or predicted_std < 1e-12:
            return 1.0 if np.allclose(actual_values, predicted_values) else 0.0

        corr = float(np.corrcoef(actual_values, predicted_values)[0, 1])
        if not np.isfinite(corr):
            return 0.0
        return corr
