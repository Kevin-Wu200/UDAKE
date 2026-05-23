"""
结果查询接口
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..dependencies import verify_task_id
from ..schemas.输出结果模型 import PredictionResult, VarianceResult
from ..tasks.任务管理器 import TaskManager

router = APIRouter()
task_manager = TaskManager()

@router.get("/result/prediction/{task_id}", response_model=PredictionResult)
async def get_prediction_result(task_id: str = Depends(verify_task_id)):
    """
    获取预测结果
    """
    try:
        result = task_manager.get_prediction_result(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="结果不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/result/variance/{task_id}", response_model=VarianceResult)
async def get_variance_result(task_id: str = Depends(verify_task_id)):
    """
    获取方差结果
    """
    try:
        result = task_manager.get_variance_result(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="方差结果不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/result/download/{task_id}/{filename}")
async def download_result_file(task_id: str, filename: str):
    """
    下载导出文件（GeoJSON / Shapefile / GeoTIFF）
    """
    # 安全校验：只允许下载属于该任务的文件
    if not filename.startswith(task_id):
        raise HTTPException(status_code=400, detail="文件名不合法")

    filepath = settings.RESULTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    # 根据扩展名设置 MIME 类型
    suffix = filepath.suffix.lower()
    media_types = {
        ".geojson": "application/geo+json",
        ".shp": "application/x-shapefile",
        ".shx": "application/x-shapefile",
        ".dbf": "application/x-dbf",
        ".prj": "text/plain",
        ".tif": "image/tiff",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type=media_type
    )
