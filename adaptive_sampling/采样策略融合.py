"""
采样策略融合模块
================
将遥感反演网格点作为 SamplingRecommender 的输入，
基于物理指标的异常值自动提升该区域的采样优先级。

核心功能：
1. 反演异常值检测与加权
2. 多指标融合优先级映射
3. 与现有 SamplingRecommender / ImprovedSamplingRecommender 的无缝对接
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

from adaptive_sampling.采样点推荐生成 import SamplingRecommender
from remote_sensing.uncertainty_mapping import UncertaintyMapper, UncertaintyGrid
from photogrammetry.geo_alignment import GeoAlignmentEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 融合结果
# ---------------------------------------------------------------------------

@dataclass
class FusionResult:
    """采样融合结果"""
    # 综合方差网格（可直接作为SamplingRecommender输入）
    composite_variance: np.ndarray
    # 坐标网格
    x_coords: np.ndarray
    y_coords: np.ndarray
    # 地理信息
    geo_transform: Optional[Tuple[float, ...]] = None
    projection: str = "EPSG:4326"
    # 各指标贡献
    indicator_contributions: Dict[str, np.ndarray] = field(default_factory=dict)
    # 异常区域掩膜
    anomaly_mask: Optional[np.ndarray] = None
    anomaly_regions: List[Dict] = field(default_factory=list)
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 采样融合引擎
# ---------------------------------------------------------------------------

class SamplingFusionEngine:
    """采样策略融合引擎

    将反演结果与不确定性映射合成为采样推荐的统一输入。
    """

    def __init__(self):
        self.recommender = SamplingRecommender()
        self.uncertainty_mapper = UncertaintyMapper()
        self.geo_engine = GeoAlignmentEngine()

    def fuse_inversion_to_variance(
        self,
        inversion_values: Dict[str, np.ndarray],
        inversion_uncertainties: Dict[str, UncertaintyGrid],
        geo_transform: Tuple[float, ...],
        indicator_priorities: Optional[Dict[str, float]] = None,
        anomaly_threshold_percentile: float = 90.0,
    ) -> FusionResult:
        """将反演结果和不确定性融合为综合方差网格

        Args:
            inversion_values: {指标名: 反演值数组}
            inversion_uncertainties: {指标名: 不确定性网格}
            geo_transform: 栅格地理变换参数
            indicator_priorities: {指标名: 融合权重}，未指定使用默认值
            anomaly_threshold_percentile: 异常检测百分位阈值

        Returns:
            融合结果，包含composite_variance可直接用于SamplingRecommender
        """
        if not inversion_values:
            return FusionResult(
                composite_variance=np.array([[]]),
                x_coords=np.array([]),
                y_coords=np.array([]),
            )

        # 默认指标优先级权重
        default_priorities = {
            # 水质指标
            "chl_a": 0.8,
            "tsm": 0.7,
            "turbidity": 0.6,
            "sdd": 0.5,
            "cod": 0.9,
            # 林业指标
            "volume": 0.7,
            "biomass": 0.8,
            "fvc": 0.5,
            "veg_health": 0.6,
            "species": 0.4,
            # 环境指标
            "soil_moisture": 0.6,
            "heavy_metal": 0.9,
            "lst": 0.5,
            "runoff": 0.7,
        }

        if indicator_priorities is None:
            indicator_priorities = {}

        # 确定基础形状
        base_shape = None
        for val in inversion_values.values():
            if val is not None and val.size > 0:
                base_shape = val.shape[:2]
                break

        if base_shape is None:
            return FusionResult(
                composite_variance=np.array([[]]),
                x_coords=np.array([]),
                y_coords=np.array([]),
            )

        rows, cols = base_shape
        composite = np.zeros((rows, cols), dtype=np.float64)
        contributions = {}
        anomaly_mask = np.zeros((rows, cols), dtype=bool)

        total_weight = 0.0

        for name, values in inversion_values.items():
            if values is None or values.size == 0:
                continue

            # 对齐到基础形状
            if values.shape[:2] != base_shape:
                values = self._resize_to_shape(values, base_shape)

            weight = indicator_priorities.get(name, default_priorities.get(name, 0.5))

            # 1. 不确定性贡献
            unc_grid = inversion_uncertainties.get(name)
            if unc_grid is not None:
                unc_variance = self._resize_to_shape(unc_grid.variance, base_shape)
                composite += weight * unc_variance
                total_weight += weight

            # 2. 异常值检测与加权
            anomaly_contribution = self._detect_anomaly_contribution(
                values, name, anomaly_threshold_percentile
            )
            composite += weight * 0.3 * anomaly_contribution

            contributions[name] = self._resize_to_shape(values, base_shape)

            # 异常掩膜合并
            is_anomaly = anomaly_contribution > np.percentile(
                anomaly_contribution[~np.isnan(anomaly_contribution)],
                anomaly_threshold_percentile,
            ) if anomaly_contribution.size > 0 else np.zeros_like(anomaly_mask)
            anomaly_mask |= is_anomaly

        # 归一化
        if total_weight > 0:
            composite /= total_weight

        # 生成坐标网格
        x_coords, y_coords = self._generate_coords(geo_transform, rows, cols)

        # 识别异常区域
        anomaly_regions = self._identify_anomaly_regions(anomaly_mask, x_coords, y_coords)

        return FusionResult(
            composite_variance=composite,
            x_coords=x_coords,
            y_coords=y_coords,
            geo_transform=geo_transform,
            indicator_contributions=contributions,
            anomaly_mask=anomaly_mask,
            anomaly_regions=anomaly_regions,
            metadata={
                "n_indicators": len([v for v in inversion_values.values() if v is not None]),
                "anomaly_threshold": anomaly_threshold_percentile,
                "total_weight": total_weight,
            },
        )

    def generate_sampling_recommendations(
        self,
        fusion_result: FusionResult,
        existing_points: Optional[np.ndarray] = None,
        n_recommendations: int = 20,
        strategy: str = "hybrid",
    ) -> Dict[str, Any]:
        """基于融合结果生成采样建议

        Args:
            fusion_result: 融合结果
            existing_points: 已有采样点 (N, 2)
            n_recommendations: 建议点数量
            strategy: 采样策略

        Returns:
            采样建议字典（与现有SamplingRecommendationsResponse兼容）
        """
        if fusion_result.composite_variance.size == 0:
            return {
                "strategy": strategy,
                "n_recommendations": 0,
                "recommendations": [],
                "statistics": {},
            }

        # 直接调用现有SamplingRecommender
        recommendations = self.recommender.generate_recommendations(
            variance=fusion_result.composite_variance,
            x_coords=fusion_result.x_coords,
            y_coords=fusion_result.y_coords,
            existing_points=existing_points,
            n_recommendations=n_recommendations,
            strategy=strategy,
        )

        # 增强：为异常区域的推荐点提升优先级
        if fusion_result.anomaly_mask is not None and fusion_result.anomaly_mask.any():
            recommendations = self._boost_anomaly_priorities(
                recommendations, fusion_result
            )

        # 计算统计信息
        variance = fusion_result.composite_variance
        valid_var = variance[~np.isnan(variance) & ~np.isinf(variance)]

        statistics = {
            "total_variance": float(np.sum(valid_var)) if valid_var.size > 0 else 0.0,
            "mean_variance": float(np.mean(valid_var)) if valid_var.size > 0 else 0.0,
            "max_variance": float(np.max(valid_var)) if valid_var.size > 0 else 0.0,
            "anomaly_regions": len(fusion_result.anomaly_regions),
            "n_indicators": fusion_result.metadata.get("n_indicators", 0),
            "existing_points": len(existing_points) if existing_points is not None else 0,
        }

        recommendations["statistics"] = statistics
        return recommendations

    def _detect_anomaly_contribution(
        self,
        values: np.ndarray,
        indicator_name: str,
        percentile: float,
    ) -> np.ndarray:
        """检测异常值并生成异常贡献权重

        异常值区域将获得更高的采样优先级。
        """
        valid = values[~np.isnan(values) & ~np.isinf(values)]
        if valid.size < 10:
            return np.zeros_like(values)

        # 计算异常阈值
        low_thresh = float(np.percentile(valid, 100 - percentile))
        high_thresh = float(np.percentile(valid, percentile))

        # 异常强度：偏离阈值越远权重越高
        anomaly_strength = np.zeros_like(values)

        # 高异常
        high_mask = values > high_thresh
        if high_mask.any():
            anomaly_strength[high_mask] = (
                (values[high_mask] - high_thresh)
                / (high_thresh + 1e-10)
            )

        # 低异常
        low_mask = values < low_thresh
        if low_mask.any():
            anomaly_strength[low_mask] = (
                (low_thresh - values[low_mask])
                / (low_thresh + 1e-10)
            )

        # 归一化（截断到合理范围）
        anomaly_strength = np.clip(anomaly_strength, 0.0, 5.0)

        # 水质特有：叶绿素/COD超标区域权重加倍
        if indicator_name in ("chl_a", "cod", "heavy_metal"):
            anomaly_strength *= 1.5

        return anomaly_strength

    def _identify_anomaly_regions(
        self,
        anomaly_mask: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
    ) -> List[Dict]:
        """识别异常连通区域"""
        if not anomaly_mask.any():
            return []

        # 简单的连通区域标记（4邻域）
        from scipy import ndimage
        try:
            labeled, n_features = ndimage.label(anomaly_mask)
        except Exception:
            # 无scipy时使用简化方法
            return self._simple_anomaly_regions(anomaly_mask, x_coords, y_coords)

        regions = []
        for i in range(1, n_features + 1):
            region_mask = labeled == i
            area = np.sum(region_mask)

            if area < 3:  # 忽略过小区域
                continue

            rows_idx, cols_idx = np.where(region_mask)
            center_x = float(np.mean(x_coords[cols_idx]))
            center_y = float(np.mean(y_coords[rows_idx]))

            # 边界框
            min_x = float(np.min(x_coords[cols_idx]))
            max_x = float(np.max(x_coords[cols_idx]))
            min_y = float(np.min(y_coords[rows_idx]))
            max_y = float(np.max(y_coords[rows_idx]))

            regions.append({
                "region_id": i,
                "area_pixels": int(area),
                "center": {"x": center_x, "y": center_y},
                "bbox": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
                "priority": "high" if area > 50 else "medium",
            })

        return regions

    def _simple_anomaly_regions(
        self,
        anomaly_mask: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
    ) -> List[Dict]:
        """无scipy时的简化异常区域识别"""
        rows_idx, cols_idx = np.where(anomaly_mask)
        if len(rows_idx) == 0:
            return []

        center_x = float(np.mean(x_coords[cols_idx]))
        center_y = float(np.mean(y_coords[rows_idx]))
        return [{
            "region_id": 1,
            "area_pixels": int(np.sum(anomaly_mask)),
            "center": {"x": center_x, "y": center_y},
            "bbox": {
                "min_x": float(np.min(x_coords[cols_idx])),
                "min_y": float(np.min(y_coords[rows_idx])),
                "max_x": float(np.max(x_coords[cols_idx])),
                "max_y": float(np.max(y_coords[rows_idx])),
            },
            "priority": "high",
        }]

    def _boost_anomaly_priorities(
        self,
        recommendations: Dict[str, Any],
        fusion_result: FusionResult,
    ) -> Dict[str, Any]:
        """提升位于异常区域的推荐点优先级"""
        if fusion_result.anomaly_mask is None:
            return recommendations

        for rec in recommendations.get("recommendations", []):
            # 查找该推荐点在栅格中的位置
            x, y = rec.get("x", 0), rec.get("y", 0)

            col_idx = np.argmin(np.abs(fusion_result.x_coords - x))
            row_idx = np.argmin(np.abs(fusion_result.y_coords - y))

            if (
                0 <= row_idx < fusion_result.anomaly_mask.shape[0]
                and 0 <= col_idx < fusion_result.anomaly_mask.shape[1]
                and fusion_result.anomaly_mask[row_idx, col_idx]
            ):
                # 提升优先级
                if rec.get("priority") != "high":
                    rec["priority"] = "high"
                    rec["sampling_reason"] = (
                        rec.get("sampling_reason", "")
                        + " [该点位于反演异常区域，已自动提升优先级]"
                    )

        return recommendations

    @staticmethod
    def _generate_coords(
        geo_transform: Tuple[float, ...],
        rows: int,
        cols: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """从地理变换生成坐标数组"""
        x_coords = np.array([
            geo_transform[0] + geo_transform[1] * c for c in range(cols)
        ])
        y_coords = np.array([
            geo_transform[3] + geo_transform[5] * r for r in range(rows)
        ])
        return x_coords, y_coords

    @staticmethod
    def _resize_to_shape(arr: np.ndarray, target_shape: tuple) -> np.ndarray:
        """重采样到目标形状（最近邻）"""
        if arr.shape[:2] == target_shape:
            return arr.copy()

        h_ratio = target_shape[0] / arr.shape[0]
        w_ratio = target_shape[1] / arr.shape[1]

        row_idx = np.clip(
            (np.arange(target_shape[0]) / h_ratio).astype(int),
            0, arr.shape[0] - 1,
        )
        col_idx = np.clip(
            (np.arange(target_shape[1]) / w_ratio).astype(int),
            0, arr.shape[1] - 1,
        )

        if len(arr.shape) == 2:
            return arr[row_idx[:, None], col_idx]
        else:
            return arr[row_idx[:, None], col_idx, :]
