"""
数据预处理服务
"""
import json
from typing import Any, Dict

from ..config import settings
from ..schemas.数据模型 import Point, SpatialData


class DataPreprocessor:
    """数据预处理器"""

    def __init__(self):
        self.data_cache: Dict[str, SpatialData] = {}

    def parse_geojson(self, geojson: Dict[str, Any]) -> SpatialData:
        """
        解析GeoJSON数据
        """
        points = []

        if geojson.get("type") == "FeatureCollection":
            features = geojson.get("features", [])
            for feature in features:
                geometry = feature.get("geometry", {})
                properties = feature.get("properties", {})

                if geometry.get("type") == "Point":
                    coords = geometry.get("coordinates", [])
                    value = properties.get("value", 0.0)

                    if len(coords) >= 2:
                        points.append(Point(
                            x=coords[0],
                            y=coords[1],
                            value=float(value)
                        ))

        return SpatialData(
            points=points,
            crs=geojson.get("crs", {}).get("properties", {}).get("name", "EPSG:4326")
        )

    def save_data(self, data_id: str, spatial_data: SpatialData):
        """保存数据到缓存"""
        self.data_cache[data_id] = spatial_data

        # 持久化到文件
        data_file = settings.DATA_DIR / f"{data_id}.json"
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(spatial_data.model_dump(), f, ensure_ascii=False, indent=2)

    def load_data(self, data_id: str) -> SpatialData:
        """加载数据"""
        if data_id in self.data_cache:
            return self.data_cache[data_id]

        data_file = settings.DATA_DIR / f"{data_id}.json"
        if data_file.exists():
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                spatial_data = SpatialData(**data)
                self.data_cache[data_id] = spatial_data
                return spatial_data

        raise ValueError(f"数据不存在: {data_id}")
