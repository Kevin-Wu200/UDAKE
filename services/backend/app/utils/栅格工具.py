"""
栅格工具
"""
import logging

import numpy as np
from osgeo import gdal, osr

from ..config import settings

logger = logging.getLogger(__name__)

class RasterUtils:
    """栅格处理工具"""

    def save_geotiff(
        self,
        task_id: str,
        data: np.ndarray,
        x_coords: np.ndarray,
        y_coords: np.ndarray,
        data_type: str = "prediction"
    ) -> str:
        """
        保存为GeoTIFF格式
        """
        # 文件路径
        filename = f"{task_id}_{data_type}.tif"
        filepath = settings.RESULTS_DIR / filename

        # 获取数据范围
        x_min, x_max = x_coords.min(), x_coords.max()
        y_min, y_max = y_coords.min(), y_coords.max()

        # 计算像素大小
        rows, cols = data.shape
        pixel_width = (x_max - x_min) / cols
        pixel_height = (y_max - y_min) / rows

        # 创建GeoTIFF
        driver = gdal.GetDriverByName('GTiff')
        dataset = driver.Create(
            str(filepath),
            cols,
            rows,
            1,
            gdal.GDT_Float32
        )

        # 设置地理变换
        geotransform = (
            x_min,
            pixel_width,
            0,
            y_max,
            0,
            -pixel_height
        )
        dataset.SetGeoTransform(geotransform)

        # 设置投影
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        dataset.SetProjection(srs.ExportToWkt())

        # 写入数据
        band = dataset.GetRasterBand(1)
        band.WriteArray(data)
        band.SetNoDataValue(-9999)

        # 关闭数据集
        dataset = None

        logger.info(f"GeoTIFF已保存: {filepath}")
        return str(filepath)

    def read_geotiff(self, filepath: str) -> np.ndarray:
        """读取GeoTIFF"""
        dataset = gdal.Open(filepath)
        if dataset is None:
            raise ValueError(f"无法打开文件: {filepath}")

        band = dataset.GetRasterBand(1)
        data = band.ReadAsArray()

        dataset = None
        return data
