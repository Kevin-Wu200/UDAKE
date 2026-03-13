"""
采样点推荐生成
"""
import numpy as np
from typing import List, Dict
import json

class SamplingRecommender:
    """采样点推荐生成器"""

    def generate_recommendations(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        existing_points: np.ndarray = None,
        n_recommendations: int = 20,
        strategy: str = "variance_based"
    ) -> Dict[str, any]:
        """
        生成采样点推荐
        """
        if strategy == "variance_based":
            recommendations = self._variance_based_sampling(
                variance, x_coords, y_coords, n_recommendations
            )
        elif strategy == "spatial_coverage":
            recommendations = self._spatial_coverage_sampling(
                variance, x_coords, y_coords, existing_points, n_recommendations
            )
        else:
            recommendations = self._hybrid_sampling(
                variance, x_coords, y_coords, existing_points, n_recommendations
            )

        return {
            "strategy": strategy,
            "n_recommendations": len(recommendations),
            "recommendations": recommendations
        }

    def _variance_based_sampling(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        n: int
    ) -> List[Dict[str, float]]:
        """基于方差的采样"""
        variance_flat = variance.flatten()
        xx, yy = np.meshgrid(x_coords, y_coords)
        x_flat = xx.flatten()
        y_flat = yy.flatten()

        # 选择最高方差点
        top_indices = np.argsort(variance_flat)[-n:]

        recommendations = []
        for i, idx in enumerate(reversed(top_indices)):
            recommendations.append({
                "id": i + 1,
                "x": float(x_flat[idx]),
                "y": float(y_flat[idx]),
                "variance": float(variance_flat[idx]),
                "priority": "high" if i < n // 3 else "medium" if i < 2 * n // 3 else "low"
            })

        return recommendations

    def _spatial_coverage_sampling(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        existing_points: np.ndarray,
        n: int
    ) -> List[Dict[str, float]]:
        """基于空间覆盖的采样"""
        # 简化版：网格均匀采样
        x_samples = np.linspace(x_coords.min(), x_coords.max(), int(np.sqrt(n)))
        y_samples = np.linspace(y_coords.min(), y_coords.max(), int(np.sqrt(n)))

        # 创建网格以查找方差值
        xx, yy = np.meshgrid(x_coords, y_coords)

        recommendations = []
        idx = 1
        for x in x_samples:
            for y in y_samples:
                if idx > n:
                    break

                # 查找最近的网格点获取方差值
                x_idx = np.argmin(np.abs(x_coords - x))
                y_idx = np.argmin(np.abs(y_coords - y))
                variance_value = float(variance[y_idx, x_idx])

                recommendations.append({
                    "id": idx,
                    "x": float(x),
                    "y": float(y),
                    "variance": variance_value,
                    "priority": "medium"
                })
                idx += 1

        return recommendations

    def _hybrid_sampling(
        self,
        variance: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        existing_points: np.ndarray,
        n: int
    ) -> List[Dict[str, float]]:
        """混合策略采样"""
        # 70%基于方差，30%基于空间覆盖
        n_variance = int(n * 0.7)
        n_spatial = n - n_variance

        variance_samples = self._variance_based_sampling(
            variance, x_coords, y_coords, n_variance
        )
        spatial_samples = self._spatial_coverage_sampling(
            variance, x_coords, y_coords, existing_points, n_spatial
        )

        return variance_samples + spatial_samples

    def export_to_geojson(
        self,
        recommendations: List[Dict[str, float]],
        crs: str = "EPSG:4326"
    ) -> Dict:
        """导出为GeoJSON格式"""
        features = []
        for rec in recommendations:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [rec["x"], rec["y"]]
                },
                "properties": {
                    "id": rec.get("id"),
                    "variance": rec.get("variance"),
                    "priority": rec.get("priority", "medium")
                }
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": crs}
            },
            "features": features
        }
