"""
趋势识别模型
"""
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
import numpy as np
from typing import Tuple, Dict

class TrendIdentifier:
    """趋势识别模型"""

    def __init__(self):
        self.linear_model = LinearRegression()
        self.poly_features = PolynomialFeatures(degree=2)

    def detect_linear_trend(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray
    ) -> Dict[str, float]:
        """
        检测线性趋势
        """
        # 构建特征矩阵
        X = np.column_stack([x, y])

        # 拟合线性模型
        self.linear_model.fit(X, values)

        # 获取系数
        coefficients = self.linear_model.coef_
        intercept = self.linear_model.intercept_
        r2_score = self.linear_model.score(X, values)

        return {
            "x_coefficient": float(coefficients[0]),
            "y_coefficient": float(coefficients[1]),
            "intercept": float(intercept),
            "r2_score": float(r2_score),
            "has_trend": r2_score > 0.3
        }

    def detect_polynomial_trend(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray
    ) -> Dict[str, float]:
        """
        检测多项式趋势
        """
        X = np.column_stack([x, y])
        X_poly = self.poly_features.fit_transform(X)

        poly_model = LinearRegression()
        poly_model.fit(X_poly, values)

        r2_score = poly_model.score(X_poly, values)

        return {
            "r2_score": float(r2_score),
            "has_polynomial_trend": r2_score > 0.4
        }

    def predict_trend(
        self,
        x: np.ndarray,
        y: np.ndarray
    ) -> np.ndarray:
        """
        预测趋势值
        """
        X = np.column_stack([x, y])
        return self.linear_model.predict(X)
