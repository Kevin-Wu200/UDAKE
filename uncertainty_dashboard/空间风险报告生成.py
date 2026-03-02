"""
空间风险报告生成
"""
import json
import numpy as np
from datetime import datetime
from typing import Dict, List
from pathlib import Path

class SpatialRiskReporter:
    """空间风险报告生成器"""

    def generate_risk_report(
        self,
        task_id: str,
        prediction: np.ndarray,
        variance: np.ndarray,
        risk_index: np.ndarray,
        uncertainty_levels: Dict[str, any],
        threshold_analysis: Dict[str, any],
        metadata: Dict[str, any] = None
    ) -> Dict[str, any]:
        """
        生成完整的空间风险报告
        """
        report = {
            "report_id": task_id,
            "generated_at": datetime.now().isoformat(),
            "metadata": metadata or {},
            "executive_summary": self._generate_executive_summary(
                prediction, variance, risk_index
            ),
            "risk_assessment": self._generate_risk_assessment(
                risk_index, uncertainty_levels
            ),
            "threshold_analysis": threshold_analysis,
            "spatial_statistics": self._generate_spatial_statistics(
                prediction, variance
            ),
            "recommendations": self._generate_recommendations(
                risk_index, uncertainty_levels, threshold_analysis
            )
        }

        return report

    def _generate_executive_summary(
        self,
        prediction: np.ndarray,
        variance: np.ndarray,
        risk_index: np.ndarray
    ) -> Dict[str, any]:
        """
        生成执行摘要
        """
        high_risk_percentage = np.sum(risk_index > 0.7) / risk_index.size * 100
        avg_uncertainty = np.mean(np.sqrt(variance))

        summary = {
            "total_area": int(prediction.size),
            "high_risk_percentage": float(high_risk_percentage),
            "average_uncertainty": float(avg_uncertainty),
            "prediction_range": {
                "min": float(np.min(prediction)),
                "max": float(np.max(prediction)),
                "mean": float(np.mean(prediction))
            },
            "overall_risk_level": self._classify_overall_risk(high_risk_percentage)
        }

        return summary

    def _generate_risk_assessment(
        self,
        risk_index: np.ndarray,
        uncertainty_levels: Dict[str, any]
    ) -> Dict[str, any]:
        """
        生成风险评估
        """
        return {
            "risk_distribution": {
                "low": float(np.sum(risk_index < 0.33) / risk_index.size * 100),
                "medium": float(np.sum((risk_index >= 0.33) & (risk_index < 0.67)) / risk_index.size * 100),
                "high": float(np.sum(risk_index >= 0.67) / risk_index.size * 100)
            },
            "uncertainty_levels": uncertainty_levels,
            "risk_hotspots": self._identify_risk_hotspots(risk_index)
        }

    def _generate_spatial_statistics(
        self,
        prediction: np.ndarray,
        variance: np.ndarray
    ) -> Dict[str, any]:
        """
        生成空间统计信息
        """
        return {
            "prediction": {
                "mean": float(np.mean(prediction)),
                "std": float(np.std(prediction)),
                "min": float(np.min(prediction)),
                "max": float(np.max(prediction)),
                "median": float(np.median(prediction)),
                "q25": float(np.percentile(prediction, 25)),
                "q75": float(np.percentile(prediction, 75))
            },
            "variance": {
                "mean": float(np.mean(variance)),
                "std": float(np.std(variance)),
                "min": float(np.min(variance)),
                "max": float(np.max(variance)),
                "median": float(np.median(variance))
            }
        }

    def _generate_recommendations(
        self,
        risk_index: np.ndarray,
        uncertainty_levels: Dict[str, any],
        threshold_analysis: Dict[str, any]
    ) -> List[str]:
        """
        生成建议
        """
        recommendations = []

        high_risk_pct = np.sum(risk_index > 0.7) / risk_index.size * 100

        if high_risk_pct > 20:
            recommendations.append("高风险区域占比超过20%，建议增加采样密度")

        if high_risk_pct > 10:
            recommendations.append("建议在高风险区域部署监测设备")

        if uncertainty_levels.get("statistics", {}).get("high", {}).get("percentage", 0) > 15:
            recommendations.append("高不确定性区域较多，建议进行补充采样")

        if not recommendations:
            recommendations.append("当前风险水平可接受，建议继续监测")

        return recommendations

    def _classify_overall_risk(self, high_risk_percentage: float) -> str:
        """分类整体风险等级"""
        if high_risk_percentage > 30:
            return "高风险"
        elif high_risk_percentage > 15:
            return "中等风险"
        else:
            return "低风险"

    def _identify_risk_hotspots(
        self,
        risk_index: np.ndarray,
        top_n: int = 5
    ) -> List[Dict[str, int]]:
        """识别风险热点"""
        risk_flat = risk_index.flatten()
        top_indices = np.argsort(risk_flat)[-top_n:]

        hotspots = []
        for idx in reversed(top_indices):
            y_idx = idx // risk_index.shape[1]
            x_idx = idx % risk_index.shape[1]
            hotspots.append({
                "x_index": int(x_idx),
                "y_index": int(y_idx),
                "risk_value": float(risk_flat[idx])
            })

        return hotspots

    def save_report(
        self,
        report: Dict[str, any],
        output_path: Path
    ):
        """保存报告"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
