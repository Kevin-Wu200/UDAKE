"""
采样优化建议模型
"""
from sklearn.cluster import KMeans
import numpy as np
from typing import List, Dict

class SamplingOptimizer:
    """采样优化建议模型"""

    def __init__(self):
        self.kmeans = None

    def suggest_sampling_locations(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        n_samples: int = 10,
        high_variance_weight: float = 0.7
    ) -> List[Dict[str, float]]:
        """
        基于方差建议采样位置
        """
        # 展平栅格
        variance_flat = variance.flatten()
        xx, yy = np.meshgrid(x_coords, y_coords)
        x_flat = xx.flatten()
        y_flat = yy.flatten()

        # 计算采样权重（高方差区域权重更高）
        weights = variance_flat / (np.max(variance_flat) + 1e-10)

        # 基于权重的概率采样
        high_variance_samples = int(n_samples * high_variance_weight)
        uniform_samples = n_samples - high_variance_samples

        # 高方差区域采样
        high_var_indices = np.argsort(variance_flat)[-high_variance_samples * 10:]
        selected_high = np.random.choice(
            high_var_indices,
            size=high_variance_samples,
            replace=False
        )

        # 均匀采样
        all_indices = np.arange(len(variance_flat))
        remaining_indices = np.setdiff1d(all_indices, selected_high)
        selected_uniform = np.random.choice(
            remaining_indices,
            size=uniform_samples,
            replace=False
        )

        # 合并
        selected_indices = np.concatenate([selected_high, selected_uniform])

        # 生成建议
        suggestions = []
        for idx in selected_indices:
            suggestions.append({
                "x": float(x_flat[idx]),
                "y": float(y_flat[idx]),
                "variance": float(variance_flat[idx]),
                "priority": float(weights[idx])
            })

        # 按优先级排序
        suggestions.sort(key=lambda s: s["priority"], reverse=True)

        return suggestions

    def cluster_sampling_regions(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        n_clusters: int = 5
    ) -> Dict[str, any]:
        """
        聚类高不确定性区域
        """
        # 找到高方差点
        threshold = np.percentile(variance, 75)
        high_var_mask = variance > threshold

        # 获取高方差点坐标
        xx, yy = np.meshgrid(x_coords, y_coords)
        high_var_x = xx[high_var_mask]
        high_var_y = yy[high_var_mask]

        if len(high_var_x) < n_clusters:
            n_clusters = max(1, len(high_var_x))

        # 聚类
        X = np.column_stack([high_var_x, high_var_y])
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = self.kmeans.fit_predict(X)

        # 聚类中心
        centers = self.kmeans.cluster_centers_

        return {
            "n_clusters": n_clusters,
            "cluster_centers": [
                {"x": float(c[0]), "y": float(c[1])}
                for c in centers
            ],
            "high_variance_points": len(high_var_x)
        }
