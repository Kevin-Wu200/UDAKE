"""
异常检测接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import numpy as np
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from ai_extension.异常检测模块 import AnomalyDetector

router = APIRouter()
detector = AnomalyDetector()

class AnomalyDetectRequest(BaseModel):
    """异常检测请求"""
    task_id: str = Field(..., description="任务ID")
    x_coords: List[float] = Field(..., description="X坐标列表")
    y_coords: List[float] = Field(..., description="Y坐标列表")
    values: List[float] = Field(..., description="数值列表")
    detection_method: str = Field(default="spatial", description="检测方法: spatial 或 value")
    threshold: float = Field(default=3.0, description="检测阈值")
    contamination: float = Field(default=0.1, description="异常点比例")

class AnomalyDetectResponse(BaseModel):
    """异常检测响应"""
    task_id: str
    detection_method: str
    spatial_anomalies: Optional[Dict[str, Any]] = None
    value_anomalies: Optional[Dict[str, Any]] = None
    anomaly_scores: List[float]
    statistics: Dict[str, Any]
    message: str

@router.post("/anomaly/detect", response_model=AnomalyDetectResponse)
async def detect_anomalies(request: AnomalyDetectRequest):
    """
    异常检测

    基于采样点数据检测异常点，返回：
    - 空间异常检测结果
    - 值异常检测结果
    - 异常分数
    - 统计信息
    """
    try:
        # 转换为numpy数组
        x = np.array(request.x_coords)
        y = np.array(request.y_coords)
        values = np.array(request.values)

        # 验证数据长度
        if len(x) != len(y) or len(x) != len(values):
            raise HTTPException(
                status_code=400,
                detail="坐标和数值数据长度不一致"
            )

        if len(x) < 5:
            raise HTTPException(
                status_code=400,
                detail="数据点数量过少，至少需要5个点"
            )

        # 更新检测器参数
        detector.isolation_forest.contamination = request.contamination
        detector.elliptic_envelope.contamination = request.contamination

        # 检测结果
        spatial_anomalies = None
        value_anomalies = None

        if request.detection_method == "spatial":
            # 空间异常检测
            spatial_anomalies = detector.detect_spatial_anomalies(x, y, values)
        elif request.detection_method == "value":
            # 值异常检测
            value_anomalies = detector.detect_value_anomalies(values, request.threshold)
        else:
            # 两种方法都检测
            spatial_anomalies = detector.detect_spatial_anomalies(x, y, values)
            value_anomalies = detector.detect_value_anomalies(values, request.threshold)

        # 获取异常分数
        anomaly_scores = detector.get_anomaly_scores(x, y, values).tolist()

        # 统计信息
        statistics = {
            "total_points": len(values),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "median": float(np.median(values))
        }

        return AnomalyDetectResponse(
            task_id=request.task_id,
            detection_method=request.detection_method,
            spatial_anomalies=spatial_anomalies,
            value_anomalies=value_anomalies,
            anomaly_scores=anomaly_scores,
            statistics=statistics,
            message="异常检测完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"异常检测失败: {str(e)}")