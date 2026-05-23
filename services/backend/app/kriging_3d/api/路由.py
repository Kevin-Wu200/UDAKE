"""
3D克里金API接口
"""
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from ..schemas.参数模型 import KrigingParameters3D, SliceParams, TaskStartResponse3D
from ..schemas.结果模型 import DataUploadResponse3D
from ..services.数据处理3D import DataProcessor3D
from ..services.计算服务3D import Kriging3DService

router = APIRouter()
kriging_3d_service = Kriging3DService()
data_processor = DataProcessor3D()


@router.post("/kriging3d/upload", response_model=DataUploadResponse3D)
async def upload_3d_data(file: UploadFile = File(...)):
    """上传3D空间数据（支持GeoJSON、CSV、钻孔数据格式）"""
    try:
        content = await file.read()
        filename = file.filename or ""

        if filename.endswith(".csv"):
            spatial_data = data_processor.parse_csv_3d(content.decode("utf-8"))
        else:
            data = json.loads(content)
            if "boreholes" in data:
                spatial_data = data_processor.parse_borehole_data(data)
            else:
                spatial_data = data_processor.parse_geojson_3d(data)

        data_id = str(uuid.uuid4())
        data_processor.save_data(data_id, spatial_data)
        bounds = data_processor.get_bounds(spatial_data)
        z_vals = [p.z for p in spatial_data.points]

        return DataUploadResponse3D(
            data_id=data_id,
            point_count=len(spatial_data.points),
            bounds={
                "min_x": bounds.min_x, "min_y": bounds.min_y,
                "max_x": bounds.max_x, "max_y": bounds.max_y,
            },
            z_range={"min_z": min(z_vals), "max_z": max(z_vals)},
            message="3D数据上传成功"
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的数据格式")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"3D数据上传失败: {str(e)}")


@router.post("/kriging3d/start", response_model=TaskStartResponse3D)
async def start_kriging_3d(
    params: KrigingParameters3D,
    background_tasks: BackgroundTasks
):
    """启动3D克里金插值任务"""
    try:
        task_id = str(uuid.uuid4())
        kriging_3d_service.tasks[task_id] = {"status": "pending", "progress": 0.0}
        background_tasks.add_task(kriging_3d_service.execute_kriging_3d, task_id, params)
        return TaskStartResponse3D(
            task_id=task_id,
            status="pending",
            message="3D克里金任务已启动",
            grid_shape=[params.grid_resolution_x, params.grid_resolution_y, params.grid_resolution_z]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"3D任务启动失败: {str(e)}")


@router.get("/kriging3d/status/{task_id}")
async def get_3d_task_status(task_id: str):
    """查询3D任务状态"""
    status = kriging_3d_service.get_task_status(task_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="任务不存在")
    return status


@router.post("/kriging3d/slice/{task_id}")
async def get_3d_slice(task_id: str, params: SliceParams):
    """获取3D结果切片"""
    result = kriging_3d_service.get_slice(task_id, params)
    if result is None:
        raise HTTPException(status_code=404, detail="结果不存在或任务未完成")
    return result


@router.get("/kriging3d/result/{task_id}")
async def get_3d_result(task_id: str):
    """获取3D插值完整结果"""
    status = kriging_3d_service.get_task_status(task_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="任务不存在")
    if status.get("status") != "completed":
        return {"status": status.get("status"), "progress": status.get("progress", 0)}
    return {
        "status": "completed",
        "grid_shape": status.get("grid_shape"),
        "prediction_stats": status.get("prediction_stats"),
        "variance_stats": status.get("variance_stats"),
        "variogram": status.get("variogram"),
    }


@router.get("/kriging3d/export/{task_id}")
async def export_3d_result(task_id: str, format: str = "json"):
    """导出3D结果"""
    path = kriging_3d_service.export_result(task_id, format)
    if path is None:
        raise HTTPException(status_code=404, detail="结果不存在")
    return {"path": path, "format": format}


@router.get("/kriging3d/data/{data_id}/stats")
async def get_3d_data_stats(data_id: str):
    """获取3D数据统计信息"""
    try:
        data = data_processor.load_data(data_id)
        return data_processor.get_statistics(data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="数据不存在")


@router.post("/kriging3d/data/{data_id}/preprocess")
async def preprocess_3d_data(data_id: str, remove_outliers: bool = True, outlier_method: str = "iqr"):
    """预处理3D数据"""
    try:
        data = data_processor.load_data(data_id)
        data = data_processor.clean_data(data)
        outlier_indices = []
        if remove_outliers:
            data, outlier_indices = data_processor.detect_outliers(data, method=outlier_method)
        new_id = str(uuid.uuid4())
        data_processor.save_data(new_id, data)
        return {
            "data_id": new_id,
            "point_count": len(data.points),
            "outliers_removed": len(outlier_indices),
            "message": "预处理完成"
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="数据不存在")


@router.post("/kriging3d/data/{data_id}/layers")
async def get_3d_layers(data_id: str, n_layers: int = 5):
    """获取3D数据垂直分层"""
    try:
        data = data_processor.load_data(data_id)
        layers = data_processor.vertical_layers(data, n_layers)
        return {
            "layer_count": len(layers),
            "layers": {
                str(k): {
                    "point_count": len(v.points),
                    "z_range": [min(p.z for p in v.points), max(p.z for p in v.points)]
                }
                for k, v in layers.items()
            }
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="数据不存在")
