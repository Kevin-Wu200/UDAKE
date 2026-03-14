"""
实时采样预览
实时预览添加新采样点后的效果
"""
from pykrige.ok import OrdinaryKriging
import numpy as np
from typing import Dict, Any, Optional, Tuple
import logging
from scipy.ndimage import gaussian_filter
from scipy.spatial.distance import cdist

from .采样点影响评估器 import SamplingPointImpactEvaluator

logger = logging.getLogger(__name__)


class RealTimeSamplingPreview:
    """实时采样预览器"""

    def __init__(
        self,
        impact_evaluator: SamplingPointImpactEvaluator = None,
        variogram_model: str = "spherical",
        nlags: int = 6
    ):
        """
        初始化预览器

        参数:
        - impact_evaluator: 影响评估器实例
        - variogram_model: 变异函数模型
        - nlags: 滞后数
        """
        self.impact_evaluator = impact_evaluator or SamplingPointImpactEvaluator(
            variogram_model=variogram_model,
            nlags=nlags
        )
        self.variogram_model = variogram_model
        self.nlags = nlags

    def preview_sampling_effect(
        self,
        existing_points: np.ndarray,  # shape: (n, 2) - [x, y]
        existing_values: np.ndarray,  # shape: (n,)
        new_point: np.ndarray,  # shape: (2,) - [x, y]
        new_value: float,
        grid_resolution: int = 50,
        variance_grid: np.ndarray = None,
        x_coords: np.ndarray = None,
        y_coords: np.ndarray = None
    ) -> Dict[str, Any]:
        """
        预览添加新采样点后的效果

        参数:
        - existing_points: 现有采样点坐标
        - existing_values: 现有采样点值
        - new_point: 新采样点坐标
        - new_value: 新采样点值
        - grid_resolution: 预览网格分辨率
        - variance_grid: 当前方差栅格（可选）
        - x_coords: X坐标数组（可选）
        - y_coords: Y坐标数组（可选）

        返回:
        - 预览结果
          * variance_reduction_map: 方差减少热力图
          * total_variance_reduction: 总方差减少量
          * influence_radius: 影响半径
          * improved_regions: 改善区域列表
          * quantitative_metrics: 量化指标
        """
        logger.info(f"预览添加新采样点: ({new_point[0]:.2f}, {new_point[1]:.2f})")

        # 计算当前基线
        baseline_results = self._calculate_baseline(
            existing_points, existing_values,
            grid_resolution, x_coords, y_coords
        )

        # 计算添加新点后的效果
        new_results = self._calculate_with_new_point(
            existing_points, existing_values,
            new_point, new_value,
            grid_resolution, x_coords, y_coords
        )

        # 计算方差减少
        variance_reduction = baseline_results['variance'] - new_results['variance']
        variance_reduction_ratio = variance_reduction / baseline_results['variance'] if baseline_results['variance'] > 0 else 0

        # 计算影响半径
        influence_radius = self._calculate_influence_radius(
            existing_points, new_point, variance_reduction,
            baseline_results['grid_x'], baseline_results['grid_y']
        )

        # 生成方差减少热力图
        variance_reduction_map = self._generate_variance_reduction_map(
            variance_reduction,
            baseline_results['grid_x'],
            baseline_results['grid_y'],
            influence_radius
        )

        # 识别改善区域
        improved_regions = self._identify_improved_regions(
            variance_reduction,
            baseline_results['grid_x'],
            baseline_results['grid_y'],
            influence_radius
        )

        # 计算量化指标
        quantitative_metrics = self._calculate_quantitative_metrics(
            baseline_results, new_results, variance_reduction, influence_radius
        )

        return {
            'variance_reduction_map': variance_reduction_map,
            'total_variance_reduction': float(np.sum(variance_reduction)),
            'variance_reduction_ratio': float(variance_reduction_ratio),
            'influence_radius': float(influence_radius),
            'improved_regions': improved_regions,
            'quantitative_metrics': quantitative_metrics,
            'baseline_variance': float(baseline_results['mean_variance']),
            'new_variance': float(new_results['mean_variance']),
            'grid_resolution': grid_resolution,
            'grid_bounds': {
                'min_x': float(baseline_results['grid_x'].min()),
                'max_x': float(baseline_results['grid_x'].max()),
                'min_y': float(baseline_results['grid_y'].min()),
                'max_y': float(baseline_results['grid_y'].max())
            }
        }

    def _calculate_baseline(
        self,
        points: np.ndarray,
        values: np.ndarray,
        grid_resolution: int,
        x_coords: np.ndarray = None,
        y_coords: np.ndarray = None
    ) -> Dict[str, Any]:
        """
        计算基线结果
        """
        try:
            # 创建克里金模型
            ok = OrdinaryKriging(
                points[:, 0], points[:, 1], values,
                variogram_model=self.variogram_model,
                nlags=self.nlags,
                enable_plotting=False
            )

            # 生成评估网格
            if x_coords is None or y_coords is None:
                grid_x = np.linspace(points[:, 0].min(), points[:, 0].max(), grid_resolution)
                grid_y = np.linspace(points[:, 1].min(), points[:, 1].max(), grid_resolution)
            else:
                grid_x = x_coords
                grid_y = y_coords

            # 执行插值
            prediction, variance = ok.execute('grid', grid_x, grid_y)

            return {
                'prediction': prediction,
                'variance': variance,
                'mean_variance': float(np.mean(variance)),
                'max_variance': float(np.max(variance)),
                'min_variance': float(np.min(variance)),
                'grid_x': grid_x,
                'grid_y': grid_y
            }

        except Exception as e:
            logger.error(f"计算基线失败: {str(e)}")
            raise

    def _calculate_with_new_point(
        self,
        points: np.ndarray,
        values: np.ndarray,
        new_point: np.ndarray,
        new_value: float,
        grid_resolution: int,
        x_coords: np.ndarray = None,
        y_coords: np.ndarray = None
    ) -> Dict[str, Any]:
        """
        计算添加新点后的结果
        """
        try:
            # 合并数据
            combined_points = np.vstack([points, new_point])
            combined_values = np.append(values, new_value)

            # 创建克里金模型
            ok = OrdinaryKriging(
                combined_points[:, 0], combined_points[:, 1], combined_values,
                variogram_model=self.variogram_model,
                nlags=self.nlags,
                enable_plotting=False
            )

            # 生成评估网格
            if x_coords is None or y_coords is None:
                grid_x = np.linspace(combined_points[:, 0].min(), combined_points[:, 0].max(), grid_resolution)
                grid_y = np.linspace(combined_points[:, 1].min(), combined_points[:, 1].max(), grid_resolution)
            else:
                grid_x = x_coords
                grid_y = y_coords

            # 执行插值
            prediction, variance = ok.execute('grid', grid_x, grid_y)

            return {
                'prediction': prediction,
                'variance': variance,
                'mean_variance': float(np.mean(variance)),
                'max_variance': float(np.max(variance)),
                'min_variance': float(np.min(variance)),
                'grid_x': grid_x,
                'grid_y': grid_y
            }

        except Exception as e:
            logger.error(f"计算新点效果失败: {str(e)}")
            raise

    def _calculate_influence_radius(
        self,
        existing_points: np.ndarray,
        new_point: np.ndarray,
        variance_reduction: np.ndarray,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
        threshold: float = 0.1
    ) -> float:
        """
        计算影响半径

        参数:
        - existing_points: 现有采样点
        - new_point: 新采样点
        - variance_reduction: 方差减少栅格
        - grid_x: 网格X坐标
        - grid_y: 网格Y坐标
        - threshold: 影响阈值（相对于最大减少量的比例）

        返回:
        - 影响半径
        """
        if np.max(variance_reduction) == 0:
            return 0.0

        # 找到新点在栅格中的位置
        x_idx = np.argmin(np.abs(grid_x - new_point[0]))
        y_idx = np.argmin(np.abs(grid_y - new_point[1]))

        # 计算最大方差减少量
        max_reduction = np.max(variance_reduction)
        reduction_threshold = max_reduction * threshold

        # 从新点开始向外搜索，直到方差减少量低于阈值
        max_radius = min(len(grid_x), len(grid_y)) // 2

        for radius in range(1, max_radius + 1):
            # 检查半径范围内的最小方差减少量
            y_indices, x_indices = np.ogrid[-y_idx:y_idx+1, -x_idx:x_idx+1]
            mask = (x_indices**2 + y_indices**2) <= radius**2

            if np.any(mask):
                reductions_in_radius = variance_reduction[mask]
                if np.min(reductions_in_radius) < reduction_threshold:
                    return float(radius * (grid_x[1] - grid_x[0]))

        # 如果没有找到阈值，返回搜索半径
        return float(max_radius * (grid_x[1] - grid_x[0]))

    def _generate_variance_reduction_map(
        self,
        variance_reduction: np.ndarray,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
        influence_radius: float
    ) -> Dict[str, Any]:
        """
        生成方差减少热力图

        返回:
        - 热力图数据
          * data: 方差减少数据
          * normalized: 归一化数据 (0-1)
          * grid_x: X坐标
          * grid_y: Y坐标
        """
        # 归一化到 [0, 1]
        if np.max(variance_reduction) > 0:
            normalized = variance_reduction / np.max(variance_reduction)
        else:
            normalized = np.zeros_like(variance_reduction)

        # 应用高斯平滑，使热力图更平滑
        smoothed = gaussian_filter(normalized, sigma=1.0)

        return {
            'data': variance_reduction.tolist(),
            'normalized': smoothed.tolist(),
            'grid_x': grid_x.tolist(),
            'grid_y': grid_y.tolist(),
            'min': float(np.min(variance_reduction)),
            'max': float(np.max(variance_reduction)),
            'mean': float(np.mean(variance_reduction))
        }

    def _identify_improved_regions(
        self,
        variance_reduction: np.ndarray,
        grid_x: np.ndarray,
        grid_y: np.ndarray,
        influence_radius: float,
        threshold: float = 0.3
    ) -> list:
        """
        识别改善区域

        参数:
        - variance_reduction: 方差减少栅格
        - grid_x: 网格X坐标
        - grid_y: 网格Y坐标
        - influence_radius: 影响半径
        - threshold: 改善阈值（相对于最大减少量的比例）

        返回:
        - 改善区域列表
        """
        improved_regions = []

        if np.max(variance_reduction) == 0:
            return improved_regions

        # 计算阈值
        reduction_threshold = np.max(variance_reduction) * threshold

        # 二值化
        improved_mask = variance_reduction >= reduction_threshold

        # 如果没有改善区域，返回空列表
        if not np.any(improved_mask):
            return improved_regions

        # 查找连通区域
        from scipy.ndimage import label
        labeled_array, num_features = label(improved_mask)

        # 分析每个区域
        for region_id in range(1, num_features + 1):
            region_mask = labeled_array == region_id
            region_reductions = variance_reduction[region_mask]

            # 计算区域中心
            y_indices, x_indices = np.where(region_mask)
            center_x = float(grid_x[int(np.mean(x_indices))])
            center_y = float(grid_y[int(np.mean(y_indices))])

            # 计算区域面积
            grid_spacing_x = grid_x[1] - grid_x[0] if len(grid_x) > 1 else 1.0
            grid_spacing_y = grid_y[1] - grid_y[0] if len(grid_y) > 1 else 1.0
            area = float(np.sum(region_mask) * grid_spacing_x * grid_spacing_y)

            # 计算区域改善度
            mean_reduction = float(np.mean(region_reductions))
            max_reduction = float(np.max(region_reductions))

            improved_regions.append({
                'region_id': region_id,
                'center': {'x': center_x, 'y': center_y},
                'area': area,
                'mean_reduction': mean_reduction,
                'max_reduction': max_reduction,
                'relative_improvement': float(mean_reduction / np.max(variance_reduction)) if np.max(variance_reduction) > 0 else 0.0
            })

        # 按平均改善度排序
        improved_regions.sort(key=lambda r: r['mean_reduction'], reverse=True)

        return improved_regions

    def _calculate_quantitative_metrics(
        self,
        baseline: Dict[str, Any],
        new: Dict[str, Any],
        variance_reduction: np.ndarray,
        influence_radius: float
    ) -> Dict[str, float]:
        """
        计算量化指标

        返回:
        - 量化指标
          * rmse_improvement: RMSE改善百分比
          * variance_reduction_percent: 方差减少百分比
          * coverage_area: 覆盖面积
          * average_improvement: 平均改善度
        """
        # 方差减少百分比
        variance_reduction_percent = (
            (baseline['mean_variance'] - new['mean_variance']) /
            baseline['mean_variance'] * 100
        ) if baseline['mean_variance'] > 0 else 0.0

        # 最大方差减少百分比
        max_variance_reduction_percent = (
            (baseline['max_variance'] - new['max_variance']) /
            baseline['max_variance'] * 100
        ) if baseline['max_variance'] > 0 else 0.0

        # 估算RMSE改善（简化估计）
        # RMSE与方差成平方根关系
        baseline_rmse = np.sqrt(baseline['mean_variance'])
        new_rmse = np.sqrt(new['mean_variance'])
        rmse_improvement = (
            (baseline_rmse - new_rmse) / baseline_rmse * 100
        ) if baseline_rmse > 0 else 0.0

        # 计算覆盖面积（影响半径内的面积）
        coverage_area = np.pi * influence_radius ** 2

        # 计算平均改善度（影响半径内的方差减少）
        if np.max(variance_reduction) > 0:
            average_improvement = float(np.mean(variance_reduction) / np.max(variance_reduction) * 100)
        else:
            average_improvement = 0.0

        return {
            'rmse_improvement': float(rmse_improvement),
            'variance_reduction_percent': float(variance_reduction_percent),
            'max_variance_reduction_percent': float(max_variance_reduction_percent),
            'coverage_area': float(coverage_area),
            'average_improvement': average_improvement
        }

    def preview_multiple_points(
        self,
        existing_points: np.ndarray,
        existing_values: np.ndarray,
        new_points: np.ndarray,  # shape: (m, 2)
        new_values: np.ndarray,  # shape: (m,)
        grid_resolution: int = 50
    ) -> Dict[str, Any]:
        """
        预览添加多个新采样点后的效果

        参数:
        - existing_points: 现有采样点坐标
        - existing_values: 现有采样点值
        - new_points: 新采样点坐标数组
        - new_values: 新采样点值数组
        - grid_resolution: 预览网格分辨率

        返回:
        - 预览结果
        """
        logger.info(f"预览添加 {len(new_points)} 个新采样点")

        # 计算基线
        baseline = self._calculate_baseline(
            existing_points, existing_values, grid_resolution
        )

        # 计算添加新点后的效果
        combined_points = np.vstack([existing_points, new_points])
        combined_values = np.append(existing_values, new_values)
        new_results = self._calculate_with_new_point(
            existing_points, existing_values,
            new_points[0], new_values[0],  # 使用第一个点作为参考
            grid_resolution
        )

        # 重新计算所有新点
        ok = OrdinaryKriging(
            combined_points[:, 0], combined_points[:, 1], combined_values,
            variogram_model=self.variogram_model,
            nlags=self.nlags,
            enable_plotting=False
        )

        grid_x = baseline['grid_x']
        grid_y = baseline['grid_y']
        prediction, variance = ok.execute('grid', grid_x, grid_y)

        # 计算总体方差减少
        variance_reduction = baseline['variance'] - variance
        total_variance_reduction = np.sum(variance_reduction)
        variance_reduction_ratio = total_variance_reduction / np.sum(baseline['variance']) if np.sum(baseline['variance']) > 0 else 0

        return {
            'variance_reduction_map': {
                'data': variance_reduction.tolist(),
                'normalized': (variance_reduction / np.max(variance_reduction) if np.max(variance_reduction) > 0 else np.zeros_like(variance_reduction)).tolist(),
                'grid_x': grid_x.tolist(),
                'grid_y': grid_y.tolist()
            },
            'total_variance_reduction': float(total_variance_reduction),
            'variance_reduction_ratio': float(variance_reduction_ratio),
            'baseline_mean_variance': float(baseline['mean_variance']),
            'new_mean_variance': float(np.mean(variance)),
            'number_of_points': len(new_points)
        }