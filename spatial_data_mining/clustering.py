"""
空间聚类算法实现
Spatial Clustering Algorithms

实现 DBSCAN、ST-DBSCAN（时空DBSCAN）等聚类算法。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ClusterResult:
    """聚类结果"""
    labels: np.ndarray  # 每个点的簇标签（-1表示噪声）
    n_clusters: int
    noise_points: int
    cluster_sizes: Dict[int, int]
    core_points: Set[int]
    metadata: Optional[Dict[str, Any]] = None


class SpatialDBSCAN:
    """
    空间DBSCAN聚类

    基于密度的空间聚类算法，适合发现任意形状的簇。
    支持空间距离（欧氏距离）和属性距离的联合聚类。
    """

    def __init__(
        self,
        eps: float = 0.5,
        min_samples: int = 5,
        metric: str = 'euclidean',
    ):
        """
        初始化DBSCAN

        Args:
            eps: 邻域半径
            min_samples: 核心点的最小邻居数
            metric: 距离度量 ('euclidean', 'manhattan')
        """
        self.eps = eps
        self.min_samples = min_samples
        self.metric = metric

    def fit(
        self,
        points: np.ndarray,
        attributes: Optional[np.ndarray] = None,
        attribute_weight: float = 0.5,
    ) -> ClusterResult:
        """
        执行DBSCAN聚类

        Args:
            points: 点的坐标数组 [n × 2]
            attributes: 点的属性值数组 [n] 或 [n × m]
            attribute_weight: 属性距离的权重 [0, 1]

        Returns:
            ClusterResult: 聚类结果
        """
        n = len(points)
        if n == 0:
            return ClusterResult(
                labels=np.array([], dtype=int),
                n_clusters=0,
                noise_points=0,
                cluster_sizes={},
                core_points=set(),
            )

        # 构建距离矩阵
        if attributes is not None and attribute_weight > 0:
            distance_matrix = self._combined_distance(
                points, attributes, attribute_weight
            )
        else:
            distance_matrix = self._compute_distance_matrix(points)

        # DBSCAN核心算法
        labels = np.full(n, -1, dtype=int)
        visited = np.zeros(n, dtype=bool)
        core_points: Set[int] = set()
        cluster_id = 0

        for i in range(n):
            if visited[i]:
                continue

            visited[i] = True
            neighbors = self._find_neighbors(distance_matrix, i)

            if len(neighbors) < self.min_samples:
                # 噪声点（暂时标记，后续可能被归入某个簇的边界点）
                continue

            # 核心点：开始扩展簇
            core_points.add(i)
            cluster_id += 1
            labels[i] = cluster_id

            # 扩展簇
            seeds = list(neighbors)
            seeds_set = set(neighbors)
            processed = {i}

            while seeds:
                j = seeds.pop()
                if not visited[j]:
                    visited[j] = True
                    j_neighbors = self._find_neighbors(distance_matrix, j)
                    if len(j_neighbors) >= self.min_samples:
                        core_points.add(j)
                        for nb in j_neighbors:
                            if nb not in seeds_set and nb not in processed:
                                seeds.append(nb)
                                seeds_set.add(nb)

                if labels[j] <= 0:
                    labels[j] = cluster_id
                processed.add(j)

        # 统计簇
        n_clusters = cluster_id
        noise_points = int(np.sum(labels == -1))
        cluster_sizes = {}
        for cid in range(1, n_clusters + 1):
            size = int(np.sum(labels == cid))
            if size > 0:
                cluster_sizes[cid] = size

        return ClusterResult(
            labels=labels,
            n_clusters=n_clusters,
            noise_points=noise_points,
            cluster_sizes=cluster_sizes,
            core_points=core_points,
        )

    def _find_neighbors(self, distance_matrix: np.ndarray, point_idx: int) -> List[int]:
        """找到点的所有邻居"""
        neighbors = []
        for j in range(len(distance_matrix)):
            if j != point_idx and distance_matrix[point_idx, j] <= self.eps:
                neighbors.append(j)
        return neighbors

    def _compute_distance_matrix(self, points: np.ndarray) -> np.ndarray:
        """计算距离矩阵"""
        n = len(points)
        dm = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            diff = points - points[i]
            if self.metric == 'manhattan':
                dm[i] = np.sum(np.abs(diff), axis=1)
            else:
                dm[i] = np.sqrt(np.sum(diff ** 2, axis=1))
        return dm

    def _combined_distance(
        self,
        points: np.ndarray,
        attributes: np.ndarray,
        weight: float,
    ) -> np.ndarray:
        """计算空间距离和属性距离的加权组合"""
        spatial_dm = self._compute_distance_matrix(points)

        # 属性距离（归一化）
        if attributes.ndim == 1:
            attr = attributes.reshape(-1, 1)
        else:
            attr = attributes

        n = len(points)
        attr_dm = np.zeros((n, n), dtype=np.float64)
        for i in range(n):
            diff = attr - attr[i]
            attr_dm[i] = np.sqrt(np.sum(diff ** 2, axis=1))

        # 归一化
        if np.max(spatial_dm) > 0:
            spatial_dm = spatial_dm / np.max(spatial_dm)
        if np.max(attr_dm) > 0:
            attr_dm = attr_dm / np.max(attr_dm)

        return (1 - weight) * spatial_dm + weight * attr_dm


class STDBSCAN(SpatialDBSCAN):
    """
    时空DBSCAN（ST-DBSCAN）

    在空间DBSCAN基础上增加时间维度，支持时空联合聚类。
    适用于移动对象轨迹、时空事件等场景。
    """

    def __init__(
        self,
        eps_spatial: float = 0.5,
        eps_temporal: float = 3600.0,  # 时间邻域（秒）
        min_samples: int = 5,
        metric: str = 'euclidean',
    ):
        """
        初始化ST-DBSCAN

        Args:
            eps_spatial: 空间邻域半径
            eps_temporal: 时间邻域半径（秒）
            min_samples: 核心点的最小邻居数
            metric: 空间距离度量
        """
        super().__init__(eps=eps_spatial, min_samples=min_samples, metric=metric)
        self.eps_temporal = eps_temporal

    def fit_spatiotemporal(
        self,
        points: np.ndarray,
        timestamps: np.ndarray,
        attributes: Optional[np.ndarray] = None,
        attribute_weight: float = 0.3,
    ) -> ClusterResult:
        """
        时空联合聚类

        Args:
            points: 点的空间坐标 [n × 2]
            timestamps: 点的时间戳（Unix秒或datetime）[n]
            attributes: 点的属性值（可选）[n]
            attribute_weight: 属性权重

        Returns:
            ClusterResult: 聚类结果
        """
        n = len(points)
        if n == 0:
            return ClusterResult(
                labels=np.array([], dtype=int),
                n_clusters=0,
                noise_points=0,
                cluster_sizes={},
                core_points=set(),
            )

        # 将时间戳转换为秒级浮点数
        if hasattr(timestamps[0], 'timestamp'):
            temporal = np.array([t.timestamp() for t in timestamps], dtype=np.float64)
        else:
            temporal = np.array(timestamps, dtype=np.float64)

        # 空间距离矩阵
        spatial_dm = self._compute_distance_matrix(points)

        # 时间距离矩阵
        temporal_dm = np.abs(temporal[:, np.newaxis] - temporal[np.newaxis, :])

        # 时空联合距离：满足空间和时间约束
        labels = np.full(n, -1, dtype=int)
        visited = np.zeros(n, dtype=bool)
        core_points: Set[int] = set()
        cluster_id = 0

        for i in range(n):
            if visited[i]:
                continue

            visited[i] = True
            neighbors = self._find_st_neighbors(spatial_dm, temporal_dm, i)

            if len(neighbors) < self.min_samples:
                continue

            core_points.add(i)
            cluster_id += 1
            labels[i] = cluster_id

            seeds = list(neighbors)
            seeds_set = set(neighbors)
            processed = {i}

            while seeds:
                j = seeds.pop()
                if not visited[j]:
                    visited[j] = True
                    j_neighbors = self._find_st_neighbors(spatial_dm, temporal_dm, j)
                    if len(j_neighbors) >= self.min_samples:
                        core_points.add(j)
                        for nb in j_neighbors:
                            if nb not in seeds_set and nb not in processed:
                                seeds.append(nb)
                                seeds_set.add(nb)

                if labels[j] <= 0:
                    labels[j] = cluster_id
                processed.add(j)

        n_clusters = cluster_id
        noise_points = int(np.sum(labels == -1))
        cluster_sizes = {}
        for cid in range(1, n_clusters + 1):
            size = int(np.sum(labels == cid))
            if size > 0:
                cluster_sizes[cid] = size

        return ClusterResult(
            labels=labels,
            n_clusters=n_clusters,
            noise_points=noise_points,
            cluster_sizes=cluster_sizes,
            core_points=core_points,
            metadata={
                'eps_spatial': self.eps,
                'eps_temporal': self.eps_temporal,
            },
        )

    def _find_st_neighbors(
        self,
        spatial_dm: np.ndarray,
        temporal_dm: np.ndarray,
        point_idx: int,
    ) -> List[int]:
        """找到时空邻居（空间和时间约束同时满足）"""
        neighbors = []
        for j in range(len(spatial_dm)):
            if j != point_idx:
                if (spatial_dm[point_idx, j] <= self.eps and
                    temporal_dm[point_idx, j] <= self.eps_temporal):
                    neighbors.append(j)
        return neighbors
