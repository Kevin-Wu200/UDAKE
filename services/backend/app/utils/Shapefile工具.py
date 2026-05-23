"""
Shapefile工具
"""
import logging
from pathlib import Path

import numpy as np
import shapefile

logger = logging.getLogger(__name__)


class ShapefileUtils:
    """Shapefile处理工具"""

    @staticmethod
    def raster_to_shapefile(
        data: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        filepath: Path,
        property_name: str = "value"
    ) -> str:
        """
        将栅格数据转换为点 Shapefile

        Args:
            data: 二维栅格数据
            x_coords: X 坐标数组
            y_coords: Y 坐标数组
            filepath: 输出文件路径（不含扩展名）
            property_name: 属性字段名

        Returns:
            输出文件路径
        """
        filepath = Path(filepath)
        # 去掉扩展名，shapefile 库会自动添加 .shp/.shx/.dbf
        stem = filepath.with_suffix('')

        w = shapefile.Writer(str(stem))
        w.field(property_name, 'N', decimal=6)

        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                value = float(data[i, j])
                if not np.isnan(value):
                    w.point(float(x_coords[j]), float(y_coords[i]))
                    w.record(value)

        w.close()

        # 写入 .prj 投影文件 (WGS84)
        prj_path = stem.with_suffix('.prj')
        prj_content = (
            'GEOGCS["GCS_WGS_1984",'
            'DATUM["D_WGS_1984",'
            'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
            'PRIMEM["Greenwich",0.0],'
            'UNIT["Degree",0.0174532925199433]]'
        )
        with open(prj_path, 'w') as f:
            f.write(prj_content)

        logger.info(f"Shapefile 已保存: {stem}.shp")
        return str(stem) + '.shp'

    @staticmethod
    def save_from_geotiff(
        geotiff_path: str,
        output_path: Path,
        property_name: str = "value"
    ) -> str:
        """
        从 GeoTIFF 文件转换为 Shapefile

        Args:
            geotiff_path: GeoTIFF 文件路径
            output_path: 输出 Shapefile 路径
            property_name: 属性字段名

        Returns:
            输出文件路径
        """
        from osgeo import gdal

        dataset = gdal.Open(geotiff_path)
        if dataset is None:
            raise ValueError(f"无法打开文件: {geotiff_path}")

        band = dataset.GetRasterBand(1)
        data = band.ReadAsArray()
        nodata = band.GetNoDataValue()

        gt = dataset.GetGeoTransform()
        cols = dataset.RasterXSize
        rows = dataset.RasterYSize

        x_coords = np.array([gt[0] + j * gt[1] + gt[1] / 2 for j in range(cols)])
        y_coords = np.array([gt[3] + i * gt[5] + gt[5] / 2 for i in range(rows)])

        dataset = None

        # 将 nodata 值替换为 NaN
        if nodata is not None:
            data = data.astype(float)
            data[data == nodata] = np.nan

        return ShapefileUtils.raster_to_shapefile(
            data, x_coords, y_coords, output_path, property_name
        )
