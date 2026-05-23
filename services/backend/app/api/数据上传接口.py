"""
数据上传接口
"""
import json
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..schemas.数据模型 import BoundingBox, DataUploadResponse
from ..services.数据预处理服务 import DataPreprocessor

router = APIRouter()
preprocessor = DataPreprocessor()

@router.post("/upload-data", response_model=DataUploadResponse)
async def upload_data(file: UploadFile = File(...)):
    """
    上传空间数据
    支持GeoJSON格式
    """
    try:
        # 读取文件内容
        content = await file.read()
        data = json.loads(content)

        # 解析GeoJSON
        spatial_data = preprocessor.parse_geojson(data)

        # 生成数据ID
        data_id = str(uuid.uuid4())

        # 保存数据
        preprocessor.save_data(data_id, spatial_data)

        # 计算边界
        points = spatial_data.points
        bounds = BoundingBox(
            min_x=min(p.x for p in points),
            min_y=min(p.y for p in points),
            max_x=max(p.x for p in points),
            max_y=max(p.y for p in points)
        )

        return DataUploadResponse(
            data_id=data_id,
            point_count=len(points),
            bounds=bounds,
            message="数据上传成功"
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="无效的JSON格式")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据上传失败: {str(e)}")
