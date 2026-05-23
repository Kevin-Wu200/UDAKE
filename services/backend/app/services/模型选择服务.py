"""
模型选择服务 - 基于交叉验证的自动模型选择
"""
import logging
from typing import Any, Dict, Tuple

import numpy as np
from pykrige.ok import OrdinaryKriging
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import KFold

from ..schemas.插值参数模型 import KrigingMethod, VariogramModel

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

    def select_parameters_by_industry(
        self,
        industry_config: Dict[str, Any],
        x: np.ndarray,
        y: np.ndarray,
        values: np.ndarray,
        enable_cross_validation: bool = True
    ) -> Dict[str, Any]:
        """
        基于行业配置选择参数
        结合行业预设配置和数据特征，提供优化的参数推荐

        Args:
            industry_config: 行业配置字典
            x: X坐标数组
            y: Y坐标数组
            values: 值数组
            enable_cross_validation: 是否启用交叉验证优化

        Returns:
            推荐的参数字典
        """
        point_count = len(values)

        logger.info(f"基于行业配置推荐参数: {industry_config['name']}")

        # 使用行业预设的克里金方法
        method = KrigingMethod(industry_config['default_method'])

        # 使用行业预设的变异函数模型
        variogram_model = VariogramModel(industry_config['default_variogram'])

        # 如果启用交叉验证且数据量足够，尝试优化变异函数模型
        model_scores = {}
        if enable_cross_validation and point_count >= 30:
            logger.info("启用交叉验证优化变异函数模型...")
            best_model, model_scores = self.select_best_variogram_model(x, y, values)

            # 如果交叉验证的结果明显优于行业预设，则使用交叉验证结果
            if model_scores and variogram_model.value in model_scores:
                preset_score = model_scores[variogram_model.value]
                best_score = model_scores[best_model.value]

                # 如果最佳模型比预设模型好超过10%，则使用最佳模型
                if best_score < preset_score * 0.9:
                    logger.info(f"交叉验证优化: {variogram_model.value} -> {best_model.value}")
                    variogram_model = best_model
                else:
                    logger.info(f"保持行业预设模型: {variogram_model.value}")

        # 检测趋势（如果行业配置启用趋势检测）
        has_trend = False
        if industry_config.get('enable_trend_detection', True):
            has_trend = self.detect_trend(x, y, values)
            if has_trend and method != KrigingMethod.UNIVERSAL:
                logger.info("检测到趋势，建议使用泛克里金方法")
                # 不强制修改方法，只记录建议

        # 使用行业预设的网格分辨率和滞后数
        grid_resolution = industry_config['default_grid_resolution']
        nlags = industry_config['default_nlags']

        # 根据数据量调整网格分辨率（避免过度计算）
        if point_count < 50:
            grid_resolution = min(grid_resolution, 80)
            logger.info("数据量小，调整网格分辨率")

        return {
            "variogram_model": variogram_model,
            "method": method,
            "grid_resolution": grid_resolution,
            "nlags": nlags,
            "has_trend": has_trend,
            "enable_anisotropy": industry_config.get('enable_anisotropy', False),
            "max_range": industry_config.get('max_range'),
            "nugget_ratio": industry_config.get('nugget_ratio'),
            "custom_parameters": industry_config.get('custom_parameters', {}),
            "model_scores": model_scores,
            "point_count": point_count,
            "industry_name": industry_config['name']
        }
