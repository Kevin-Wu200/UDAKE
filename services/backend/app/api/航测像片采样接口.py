"""
航测像片采样推荐 API 接口
==========================
提供航测像片上传、反演计算、采样推荐的一站式 REST API。

端点:
- POST /api/aerial/upload          - 上传航测像片
- POST /api/aerial/parse-metadata  - 解析像片EXIF元数据
- POST /api/aerial/assess-quality  - 评估影像质量
- POST /api/aerial/orthorectify    - 正射校正
- POST /api/aerial/invert          - 遥感反演
- POST /api/aerial/recommend       - 生成采样推荐
- POST /api/aerial/full-pipeline   - 全流程一键处理
- GET  /api/aerial/status/{task_id} - 查询任务状态
"""
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

# 确保项目根目录在路径中
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import logging

from adaptive_sampling.采样点推荐生成 import SamplingRecommender
from adaptive_sampling.采样策略融合 import SamplingFusionEngine
from photogrammetry.exif_parser import AerialImageMetadata, ExifParser
from photogrammetry.geo_alignment import GeoAlignmentEngine
from photogrammetry.image_quality import ImageQualityAssessor
from photogrammetry.orthorectification import (
    OrthorectificationEngine,
)
from remote_sensing.environment import EnvironmentInverter, EnvironmentResult
from remote_sensing.forestry import ForestryInverter, ForestryResult
from remote_sensing.uncertainty_mapping import UncertaintyGrid, UncertaintyMapper
from remote_sensing.water_quality import (
    SpectralBands,
    WaterQualityInverter,
    WaterQualityResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局单例
exif_parser = ExifParser()
quality_assessor = ImageQualityAssessor()
ortho_engine = OrthorectificationEngine()
geo_engine = GeoAlignmentEngine()
water_inverter = WaterQualityInverter()
forestry_inverter = ForestryInverter()
env_inverter = EnvironmentInverter()
uncertainty_mapper = UncertaintyMapper()
fusion_engine = SamplingFusionEngine()
sampling_recommender = SamplingRecommender()

# 任务存储（生产环境应使用数据库）
_task_store: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class MetadataResponse(BaseModel):
    """元数据解析响应"""
    file_name: str
    file_size_bytes: int
    image_format: str
    gps: Dict[str, Any]
    imu: Dict[str, Any]
    camera: Dict[str, Any]
    capture_time: Optional[str] = None


class QualityResponse(BaseModel):
    """质量评估响应"""
    file_path: str
    blur_score: float
    exposure_score: float
    tilt_angle: float
    overall_score: float
    quality_level: str
    recommendations: List[str]


class InversionRequest(BaseModel):
    """反演请求"""
    task_id: str
    scenario: str = Field("water", description="反演场景: water/forestry/environment/all")
    method_params: Dict[str, Any] = Field(default_factory=dict)


class InversionSummary(BaseModel):
    """反演摘要"""
    scenario: str
    indicators: Dict[str, Dict[str, float]]
    anomaly_count: int


class PipelineRequest(BaseModel):
    """全流程请求"""
    scenario: str = Field("all", description="反演场景: water/forestry/environment/all")
    strategy: str = Field("hybrid", description="采样策略")
    n_recommendations: int = Field(20, ge=1, le=100, description="建议点数量")
    ground_resolution: float = Field(0.1, description="地面分辨率(米)")


class RecommendationItem(BaseModel):
    """采样建议项"""
    id: int
    x: float
    y: float
    variance: float
    priority: str
    uncertainty_level: int
    sampling_reason: str
    expected_benefit: float


class PipelineResponse(BaseModel):
    """全流程响应"""
    task_id: str
    status: str
    metadata: Optional[Dict[str, Any]] = None
    quality: Optional[Dict[str, Any]] = None
    inversion_summary: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[RecommendationItem]] = None
    geo_transform: Optional[List[float]] = None
    processing_time_ms: float = 0.0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.post("/aerial/parse-metadata", response_model=MetadataResponse)
async def parse_metadata(file: UploadFile = File(...)):
    """
    解析航测像片的EXIF元数据

    自动识别GPS（经纬高）及IMU（姿态角：Pitch, Roll, Yaw）
    """
    try:
        # 保存上传文件到临时目录
        tmp_path = Path(tempfile.gettempdir()) / f"aerial_{uuid.uuid4().hex[:8]}_{file.filename}"
        content = await file.read()
        tmp_path.write_bytes(content)

        # 解析元数据
        metadata = exif_parser.parse(str(tmp_path))

        # 清理临时文件
        try:
            tmp_path.unlink()
        except OSError:
            pass

        return MetadataResponse(
            file_name=metadata.file_name,
            file_size_bytes=metadata.file_size_bytes,
            image_format=metadata.image_format,
            gps=metadata.gps.to_dict(),
            imu=metadata.imu.to_dict(),
            camera=metadata.camera.to_dict(),
            capture_time=metadata.capture_time.isoformat() if metadata.capture_time else None,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"解析元数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"解析元数据失败: {str(e)}")


@router.post("/aerial/assess-quality", response_model=QualityResponse)
async def assess_quality(file: UploadFile = File(...)):
    """
    评估航测影像质量

    分析模糊度、曝光值和倾斜程度
    """
    try:
        tmp_path = Path(tempfile.gettempdir()) / f"aerial_q_{uuid.uuid4().hex[:8]}_{file.filename}"
        content = await file.read()
        tmp_path.write_bytes(content)

        # 解析元数据（用于倾斜评估）
        metadata = exif_parser.parse(str(tmp_path))

        # 质量评估
        quality = quality_assessor.assess_all(str(tmp_path), metadata)

        try:
            tmp_path.unlink()
        except OSError:
            pass

        return QualityResponse(
            file_path=file.filename or "unknown",
            blur_score=quality.blur.blur_score,
            exposure_score=quality.exposure.exposure_score,
            tilt_angle=quality.tilt.tilt_angle,
            overall_score=quality.overall_score,
            quality_level=quality.quality_level,
            recommendations=quality.recommendations,
        )

    except Exception as e:
        logger.error(f"质量评估失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"质量评估失败: {str(e)}")


@router.post("/aerial/invert")
async def invert_remote_sensing(request: InversionRequest):
    """
    执行遥感反演计算

    根据场景类型执行对应的专题反演：
    - water: 水质5项指标
    - forestry: 林业5项指标
    - environment: 环境4项指标
    - all: 全部14项指标
    """
    try:
        task_id = request.task_id
        task_data = _task_store.get(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        # 构建模拟多光谱波段（实际应从纠正后的影像提取）
        # 这里使用矫正后的影像模拟波段提取
        ortho_result = task_data.get("ortho_result")
        if ortho_result is None:
            raise HTTPException(status_code=400, detail="请先完成正射校正")

        ortho_image = task_data.get("ortho_image")
        if ortho_image is None:
            raise HTTPException(status_code=400, detail="正射影像数据缺失")

        # 模拟多光谱波段（基于RGB影像的分量）
        bands = _simulate_multispectral_bands(ortho_image)

        results = {}
        scenario = request.scenario

        if scenario in ("water", "all"):
            water_result = water_inverter.retrieve_all(bands)
            results["water"] = water_result.to_dict_summary()

        if scenario in ("forestry", "all"):
            forestry_result = forestry_inverter.retrieve_all(bands)
            results["forestry"] = forestry_result.to_dict_summary()

        if scenario in ("environment", "all"):
            env_result = env_inverter.retrieve_all(bands)
            results["environment"] = env_result.to_dict_summary()

        # 生成不确定性网格
        uncertainty_grids = _generate_uncertainty_grids(
            water_result if scenario in ("water", "all") else None,
            forestry_result if scenario in ("forestry", "all") else None,
            env_result if scenario in ("environment", "all") else None,
            ortho_result,
        )

        # 保存反演结果
        task_data["inversion_results"] = {
            "water": water_result if scenario in ("water", "all") else None,
            "forestry": forestry_result if scenario in ("forestry", "all") else None,
            "environment": env_result if scenario in ("environment", "all") else None,
        }
        task_data["uncertainty_grids"] = uncertainty_grids
        task_data["status"] = "inversion_done"

        return {
            "task_id": task_id,
            "status": "inversion_done",
            "scenario": scenario,
            "summary": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"反演计算失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"反演计算失败: {str(e)}")


@router.post("/aerial/recommend", response_model=PipelineResponse)
async def generate_aerial_recommendations(
    task_id: str = Form(...),
    strategy: str = Form("hybrid"),
    n_recommendations: int = Form(20),
):
    """
    基于反演结果生成采样推荐

    将反演网格点作为SamplingRecommender输入，
    基于物理指标异常值自动提升采样优先级。
    """
    try:
        task_data = _task_store.get(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        if "inversion_results" not in task_data:
            raise HTTPException(status_code=400, detail="请先完成遥感反演")

        start_time = datetime.now()

        # 收集反演值和不确定性
        inversion_values = {}
        uncertainty_grids = task_data.get("uncertainty_grids", {})

        for scenario_key in ["water", "forestry", "environment"]:
            result = task_data["inversion_results"].get(scenario_key)
            if result is None:
                continue

            if scenario_key == "water" and isinstance(result, WaterQualityResult):
                for name in ["chl_a", "tsm", "turbidity", "sdd", "cod"]:
                    val = getattr(result, name)
                    if val is not None and val.size > 0:
                        inversion_values[name] = val

            elif scenario_key == "forestry" and isinstance(result, ForestryResult):
                for name in ["volume", "biomass", "fvc"]:
                    val = getattr(result, name)
                    if val is not None and val.size > 0:
                        inversion_values[name] = val
                if result.vegetation_indices and result.vegetation_indices.ndvi is not None:
                    inversion_values["ndvi"] = result.vegetation_indices.ndvi

            elif scenario_key == "environment" and isinstance(result, EnvironmentResult):
                for name in ["soil_moisture", "heavy_metal_stress", "lst", "runoff_coefficient"]:
                    val = getattr(result, name)
                    if val is not None and val.size > 0:
                        inversion_values[name] = val

        # 默认地理变换
        geo_transform = task_data.get("geo_transform", (0.0, 0.0001, 0.0, 0.0, 0.0, -0.0001))

        # 融合为综合方差
        fusion_result = fusion_engine.fuse_inversion_to_variance(
            inversion_values=inversion_values,
            inversion_uncertainties=uncertainty_grids,
            geo_transform=geo_transform,
        )

        # 生成推荐
        recommendations_data = fusion_engine.generate_sampling_recommendations(
            fusion_result=fusion_result,
            n_recommendations=n_recommendations,
            strategy=strategy,
        )

        # 转换格式
        recommendations = []
        for rec in recommendations_data.get("recommendations", []):
            recommendations.append(RecommendationItem(
                id=rec.get("id", 0),
                x=rec.get("x", 0),
                y=rec.get("y", 0),
                variance=rec.get("variance", 0),
                priority=rec.get("priority", "medium"),
                uncertainty_level=min(5, max(1, int(rec.get("variance", 0) * 10))),
                sampling_reason=rec.get("sampling_reason", ""),
                expected_benefit=rec.get("variance", 0) * 0.3,
            ))

        elapsed = (datetime.now() - start_time).total_seconds() * 1000

        # 更新任务状态
        task_data["recommendations"] = recommendations_data
        task_data["fusion_result"] = fusion_result
        task_data["status"] = "completed"

        return PipelineResponse(
            task_id=task_id,
            status="completed",
            inversion_summary=_build_inversion_summary(task_data),
            recommendations=recommendations,
            geo_transform=list(geo_transform) if geo_transform else None,
            processing_time_ms=elapsed,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成采样推荐失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成采样推荐失败: {str(e)}")


@router.post("/aerial/full-pipeline", response_model=PipelineResponse)
async def full_pipeline(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    scenario: str = Form("all"),
    strategy: str = Form("hybrid"),
    n_recommendations: int = Form(20),
):
    """
    全流程一键处理：上传 -> 解析 -> 评估 -> 纠正 -> 反演 -> 推荐

    这是最常用的端点，一次性完成从航测像片到采样建议的全流程。
    """
    task_id = uuid.uuid4().hex[:12]
    start_time = datetime.now()

    try:
        # 保存上传文件
        upload_dir = Path(tempfile.gettempdir()) / f"udake_aerial_{task_id}"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / (file.filename or "upload.jpg")
        content = await file.read()
        file_path.write_bytes(content)

        # 初始化任务
        _task_store[task_id] = {
            "task_id": task_id,
            "status": "processing",
            "file_path": str(file_path),
            "file_name": file.filename,
            "created_at": datetime.now(),
        }

        # 步骤1: 解析元数据
        metadata = exif_parser.parse(str(file_path))
        _task_store[task_id]["metadata"] = metadata

        # 步骤2: 质量评估
        quality = quality_assessor.assess_all(str(file_path), metadata)
        _task_store[task_id]["quality"] = quality

        # 检查质量
        if quality.overall_score < 30:
            return PipelineResponse(
                task_id=task_id,
                status="rejected",
                metadata=metadata.to_dict() if metadata else None,
                quality=quality.to_dict(),
                error=f"影像质量不合格（{quality.quality_level}），综合评分{quality.overall_score}",
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        # 步骤3: 构建共线方程模型
        ortho_engine.build_from_metadata(metadata)

        # 步骤4: 计算覆盖范围和地面分辨率
        coverage = OrthorectificationEngine._compute_coverage(metadata)
        gsd = ortho_engine.collinearity_model.compute_ground_resolution(0.0)

        # 步骤5: 模拟正射校正（生产环境需要对实际影像进行纠正）
        # 此处构建一个模拟的正射影像用于反演
        ortho_rows, ortho_cols = 500, 500
        simulated_ortho = _create_demo_ortho_image(ortho_rows, ortho_cols, metadata)

        geo_transform = (
            coverage[0],  # origin_x
            (coverage[2] - coverage[0]) / ortho_cols,  # pixel_width
            0.0,
            coverage[3],  # origin_y
            0.0,
            (coverage[1] - coverage[3]) / ortho_rows,  # pixel_height (负)
        )

        _task_store[task_id]["ortho_image"] = simulated_ortho
        _task_store[task_id]["geo_transform"] = geo_transform
        _task_store[task_id]["coverage"] = coverage
        _task_store[task_id]["gsd"] = gsd

        # 步骤6: 遥感反演
        bands = _simulate_multispectral_bands(simulated_ortho)
        inversion_results = {}
        uncertainty_grids = {}

        if scenario in ("water", "all"):
            water_result = water_inverter.retrieve_all(bands)
            inversion_results["water"] = water_result
            # 为每个水质指标生成不确定性
            for name in ["chl_a", "tsm", "turbidity", "sdd", "cod"]:
                val = getattr(water_result, name)
                if val is not None:
                    grid = uncertainty_mapper.compute_indicator_uncertainty(
                        val, name, ground_resolution=gsd, model_type="semi_empirical"
                    )
                    uncertainty_grids[name] = grid

        if scenario in ("forestry", "all"):
            forestry_result = forestry_inverter.retrieve_all(bands)
            inversion_results["forestry"] = forestry_result
            for name in ["volume", "biomass", "fvc"]:
                val = getattr(forestry_result, name)
                if val is not None:
                    grid = uncertainty_mapper.compute_indicator_uncertainty(
                        val, name, ground_resolution=gsd, model_type="empirical"
                    )
                    uncertainty_grids[name] = grid

        if scenario in ("environment", "all"):
            env_result = env_inverter.retrieve_all(bands)
            inversion_results["environment"] = env_result
            for name in ["soil_moisture", "heavy_metal_stress", "lst", "runoff_coefficient"]:
                val = getattr(env_result, name)
                if val is not None:
                    grid = uncertainty_mapper.compute_indicator_uncertainty(
                        val, name, ground_resolution=gsd, model_type="empirical"
                    )
                    uncertainty_grids[name] = grid

        _task_store[task_id]["inversion_results"] = inversion_results
        _task_store[task_id]["uncertainty_grids"] = uncertainty_grids

        # 步骤7: 生成采样推荐
        return await generate_aerial_recommendations(
            task_id=task_id,
            strategy=strategy,
            n_recommendations=n_recommendations,
        )

    except Exception as e:
        logger.error(f"全流程处理失败: {e}", exc_info=True)
        _task_store[task_id] = _task_store.get(task_id, {})
        _task_store[task_id]["status"] = "failed"
        _task_store[task_id]["error"] = str(e)

        return PipelineResponse(
            task_id=task_id,
            status="failed",
            error=str(e),
            processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
        )


@router.get("/aerial/status/{task_id}")
async def get_task_status(task_id: str):
    """查询航测处理任务状态"""
    task = _task_store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    return {
        "task_id": task_id,
        "status": task.get("status", "unknown"),
        "file_name": task.get("file_name"),
        "created_at": task.get("created_at", ""),
        "error": task.get("error"),
    }


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _simulate_multispectral_bands(rgb_image: np.ndarray) -> SpectralBands:
    """从RGB影像模拟多光谱波段

    使用颜色通道近似映射到多光谱波段：
    - Red -> Red (~660nm)
    - Green -> Green (~560nm)
    - Blue -> Blue (~490nm)
    - NIR 近似 = 0.8*R + 0.2*G (简化)
    - 红边近似 = 0.5*R + 0.5*NIR
    """
    if rgb_image is None or rgb_image.size == 0:
        return SpectralBands()

    # 提取通道
    if len(rgb_image.shape) == 3:
        R = rgb_image[:, :, 0].astype(np.float64) / 255.0
        G = rgb_image[:, :, 1].astype(np.float64) / 255.0
        B = rgb_image[:, :, 2].astype(np.float64) / 255.0
    else:
        R = G = B = rgb_image.astype(np.float64) / 255.0

    # NIR近似（植被在NIR高反射）
    NIR = 0.75 * R + 0.25 * G + np.random.normal(0, 0.02, R.shape)

    # SWIR近似
    SWIR1 = 0.3 * R + 0.1 * G + np.random.normal(0, 0.03, R.shape)

    return SpectralBands(
        blue=B,
        green=G,
        red=R,
        red_edge=0.4 * R + 0.6 * NIR,
        nir=NIR,
        swir1=SWIR1,
        swir2=0.2 * SWIR1 + np.random.normal(0, 0.02, R.shape),
    )


def _generate_uncertainty_grids(
    water_result: Optional[WaterQualityResult],
    forestry_result: Optional[ForestryResult],
    env_result: Optional[EnvironmentResult],
    ortho_result: Any,
) -> Dict[str, UncertaintyGrid]:
    """生成不确定性网格"""
    grids = {}
    gsd = 0.1  # 默认地面分辨率

    # 水质指标
    if water_result:
        for name in ["chl_a", "tsm", "turbidity", "sdd", "cod"]:
            val = getattr(water_result, name)
            if val is not None:
                grids[name] = uncertainty_mapper.compute_indicator_uncertainty(
                    val, name, ground_resolution=gsd, model_type="semi_empirical"
                )

    # 林业指标
    if forestry_result:
        for name in ["volume", "biomass", "fvc"]:
            val = getattr(forestry_result, name)
            if val is not None:
                grids[name] = uncertainty_mapper.compute_indicator_uncertainty(
                    val, name, ground_resolution=gsd, model_type="empirical"
                )

    # 环境指标
    if env_result:
        for name in ["soil_moisture", "heavy_metal_stress", "lst", "runoff_coefficient"]:
            val = getattr(env_result, name)
            if val is not None:
                grids[name] = uncertainty_mapper.compute_indicator_uncertainty(
                    val, name, ground_resolution=gsd, model_type="empirical"
                )

    return grids


def _build_inversion_summary(task_data: Dict) -> Dict[str, Any]:
    """构建反演摘要"""
    summary = {}
    for scenario_key in ["water", "forestry", "environment"]:
        result = task_data.get("inversion_results", {}).get(scenario_key)
        if result and hasattr(result, "to_dict_summary"):
            summary[scenario_key] = result.to_dict_summary()
    return summary


def _create_demo_ortho_image(rows: int, cols: int, metadata: AerialImageMetadata) -> np.ndarray:
    """创建演示用正射影像（实际应使用纠正后的影像）"""
    # 基于GPS位置生成模拟的植被-水体混合场景
    lat = metadata.gps.latitude
    lon = metadata.gps.longitude

    # 创建坐标网格
    yy, xx = np.meshgrid(
        np.linspace(lat - 0.005, lat + 0.005, rows),
        np.linspace(lon - 0.005, lon + 0.005, cols),
        indexing="ij",
    )

    # 模拟场景：中心为水体，边缘为植被
    dist = np.sqrt((xx - lon) ** 2 + (yy - lat) ** 2)

    # RGB影像
    rgb = np.zeros((rows, cols, 3), dtype=np.uint8)

    # 水体区域
    water_mask = dist < 0.002
    rgb[water_mask, 0] = np.random.randint(10, 40, size=water_mask.sum())  # R低
    rgb[water_mask, 1] = np.random.randint(30, 80, size=water_mask.sum())  # G中等
    rgb[water_mask, 2] = np.random.randint(50, 120, size=water_mask.sum())  # B高

    # 植被区域
    veg_mask = dist >= 0.002
    rgb[veg_mask, 0] = np.random.randint(20, 60, size=veg_mask.sum())   # R低
    rgb[veg_mask, 1] = np.random.randint(80, 180, size=veg_mask.sum())  # G高
    rgb[veg_mask, 2] = np.random.randint(10, 50, size=veg_mask.sum())   # B低

    # 添加一些噪声使影像更真实
    rgb = np.clip(rgb + np.random.randint(-5, 5, rgb.shape), 0, 255).astype(np.uint8)

    return rgb
