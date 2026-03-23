"""
异常检测模块
"""
from sklearn.ensemble import IsolationForest
from sklearn.covariance import EllipticEnvelope
import numpy as np
from typing import Any, Dict

from deep_learning.models.anomaly_detection import (
    AnomalyEnsembleIntegrator,
    ContrastiveAnomalyDetector,
    GANAnomalyDetector,
    GCAEAnomalyDetector,
    VAEAnomalyDetector,
)

class AnomalyDetector:
    """异常检测器"""

    def __init__(self):
        self.isolation_forest = IsolationForest(
            contamination=0.1,
            random_state=42
        )
        self.elliptic_envelope = EllipticEnvelope(
            contamination=0.1,
            random_state=42
        )

    def detect_spatial_anomalies(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray
    ) -> Dict[str, any]:
        """
        检测空间异常点
        """
        # 构建特征矩阵
        X = np.column_stack([x, y, values])

        # 使用孤立森林检测异常
        predictions = self.isolation_forest.fit_predict(X)

        # 异常点索引（-1表示异常）
        anomaly_indices = np.where(predictions == -1)[0]

        return {
            "anomaly_count": len(anomaly_indices),
            "anomaly_indices": anomaly_indices.tolist(),
            "anomaly_ratio": len(anomaly_indices) / len(values),
            "anomaly_locations": [
                {"x": float(x[i]), "y": float(y[i]), "value": float(values[i])}
                for i in anomaly_indices
            ]
        }

    def detect_value_anomalies(
        self,
        values: np.ndarray,
        threshold: float = 3.0
    ) -> Dict[str, any]:
        """
        基于统计方法检测值异常
        """
        mean = np.mean(values)
        std = np.std(values)

        # 使用更鲁棒的 MAD z-score，避免离群值拉高标准差导致漏检
        median = np.median(values)
        mad = np.median(np.abs(values - median))

        if mad > 1e-10:
            robust_z_scores = np.abs(0.6745 * (values - median) / (mad + 1e-10))
            anomaly_indices = np.where(robust_z_scores > threshold)[0]
            # 小样本且分布对称时，MAD 可能过于保守；补充标准 z-score 检测
            if len(anomaly_indices) == 0 and std > 1e-10:
                z_scores = np.abs((values - mean) / (std + 1e-10))
                anomaly_indices = np.where(z_scores > threshold)[0]
        elif std > 1e-10:
            z_scores = np.abs((values - mean) / (std + 1e-10))
            anomaly_indices = np.where(z_scores > threshold)[0]
        else:
            anomaly_indices = np.array([], dtype=int)

        return {
            "anomaly_count": len(anomaly_indices),
            "anomaly_indices": anomaly_indices.tolist(),
            "mean": float(mean),
            "std": float(std),
            "threshold": threshold
        }

    def get_anomaly_scores(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray
    ) -> np.ndarray:
        """
        获取异常分数
        """
        X = np.column_stack([x, y, values])
        scores = self.isolation_forest.fit(X).score_samples(X)
        return scores


class DeepAnomalyFusionDetector:
    """深度异常检测融合器，保留传统方法并融合四类深度模型。"""

    def __init__(self) -> None:
        self.baseline = AnomalyDetector()
        self.detectors = {
            "vae": VAEAnomalyDetector(),
            "gcae": GCAEAnomalyDetector(),
            "gan": GANAnomalyDetector(),
            "contrastive": ContrastiveAnomalyDetector(),
        }
        self.ensemble = AnomalyEnsembleIntegrator(self.detectors)
        self._fitted = False

    def fit(self, x: np.ndarray, y: np.ndarray, values: np.ndarray) -> Dict[str, Any]:
        coords = np.column_stack([x, y])
        summary: Dict[str, Any] = {}
        for name, detector in self.detectors.items():
            if name == "contrastive":
                summary[name] = detector.fit(coords, values, epochs=25)
            else:
                summary[name] = detector.fit(coords, values)
        self._fitted = True
        return summary

    def detect(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray,
        threshold_method: str = "percentile",
        percentile: float = 95.0,
    ) -> Dict[str, Any]:
        if not self._fitted:
            self.fit(x, y, values)

        coords = np.column_stack([x, y])
        deep_result = self.ensemble.detect(
            coords,
            values,
            threshold_method=threshold_method,  # type: ignore[arg-type]
            percentile=percentile,
        )
        baseline_scores = -self.baseline.get_anomaly_scores(x, y, values)
        baseline_scores = (baseline_scores - baseline_scores.min()) / (baseline_scores.max() - baseline_scores.min() + 1e-9)

        fused = 0.75 * np.asarray(deep_result["fused_scores"], dtype=float) + 0.25 * baseline_scores
        threshold = float(np.percentile(fused, percentile))
        anomaly_idx = np.where(fused >= threshold)[0]

        return {
            "anomaly_count": int(len(anomaly_idx)),
            "anomaly_indices": anomaly_idx.tolist(),
            "fused_scores": fused.tolist(),
            "threshold": threshold,
            "deep_component": deep_result,
            "baseline_component": {
                "scores": baseline_scores.tolist(),
            },
        }
