"""
决策阈值分析
"""
import numpy as np
from typing import Dict, List, Tuple
from scipy import stats

class DecisionThresholdAnalyzer:
    """决策阈值分析器"""

    def analyze_thresholds(
        self,
        prediction: np.ndarray,
        variance: np.ndarray,
        decision_thresholds: List[float]
    ) -> Dict[str, any]:
        """
        分析决策阈值
        """
        results = {}

        for threshold in decision_thresholds:
            analysis = self._analyze_single_threshold(
                prediction, variance, threshold
            )
            results[f"threshold_{threshold}"] = analysis

        return {
            "thresholds": decision_thresholds,
            "analyses": results,
            "recommended_threshold": self._recommend_threshold(results)
        }

    def _analyze_single_threshold(
        self,
        prediction: np.ndarray,
        variance: np.ndarray,
        threshold: float
    ) -> Dict[str, any]:
        """
        分析单个阈值
        """
        # 超过阈值的区域
        exceeds_threshold = prediction > threshold

        # 统计
        exceeding_count = np.sum(exceeds_threshold)
        exceeding_percentage = exceeding_count / prediction.size * 100

        # 超过阈值区域的平均不确定性
        if exceeding_count > 0:
            avg_uncertainty = np.mean(variance[exceeds_threshold])
            max_uncertainty = np.max(variance[exceeds_threshold])
        else:
            avg_uncertainty = 0.0
            max_uncertainty = 0.0

        # 置信度评估
        confidence = self._calculate_confidence(
            prediction[exceeds_threshold],
            variance[exceeds_threshold]
        ) if exceeding_count > 0 else 0.0

        return {
            "exceeding_count": int(exceeding_count),
            "exceeding_percentage": float(exceeding_percentage),
            "avg_uncertainty": float(avg_uncertainty),
            "max_uncertainty": float(max_uncertainty),
            "confidence": float(confidence)
        }

    def _calculate_confidence(
        self,
        prediction: np.ndarray,
        variance: np.ndarray
    ) -> float:
        """
        计算置信度
        """
        # 置信度 = 1 - 归一化不确定性
        normalized_variance = variance / (np.max(variance) + 1e-10)
        confidence = 1 - np.mean(normalized_variance)
        return max(0, min(1, confidence))

    def _recommend_threshold(
        self,
        analyses: Dict[str, Dict]
    ) -> float:
        """
        推荐最佳阈值
        """
        # 选择置信度最高的阈值
        best_threshold = None
        best_confidence = -1

        for threshold_key, analysis in analyses.items():
            confidence = analysis.get("confidence", 0)
            if confidence > best_confidence:
                best_confidence = confidence
                best_threshold = float(threshold_key.split("_")[1])

        return best_threshold

    def calculate_decision_risk(
        self,
        prediction: np.ndarray,
        variance: np.ndarray,
        threshold: float,
        risk_tolerance: float = 0.1
    ) -> Dict[str, any]:
        """
        计算决策风险
        """
        exceeds_threshold = prediction > threshold

        # 计算置信区间
        std = np.sqrt(variance)
        lower_bound = prediction - 1.96 * std
        upper_bound = prediction + 1.96 * std

        # 不确定性导致的误判风险
        false_positive_risk = np.sum(
            (lower_bound < threshold) & (prediction > threshold)
        ) / prediction.size

        false_negative_risk = np.sum(
            (upper_bound > threshold) & (prediction < threshold)
        ) / prediction.size

        total_risk = false_positive_risk + false_negative_risk

        return {
            "threshold": threshold,
            "false_positive_risk": float(false_positive_risk),
            "false_negative_risk": float(false_negative_risk),
            "total_risk": float(total_risk),
            "acceptable": total_risk <= risk_tolerance,
            "risk_tolerance": risk_tolerance
        }

    def generate_threshold_recommendations(
        self,
        prediction: np.ndarray,
        variance: np.ndarray,
        n_thresholds: int = 5
    ) -> List[Dict[str, float]]:
        """
        生成阈值建议
        """
        # 基于预测值分位数生成阈值
        percentiles = np.linspace(20, 80, n_thresholds)
        thresholds = [np.percentile(prediction, p) for p in percentiles]

        recommendations = []
        for threshold in thresholds:
            analysis = self._analyze_single_threshold(
                prediction, variance, threshold
            )
            risk = self.calculate_decision_risk(
                prediction, variance, threshold
            )

            recommendations.append({
                "threshold": float(threshold),
                "confidence": analysis["confidence"],
                "risk": risk["total_risk"],
                "exceeding_percentage": analysis["exceeding_percentage"]
            })

        # 按置信度排序
        recommendations.sort(key=lambda x: x["confidence"], reverse=True)

        return recommendations
