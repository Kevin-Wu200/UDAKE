"""
空间异常值检测
Spatial Outlier Detection

检测空间数据中的异常点。
"""

import numpy as np
from typing import List, Tuple, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SpatialOutlierDetector:
    """
    空间异常值检测器

    使用多种方法检测空间异常：
    - 空间Z-score（局部偏离全局均值的程度）
    - 空间局部异常因子（SLOF）
    - 空间差分法
    """

    def __init__(
        self,
        method: str = 'zscore',
        threshold: float = 2.0,
        k_neighbors: int = 10,
    ):
        """
        初始化异常检测器

        Args:
            method: 检测方法 ('zscore', 'slof', 'spatial_diff')
            threshold: 异常阈值（标准差倍数）
            k_neighbors: 局部方法使用的邻居数
        """
        self.method = method
        self.threshold = threshold
        self.k_neighbors = k_neighbors

    def detect(
        self,
        points: np.ndarray,
        values: np.ndarray,
    ) -> Dict[str, Any]:
        """
        检测空间异常值

        Args:
            points: 点的坐标数组 [n × 2]
            values: 点的属性值数组 [n]

        Returns:
            Dict: 检测结果
        """
        if self.method == 'zscore':
            return self._zscore_detect(points, values)
        elif self.method == 'slof':
            return self._slof_detect(points, values)
        elif self.method == 'spatial_diff':
            return self._spatial_diff_detect(points, values)
        else:
            raise ValueError(f"未知检测方法: {self.method}")

    def _zscore_detect(self, points: np.ndarray, values: np.ndarray) -> Dict[str, Any]:
        """空间Z-score异常检测"""
        n = len(points)
        if n < 3:
            return {'outliers': [], 'scores': np.zeros(n).tolist(), 'is_outlier': np.zeros(n, dtype=bool).tolist()}

        # 构建空间权重
        dm = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            diff = points - points[i]
            dm[i] = np.sqrt(np.sum(diff ** 2, axis=1))

        scores = np.zeros(n)

        for i in range(n):
            # 找到k个最近邻居
            sorted_idx = np.argsort(dm[i])
            neighbors = sorted_idx[1:self.k_neighbors + 1]  # 跳过自身

            if len(neighbors) > 0:
                local_mean = np.mean(values[neighbors])
                local_std = np.std(values[neighbors])
                if local_std == 0:
                    local_std = 1e-10
                scores[i] = abs(values[i] - local_mean) / local_std

        is_outlier = scores > self.threshold
        outlier_indices = np.where(is_outlier)[0].tolist()

        return {
            'outliers': outlier_indices,
            'scores': scores.tolist(),
            'is_outlier': is_outlier.tolist(),
            'n_outliers': len(outlier_indices),
            'outlier_ratio': float(len(outlier_indices) / n) if n > 0 else 0.0,
        }

    def _slof_detect(self, points: np.ndarray, values: np.ndarray) -> Dict[str, Any]:
        """空间局部异常因子（SLOF）"""
        n = len(points)
        if n < self.k_neighbors + 1:
            return {'outliers': [], 'scores': np.zeros(n).tolist(), 'is_outlier': np.zeros(n, dtype=bool).tolist()}

        # 计算k-距离
        dm = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            diff = points - points[i]
            dm[i] = np.sqrt(np.sum(diff ** 2, axis=1))

        k_distances = np.zeros(n)
        k_neighbors_list = []

        for i in range(n):
            sorted_idx = np.argsort(dm[i])
            k_distances[i] = dm[i, sorted_idx[self.k_neighbors]]
            k_neighbors_list.append(sorted_idx[1:self.k_neighbors + 1])

        # 计算可达距离
        reach_dist = np.zeros((n, self.k_neighbors))
        for i in range(n):
            for j_idx, j in enumerate(k_neighbors_list[i]):
                reach_dist[i, j_idx] = max(k_distances[j], dm[i, j])

        # 局部可达密度
        lrd = np.zeros(n)
        for i in range(n):
            avg_reach = np.mean(reach_dist[i])
            if avg_reach > 0:
                lrd[i] = self.k_neighbors / avg_reach
            else:
                lrd[i] = float('inf')

        # LOF
        lof_scores = np.zeros(n)
        for i in range(n):
            lrd_ratio = 0.0
            count = 0
            for j in k_neighbors_list[i]:
                if lrd[i] > 0:
                    lrd_ratio += lrd[j] / lrd[i]
                    count += 1
            if count > 0:
                lof_scores[i] = lrd_ratio / count
            else:
                lof_scores[i] = 1.0

        is_outlier = lof_scores > self.threshold
        outlier_indices = np.where(is_outlier)[0].tolist()

        return {
            'outliers': outlier_indices,
            'scores': lof_scores.tolist(),
            'is_outlier': is_outlier.tolist(),
            'n_outliers': len(outlier_indices),
            'outlier_ratio': float(len(outlier_indices) / n) if n > 0 else 0.0,
        }

    def _spatial_diff_detect(self, points: np.ndarray, values: np.ndarray) -> Dict[str, Any]:
        """空间差分法异常检测"""
        n = len(points)
        if n < 3:
            return {'outliers': [], 'scores': np.zeros(n).tolist(), 'is_outlier': np.zeros(n, dtype=bool).tolist()}

        # 对每个点，与邻居的差分
        dm = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            diff = points - points[i]
            dm[i] = np.sqrt(np.sum(diff ** 2, axis=1))

        scores = np.zeros(n)
        for i in range(n):
            sorted_idx = np.argsort(dm[i])
            neighbors = sorted_idx[1:self.k_neighbors + 1]

            # 空间加权的属性差分
            total_diff = 0.0
            total_weight = 0.0
            for j in neighbors:
                w = 1.0 / (dm[i, j] + 1e-6)
                total_diff += w * abs(values[i] - values[j])
                total_weight += w

            if total_weight > 0:
                scores[i] = total_diff / total_weight
            else:
                scores[i] = 0.0

        # 标准化分数
        mean_score = np.mean(scores)
        std_score = np.std(scores)
        if std_score > 0:
            z_scores = (scores - mean_score) / std_score
        else:
            z_scores = np.zeros(n)

        is_outlier = z_scores > self.threshold
        outlier_indices = np.where(is_outlier)[0].tolist()

        return {
            'outliers': outlier_indices,
            'scores': z_scores.tolist(),
            'is_outlier': is_outlier.tolist(),
            'n_outliers': len(outlier_indices),
            'outlier_ratio': float(len(outlier_indices) / n) if n > 0 else 0.0,
        }
