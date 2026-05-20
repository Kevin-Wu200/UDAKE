"""
无缝地理对齐模块
================
确保反演出的物理指标点位与项目底图坐标系一致。

功能：
1. 坐标系统一转换（支持多种投影）
2. 栅格对齐（像元级精确对齐）
3. 矢量-栅格配准验证
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any

import numpy as np

try:
    from osgeo import osr, ogr
    HAS_GDAL = True
except ImportError:
    HAS_GDAL = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class CRSDefinition:
    """坐标参考系定义"""
    epsg: Optional[int] = None
    proj4: Optional[str] = None
    wkt: Optional[str] = None
    name: Optional[str] = None

    @classmethod
    def from_epsg(cls, code: int) -> "CRSDefinition":
        return cls(epsg=code)

    @classmethod
    def wgs84(cls) -> "CRSDefinition":
        return cls(epsg=4326, name="WGS84")

    @classmethod
    def web_mercator(cls) -> "CRSDefinition":
        return cls(epsg=3857, name="Web Mercator")

    @classmethod
    def cgcs2000(cls) -> "CRSDefinition":
        return cls(epsg=4490, name="CGCS2000")


@dataclass
class GeoTransform:
    """地理变换参数（GDAL格式）"""
    origin_x: float       # 左上角X坐标
    pixel_width: float    # 像元宽度（X方向分辨率）
    rotation_x: float = 0.0  # X方向旋转
    origin_y: float = 0.0    # 左上角Y坐标
    rotation_y: float = 0.0  # Y方向旋转
    pixel_height: float = -1.0  # 像元高度（通常为负，Y方向分辨率）

    def to_gdal_tuple(self) -> Tuple[float, ...]:
        return (
            self.origin_x, self.pixel_width, self.rotation_x,
            self.origin_y, self.rotation_y, self.pixel_height,
        )

    @classmethod
    def from_gdal_tuple(cls, gt: Tuple[float, ...]) -> "GeoTransform":
        return cls(
            origin_x=gt[0], pixel_width=gt[1], rotation_x=gt[2],
            origin_y=gt[3], rotation_y=gt[4], pixel_height=gt[5],
        )


@dataclass
class AlignmentResult:
    """对齐结果"""
    aligned_data: np.ndarray             # 对齐后的数据
    geo_transform: Tuple[float, ...]     # 对齐后的地理变换
    projection: str                      # 投影信息
    offset_x: float                      # X方向偏移（像素）
    offset_y: float                      # Y方向偏移（像素）
    scale_x: float = 1.0                 # X方向缩放
    scale_y: float = 1.0                 # Y方向缩放
    rmse: Optional[float] = None         # 配准均方根误差
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 地理对齐引擎
# ---------------------------------------------------------------------------

class GeoAlignmentEngine:
    """无缝地理对齐引擎

    负责将不同来源的空间数据统一到同一坐标参考系和栅格格网上。
    """

    def __init__(self, target_crs: Optional[CRSDefinition] = None):
        self.target_crs = target_crs or CRSDefinition.wgs84()

    def align_raster_to_base(
        self,
        source_data: np.ndarray,
        source_geo_transform: Tuple[float, ...],
        source_projection: str,
        base_geo_transform: Tuple[float, ...],
        base_shape: Tuple[int, int],
        base_projection: str = "EPSG:4326",
        no_data_value: float = np.nan,
    ) -> AlignmentResult:
        """将源栅格对齐到底图栅格格网上

        使用最近邻重采样将源栅格对齐到目标格网。

        Args:
            source_data: 源栅格数据
            source_geo_transform: 源地理变换参数
            source_projection: 源投影
            base_geo_transform: 底图地理变换参数
            base_shape: 底图形状 (rows, cols)
            base_projection: 底图投影
            no_data_value: 无数据填充值
        """
        if HAS_GDAL:
            return self._align_with_gdal(
                source_data, source_geo_transform, source_projection,
                base_geo_transform, base_shape, base_projection, no_data_value,
            )
        else:
            return self._align_with_numpy(
                source_data, source_geo_transform,
                base_geo_transform, base_shape, no_data_value,
            )

    def _align_with_gdal(
        self,
        source_data: np.ndarray,
        source_geo_transform: Tuple[float, ...],
        source_projection: str,
        base_geo_transform: Tuple[float, ...],
        base_shape: Tuple[int, int],
        base_projection: str,
        no_data_value: float,
    ) -> AlignmentResult:
        """使用GDAL进行重采样对齐"""
        import tempfile
        from osgeo import gdal

        base_rows, base_cols = base_shape

        # 将源数据写入临时文件
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_src:
            src_path = tmp_src.name

        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_dst:
            dst_path = tmp_dst.name

        try:
            # 创建源数据集
            driver = gdal.GetDriverByName("GTiff")
            bands = 1 if len(source_data.shape) == 2 else source_data.shape[2]
            src_ds = driver.Create(
                src_path, source_data.shape[1], source_data.shape[0],
                bands, gdal.GDT_Float64,
            )

            src_ds.SetGeoTransform(source_geo_transform)
            src_ds.SetProjection(source_projection)

            if bands == 1:
                src_ds.GetRasterBand(1).WriteArray(source_data)
            else:
                for b in range(bands):
                    src_ds.GetRasterBand(b + 1).WriteArray(source_data[:, :, b])

            src_ds.GetRasterBand(1).SetNoDataValue(no_data_value)
            src_ds.FlushCache()
            src_ds = None

            # 使用gdal.Warp进行重投影+对齐
            warp_options = gdal.WarpOptions(
                format="GTiff",
                outputBounds=(
                    base_geo_transform[0],
                    base_geo_transform[3] + base_rows * base_geo_transform[5],
                    base_geo_transform[0] + base_cols * base_geo_transform[1],
                    base_geo_transform[3],
                ),
                width=base_cols,
                height=base_rows,
                srcSRS=source_projection,
                dstSRS=base_projection,
                resampleAlg=gdal.GRA_NearestNeighbour,
                srcNodata=no_data_value,
                dstNodata=no_data_value,
            )

            gdal.Warp(dst_path, src_path, options=warp_options)

            # 读取结果
            dst_ds = gdal.Open(dst_path)
            if dst_ds is None:
                raise RuntimeError("GDAL Warp失败")

            if bands == 1:
                result = dst_ds.GetRasterBand(1).ReadAsArray()
            else:
                result = np.zeros((base_rows, base_cols, bands), dtype=np.float64)
                for b in range(bands):
                    result[:, :, b] = dst_ds.GetRasterBand(b + 1).ReadAsArray()

            dst_ds = None

            return AlignmentResult(
                aligned_data=result,
                geo_transform=base_geo_transform,
                projection=base_projection,
                offset_x=0.0,
                offset_y=0.0,
                metadata={"method": "gdal_warp"},
            )

        finally:
            import os
            for p in [src_path, dst_path]:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def _align_with_numpy(
        self,
        source_data: np.ndarray,
        source_geo_transform: Tuple[float, ...],
        base_geo_transform: Tuple[float, ...],
        base_shape: Tuple[int, int],
        no_data_value: float,
    ) -> AlignmentResult:
        """纯NumPy对齐（无GDAL后备方案）—— 仅适用于同一投影"""
        base_rows, base_cols = base_shape
        src_rows, src_cols = source_data.shape[:2]
        is_multi_band = len(source_data.shape) == 3

        # 计算源数据在底图格网中的位置
        src_gt = GeoTransform.from_gdal_tuple(source_geo_transform)
        base_gt = GeoTransform.from_gdal_tuple(base_geo_transform)

        # 简化：假设同一投影，仅平移+缩放
        scale_x = src_gt.pixel_width / base_gt.pixel_width
        scale_y = abs(src_gt.pixel_height) / abs(base_gt.pixel_height)

        offset_x = int(round((src_gt.origin_x - base_gt.origin_x) / base_gt.pixel_width))
        offset_y = int(round((src_gt.origin_y - base_gt.origin_y) / base_gt.pixel_height))

        # 创建输出数组
        if is_multi_band:
            result = np.full(
                (base_rows, base_cols, source_data.shape[2]),
                no_data_value, dtype=np.float64,
            )
        else:
            result = np.full((base_rows, base_cols), no_data_value, dtype=np.float64)

        # 最近邻重采样
        src_y_indices = (np.arange(base_rows) - offset_y) / scale_y
        src_x_indices = (np.arange(base_cols) - offset_x) / scale_x

        src_y_int = np.clip(np.round(src_y_indices).astype(int), 0, src_rows - 1)
        src_x_int = np.clip(np.round(src_x_indices).astype(int), 0, src_cols - 1)

        # 有效范围掩码
        valid_y = (src_y_indices >= 0) & (src_y_indices < src_rows)
        valid_x = (src_x_indices >= 0) & (src_x_indices < src_cols)

        for i in range(base_rows):
            if not valid_y[i]:
                continue
            for j in range(base_cols):
                if not valid_x[j]:
                    continue
                if is_multi_band:
                    result[i, j] = source_data[src_y_int[i], src_x_int[j]]
                else:
                    result[i, j] = source_data[src_y_int[i], src_x_int[j]]

        return AlignmentResult(
            aligned_data=result,
            geo_transform=base_geo_transform,
            projection="EPSG:4326",  # 假设同一投影
            offset_x=float(offset_x),
            offset_y=float(offset_y),
            scale_x=scale_x,
            scale_y=scale_y,
            metadata={"method": "numpy_nearest"},
        )

    def align_points_to_raster(
        self,
        points_x: np.ndarray,
        points_y: np.ndarray,
        geo_transform: Tuple[float, ...],
        raster_shape: Tuple[int, int],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """将地理坐标点转换为栅格行列号

        Args:
            points_x: 点X坐标（地理坐标）
            points_y: 点Y坐标（地理坐标）
            geo_transform: 栅格地理变换
            raster_shape: 栅格形状 (rows, cols)

        Returns:
            (row_indices, col_indices) 栅格行列号
        """
        gt = GeoTransform.from_gdal_tuple(geo_transform)
        rows, cols = raster_shape

        col_indices = ((points_x - gt.origin_x) / gt.pixel_width).astype(int)
        row_indices = ((points_y - gt.origin_y) / gt.pixel_height).astype(int)

        # 裁剪到有效范围
        col_indices = np.clip(col_indices, 0, cols - 1)
        row_indices = np.clip(row_indices, 0, rows - 1)

        return row_indices, col_indices

    def raster_to_grid_points(
        self,
        data: np.ndarray,
        geo_transform: Tuple[float, ...],
        stride: int = 1,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """将栅格转换为格网点坐标和值

        用于将反演结果网格点作为SamplingRecommender的输入。

        Args:
            data: 栅格数据
            geo_transform: 地理变换
            stride: 采样步长（每隔N个像元取一个点）
            min_value: 值域下限过滤
            max_value: 值域上限过滤

        Returns:
            (x_coords, y_coords, values) 有效点的坐标和值
        """
        gt = GeoTransform.from_gdal_tuple(geo_transform)
        rows, cols = data.shape[:2]

        # 生成坐标网格
        row_indices = np.arange(0, rows, stride)
        col_indices = np.arange(0, cols, stride)

        x_coords = gt.origin_x + col_indices * gt.pixel_width
        y_coords = gt.origin_y + row_indices * gt.pixel_height

        xx, yy = np.meshgrid(x_coords, y_coords)

        # 提取值
        if len(data.shape) == 3:
            values = np.mean(data[::stride, ::stride], axis=2).flatten()
        else:
            values = data[::stride, ::stride].flatten()

        x_flat = xx.flatten()
        y_flat = yy.flatten()

        # 过滤无效值
        valid_mask = ~np.isnan(values)
        if min_value is not None:
            valid_mask &= values >= min_value
        if max_value is not None:
            valid_mask &= values <= max_value

        return x_flat[valid_mask], y_flat[valid_mask], values[valid_mask]

    @staticmethod
    def validate_alignment(
        source_coords: np.ndarray,
        target_coords: np.ndarray,
        tolerance: float = 1.0,
    ) -> Dict[str, Any]:
        """验证两组坐标的对齐精度"""
        if len(source_coords) != len(target_coords):
            return {"valid": False, "error": "坐标数量不一致"}

        diffs = source_coords - target_coords
        rmse = float(np.sqrt(np.mean(diffs**2)))
        max_error = float(np.max(np.abs(diffs)))

        return {
            "valid": rmse < tolerance,
            "rmse": rmse,
            "max_error": max_error,
            "mean_error": float(np.mean(np.abs(diffs))),
            "tolerance": tolerance,
        }

    def coordinate_transform(
        self,
        x: float, y: float,
        source_epsg: int,
        target_epsg: int = 4326,
    ) -> Tuple[float, float]:
        """坐标系统转换"""
        if source_epsg == target_epsg:
            return x, y

        if HAS_GDAL:
            src_srs = osr.SpatialReference()
            src_srs.ImportFromEPSG(source_epsg)
            dst_srs = osr.SpatialReference()
            dst_srs.ImportFromEPSG(target_epsg)

            transform = osr.CoordinateTransformation(src_srs, dst_srs)
            point = ogr.CreateGeometryFromWkt(f"POINT ({x} {y})")
            point.Transform(transform)

            return point.GetX(), point.GetY()

        # 无GDAL时，仅支持WGS84 <-> Web Mercator
        if {source_epsg, target_epsg} == {4326, 3857}:
            if source_epsg == 4326:
                return self._wgs84_to_mercator(x, y)
            else:
                return self._mercator_to_wgs84(x, y)

        logger.warning(f"无GDAL环境，无法进行EPSG:{source_epsg}->EPSG:{target_epsg}转换")
        return x, y

    @staticmethod
    def _wgs84_to_mercator(lon: float, lat: float) -> Tuple[float, float]:
        """WGS84 -> Web Mercator"""
        R = 6378137.0
        x = R * np.radians(lon)
        y = R * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
        return x, y

    @staticmethod
    def _mercator_to_wgs84(x: float, y: float) -> Tuple[float, float]:
        """Web Mercator -> WGS84"""
        R = 6378137.0
        lon = np.degrees(x / R)
        lat = np.degrees(2 * np.arctan(np.exp(y / R)) - np.pi / 2)
        return lon, lat
