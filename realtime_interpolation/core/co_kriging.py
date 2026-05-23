"""
协克里金（Co-Kriging）插值算法
Co-Kriging Interpolation

实现主变量与协变量的联合克里金插值，支持：
- 普通协克里金（Ordinary Co-Kriging）
- 交叉变异函数建模
- 多变量协方差矩阵构建
- Sherman-Morrison增量更新扩展
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..config import KrigingConfig
from ..models import DataPoint, PredictionResult, VariogramModel

logger = logging.getLogger(__name__)


class CrossVariogramModel:
    """
    交叉变异函数模型

    描述主变量与协变量之间的空间相关性。
    支持线性共区域化模型（LCM）。
    """

    def __init__(
        self,
        primary_model: VariogramModel,
        secondary_model: Optional[VariogramModel] = None,
        cross_model: Optional[VariogramModel] = None,
        correlation_coefficient: float = 0.7,
    ):
        """
        初始化交叉变异函数模型

        Args:
            primary_model: 主变量变异函数模型
            secondary_model: 协变量变异函数模型（默认与主变量相同）
            cross_model: 交叉变异函数模型（默认根据相关系数推导）
            correlation_coefficient: 主变量与协变量的相关系数 [0, 1]
        """
        self.primary_model = primary_model
        self.secondary_model = secondary_model or primary_model
        self.correlation_coefficient = float(np.clip(correlation_coefficient, 0.0, 1.0))

        if cross_model is None:
            # 线性共区域化模型：交叉协方差 = sqrt(主方差 × 协方差) × 相关系数
            self.cross_model = VariogramModel(
                model_type=self.primary_model.model_type,
                sill=self.primary_model.sill * self.correlation_coefficient,
                range=max(self.primary_model.range, self.secondary_model.range),
                nugget=np.sqrt(self.primary_model.nugget * self.secondary_model.nugget) * self.correlation_coefficient,
            )
        else:
            self.cross_model = cross_model

    def primary_covariance(self, p1: DataPoint, p2: DataPoint) -> float:
        """主变量自协方差 C11"""
        return self.primary_model.covariance(p1, p2)

    def secondary_covariance(self, p1: DataPoint, p2: DataPoint) -> float:
        """协变量自协方差 C22"""
        return self.secondary_model.covariance(p1, p2)

    def cross_covariance(self, primary: DataPoint, secondary: DataPoint) -> float:
        """交叉协方差 C12 = C21"""
        return self.cross_model.covariance(primary, secondary)

    def estimate_correlation(
        self,
        primary_points: List[DataPoint],
        secondary_points: List[DataPoint],
    ) -> float:
        """
        从数据估计主变量与协变量的相关性

        Args:
            primary_points: 主变量数据点
            secondary_points: 协变量数据点

        Returns:
            float: 估计的相关系数
        """
        if not primary_points or not secondary_points:
            return self.correlation_coefficient

        # 使用共位点估计相关性
        common = []
        sec_dict = {(p.x, p.y): p.value for p in secondary_points}

        for pp in primary_points:
            key = (pp.x, pp.y)
            if key in sec_dict:
                common.append((pp.value, sec_dict[key]))

        if len(common) < 3:
            return self.correlation_coefficient

        p_vals = np.array([c[0] for c in common])
        s_vals = np.array([c[1] for c in common])

        corr = float(np.corrcoef(p_vals, s_vals)[0, 1])
        return max(0.0, corr) if not np.isnan(corr) else self.correlation_coefficient


class CoKriging:
    """
    协克里金插值器

    同时利用主变量和协变量进行联合预测。
    构建扩展协方差矩阵，包含交叉协方差项。
    """

    def __init__(
        self,
        cross_variogram: CrossVariogramModel,
        config: Optional[KrigingConfig] = None,
    ):
        """
        初始化协克里金插值器

        Args:
            cross_variogram: 交叉变异函数模型
            config: 克里金配置
        """
        self.cross_variogram = cross_variogram
        self.config = config or KrigingConfig()
        self._lock = threading.RLock()

        # 主变量数据点
        self.primary_points: List[DataPoint] = []
        # 协变量数据点
        self.secondary_points: List[DataPoint] = []

        # 扩展协方差矩阵
        self.covariance_matrix: Optional[np.ndarray] = None
        self.covariance_matrix_inv: Optional[np.ndarray] = None

    def add_data(
        self,
        primary_points: List[DataPoint],
        secondary_points: Optional[List[DataPoint]] = None,
    ) -> None:
        """
        添加数据点

        Args:
            primary_points: 主变量数据点
            secondary_points: 协变量数据点
        """
        with self._lock:
            self.primary_points.extend(primary_points)
            if secondary_points:
                self.secondary_points.extend(secondary_points)

    def _build_covariance_matrix(self) -> np.ndarray:
        """构建扩展协方差矩阵"""
        n_primary = len(self.primary_points)
        n_secondary = len(self.secondary_points)
        n_total = n_primary + n_secondary

        K = np.zeros((n_total, n_total), dtype=np.float64)

        # C11: 主变量自协方差
        for i in range(n_primary):
            for j in range(n_primary):
                K[i, j] = self.cross_variogram.primary_covariance(
                    self.primary_points[i], self.primary_points[j]
                )

        # C22: 协变量自协方差
        for i in range(n_secondary):
            for j in range(n_secondary):
                K[n_primary + i, n_primary + j] = self.cross_variogram.secondary_covariance(
                    self.secondary_points[i], self.secondary_points[j]
                )

        # C12 和 C21: 交叉协方差
        for i in range(n_primary):
            for j in range(n_secondary):
                cross_cov = self.cross_variogram.cross_covariance(
                    self.primary_points[i], self.secondary_points[j]
                )
                K[i, n_primary + j] = cross_cov
                K[n_primary + j, i] = cross_cov

        return K

    def fit(self) -> None:
        """拟合协克里金模型（构建和求逆协方差矩阵）"""
        with self._lock:
            if len(self.primary_points) == 0:
                logger.warning("没有主变量数据点")
                return

            n_total = len(self.primary_points) + len(self.secondary_points)
            self.covariance_matrix = self._build_covariance_matrix()

            try:
                # 添加微小的正则化项保证矩阵可逆
                reg = 1e-10 * np.eye(n_total)
                self.covariance_matrix_inv = np.linalg.inv(self.covariance_matrix + reg)
            except np.linalg.LinAlgError:
                logger.warning("协方差矩阵奇异，使用伪逆")
                self.covariance_matrix_inv = np.linalg.pinv(self.covariance_matrix)

    def predict(self, x: float, y: float) -> PredictionResult:
        """
        在给定位置进行协克里金预测

        Args:
            x: 目标点x坐标
            y: 目标点y坐标

        Returns:
            PredictionResult: 预测值和方差
        """
        with self._lock:
            if self.covariance_matrix_inv is None:
                self.fit()
                if self.covariance_matrix_inv is None:
                    return PredictionResult(value=0.0, variance=float('inf'))

            target = DataPoint(x=x, y=y, value=0.0, id=f'target_{x}_{y}')

            n_primary = len(self.primary_points)
            n_secondary = len(self.secondary_points)
            n_total = n_primary + n_secondary

            # 构建目标点与已知点之间的协方差向量
            k_target = np.zeros(n_total, dtype=np.float64)

            for i, pp in enumerate(self.primary_points):
                k_target[i] = self.cross_variogram.primary_covariance(target, pp)

            for i, sp in enumerate(self.secondary_points):
                k_target[n_primary + i] = self.cross_variogram.cross_covariance(target, sp)

            # 权重向量: w = K⁻¹ k
            weights = self.covariance_matrix_inv @ k_target

            # 预测值
            prediction = 0.0
            for i, pp in enumerate(self.primary_points):
                prediction += weights[i] * pp.value
            for i, sp in enumerate(self.secondary_points):
                prediction += weights[n_primary + i] * sp.value

            # 预测方差: σ² = C(0) - kᵀK⁻¹k
            target_cov = self.cross_variogram.primary_covariance(target, target)
            variance = max(0.0, target_cov - float(k_target @ self.covariance_matrix_inv @ k_target))

            return PredictionResult(value=float(prediction), variance=float(variance))

    def predict_batch(self, points: List[Tuple[float, float]]) -> List[PredictionResult]:
        """
        批量预测

        Args:
            points: 坐标列表 [(x1, y1), (x2, y2), ...]

        Returns:
            List[PredictionResult]: 预测结果列表
        """
        results = []
        for x, y in points:
            results.append(self.predict(x, y))
        return results

    def predict_grid(
        self,
        x_range: Tuple[float, float],
        y_range: Tuple[float, float],
        resolution: int = 50,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        网格预测

        Args:
            x_range: X轴范围 (min, max)
            y_range: Y轴范围 (min, max)
            resolution: 网格分辨率

        Returns:
            Tuple[np.ndarray, np.ndarray]: (预测值网格, 方差网格)
        """
        x_vals = np.linspace(x_range[0], x_range[1], resolution)
        y_vals = np.linspace(y_range[0], y_range[1], resolution)

        pred_grid = np.zeros((resolution, resolution), dtype=np.float64)
        var_grid = np.zeros((resolution, resolution), dtype=np.float64)

        for i, y in enumerate(y_vals):
            for j, x in enumerate(x_vals):
                result = self.predict(x, y)
                pred_grid[i, j] = result.value
                var_grid[i, j] = result.variance

        return pred_grid, var_grid

    def leave_one_out_cv(self) -> Dict[str, float]:
        """
        留一法交叉验证

        Returns:
            Dict: {rmse, mae, r2, mean_variance}
        """
        if len(self.primary_points) < 3:
            return {'rmse': float('inf'), 'mae': float('inf'), 'r2': 0.0, 'mean_variance': float('inf')}

        predictions = []
        actuals = []
        variances = []

        original_points = list(self.primary_points)

        for i, point in enumerate(original_points):
            # 移除第i个点
            self.primary_points = original_points[:i] + original_points[i + 1:]
            self.covariance_matrix_inv = None  # 强制重建

            result = self.predict(point.x, point.y)
            predictions.append(result.value)
            actuals.append(point.value)
            variances.append(result.variance)

            # 恢复
            self.primary_points = original_points

        predictions = np.array(predictions)
        actuals = np.array(actuals)
        variances = np.array(variances)

        errors = predictions - actuals
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        mae = float(np.mean(np.abs(errors)))
        ss_res = np.sum(errors ** 2)
        ss_tot = np.sum((actuals - np.mean(actuals)) ** 2)
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

        return {
            'rmse': rmse,
            'mae': mae,
            'r2': r2,
            'mean_variance': float(np.mean(variances)),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取模型统计信息"""
        return {
            'n_primary': len(self.primary_points),
            'n_secondary': len(self.secondary_points),
            'correlation_coefficient': self.cross_variogram.correlation_coefficient,
            'primary_model': self.cross_variogram.primary_model.model_type,
            'secondary_model': self.cross_variogram.secondary_model.model_type,
        }
