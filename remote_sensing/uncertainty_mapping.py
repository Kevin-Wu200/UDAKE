"""
不确定性映射模块
================
根据影像分辨率及模型置信度，为每个反演指标生成对应的方差/不确定性分布网格。

功能：
1. 基于影像分辨率的空间不确定性建模
2. 基于模型置信度的指标不确定性估计
3. 综合不确定性网格生成（适用于SamplingRecommender输入）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class UncertaintyGrid:
    """不确定性分布网格"""
    variance: np.ndarray               # 方差网格
    std_dev: np.ndarray                # 标准差网格
    confidence: np.ndarray             # 置信度网格 (0-1)
    relative_error: np.ndarray         # 相对误差网格
    geo_transform: Optional[tuple] = None  # 地理变换参数
    indicator_name: str = ""           # 对应指标名称
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 不确定性映射引擎
# ---------------------------------------------------------------------------

class UncertaintyMapper:
    """不确定性分布网格生成器

    为每个反演指标生成对应的方差/不确定性分布，
    可直接作为SamplingRecommender的输入。
    """

    def __init__(
        self,
        base_resolution: float = 0.0001,  # 基础地面分辨率（度）
        sensor_noise_floor: float = 0.01,  # 传感器噪声本底
    ):
        self.base_resolution = base_resolution
        self.sensor_noise_floor = sensor_noise_floor

    # -------------------------------------------------------------------
    # 影像分辨率不确定性
    # -------------------------------------------------------------------

    def compute_resolution_uncertainty(
        self,
        shape: tuple,
        ground_resolution: float,
        geo_transform: Optional[tuple] = None,
    ) -> UncertaintyGrid:
        """根据地面分辨率计算空间不确定性

        原理：较低空间分辨率导致混合像元效应，
        反演结果的不确定性随分辨率降低而增加。

        Args:
            shape: 栅格形状 (rows, cols)
            ground_resolution: 地面采样距离(GSD) (m/pixel)
            geo_transform: GDAL地理变换参数

        Returns:
            不确定性网格
        """
        # 以0.1m分辨率为基准
        base_gsd = 0.1

        # 分辨率因子：分辨率越粗，不确定性越高
        resolution_factor = ground_resolution / base_gsd

        # 基础方差（空间自相关递减）
        rows, cols = shape

        # 构建距离衰减的不确定性（边缘通常更高）
        y_center, x_center = rows / 2.0, cols / 2.0
        yy, xx = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")

        # 归一化距离
        dist = np.sqrt(
            ((yy - y_center) / (rows / 2.0)) ** 2
            + ((xx - x_center) / (cols / 2.0)) ** 2
        )

        # 边缘不确定性增加（边缘效应10%增加）
        edge_factor = 1.0 + 0.1 * dist

        # 分辨率导致的不确定性
        variance = (
            self.sensor_noise_floor
            * resolution_factor
            * edge_factor
        )

        std_dev = np.sqrt(variance)
        confidence = np.exp(-variance * 10.0)  # 指数衰减置信度
        relative_error = std_dev / (ground_resolution + 1e-10)

        return UncertaintyGrid(
            variance=variance,
            std_dev=std_dev,
            confidence=confidence,
            relative_error=relative_error,
            geo_transform=geo_transform,
            indicator_name="resolution",
            metadata={
                "ground_resolution_m": ground_resolution,
                "base_gsd_m": base_gsd,
                "resolution_factor": resolution_factor,
            },
        )

    # -------------------------------------------------------------------
    # 模型置信度不确定性
    # -------------------------------------------------------------------

    def compute_model_uncertainty(
        self,
        predictions: np.ndarray,
        prediction_range: Optional[tuple] = None,
        model_type: str = "empirical",
    ) -> UncertaintyGrid:
        """基于模型类型和预测值范围计算模型不确定性

        Args:
            predictions: 反演结果数组
            prediction_range: (min, max) 预期范围，用于归一化
            model_type: 模型类型 (empirical/semi_empirical/physical)

        Returns:
            不确定性网格
        """
        # 模型类型基础不确定性
        model_uncertainty_base = {
            "empirical": 0.20,        # 经验模型：~20%相对误差
            "semi_empirical": 0.15,   # 半经验模型：~15%
            "physical": 0.10,         # 物理模型：~10%
            "machine_learning": 0.12, # ML模型：~12%
        }
        base_unc = model_uncertainty_base.get(model_type, 0.20)

        # 基于预测值的不确定性调制
        valid = ~np.isnan(predictions) & ~np.isinf(predictions)

        if prediction_range is None and valid.any():
            pred_min = float(np.nanmin(predictions[valid]))
            pred_max = float(np.nanmax(predictions[valid]))
            if pred_max - pred_min < 1e-10:
                pred_max = pred_min + 1.0
            prediction_range = (pred_min, pred_max)

        # 归一化预测值
        norm_pred = np.zeros_like(predictions)
        if prediction_range and prediction_range[1] > prediction_range[0]:
            norm_pred[valid] = (
                (predictions[valid] - prediction_range[0])
                / (prediction_range[1] - prediction_range[0])
            )

        # 极高值和极低值通常具有更高的不确定性
        value_uncertainty_factor = 1.0 + 0.3 * np.abs(norm_pred - 0.5) * 2.0

        # 综合方差
        variance = (base_unc + self.sensor_noise_floor) * value_uncertainty_factor

        std_dev = np.sqrt(variance)
        confidence = 1.0 - base_unc * 2.0  # 简化的置信度
        relative_error = np.full_like(predictions, base_unc)

        return UncertaintyGrid(
            variance=variance,
            std_dev=std_dev,
            confidence=np.full_like(predictions, np.clip(confidence, 0.0, 1.0)),
            relative_error=relative_error,
            indicator_name=f"model_{model_type}",
            metadata={
                "model_type": model_type,
                "base_uncertainty": base_unc,
                "prediction_range": prediction_range,
            },
        )

    # -------------------------------------------------------------------
    # 指标特定不确定性
    # -------------------------------------------------------------------

    def compute_indicator_uncertainty(
        self,
        values: np.ndarray,
        indicator_name: str,
        ground_resolution: float = 0.1,
        model_type: str = "empirical",
    ) -> UncertaintyGrid:
        """为特定反演指标生成综合不确定性网格

        融合：
        1. 分辨率导致的空间不确定性
        2. 模型类型导致的系统不确定性
        3. 指标特定算法不确定性

        Args:
            values: 反演结果数组
            indicator_name: 指标名称
            ground_resolution: 地面分辨率
            model_type: 该指标使用的模型类型

        Returns:
            综合不确定性网格
        """
        shape = values.shape[:2]

        # 1. 分辨率不确定性和模型不确定性的融合
        res_unc = self.compute_resolution_uncertainty(shape, ground_resolution)
        model_unc = self.compute_model_uncertainty(values, model_type=model_type)

        # 指标特定权重
        indicator_weights = {
            # 水质指标
            "chl_a": 1.2,       # 叶绿素反演较成熟，权重略低
            "tsm": 1.0,
            "turbidity": 1.0,
            "sdd": 1.3,         # 透明度受大气影响大
            "cod": 1.5,         # COD反演不确定性较高
            # 林业指标
            "volume": 1.3,
            "biomass": 1.4,     # 生物量反演挑战大
            "fvc": 0.8,         # FVC反演较成熟
            "species": 1.6,     # 树种分类需要高分辨率
            "veg_health": 1.0,
            # 环境指标
            "soil_moisture": 1.2,
            "heavy_metal": 1.5,  # 重金属胁迫不确定性高
            "lst": 0.9,         # LST反演较成熟
            "runoff": 1.3,
        }

        weight = indicator_weights.get(indicator_name, 1.0)

        # 融合：加权几何平均
        variance = (
            weight
            * np.sqrt(res_unc.variance * model_unc.variance + 1e-10)
        )

        # 影像边缘效应（边缘像素通常质量较差）
        rows, cols = shape
        if rows > 5 and cols > 5:
            # 边缘5%区域的额外不确定性
            edge_band = int(min(rows, cols) * 0.05)
            variance[:edge_band, :] *= 1.2
            variance[-edge_band:, :] *= 1.2
            variance[:, :edge_band] *= 1.2
            variance[:, -edge_band:] *= 1.2

        std_dev = np.sqrt(variance)
        confidence = np.clip(1.0 - std_dev * 3.0, 0.0, 1.0)
        relative_error = std_dev / (np.abs(values) + 1e-10)

        return UncertaintyGrid(
            variance=variance,
            std_dev=std_dev,
            confidence=confidence,
            relative_error=relative_error,
            geo_transform=None,
            indicator_name=indicator_name,
            metadata={
                "indicator": indicator_name,
                "model_type": model_type,
                "ground_resolution": ground_resolution,
                "indicator_weight": weight,
                "sensor_noise_floor": self.sensor_noise_floor,
            },
        )

    # -------------------------------------------------------------------
    # 综合不确定性（多指标融合）
    # -------------------------------------------------------------------

    def compute_composite_uncertainty(
        self,
        indicator_grids: List[UncertaintyGrid],
        weights: Optional[List[float]] = None,
    ) -> np.ndarray:
        """多指标综合不确定性网格

        融合多个指标的不确定性，生成用于采样推荐的统一不确定性分布。

        Args:
            indicator_grids: 各指标的不确定性网格列表
            weights: 各指标的融合权重

        Returns:
            综合方差网格（可直接作为SamplingRecommender输入）
        """
        if not indicator_grids:
            return np.array([[]])

        if weights is None:
            weights = [1.0] * len(indicator_grids)

        # 确保形状一致
        base_shape = indicator_grids[0].variance.shape
        composite = np.zeros(base_shape)

        total_weight = sum(weights)
        for grid, w in zip(indicator_grids, weights):
            # 重采样到统一形状
            if grid.variance.shape != base_shape:
                var_resized = self._resize_array(grid.variance, base_shape)
            else:
                var_resized = grid.variance

            composite += (w / total_weight) * var_resized

        return composite

    @staticmethod
    def _resize_array(arr: np.ndarray, target_shape: tuple) -> np.ndarray:
        """简单的数组重采样（最近邻）"""
        if arr.shape == target_shape:
            return arr.copy()

        h_ratio = target_shape[0] / arr.shape[0]
        w_ratio = target_shape[1] / arr.shape[1]

        row_idx = np.clip(
            (np.arange(target_shape[0]) / h_ratio).astype(int), 0, arr.shape[0] - 1
        )
        col_idx = np.clip(
            (np.arange(target_shape[1]) / w_ratio).astype(int), 0, arr.shape[1] - 1
        )

        return arr[row_idx[:, None], col_idx]

    # -------------------------------------------------------------------
    # 便捷方法：一键生成所有指标的不确定性
    # -------------------------------------------------------------------

    def generate_all_uncertainties(
        self,
        inversion_results: Dict[str, np.ndarray],
        ground_resolution: float = 0.1,
        model_types: Optional[Dict[str, str]] = None,
        geo_transform: Optional[tuple] = None,
    ) -> Dict[str, UncertaintyGrid]:
        """为所有反演结果生成不确定性网格

        Args:
            inversion_results: {指标名: 反演值数组}
            ground_resolution: 地面分辨率
            model_types: {指标名: 模型类型}
            geo_transform: 地理变换参数

        Returns:
            {指标名: 不确定性网格}
        """
        if model_types is None:
            model_types = {}

        uncertainties = {}
        for name, values in inversion_results.items():
            if values is None or values.size == 0:
                continue

            model_type = model_types.get(name, "empirical")
            grid = self.compute_indicator_uncertainty(
                values, name, ground_resolution, model_type
            )
            grid.geo_transform = geo_transform
            uncertainties[name] = grid

        return uncertainties
