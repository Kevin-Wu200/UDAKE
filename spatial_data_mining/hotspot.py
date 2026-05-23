"""
热点分析算法
Hotspot Analysis

实现 Getis-Ord Gi* 统计量和空间自相关分析。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

try:
    from scipy import stats as scipy_stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    scipy_stats = None

logger = logging.getLogger(__name__)


def _norm_cdf(x: float) -> float:
    """正态分布CDF近似（当scipy不可用时）"""
    # 使用误差函数近似
    import math
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_sf(x: float) -> float:
    """正态分布生存函数近似"""
    return 1.0 - _norm_cdf(x)


@dataclass
class HotspotResult:
    """热点分析结果"""
    gi_star: np.ndarray  # Getis-Ord Gi* 统计量
    z_scores: np.ndarray  # Z分数
    p_values: np.ndarray  # P值
    is_hotspot: np.ndarray  # 热点标识（bool）
    is_coldspot: np.ndarray  # 冷点标识（bool）
    confidence: np.ndarray  # 置信度 [0, 1]
    metadata: Optional[Dict[str, Any]] = None


class GetisOrdGi:
    """
    Getis-Ord Gi* 热点分析

    识别空间数据中的高值聚集区（热点）和低值聚集区（冷点）。
    """

    def __init__(
        self,
        distance_band: Optional[float] = None,
        k_neighbors: int = 8,
        significance_level: float = 0.05,
    ):
        """
        初始化Getis-Ord Gi*

        Args:
            distance_band: 距离阈值，None则使用k近邻
            k_neighbors: 当distance_band为None时使用的邻居数
            significance_level: 显著性水平
        """
        self.distance_band = distance_band
        self.k_neighbors = k_neighbors
        self.significance_level = significance_level

    def analyze(
        self,
        points: np.ndarray,
        values: np.ndarray,
    ) -> HotspotResult:
        """
        执行Getis-Ord Gi*分析

        Args:
            points: 点的坐标数组 [n × 2]
            values: 点的属性值数组 [n]

        Returns:
            HotspotResult: 热点分析结果
        """
        n = len(points)
        if n < 3:
            return HotspotResult(
                gi_star=np.zeros(n),
                z_scores=np.zeros(n),
                p_values=np.ones(n),
                is_hotspot=np.zeros(n, dtype=bool),
                is_coldspot=np.zeros(n, dtype=bool),
                confidence=np.zeros(n),
            )

        # 构建空间权重矩阵
        W = self._build_weight_matrix(points)

        # 全局统计量
        global_mean = np.mean(values)
        global_std = np.std(values)
        if global_std == 0:
            global_std = 1e-10

        # 计算每个位置的 Gi*
        gi_star = np.zeros(n)
        e_gi = np.zeros(n)
        var_gi = np.zeros(n)

        for i in range(n):
            wij_sum = np.sum(W[i])
            if wij_sum == 0:
                gi_star[i] = 0.0
                continue

            # 加权和
            weighted_sum = np.sum(W[i] * values)
            # 期望值
            e_gi[i] = global_mean * wij_sum
            # 方差
            n_eff = wij_sum
            var_gi[i] = (global_std ** 2) * (n_eff * (n - n_eff) / (n - 1)) if n > 1 else global_std ** 2

            if var_gi[i] > 0:
                gi_star[i] = (weighted_sum - e_gi[i]) / np.sqrt(var_gi[i])
            else:
                gi_star[i] = 0.0

        # Z分数
        z_scores = gi_star.copy()

        # P值
        if SCIPY_AVAILABLE:
            p_values = 2 * (1 - scipy_stats.norm.cdf(np.abs(z_scores)))
        else:
            p_values = 2 * np.vectorize(_norm_sf)(np.abs(z_scores))

        # 热点/冷点识别
        is_hotspot = (z_scores > 0) & (p_values < self.significance_level)
        is_coldspot = (z_scores < 0) & (p_values < self.significance_level)

        # 置信度
        confidence = 1.0 - p_values

        return HotspotResult(
            gi_star=gi_star,
            z_scores=z_scores,
            p_values=p_values,
            is_hotspot=is_hotspot,
            is_coldspot=is_coldspot,
            confidence=confidence,
        )

    def _build_weight_matrix(self, points: np.ndarray) -> np.ndarray:
        """构建空间权重矩阵"""
        n = len(points)
        W = np.zeros((n, n), dtype=np.float64)

        # 计算距离矩阵
        dm = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            diff = points - points[i]
            dm[i] = np.sqrt(np.sum(diff ** 2, axis=1))

        if self.distance_band is not None:
            # 固定距离阈值
            W[dm <= self.distance_band] = 1.0
            np.fill_diagonal(W, 0.0)
        else:
            # K近邻
            for i in range(n):
                # 排除自身
                sorted_indices = np.argsort(dm[i])
                k = min(self.k_neighbors + 1, n)
                neighbors = sorted_indices[1:k]  # 跳过自身
                W[i, neighbors] = 1.0

        return W


class HotspotAnalyzer:
    """
    热点分析器

    整合多种空间分析方法：
    - Getis-Ord Gi* 热点分析
    - 局部莫兰指数（LISA）
    - 空间扫描统计
    """

    def __init__(
        self,
        distance_band: Optional[float] = None,
        significance_level: float = 0.05,
    ):
        self.distance_band = distance_band
        self.significance_level = significance_level
        self._gi = GetisOrdGi(
            distance_band=distance_band,
            significance_level=significance_level,
        )

    def analyze(
        self,
        points: np.ndarray,
        values: np.ndarray,
    ) -> Dict[str, Any]:
        """
        综合热点分析

        Args:
            points: 点的坐标数组
            values: 点的属性值数组

        Returns:
            Dict: 分析结果
        """
        n = len(points)

        # Getis-Ord Gi* 分析
        gi_result = self._gi.analyze(points, values)

        # 局部莫兰指数 (LISA)
        lisa_result = self._local_moran(points, values)

        # 聚合结果
        n_hotspots = int(np.sum(gi_result.is_hotspot))
        n_coldspots = int(np.sum(gi_result.is_coldspot))
        n_significant_lisa = int(np.sum(np.abs(lisa_result['moran_i']) > 1.96))

        return {
            'gi_star': {
                'gi_values': gi_result.gi_star.tolist(),
                'z_scores': gi_result.z_scores.tolist(),
                'p_values': gi_result.p_values.tolist(),
                'is_hotspot': gi_result.is_hotspot.tolist(),
                'is_coldspot': gi_result.is_coldspot.tolist(),
                'n_hotspots': n_hotspots,
                'n_coldspots': n_coldspots,
            },
            'lisa': lisa_result,
            'summary': {
                'total_points': n,
                'hotspot_ratio': float(n_hotspots / n) if n > 0 else 0.0,
                'coldspot_ratio': float(n_coldspots / n) if n > 0 else 0.0,
                'global_moran_i': float(lisa_result['global_moran_i']),
                'significant_clusters': n_significant_lisa,
            },
        }

    def _local_moran(self, points: np.ndarray, values: np.ndarray) -> Dict[str, Any]:
        """计算局部莫兰指数"""
        n = len(points)
        if n < 3:
            return {
                'moran_i': np.zeros(n).tolist(),
                'global_moran_i': 0.0,
                'z_scores': np.zeros(n).tolist(),
            }

        # 构建权重矩阵
        W = self._gi._build_weight_matrix(points)

        # 标准化值
        mean_val = np.mean(values)
        std_val = np.std(values)
        if std_val == 0:
            std_val = 1e-10
        z = (values - mean_val) / std_val

        # 局部莫兰指数
        local_moran = np.zeros(n)
        s2 = np.sum(z ** 2) / n

        for i in range(n):
            wij_sum = np.sum(W[i])
            if wij_sum == 0:
                continue
            local_moran[i] = (z[i] / s2) * np.sum(W[i] * z)

        # 全局莫兰指数
        W_sum = np.sum(W)
        global_moran = float(n / W_sum * np.sum(z[:, np.newaxis] * W * z[np.newaxis, :]) / np.sum(z ** 2)) if W_sum > 0 else 0.0

        return {
            'moran_i': local_moran.tolist(),
            'global_moran_i': global_moran,
            'z_scores': np.abs(local_moran).tolist(),
        }
