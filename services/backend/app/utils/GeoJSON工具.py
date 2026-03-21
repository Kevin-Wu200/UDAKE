"""
GeoJSON工具
"""
import json
import numpy as np
from typing import List, Dict, Any
from pathlib import Path

class GeoJSONUtils:
    """GeoJSON处理工具"""

    @staticmethod
    def create_point_feature(
        x: float,
        y: float,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建点要素"""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [x, y]
            },
            "properties": properties
        }

    @staticmethod
    def create_feature_collection(
        features: List[Dict[str, Any]],
        crs: str = "EPSG:4326"
    ) -> Dict[str, Any]:
        """创建要素集合"""
        return {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {
                    "name": crs
                }
            },
            "features": features
        }

    @staticmethod
    def raster_to_points(
        data: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        property_name: str = "value"
    ) -> Dict[str, Any]:
        """
        将栅格转换为点GeoJSON
        """
        features = []

        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                value = float(data[i, j])
                if not np.isnan(value):
                    feature = GeoJSONUtils.create_point_feature(
                        x=float(x_coords[j]),
                        y=float(y_coords[i]),
                        properties={property_name: value}
                    )
                    features.append(feature)

        return GeoJSONUtils.create_feature_collection(features)

    @staticmethod
    def save_geojson(data: Dict[str, Any], filepath: Path):
        """保存GeoJSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_geojson(filepath: Path) -> Dict[str, Any]:
        """加载GeoJSON文件"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
