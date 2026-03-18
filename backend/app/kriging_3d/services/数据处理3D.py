"""
3D数据处理模块
支持数据导入、预处理、分层、采样
"""
import numpy as np
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from ..schemas.数据模型 import SpatialData3D, Point3D, BoundingBox3D
from ...config import settings
import logging

logger = logging.getLogger(__name__)


class DataProcessor3D:
    """3D数据处理器"""

    def __init__(self):
        self.data_store: Dict[str, SpatialData3D] = {}

    # ========== 数据导入 ==========

    def parse_geojson_3d(self, data: dict) -> SpatialData3D:
        """解析3D GeoJSON数据"""
        points = []
        features = data.get("features", [])
        for feature in features:
            geom = feature.get("geometry", {})
            props = feature.get("properties", {})
            coords = geom.get("coordinates", [])

            if geom.get("type") == "Point" and len(coords) >= 3:
                points.append(Point3D(
                    x=coords[0], y=coords[1], z=coords[2],
                    value=props.get("value", 0.0),
                    label=props.get("label")
                ))

        if not points:
            raise ValueError("未找到有效的3D点数据")

        return SpatialData3D(
            points=points,
            crs=data.get("crs", {}).get("properties", {}).get("name", "EPSG:4326"),
            metadata=data.get("metadata")
        )

    def parse_csv_3d(self, content: str, x_col: int = 0, y_col: int = 1,
                     z_col: int = 2, value_col: int = 3, has_header: bool = True) -> SpatialData3D:
        """解析CSV格式的3D数据"""
        lines = content.strip().split("\n")
        start = 1 if has_header else 0
        points = []
        for line in lines[start:]:
            parts = line.strip().split(",")
            if len(parts) > max(x_col, y_col, z_col, value_col):
                try:
                    points.append(Point3D(
                        x=float(parts[x_col]),
                        y=float(parts[y_col]),
                        z=float(parts[z_col]),
                        value=float(parts[value_col])
                    ))
                except (ValueError, IndexError):
                    continue
        if not points:
            raise ValueError("CSV中未找到有效的3D点数据")
        return SpatialData3D(points=points)

    def parse_borehole_data(self, data: dict) -> SpatialData3D:
        """解析钻孔数据格式"""
        points = []
        boreholes = data.get("boreholes", [])
        for bh in boreholes:
            x, y = bh.get("x", 0), bh.get("y", 0)
            samples = bh.get("samples", [])
            for sample in samples:
                points.append(Point3D(
                    x=x, y=y,
                    z=sample.get("depth", 0),
                    value=sample.get("value", 0),
                    label=bh.get("id")
                ))
        if not points:
            raise ValueError("钻孔数据中未找到有效样本")
        return SpatialData3D(points=points)

    def save_data(self, data_id: str, data: SpatialData3D):
        """保存3D数据"""
        self.data_store[data_id] = data
        # 持久化到文件
        save_path = settings.DATA_DIR / f"{data_id}_3d.json"
        save_dict = {
            "points": [p.model_dump() for p in data.points],
            "crs": data.crs,
            "z_unit": data.z_unit,
            "metadata": data.metadata
        }
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(save_dict, f, ensure_ascii=False, indent=2)
        logger.info(f"3D数据已保存: {save_path}, 点数: {len(data.points)}")

    def load_data(self, data_id: str) -> SpatialData3D:
        """加载3D数据"""
        if data_id in self.data_store:
            return self.data_store[data_id]
        load_path = settings.DATA_DIR / f"{data_id}_3d.json"
        if not load_path.exists():
            raise FileNotFoundError(f"3D数据不存在: {data_id}")
        with open(load_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        data = SpatialData3D(
            points=[Point3D(**p) for p in raw["points"]],
            crs=raw.get("crs", "EPSG:4326"),
            z_unit=raw.get("z_unit", "m"),
            metadata=raw.get("metadata")
        )
        self.data_store[data_id] = data
        return data

    # ========== 数据预处理 ==========

    def clean_data(self, data: SpatialData3D) -> SpatialData3D:
        """3D数据清洗：去除重复点和NaN值"""
        seen = set()
        cleaned = []
        for p in data.points:
            key = (round(p.x, 8), round(p.y, 8), round(p.z, 8))
            if key not in seen and np.isfinite(p.value):
                seen.add(key)
                cleaned.append(p)
        logger.info(f"数据清洗: {len(data.points)} -> {len(cleaned)} 点")
        return SpatialData3D(points=cleaned, crs=data.crs, z_unit=data.z_unit, metadata=data.metadata)

    def detect_outliers(self, data: SpatialData3D, method: str = "iqr",
                        factor: float = 1.5) -> Tuple[SpatialData3D, List[int]]:
        """3D异常值检测"""
        values = np.array([p.value for p in data.points])
        if method == "iqr":
            q1, q3 = np.percentile(values, [25, 75])
            iqr = q3 - q1
            lower, upper = q1 - factor * iqr, q3 + factor * iqr
            outlier_mask = (values < lower) | (values > upper)
        elif method == "zscore":
            z_scores = np.abs((values - values.mean()) / values.std())
            outlier_mask = z_scores > factor
        else:
            outlier_mask = np.zeros(len(values), dtype=bool)

        outlier_indices = np.where(outlier_mask)[0].tolist()
        clean_points = [p for i, p in enumerate(data.points) if not outlier_mask[i]]
        logger.info(f"异常值检测: 发现 {len(outlier_indices)} 个异常点")
        return (
            SpatialData3D(points=clean_points, crs=data.crs, z_unit=data.z_unit, metadata=data.metadata),
            outlier_indices
        )

    def normalize_coordinates(self, data: SpatialData3D) -> Tuple[SpatialData3D, Dict[str, float]]:
        """坐标归一化到[0,1]"""
        points_arr = np.array([[p.x, p.y, p.z] for p in data.points])
        mins = points_arr.min(axis=0)
        maxs = points_arr.max(axis=0)
        ranges = maxs - mins
        ranges[ranges == 0] = 1.0

        norm_points = []
        for p in data.points:
            norm_points.append(Point3D(
                x=(p.x - mins[0]) / ranges[0],
                y=(p.y - mins[1]) / ranges[1],
                z=(p.z - mins[2]) / ranges[2],
                value=p.value, label=p.label
            ))
        transform = {
            "min_x": float(mins[0]), "min_y": float(mins[1]), "min_z": float(mins[2]),
            "range_x": float(ranges[0]), "range_y": float(ranges[1]), "range_z": float(ranges[2]),
        }
        return SpatialData3D(points=norm_points, crs=data.crs, z_unit=data.z_unit, metadata=data.metadata), transform

    # ========== 数据分层 ==========

    def vertical_layers(self, data: SpatialData3D, n_layers: int = 5) -> Dict[int, SpatialData3D]:
        """按Z值等间距垂直分层"""
        z_vals = np.array([p.z for p in data.points])
        edges = np.linspace(z_vals.min(), z_vals.max(), n_layers + 1)
        layers = {}
        for i in range(n_layers):
            layer_points = [p for p in data.points if edges[i] <= p.z < edges[i + 1]]
            if i == n_layers - 1:
                layer_points = [p for p in data.points if edges[i] <= p.z <= edges[i + 1]]
            if layer_points:
                layers[i] = SpatialData3D(points=layer_points, crs=data.crs, z_unit=data.z_unit)
        logger.info(f"垂直分层: {n_layers} 层, 各层点数: {[len(l.points) for l in layers.values()]}")
        return layers

    def horizontal_layers(self, data: SpatialData3D, n_layers_x: int = 3,
                          n_layers_y: int = 3) -> Dict[str, SpatialData3D]:
        """按XY平面水平分块"""
        x_vals = np.array([p.x for p in data.points])
        y_vals = np.array([p.y for p in data.points])
        x_edges = np.linspace(x_vals.min(), x_vals.max(), n_layers_x + 1)
        y_edges = np.linspace(y_vals.min(), y_vals.max(), n_layers_y + 1)
        layers = {}
        for i in range(n_layers_x):
            for j in range(n_layers_y):
                key = f"{i}_{j}"
                pts = [p for p in data.points
                       if x_edges[i] <= p.x <= x_edges[i + 1] and y_edges[j] <= p.y <= y_edges[j + 1]]
                if pts:
                    layers[key] = SpatialData3D(points=pts, crs=data.crs, z_unit=data.z_unit)
        return layers

    # ========== 数据采样 ==========

    def resample(self, data: SpatialData3D, target_count: int) -> SpatialData3D:
        """随机重采样到目标点数"""
        if len(data.points) <= target_count:
            return data
        indices = np.random.choice(len(data.points), target_count, replace=False)
        sampled = [data.points[i] for i in sorted(indices)]
        return SpatialData3D(points=sampled, crs=data.crs, z_unit=data.z_unit, metadata=data.metadata)

    def downsample_grid(self, data: SpatialData3D, cell_size: float) -> SpatialData3D:
        """网格降采样：每个网格单元取均值"""
        points_arr = np.array([[p.x, p.y, p.z, p.value] for p in data.points])
        grid_keys = {}
        for row in points_arr:
            key = (
                int(row[0] / cell_size),
                int(row[1] / cell_size),
                int(row[2] / cell_size)
            )
            if key not in grid_keys:
                grid_keys[key] = []
            grid_keys[key].append(row)

        sampled = []
        for key, rows in grid_keys.items():
            arr = np.array(rows)
            sampled.append(Point3D(
                x=float(arr[:, 0].mean()),
                y=float(arr[:, 1].mean()),
                z=float(arr[:, 2].mean()),
                value=float(arr[:, 3].mean())
            ))
        logger.info(f"网格降采样: {len(data.points)} -> {len(sampled)} 点, cell_size={cell_size}")
        return SpatialData3D(points=sampled, crs=data.crs, z_unit=data.z_unit, metadata=data.metadata)

    def get_bounds(self, data: SpatialData3D) -> BoundingBox3D:
        """获取3D边界框"""
        points = data.points
        return BoundingBox3D(
            min_x=min(p.x for p in points),
            min_y=min(p.y for p in points),
            min_z=min(p.z for p in points),
            max_x=max(p.x for p in points),
            max_y=max(p.y for p in points),
            max_z=max(p.z for p in points),
        )

    def get_statistics(self, data: SpatialData3D) -> Dict[str, Any]:
        """获取3D数据统计信息"""
        values = np.array([p.value for p in data.points])
        coords = np.array([[p.x, p.y, p.z] for p in data.points])
        return {
            "point_count": len(data.points),
            "value_stats": {
                "mean": float(values.mean()),
                "std": float(values.std()),
                "min": float(values.min()),
                "max": float(values.max()),
                "median": float(np.median(values)),
            },
            "x_range": [float(coords[:, 0].min()), float(coords[:, 0].max())],
            "y_range": [float(coords[:, 1].min()), float(coords[:, 1].max())],
            "z_range": [float(coords[:, 2].min()), float(coords[:, 2].max())],
        }
