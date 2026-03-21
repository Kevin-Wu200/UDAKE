"""
3D克里金调度器
统一管理普通克里金、泛克里金、指示克里金
"""
import numpy as np
from typing import Dict, Any, Optional
from ..schemas.参数模型 import KrigingParameters3D, KrigingMethod3D
from ..schemas.数据模型 import SpatialData3D
from .普通克里金3D import OrdinaryKriging3D
from .泛克里金3D import UniversalKriging3D
from .指示克里金3D import IndicatorKriging3D
import logging

logger = logging.getLogger(__name__)


class KrigingScheduler3D:
    """3D克里金调度器"""

    def __init__(self):
        self.ok3d = OrdinaryKriging3D()
        self.uk3d = UniversalKriging3D()
        self.ik3d = IndicatorKriging3D()

    def execute(
        self,
        task_id: str,
        spatial_data: SpatialData3D,
        params: KrigingParameters3D
    ) -> Dict[str, Any]:
        """执行3D克里金插值"""
        points = np.array([[p.x, p.y, p.z] for p in spatial_data.points])
        values = np.array([p.value for p in spatial_data.points])

        # 生成网格
        grid_x = np.linspace(points[:, 0].min(), points[:, 0].max(), params.grid_resolution_x)
        grid_y = np.linspace(points[:, 1].min(), points[:, 1].max(), params.grid_resolution_y)
        grid_z = np.linspace(points[:, 2].min(), points[:, 2].max(), params.grid_resolution_z)

        # 各向异性参数
        aniso = None
        if params.enable_anisotropy and params.anisotropy:
            aniso = {
                "ratio_xy": params.anisotropy.ratio_xy,
                "ratio_xz": params.anisotropy.ratio_xz,
                "angle_xy": params.anisotropy.angle_xy,
                "angle_xz": params.anisotropy.angle_xz,
                "angle_yz": params.anisotropy.angle_yz,
            }

        logger.info(f"任务 {task_id}: 方法={params.method.value}, "
                     f"网格={params.grid_resolution_x}x{params.grid_resolution_y}x{params.grid_resolution_z}, "
                     f"点数={len(points)}")

        if params.method == KrigingMethod3D.ORDINARY:
            result = self.ok3d.interpolate(
                points, values, grid_x, grid_y, grid_z,
                variogram_model=params.variogram_model.value,
                nlags=params.nlags,
                n_closest=params.n_closest,
                anisotropy_params=aniso
            )
        elif params.method == KrigingMethod3D.UNIVERSAL:
            result = self.uk3d.interpolate(
                points, values, grid_x, grid_y, grid_z,
                variogram_model=params.variogram_model.value,
                nlags=params.nlags,
                n_closest=params.n_closest,
                drift_terms=params.drift_terms,
                anisotropy_params=aniso
            )
        elif params.method == KrigingMethod3D.INDICATOR:
            if params.indicator_threshold is None:
                params.indicator_threshold = float(np.median(values))
            result = self.ik3d.interpolate(
                points, values, grid_x, grid_y, grid_z,
                threshold=params.indicator_threshold,
                variogram_model=params.variogram_model.value,
                nlags=params.nlags,
                n_closest=params.n_closest,
                anisotropy_params=aniso
            )
        else:
            raise ValueError(f"不支持的3D克里金方法: {params.method}")

        result["task_id"] = task_id
        result["method"] = params.method.value
        result["grid_shape"] = [params.grid_resolution_x, params.grid_resolution_y, params.grid_resolution_z]
        return result