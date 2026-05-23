"""
普通克里金引擎
"""
import logging
from typing import Any, Dict

import numpy as np
from pykrige.ok import OrdinaryKriging

from ..config import settings
from ..core.交叉验证模块 import CrossValidator
from ..schemas.插值参数模型 import KrigingParameters
from ..schemas.数据模型 import SpatialData
from ..utils.GeoJSON工具 import GeoJSONUtils
from ..utils.Shapefile工具 import ShapefileUtils
from ..utils.栅格工具 import RasterUtils

logger = logging.getLogger(__name__)

class OrdinaryKrigingEngine:
    """普通克里金引擎"""

    def __init__(self):
        self.raster_utils = RasterUtils()
        self.cross_validator = CrossValidator()

    def interpolate(
        self,
        task_id: str,
        spatial_data: SpatialData,
        params: KrigingParameters
    ) -> Dict[str, Any]:
        """
        执行普通克里金插值
        """
        # 提取坐标和值
        x = np.array([p.x for p in spatial_data.points])
        y = np.array([p.y for p in spatial_data.points])
        values = np.array([p.value for p in spatial_data.points])

        logger.info(f"数据范围: X[{x.min():.2f}, {x.max():.2f}], Y[{y.min():.2f}, {y.max():.2f}]")

        # 创建克里金对象
        ok = OrdinaryKriging(
            x, y, values,
            variogram_model=params.variogram_model.value,
            nlags=params.nlags,
            enable_plotting=False
        )

        # 生成网格
        grid_x = np.linspace(x.min(), x.max(), params.grid_resolution)
        grid_y = np.linspace(y.min(), y.max(), params.grid_resolution)

        # 执行插值
        z, ss = ok.execute('grid', grid_x, grid_y)

        # 保存结果
        prediction_path = self.raster_utils.save_geotiff(
            task_id, z, grid_x, grid_y, "prediction"
        )
        variance_path = self.raster_utils.save_geotiff(
            task_id, ss, grid_x, grid_y, "variance"
        )

        # 交叉验证
        cv_metrics = None
        if params.enable_cross_validation:
            cv_metrics = self.cross_validator.validate(x, y, values, params)

        # 导出 GeoJSON
        prediction_geojson = GeoJSONUtils.raster_to_points(z, grid_x, grid_y, "prediction")
        prediction_geojson_path = settings.RESULTS_DIR / f"{task_id}_prediction.geojson"
        GeoJSONUtils.save_geojson(prediction_geojson, prediction_geojson_path)

        variance_geojson = GeoJSONUtils.raster_to_points(ss, grid_x, grid_y, "variance")
        variance_geojson_path = settings.RESULTS_DIR / f"{task_id}_variance.geojson"
        GeoJSONUtils.save_geojson(variance_geojson, variance_geojson_path)

        logger.info(f"GeoJSON 已导出: {prediction_geojson_path}, {variance_geojson_path}")

        # 导出 Shapefile
        prediction_shp_path = ShapefileUtils.raster_to_shapefile(
            z, grid_x, grid_y,
            settings.RESULTS_DIR / f"{task_id}_prediction.shp",
            "prediction"
        )
        variance_shp_path = ShapefileUtils.raster_to_shapefile(
            ss, grid_x, grid_y,
            settings.RESULTS_DIR / f"{task_id}_variance.shp",
            "variance"
        )
        logger.info(f"Shapefile 已导出: {prediction_shp_path}, {variance_shp_path}")

        # 统计信息
        prediction_stats = {
            "mean": float(np.mean(z)),
            "std": float(np.std(z)),
            "min": float(np.min(z)),
            "max": float(np.max(z))
        }

        variance_stats = {
            "mean": float(np.mean(ss)),
            "std": float(np.std(ss)),
            "min": float(np.min(ss)),
            "max": float(np.max(ss))
        }

        return {
            "prediction_path": prediction_path,
            "variance_path": variance_path,
            "prediction_geojson_path": str(prediction_geojson_path),
            "variance_geojson_path": str(variance_geojson_path),
            "prediction_shp_path": prediction_shp_path,
            "variance_shp_path": variance_shp_path,
            "prediction_stats": prediction_stats,
            "variance_stats": variance_stats,
            "cross_validation": cv_metrics,
            "grid_shape": z.shape
        }
