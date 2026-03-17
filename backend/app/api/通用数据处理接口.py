"""
通用数据处理接口
提供插值、采样、分析、报告、导出、导入等通用功能
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
from datetime import datetime

router = APIRouter()

# ==================== 数据模型 ====================

class InterpolationRequest(BaseModel):
    """插值请求"""
    points: List[Dict[str, float]]
    parameters: Dict[str, Any]

class InterpolationResponse(BaseModel):
    """插值响应"""
    id: str
    grid: List[List[float]]
    variance: List[List[float]]
    bounds: Dict[str, float]
    cellSize: float
    statistics: Dict[str, float]

class SamplingRequest(BaseModel):
    """采样请求"""
    bounds: Optional[Dict[str, float]] = None
    existingPoints: Optional[List[Dict[str, float]]] = None
    parameters: Dict[str, Any]

class SamplingResponse(BaseModel):
    """采样响应"""
    taskId: str
    points: List[Dict[str, Any]]
    count: int

class AnalysisRequest(BaseModel):
    """分析请求"""
    datasetId: Optional[str] = None
    grid: Optional[List[List[float]]] = None
    bounds: Optional[Dict[str, float]] = None
    variance: Optional[List[List[float]]] = None
    parameters: Dict[str, Any]

class AnalysisResponse(BaseModel):
    """分析响应"""
    taskId: str
    analysisType: str
    result: Any
    generatedAt: datetime

class ReportResponse(BaseModel):
    """报告响应"""
    id: str
    title: str
    content: str
    format: str
    generatedAt: datetime

class ExportRequest(BaseModel):
    """导出请求"""
    taskId: Optional[str] = None
    datasetId: Optional[str] = None
    format: str
    options: Optional[Dict[str, Any]] = None

class ExportResponse(BaseModel):
    """导出响应"""
    fileId: str
    fileName: str
    format: str
    size: int
    downloadUrl: str
    expiresAt: datetime
    recordCount: Optional[int] = None

class ImportRequest(BaseModel):
    """导入请求"""
    format: str
    options: Optional[Dict[str, Any]] = None
    content: Optional[str] = None
    url: Optional[str] = None

class ImportResponse(BaseModel):
    """导入响应"""
    datasetId: str
    fileName: str
    recordCount: int
    bounds: Dict[str, float]
    statistics: Dict[str, float]
    validation: Optional[Dict[str, Any]] = None

class ParseResponse(BaseModel):
    """解析响应"""
    fileName: str
    format: str
    recordCount: int
    fields: List[Dict[str, Any]]
    sampleData: List[Dict[str, Any]]

# ==================== 插值接口 ====================

@router.post("/interpolation", response_model=str)
async def submit_interpolation(request: InterpolationRequest):
    """
    提交插值任务
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        interpolation_id = str(uuid.uuid4())
        logger.info(f"开始处理插值任务: {interpolation_id}")
        
        # 执行实际的插值计算
        import numpy as np
        from pykrige.ok import OrdinaryKriging
        
        # 提取数据点
        x = [p['x'] for p in request.points]
        y = [p['y'] for p in request.points]
        z = [p['value'] for p in request.points]
        
        logger.info(f"输入数据点数: {len(x)}")
        logger.info(f"X范围: [{min(x):.6f}, {max(x):.6f}]")
        logger.info(f"Y范围: [{min(y):.6f}, {max(y):.6f}]")
        logger.info(f"Z范围: [{min(z):.6f}, {max(z):.6f}]")
        
        # 获取参数
        params = request.parameters
        variogram_model = params.get('variogram_model', 'spherical')
        nlags = params.get('nlags', 6)
        grid_resolution = params.get('grid_resolution', 50)
        
        logger.info(f"插值参数: model={variogram_model}, nlags={nlags}, resolution={grid_resolution}")
        
        # 计算网格边界
        x_min, x_max = min(x), max(x)
        y_min, y_max = min(y), max(y)
        gridx = np.linspace(x_min, x_max, grid_resolution)
        gridy = np.linspace(y_min, y_max, grid_resolution)
        
        # 执行克里金插值
        logger.info("开始执行克里金插值...")
        ok = OrdinaryKriging(
            x, y, z,
            variogram_model=variogram_model,
            verbose=False,
            enable_plotting=False,
            nlags=nlags
        )
        
        # 计算预测值和方差
        z_pred, ss_pred = ok.execute('grid', gridx, gridy)
        
        logger.info(f"插值完成，结果形状: {z_pred.shape}")
        logger.info(f"预测值范围: [{np.min(z_pred):.6f}, {np.max(z_pred):.6f}]")
        logger.info(f"方差范围: [{np.min(ss_pred):.6f}, {np.max(ss_pred):.6f}]")
        
        # 计算统计信息
        mean_val = float(np.mean(z_pred))
        std_val = float(np.std(z_pred))
        min_val = float(np.min(z_pred))
        max_val = float(np.max(z_pred))
        
        # 保存到内存存储
        from ..services.插值结果存储 import get_interpolation_storage
        storage = get_interpolation_storage()
        
        logger.info(f"保存插值结果到内存存储: {interpolation_id}")
        storage.save_result(
            interpolation_id,
            z_pred.tolist(),
            ss_pred.tolist(),
            {
                "minX": float(x_min),
                "minY": float(y_min),
                "maxX": float(x_max),
                "maxY": float(y_max)
            },
            float((x_max - x_min) / grid_resolution),
            {
                "mean": mean_val,
                "std": std_val,
                "min": min_val,
                "max": max_val
            }
        )
        
        # 保存到文件系统（GeoTIFF格式）
        try:
            from ..config import settings
            from osgeo import gdal, osr
            
            logger.info(f"保存插值结果到文件系统: {interpolation_id}")
            
            # 确保结果目录存在
            settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            
            # 保存预测值栅格
            prediction_path = settings.RESULTS_DIR / f"{interpolation_id}_prediction.tif"
            _save_geotiff(z_pred, gridx, gridy, prediction_path)
            logger.info(f"已保存预测栅格: {prediction_path}")
            
            # 保存方差栅格
            variance_path = settings.RESULTS_DIR / f"{interpolation_id}_variance.tif"
            _save_geotiff(ss_pred, gridx, gridy, variance_path)
            logger.info(f"已保存方差栅格: {variance_path}")
            
        except Exception as e:
            logger.error(f"保存到文件系统失败: {str(e)}")
            # 不影响主流程，继续返回
        
        return interpolation_id
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"插值任务失败: {str(e)}")
        logger.error(f"错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"提交插值任务失败: {str(e)}")


def _save_geotiff(data, x_coords, y_coords, output_path):
    """
    保存数组为GeoTIFF文件
    
    Args:
        data: 要保存的二维数组
        x_coords: X坐标数组
        y_coords: Y坐标数组
        output_path: 输出文件路径
    """
    from osgeo import gdal, osr
    import numpy as np
    
    # 获取数组尺寸
    rows, cols = data.shape
    
    # 计算地理变换参数
    x_min, x_max = x_coords[0], x_coords[-1]
    y_min, y_max = y_coords[0], y_coords[-1]
    
    # 假设坐标是递增的
    pixel_width = (x_max - x_min) / (cols - 1) if cols > 1 else 1.0
    pixel_height = (y_max - y_min) / (rows - 1) if rows > 1 else 1.0
    
    # 如果y坐标是递减的（常见于GIS），pixel_height应该是负的
    if y_coords[-1] < y_coords[0]:
        pixel_height = -abs(pixel_height)
    
    # 创建GeoTIFF文件
    driver = gdal.GetDriverByName('GTiff')
    dataset = driver.Create(str(output_path), cols, rows, 1, gdal.GDT_Float32)
    
    if dataset is None:
        raise RuntimeError(f"无法创建GeoTIFF文件: {output_path}")
    
    # 设置地理变换
    # 左上角坐标为 (x_min, y_max)
    dataset.SetGeoTransform((x_min, pixel_width, 0, y_max, 0, pixel_height))
    
    # 设置空间参考系统（使用WGS84）
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    
    # 写入数据
    band = dataset.GetRasterBand(1)
    band.WriteArray(data)
    band.FlushCache()
    
    # 关闭数据集
    dataset = None


@router.get("/interpolation/{interpolation_id}", response_model=InterpolationResponse)
async def get_interpolation_result(interpolation_id: str):
    """
    获取插值结果
    """
    try:
        # 从存储中获取实际的插值结果
        from ..services.插值结果存储 import InterpolationResultStorage
        storage = InterpolationResultStorage()
        result = storage.get_result(interpolation_id)
        
        if result is None:
            raise HTTPException(status_code=404, detail="插值结果不存在")
        
        return InterpolationResponse(
            id=interpolation_id,
            grid=result['grid'],
            variance=result['variance'],
            bounds=result['bounds'],
            cellSize=result['cellSize'],
            statistics=result['statistics']
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取插值结果失败: {str(e)}")


# ==================== 采样接口 ====================

@router.post("/sampling", response_model=SamplingResponse)
async def generate_sampling_points(request: SamplingRequest):
    """
    生成采样点
    """
    try:
        task_id = str(uuid.uuid4())
        # 这里应该实际执行采样点生成算法
        # 目前返回一个占位符结果
        return SamplingResponse(
            taskId=task_id,
            points=[],
            count=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成采样点失败: {str(e)}")


# ==================== 分析接口 ====================

@router.post("/analysis", response_model=AnalysisResponse)
async def perform_analysis(request: AnalysisRequest):
    """
    执行分析
    """
    try:
        task_id = str(uuid.uuid4())
        # 这里应该实际执行分析算法
        # 目前返回一个占位符结果
        return AnalysisResponse(
            taskId=task_id,
            analysisType="basic",
            result={},
            generatedAt=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行分析失败: {str(e)}")


@router.get("/analysis/{analysis_id}/report", response_model=ReportResponse)
async def generate_report(analysis_id: str):
    """
    生成报告
    """
    try:
        # 这里应该实际生成分析报告
        # 目前返回一个占位符报告
        return ReportResponse(
            id=analysis_id,
            title="分析报告",
            content="报告内容占位符",
            format="markdown",
            generatedAt=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


# ==================== 导出接口 ====================

@router.post("/export", response_model=ExportResponse)
async def export_data(request: ExportRequest):
    """
    导出数据
    """
    try:
        file_id = str(uuid.uuid4())
        # 这里应该实际执行数据导出
        # 目前返回一个占位符结果
        return ExportResponse(
            fileId=file_id,
            fileName=f"export_{file_id}.{request.format}",
            format=request.format,
            size=0,
            downloadUrl=f"/api/export/{file_id}",
            expiresAt=datetime.now(),
            recordCount=0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出数据失败: {str(e)}")


# ==================== 导入接口 ====================

@router.post("/import/parse", response_model=ParseResponse)
async def parse_import_file(file: UploadFile = File(...)):
    """
    解析导入文件
    """
    try:
        # 这里应该实际解析上传的文件
        # 目前返回一个占位符结果
        return ParseResponse(
            fileName=file.filename,
            format="unknown",
            recordCount=0,
            fields=[],
            sampleData=[]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析导入文件失败: {str(e)}")


@router.post("/import", response_model=ImportResponse)
async def import_data(request: ImportRequest):
    """
    导入数据
    """
    try:
        dataset_id = str(uuid.uuid4())
        # 这里应该实际执行数据导入
        # 目前返回一个占位符结果
        return ImportResponse(
            datasetId=dataset_id,
            fileName="imported_data",
            recordCount=0,
            bounds={"minX": 0.0, "minY": 0.0, "maxX": 1.0, "maxY": 1.0},
            statistics={"count": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0},
            validation=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入数据失败: {str(e)}")