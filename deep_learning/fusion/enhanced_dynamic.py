"""
增强动态融合策略
Enhanced Dynamic Fusion

提供：
- 空间异质性感知的动态权重融合
- 多层级不确定性加权融合
- 局部精度自适应的模型选择与权重分配
- 时空联合不确定性传播
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SpatialHeterogeneityFusion:
    """
    空间异质性感知的动态融合

    核心思想：不同空间位置的数据特征可能差异很大，
    不同模型在不同区域的表现也不一致。
    此策略根据局部预测精度的空间分布，动态调整各模型的权重。
    """

    def __init__(
        self,
        spatial_bandwidth: float = 1.0,
        min_points_per_region: int = 5,
        smooth_weights: bool = True,
    ):
        """
        初始化空间异质性融合

        Args:
            spatial_bandwidth: 空间带宽（用于局部精度估计）
            min_points_per_region: 每个区域最小点数
            smooth_weights: 是否平滑权重
        """
        self.spatial_bandwidth = spatial_bandwidth
        self.min_points_per_region = min_points_per_region
        self.smooth_weights = smooth_weights

    def compute_local_weights(
        self,
        model_predictions: Dict[str, np.ndarray],
        true_values: np.ndarray,
        locations: np.ndarray,  # [n × 2] 空间坐标
    ) -> Dict[str, np.ndarray]:
        """
        计算空间局部权重

        Args:
            model_predictions: {model_id: predictions [n]}
            true_values: 真实值 [n]
            locations: 空间坐标 [n × 2]

        Returns:
            Dict[str, np.ndarray]: {model_id: weights [n]}
        """
        n_points = len(locations)
        model_ids = list(model_predictions.keys())
        n_models = len(model_ids)

        if n_models == 0:
            return {}

        # 构建距离矩阵
        dm = np.zeros((n_points, n_points), dtype=np.float64)
        for i in range(n_points):
            diff = locations - locations[i]
            dm[i] = np.sqrt(np.sum(diff ** 2, axis=1))

        # 对每个点计算局部精度权重
        weights = {mid: np.zeros(n_points, dtype=np.float64) for mid in model_ids}

        for i in range(n_points):
            # 空间加权邻域
            dist_w = np.exp(-dm[i] ** 2 / (2 * self.spatial_bandwidth ** 2))
            mask = dist_w > 0.01  # 忽略远距离点

            if np.sum(mask) < self.min_points_per_region:
                # 回退到均匀权重
                for mid in model_ids:
                    weights[mid][i] = 1.0 / n_models
                continue

            # 每模型局部误差
            local_errors = {}
            for mid in model_ids:
                preds = model_predictions[mid]
                errors = (preds - true_values) ** 2
                local_rmse = float(np.sqrt(np.average(errors[mask], weights=dist_w[mask])))
                local_errors[mid] = max(local_rmse, 1e-8)

            # 转化误差为权重
            total_inv = sum(1.0 / e for e in local_errors.values())
            for mid in model_ids:
                weights[mid][i] = (1.0 / local_errors[mid]) / total_inv

        # 可选平滑
        if self.smooth_weights:
            for mid in model_ids:
                weights[mid] = self._spatial_smooth(weights[mid], dm)

        return weights

    def _spatial_smooth(self, values: np.ndarray, distance_matrix: np.ndarray) -> np.ndarray:
        """空间平滑"""
        n = len(values)
        smoothed = np.zeros(n, dtype=np.float64)
        bw_sq = self.spatial_bandwidth ** 2

        for i in range(n):
            w = np.exp(-distance_matrix[i] ** 2 / (2 * bw_sq))
            smoothed[i] = float(np.average(values, weights=w))

        return smoothed


class MultiLevelUncertaintyFusion:
    """
    多层级不确定性加权融合

    融合三个层级的不确定性：
    1. 模型级不确定性（历史精度指标）
    2. 点级不确定性（每个预测点的方差）
    3. 空间级不确定性（局部区域的数据密度/变异性）
    """

    def __init__(
        self,
        model_weight: float = 0.3,
        point_weight: float = 0.4,
        spatial_weight: float = 0.3,
    ):
        self.model_weight = model_weight
        self.point_weight = point_weight
        self.spatial_weight = spatial_weight

    def fuse(
        self,
        model_predictions: Dict[str, np.ndarray],
        model_variances: Dict[str, np.ndarray],
        model_metrics: Dict[str, Dict[str, float]],
        locations: np.ndarray,
    ) -> Dict[str, Any]:
        """
        多层级不确定性融合

        Args:
            model_predictions: {model_id: predictions [n]}
            model_variances: {model_id: variances [n]}
            model_metrics: {model_id: {rmse, mae, r2, ...}}
            locations: 空间坐标 [n × 2]

        Returns:
            Dict: {
                'fused_predictions': np.ndarray,
                'fused_variances': np.ndarray,
                'weights_per_point': Dict,
                'uncertainty_breakdown': Dict,
            }
        """
        model_ids = list(model_predictions.keys())
        n_models = len(model_ids)
        n_points = len(next(iter(model_predictions.values())))

        # 1. 模型级权重（基于历史精度）
        model_level_w = np.zeros(n_models, dtype=np.float64)
        for idx, mid in enumerate(model_ids):
            if mid in model_metrics:
                rmse = model_metrics[mid].get('rmse', 1.0)
                model_level_w[idx] = 1.0 / max(rmse ** 2, 1e-8)
            else:
                model_level_w[idx] = 1.0 / n_models
        model_level_w = model_level_w / np.sum(model_level_w)

        # 2. 点级权重（基于每点方差）
        point_level_weights = np.zeros((n_models, n_points), dtype=np.float64)
        for idx, mid in enumerate(model_ids):
            if mid in model_variances:
                vars_arr = np.array(model_variances[mid], dtype=np.float64)
                point_level_weights[idx, :] = 1.0 / np.maximum(vars_arr, 1e-8)
            else:
                point_level_weights[idx, :] = 1.0

        # 归一化每点权重
        col_sums = np.sum(point_level_weights, axis=0)
        col_sums = np.maximum(col_sums, 1e-8)
        point_level_weights = point_level_weights / col_sums[np.newaxis, :]

        # 3. 空间级权重（基于局部密度/变异性）
        spatial_level_w = self._compute_spatial_weights(locations, n_points, n_models)

        # 融合三级权重
        combined_weights = np.zeros((n_models, n_points), dtype=np.float64)
        for i in range(n_points):
            for idx in range(n_models):
                combined_weights[idx, i] = (
                    self.model_weight * model_level_w[idx] +
                    self.point_weight * point_level_weights[idx, i] +
                    self.spatial_weight * spatial_level_w[idx, i]
                )
            # 重新归一化
            row_sum = np.sum(combined_weights[:, i])
            if row_sum > 0:
                combined_weights[:, i] /= row_sum

        # 融合预测
        predictions_matrix = np.array([model_predictions[mid] for mid in model_ids], dtype=np.float64)
        fused_pred = np.sum(combined_weights * predictions_matrix, axis=0)

        # 融合方差
        fused_var = np.zeros(n_points, dtype=np.float64)
        for i in range(n_points):
            # 加权方差 + 模型间分歧
            weighted_var = 0.0
            disagreement = 0.0
            for idx in range(n_models):
                weighted_var += combined_weights[idx, i] * (model_variances.get(model_ids[idx], np.zeros(n_points))[i])
                disagreement += combined_weights[idx, i] * (predictions_matrix[idx, i] - fused_pred[i]) ** 2
            fused_var[i] = weighted_var + disagreement

        return {
            'fused_predictions': fused_pred,
            'fused_variances': fused_var,
            'weights_per_point': {mid: combined_weights[idx, :].tolist() for idx, mid in enumerate(model_ids)},
            'uncertainty_breakdown': {
                'model_level': model_level_w.tolist(),
                'point_level_avg': np.mean(point_level_weights, axis=1).tolist(),
                'spatial_level_avg': np.mean(spatial_level_w, axis=1).tolist(),
            },
        }

    def _compute_spatial_weights(
        self,
        locations: np.ndarray,
        n_points: int,
        n_models: int,
    ) -> np.ndarray:
        """计算空间级权重（基于局部数据密度）"""
        if n_points < 3:
            return np.ones((n_models, n_points)) / n_models

        # 计算局部密度（k近邻距离的倒数）
        dm = np.zeros((n_points, n_points), dtype=np.float64)
        for i in range(n_points):
            diff = locations - locations[i]
            dm[i] = np.sqrt(np.sum(diff ** 2, axis=1))

        k = min(10, n_points - 1)
        local_density = np.zeros(n_points, dtype=np.float64)
        for i in range(n_points):
            sorted_dist = np.sort(dm[i])
            avg_dist = np.mean(sorted_dist[1:k + 1])  # 跳过自身
            local_density[i] = 1.0 / max(avg_dist, 1e-8)

        # 归一化密度
        local_density = local_density / np.max(local_density)

        # 高密度区域所有模型权重相等，低密度区域增加对稳定模型的信赖
        weights = np.zeros((n_models, n_points), dtype=np.float64)
        for i in range(n_points):
            density_factor = local_density[i]
            # 低密度区域：更依赖于模型级先验
            spatial_influence = 1.0 - density_factor
            for idx in range(n_models):
                weights[idx, i] = 0.5 + 0.5 * spatial_influence
            # 归一化
            row_sum = np.sum(weights[:, i])
            if row_sum > 0:
                weights[:, i] /= row_sum

        return weights


class LocalPrecisionAdaptiveFusion:
    """
    局部精度自适应融合

    在预测时根据局部验证精度动态选择最优模型或加权组合。
    支持滑动窗口局部验证，实时更新模型在各区域的精度估计。
    """

    def __init__(
        self,
        window_size: int = 50,
        min_window: int = 10,
        forget_factor: float = 0.95,
    ):
        """
        初始化局部精度自适应融合

        Args:
            window_size: 滑动窗口大小
            min_window: 最小窗口大小（此时开始自适应）
            forget_factor: 遗忘因子（指数加权移动平均）
        """
        self.window_size = window_size
        self.min_window = min_window
        self.forget_factor = forget_factor

        # 运行时状态
        self._prediction_history: List[Dict] = []
        self._model_local_metrics: Dict[str, Dict] = {}

    def update(self, model_predictions: Dict[str, float], true_value: float, location: Tuple[float, float]) -> None:
        """
        更新局部精度记录

        Args:
            model_predictions: {model_id: prediction}
            true_value: 真实值
            location: 空间坐标
        """
        record = {
            'predictions': model_predictions,
            'true_value': true_value,
            'location': location,
        }
        self._prediction_history.append(record)

        # 滑动窗口截断
        if len(self._prediction_history) > self.window_size * 3:
            self._prediction_history = self._prediction_history[-self.window_size * 3:]

    def predict(
        self,
        model_predictions: Dict[str, float],
        location: Tuple[float, float],
        fallback_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        局部精度自适应预测

        Args:
            model_predictions: {model_id: prediction}
            location: 当前预测位置
            fallback_weights: 回退权重

        Returns:
            Dict: {'fused_value': float, 'weights': Dict, 'selected_model': str}
        """
        if len(self._prediction_history) < self.min_window:
            # 回退到均匀或提供的权重
            if fallback_weights:
                weights = fallback_weights
            else:
                n = len(model_predictions)
                weights = {mid: 1.0 / n for mid in model_predictions}

            fused = sum(w * model_predictions[mid] for mid, w in weights.items())
            return {
                'fused_value': fused,
                'weights': weights,
                'selected_model': max(weights, key=weights.get),
            }

        # 计算局部加权精度
        local_errors = self._compute_local_errors(location)

        # 转化为权重
        weights = {}
        total_inv = 0.0
        for mid in model_predictions:
            err = local_errors.get(mid, 1.0)
            w = 1.0 / max(err, 1e-8)
            weights[mid] = w
            total_inv += w

        if total_inv > 0:
            weights = {mid: w / total_inv for mid, w in weights.items()}
        else:
            n = len(model_predictions)
            weights = {mid: 1.0 / n for mid in model_predictions}

        fused = sum(w * model_predictions[mid] for mid, w in weights.items())
        return {
            'fused_value': fused,
            'weights': weights,
            'selected_model': max(weights, key=weights.get),
        }

    def _compute_local_errors(self, location: Tuple[float, float]) -> Dict[str, float]:
        """计算局部误差（空间加权）"""
        x, y = location
        errors = {}
        weights = {}

        for record in self._prediction_history[-self.window_size:]:
            loc = record['location']
            dist = np.sqrt((x - loc[0]) ** 2 + (y - loc[1]) ** 2)
            w = np.exp(-dist)  # 空间距离加权

            for mid, pred in record['predictions'].items():
                sq_err = (pred - record['true_value']) ** 2
                if mid not in errors:
                    errors[mid] = 0.0
                    weights[mid] = 0.0
                errors[mid] += w * sq_err
                weights[mid] += w

        result = {}
        for mid in errors:
            if weights[mid] > 0:
                result[mid] = float(np.sqrt(errors[mid] / weights[mid]))
            else:
                result[mid] = 1.0

        return result
