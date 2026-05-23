"""
高不确定性区域识别
"""
from typing import Dict, List

import numpy as np
from scipy.ndimage import label


class HighUncertaintyIdentifier:
    """高不确定性区域识别器"""

    def identify_high_uncertainty_regions(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        threshold_percentile: float = 75
    ) -> Dict[str, any]:
        """
        识别高不确定性区域
        """
        # 计算阈值
        threshold = np.percentile(variance, threshold_percentile)

        # 二值化
        high_uncertainty_mask = variance > threshold

        # 连通区域标记
        labeled_array, num_features = label(high_uncertainty_mask)

        # 分析每个区域
        regions = []
        for region_id in range(1, num_features + 1):
            region_mask = labeled_array == region_id
            region_variance = variance[region_mask]

            # 计算区域中心
            y_indices, x_indices = np.where(region_mask)
            center_x = float(x_coords[int(np.mean(x_indices))])
            center_y = float(y_coords[int(np.mean(y_indices))])

            regions.append({
                "region_id": region_id,
                "center": {"x": center_x, "y": center_y},
                "area": int(np.sum(region_mask)),
                "mean_variance": float(np.mean(region_variance)),
                "max_variance": float(np.max(region_variance))
            })

        # 按平均方差排序
        regions.sort(key=lambda r: r["mean_variance"], reverse=True)

        return {
            "threshold": float(threshold),
            "num_regions": num_features,
            "regions": regions,
            "total_high_uncertainty_area": int(np.sum(high_uncertainty_mask))
        }

    def calculate_uncertainty_hotspots(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        top_n: int = 10
    ) -> List[Dict[str, float]]:
        """
        计算不确定性热点
        """
        # 展平
        variance_flat = variance.flatten()
        xx, yy = np.meshgrid(x_coords, y_coords)
        x_flat = xx.flatten()
        y_flat = yy.flatten()

        # 找到最高方差点
        top_indices = np.argsort(variance_flat)[-top_n:]

        hotspots = []
        for idx in reversed(top_indices):
            hotspots.append({
                "x": float(x_flat[idx]),
                "y": float(y_flat[idx]),
                "variance": float(variance_flat[idx]),
                "rank": len(hotspots) + 1
            })

        return hotspots
