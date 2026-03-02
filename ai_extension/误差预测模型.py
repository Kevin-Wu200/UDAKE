"""
误差预测模型
"""
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
import numpy as np
from typing import Dict, Tuple

class ErrorPredictor:
    """误差预测模型"""

    def __init__(self):
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

    def train(
        self,
        x: np.ndarray,
        y: np.ndarray,
        actual_values: np.ndarray,
        predicted_values: np.ndarray
    ) -> Dict[str, float]:
        """
        训练误差预测模型
        """
        # 计算实际误差
        errors = np.abs(actual_values - predicted_values)

        # 构建特征
        X = np.column_stack([x, y, predicted_values])

        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, errors, test_size=0.2, random_state=42
        )

        # 训练模型
        self.model.fit(X_train, y_train)

        # 评估
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)

        return {
            "train_r2": float(train_score),
            "test_r2": float(test_score),
            "feature_importance": self.model.feature_importances_.tolist()
        }

    def predict_error(
        self,
        x: np.ndarray,
        y: np.ndarray,
        predicted_values: np.ndarray
    ) -> np.ndarray:
        """
        预测误差
        """
        X = np.column_stack([x, y, predicted_values])
        return self.model.predict(X)

    def estimate_confidence(
        self,
        x: np.ndarray,
        y: np.ndarray,
        predicted_values: np.ndarray
    ) -> np.ndarray:
        """
        估计预测置信度
        """
        predicted_errors = self.predict_error(x, y, predicted_values)

        # 置信度 = 1 - 归一化误差
        max_error = np.max(predicted_errors)
        confidence = 1 - (predicted_errors / (max_error + 1e-10))

        return confidence
