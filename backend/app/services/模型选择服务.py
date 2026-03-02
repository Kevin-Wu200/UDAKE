"""
模型选择服务 - 基于交叉验证的自动模型选择
"""
from ..schemas.插值参数模型 import VariogramModel, KrigingMethod
from pykrige.ok import OrdinaryKriging
from sklearn.model_selection import KFold
from sklearn.metrics import mean_squared_error
from typing import Dict, Any, List, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ModelSelector:
    """智能模型选择器 - 基于交叉验证自动选择最优模型"""

    def __init__(self):
        self.variogram_models = [
            VariogramModel.SPHERICAL,
            VariogramModel.EXPONENTIAL,
            VariogramModel.GAUSSIAN,
            VariogramModel.LINEAR
        ]

    def detect_trend(self, x: np.ndarray, y: np.ndarray, values: np.ndarray) -> bool:
        """
        检测空间趋势
        使用线性回归检测是否存在显著趋势
        """
        from scipy.stats import linregress

        # X方向趋势
        slope_x, _, r_value_x, p_value_x, _ = linregress(x, values)
        # Y方向趋势
        slope_y, _, r_value_y, p_value_y, _ = linregress(y, values)

        # 如果任一方向存在显著趋势（p<0.05且R²>0.3）
        has_trend = (p_value_x < 0.05 and r_value_x**2 > 0.3) or \
                    (p_value_y < 0.05 and r_value_y**2 > 0.3)

        if has_trend:
            logger.info(f"检测到空间趋势: X方向R²={r_value_x**2:.3f}, Y方向R²={r_value_y**2:.3f}")

        return has_trend

    def evaluate_variogram_model(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray,
        model: VariogramModel,
        n_folds: int = 5
    ) -> float:
        """
        使用交叉验证评估变异函数模型
        返回RMSE分数（越小越好）
        """
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        rmse_scores = []

        for train_idx, test_idx in kf.split(x):
            x_train, x_test = x[train_idx], x[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            values_train, values_test = values[train_idx], values[test_idx]

            try:
                ok = OrdinaryKriging(
                    x_train, y_train, values_train,
                    variogram_model=model.value,
                    enable_plotting=False,
                    verbose=False
                )

                z, _ = ok.execute('points', x_test, y_test)
                rmse = np.sqrt(mean_squared_error(values_test, z))
                rmse_scores.append(rmse)

            except Exception as e:
                logger.warning(f"模型 {model.value} 评估失败: {str(e)}")
                return float('inf')

        return np.mean(rmse_scores) if rmse_scores else float('inf')

    def select_best_variogram_model(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray
    ) -> Tuple[VariogramModel, Dict[str, float]]:
        """
        自动选择最佳变异函数模型
        返回: (最佳模型, 所有模型的评分)
        """
        logger.info("开始多变异函数模型评估...")

        scores = {}
        for model in self.variogram_models:
            logger.info(f"评估模型: {model.value}")
            score = self.evaluate_variogram_model(x, y, values, model)
            scores[model.value] = score
            logger.info(f"  RMSE: {score:.4f}")

        # 选择RMSE最小的模型
        best_model_name = min(scores, key=scores.get)
        best_model = VariogramModel(best_model_name)

        logger.info(f"✓ 最佳模型: {best_model.value} (RMSE={scores[best_model_name]:.4f})")

        return best_model, scores

    def select_kriging_method(
        self,
        point_count: int,
        has_trend: bool = False
    ) -> KrigingMethod:
        """
        选择克里金方法
        """
        if has_trend:
            logger.info("检测到趋势，使用泛克里金")
            return KrigingMethod.UNIVERSAL
        elif point_count > 1000:
            logger.info("数据量大，使用分块克里金")
            return KrigingMethod.BLOCK
        else:
            logger.info("使用普通克里金")
            return KrigingMethod.ORDINARY

    def auto_select_parameters(
        self,
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray,
        enable_auto_model: bool = True
    ) -> Dict[str, Any]:
        """
        自动选择最优插值参数

        Args:
            x: X坐标数组
            y: Y坐标数组
            values: 值数组
            enable_auto_model: 是否启用自动模型选择（交叉验证）

        Returns:
            推荐的参数字典
        """
        point_count = len(values)

        # 趋势检测
        has_trend = self.detect_trend(x, y, values)

        # 选择克里金方法
        method = self.select_kriging_method(point_count, has_trend)

        # 选择变异函数模型
        if enable_auto_model and point_count >= 30:
            best_model, model_scores = self.select_best_variogram_model(x, y, values)
        else:
            # 数据量太小，使用默认模型
            best_model = VariogramModel.SPHERICAL
            model_scores = {}
            logger.info("数据量较小，使用默认球状模型")

        # 推荐网格分辨率
        grid_resolution = min(200, max(50, int(np.sqrt(point_count) * 5)))

        # 推荐滞后数
        nlags = 6 if point_count < 100 else 12

        return {
            "variogram_model": best_model,
            "method": method,
            "grid_resolution": grid_resolution,
            "nlags": nlags,
            "has_trend": has_trend,
            "model_scores": model_scores,
            "point_count": point_count
        }
