"""
采样建议接口 - 基于不确定性分析的智能采样点推荐
"""
from fastapi import APIRouter, HTTPException, Depends
from ..schemas.输出结果模型 import SamplingRecommendation, SamplingRecommendationsResponse
from ..tasks.任务管理器 import TaskManager
from ..dependencies import verify_task_id
from adaptive_sampling.采样点推荐生成 import SamplingRecommender
from adaptive_sampling.高不确定性区域识别 import HighUncertaintyIdentifier
from ai_extension.采样优化建议模型 import SamplingOptimizer
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
task_manager = TaskManager()
sampling_recommender = SamplingRecommender()
uncertainty_identifier = HighUncertaintyIdentifier()
sampling_optimizer = SamplingOptimizer()


class GenerateRecommendationsRequest:
    """生成采样建议请求"""
    def __init__(
        self,
        task_id: str,
        strategy: str = "hybrid",
        n_recommendations: int = 20,
        threshold_percentile: float = 75
    ):
        self.task_id = task_id
        self.strategy = strategy
        self.n_recommendations = n_recommendations
        self.threshold_percentile = threshold_percentile


@router.post("/sampling-recommendations/generate", response_model=SamplingRecommendationsResponse)
async def generate_recommendations(
    task_id: str,
    strategy: str = "hybrid",
    n_recommendations: int = 20,
    threshold_percentile: float = 75
):
    """
    生成采样建议

    基于克里金插值的不确定性分析，智能推荐下一步采样位置

    参数:
    - task_id: 任务ID
    - strategy: 采样策略
      - variance_based: 基于方差优先（推荐高不确定性区域）
      - spatial_coverage: 基于空间覆盖（填补空白区域）
      - hybrid: 混合策略（70%高方差 + 30%均匀分布）
    - n_recommendations: 建议点数量（默认20）
    - threshold_percentile: 高不确定性阈值百分位（默认75）
    """
    try:
        # 验证任务
        verify_task_id(task_id)

        # 直接从文件路径读取结果
        from ..utils.栅格工具 import RasterUtils
        from ..config import settings

        raster_utils = RasterUtils()

        # 构建文件路径
        variance_path = settings.RESULTS_DIR / f"{task_id}_variance.tif"
        prediction_path = settings.RESULTS_DIR / f"{task_id}_prediction.tif"

        if not variance_path.exists():
            raise HTTPException(status_code=404, detail="方差栅格不存在，请先完成插值计算")

        # 验证文件大小
        file_size = variance_path.stat().st_size
        if file_size == 0:
            raise HTTPException(status_code=400, detail="方差栅格文件为空，请重新生成")
        if file_size > 500 * 1024 * 1024:  # 500MB 限制
            raise HTTPException(status_code=400, detail="方差栅格文件过大，超过500MB限制")

        # 读取方差栅格
        from osgeo import gdal
        try:
            dataset = gdal.Open(str(variance_path))
        except Exception as e:
            logger.error(f"GDAL打开文件失败: {str(e)}")
            raise HTTPException(status_code=500, detail="无法读取栅格文件，请检查文件格式")

        if dataset is None:
            raise HTTPException(status_code=404, detail="无法打开方差栅格文件，文件可能已损坏")

        # 验证栅格格式
        if dataset.RasterCount < 1:
            dataset = None
            raise HTTPException(status_code=400, detail="栅格文件不包含任何波段")

        # 读取数据
        band = dataset.GetRasterBand(1)
        if band is None:
            dataset = None
            raise HTTPException(status_code=400, detail="无法获取栅格波段")

        variance = band.ReadAsArray()

        # 验证数据完整性
        if variance is None or variance.size == 0:
            dataset = None
            raise HTTPException(status_code=400, detail="栅格数据为空，请重新生成")

        # 检查数据是否包含有效值
        if np.all(np.isnan(variance)):
            dataset = None
            raise HTTPException(status_code=400, detail="栅格数据全部为无效值，请重新生成")

        # 获取地理变换参数
        transform = dataset.GetGeoTransform()

        # 生成坐标网格
        cols = dataset.RasterXSize
        rows = dataset.RasterYSize

        x_coords = np.array([transform[0] + transform[1] * x for x in range(cols)])
        y_coords = np.array([transform[3] + transform[5] * y for y in range(rows)])

        dataset = None

        # 尝试从任务管理器获取原始数据点，如果失败则跳过
        existing_points = None
        try:
            task_info = task_manager.get_task_info(task_id)
            if task_info and task_info.data_id:
                from ..schemas.数据模型 import SpatialData
                spatial_data = task_manager.get_spatial_data(task_info.data_id)
                if spatial_data:
                    existing_points = np.array([[p.x, p.y] for p in spatial_data.points])
        except Exception as e:
            logger.warning(f"获取原始采样点失败: {str(e)}，将不使用现有采样点信息")
            existing_points = None

        # 生成基础推荐
        base_recommendations = sampling_recommender.generate_recommendations(
            variance=variance,
            x_coords=x_coords,
            y_coords=y_coords,
            existing_points=existing_points,
            n_recommendations=n_recommendations,
            strategy=strategy
        )

        # 识别高不确定性区域
        high_uncertainty_regions = uncertainty_identifier.identify_high_uncertainty_regions(
            variance=variance,
            x_coords=x_coords,
            y_coords=y_coords,
            threshold_percentile=threshold_percentile
        )

        # 为每个建议点添加详细标注
        recommendations = []
        for idx, rec in enumerate(base_recommendations["recommendations"]):
            # 计算不确定性等级（1-5）
            variance_percentile = (np.percentile(variance, rec["variance"] * 100 / np.max(variance)))
            uncertainty_level = int(np.ceil(variance_percentile * 5 / 100))

            # 计算距离最近采样点的距离
            if existing_points is not None and len(existing_points) > 0:
                distances = np.sqrt(np.sum((existing_points - np.array([rec["x"], rec["y"]])) ** 2, axis=1))
                distance_to_nearest = float(np.min(distances))
            else:
                # 使用一个很大的值表示无限远，避免JSON序列化错误
                distance_to_nearest = 999999.0

            # 查找所属区域
            region_id = None
            for region in high_uncertainty_regions["regions"]:
                # 简化判断：如果点在区域中心附近
                dist_to_center = np.sqrt(
                    (rec["x"] - region["center"]["x"]) ** 2 +
                    (rec["y"] - region["center"]["y"]) ** 2
                )
                if dist_to_center < np.sqrt(region["area"]) * 0.5:
                    region_id = region["region_id"]
                    break

            # 生成采样理由
            if rec["priority"] == "high":
                sampling_reason = f"该区域不确定性较高（方差={rec['variance']:.4f}），采样可显著降低整体误差"
            elif region_id:
                sampling_reason = f"属于高不确定性区域 #{region_id}，建议优先采样"
            else:
                sampling_reason = "填补采样空白区域，提高空间覆盖度"

            # 计算预期收益（方差减少量估计）
            expected_benefit = rec["variance"] * 0.3  # 简化估计

            recommendations.append(SamplingRecommendation(
                id=rec["id"],
                x=rec["x"],
                y=rec["y"],
                variance=rec["variance"],
                priority=rec["priority"],
                uncertainty_level=uncertainty_level,
                region_id=region_id,
                distance_to_nearest=distance_to_nearest,
                sampling_reason=sampling_reason,
                expected_benefit=expected_benefit
            ))

        # 统计信息
        statistics = {
            "total_variance": float(np.sum(variance)),
            "mean_variance": float(np.mean(variance)),
            "max_variance": float(np.max(variance)),
            "high_uncertainty_regions": high_uncertainty_regions["num_regions"],
            "threshold": float(high_uncertainty_regions["threshold"]),
            "existing_points": len(existing_points) if existing_points is not None else 0
        }

        return SamplingRecommendationsResponse(
            task_id=task_id,
            strategy=strategy,
            n_recommendations=len(recommendations),
            recommendations=recommendations,
            statistics=statistics,
            generated_at=datetime.now()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成采样建议失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成采样建议失败: {str(e)}")


@router.get("/sampling-recommendations/{task_id}", response_model=SamplingRecommendationsResponse)
async def get_recommendations(task_id: str = Depends(verify_task_id)):
    """
    获取已生成的采样建议

    如果未生成，则自动生成（使用默认参数）
    """
    try:
        # 尝试从缓存获取（可选实现）
        # 这里简化为每次重新生成
        return await generate_recommendations(task_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取采样建议失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取采样建议失败: {str(e)}")


@router.get("/sampling-recommendations/export/{task_id}")
async def export_recommendations_geojson(task_id: str = Depends(verify_task_id)):
    """
    导出采样建议为GeoJSON格式
    """
    try:
        recommendations_response = await get_recommendations(task_id)

        # 转换为GeoJSON
        features = []
        for rec in recommendations_response.recommendations:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [rec.x, rec.y]
                },
                "properties": {
                    "id": rec.id,
                    "variance": rec.variance,
                    "priority": rec.priority,
                    "uncertainty_level": rec.uncertainty_level,
                    "region_id": rec.region_id,
                    "distance_to_nearest": rec.distance_to_nearest,
                    "sampling_reason": rec.sampling_reason,
                    "expected_benefit": rec.expected_benefit
                }
            }
            features.append(feature)

        geojson = {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": "EPSG:4326"}
            },
            "features": features
        }

        from fastapi.responses import JSONResponse
        return JSONResponse(content=geojson)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出采样建议失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导出采样建议失败: {str(e)}")