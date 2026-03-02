"""
异常检测模块
"""
from sklearn.ensemble import IsolationForest
from sklearn.covariance import EllipticEnvelope
import numpy as np
from typing import Dict, List

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

        # Z-score方法
        z_scores = np.abs((values - mean) / std)
        anomaly_indices = np.where(z_scores > threshold)[0]

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
