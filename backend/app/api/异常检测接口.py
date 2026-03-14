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
    """异常检测请求

    基于采样点数据检测异常点，支持空间异常检测和值异常检测两种方法。

    Attributes:
        task_id: 任务唯一标识符
        x_coords: X坐标列表
        y_coords: Y坐标列表
        values: 数值列表，对应每个采样点的观测值
        detection_method: 检测方法，可选"spatial"（空间异常）、"value"（值异常）或"both"（两者都检测）
        threshold: 检测阈值，用于值异常检测（标准差倍数）
        contamination: 异常点比例，用于异常检测算法（0-1之间）
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        example="task-20260314-001",
        min_length=1
    )
    x_coords: List[float] = Field(
        ...,
        description="X坐标列表",
        example=[120.1, 120.2, 120.3, 120.4, 120.5]
    )
    y_coords: List[float] = Field(
        ...,
        description="Y坐标列表",
        example=[30.1, 30.2, 30.3, 30.4, 30.5]
    )
    values: List[float] = Field(
        ...,
        description="数值列表，对应每个采样点的观测值",
        example=[10.5, 11.2, 10.8, 11.0, 10.7]
    )
    detection_method: str = Field(
        default="spatial",
        description="检测方法: spatial（空间异常）、value（值异常）或both（两者都检测）",
        example="spatial"
    )
    threshold: float = Field(
        default=3.0,
        description="检测阈值（标准差倍数），用于值异常检测",
        ge=1.0,
        example=3.0
    )
    contamination: float = Field(
        default=0.1,
        description="异常点比例（0-1之间），用于异常检测算法",
        ge=0.0,
        le=0.5,
        example=0.1
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task-20260314-001",
                "x_coords": [120.1, 120.2, 120.3, 120.4, 120.5],
                "y_coords": [30.1, 30.2, 30.3, 30.4, 30.5],
                "values": [10.5, 11.2, 10.8, 11.0, 10.7],
                "detection_method": "spatial",
                "threshold": 3.0,
                "contamination": 0.1
            }
        }

class AnomalyDetectResponse(BaseModel):
    """异常检测响应

    返回异常检测结果，包括：
    - 空间异常检测结果
    - 值异常检测结果
    - 异常分数
    - 统计信息

    Attributes:
        task_id: 任务ID
        detection_method: 使用的检测方法
        spatial_anomalies: 空间异常检测结果（如果进行空间异常检测）
        value_anomalies: 值异常检测结果（如果进行值异常检测）
        anomaly_scores: 异常分数列表，每个采样点的异常程度
        statistics: 统计信息，包含数据的均值、标准差等
        message: 操作状态消息
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        example="task-20260314-001"
    )
    detection_method: str = Field(
        ...,
        description="使用的检测方法",
        example="spatial"
    )
    spatial_anomalies: Optional[Dict[str, Any]] = Field(
        default=None,
        description="空间异常检测结果，包含异常点坐标和异常类型",
        example={
            "anomaly_count": 2,
            "anomalies": [
                {"x": 120.2, "y": 30.2, "value": 11.2, "type": "isolation_forest"},
                {"x": 120.4, "y": 30.4, "value": 11.0, "type": "elliptic_envelope"}
            ]
        }
    )
    value_anomalies: Optional[Dict[str, Any]] = Field(
        default=None,
        description="值异常检测结果，包含异常值和阈值信息",
        example={
            "upper_threshold": 12.5,
            "lower_threshold": 9.5,
            "anomalies": [
                {"index": 1, "value": 11.2, "type": "high"},
                {"index": 3, "value": 11.0, "type": "high"}
            ]
        }
    )
    anomaly_scores: List[float] = Field(
        ...,
        description="异常分数列表，每个采样点的异常程度（越高越异常）",
        example=[0.1, 0.8, 0.2, 0.7, 0.15]
    )
    statistics: Dict[str, Any] = Field(
        ...,
        description="统计信息，包含数据的均值、标准差、最小值、最大值、中位数",
        example={
            "total_points": 5,
            "mean": 10.84,
            "std": 0.29,
            "min": 10.5,
            "max": 11.2,
            "median": 10.8
        }
    )
    message: str = Field(
        ...,
        description="操作状态消息",
        example="异常检测完成"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task-20260314-001",
                "detection_method": "spatial",
                "spatial_anomalies": {
                    "anomaly_count": 2,
                    "anomalies": [
                        {"x": 120.2, "y": 30.2, "value": 11.2, "type": "isolation_forest"},
                        {"x": 120.4, "y": 30.4, "value": 11.0, "type": "elliptic_envelope"}
                    ]
                },
                "value_anomalies": None,
                "anomaly_scores": [0.1, 0.8, 0.2, 0.7, 0.15],
                "statistics": {
                    "total_points": 5,
                    "mean": 10.84,
                    "std": 0.29,
                    "min": 10.5,
                    "max": 11.2,
                    "median": 10.8
                },
                "message": "异常检测完成"
            }
        }

@router.post(
    "/anomaly/detect",
    response_model=AnomalyDetectResponse,
    summary="异常检测",
    description="""
基于采样点数据检测异常点，支持空间异常检测和值异常检测。

## 功能说明

该接口接收采样点的坐标和观测值，使用多种算法检测异常点。

### 主要功能

1. **空间异常检测**：使用隔离森林和椭圆包络算法检测空间异常
2. **值异常检测**：使用统计方法检测数值异常（基于标准差阈值）
3. **异常分数计算**：为每个采样点计算异常程度分数
4. **统计分析**：提供数据的完整统计信息
5. **混合检测**：支持同时进行空间和值异常检测

### 检测方法

- **spatial**: 空间异常检测，考虑位置和值的联合分布
- **value**: 值异常检测，仅考虑数值的统计特性
- **both**: 同时进行空间和值异常检测

### 空间异常检测算法

1. **隔离森林**：基于随机分割的异常检测算法
2. **椭圆包络**：基于协方差估计的异常检测算法

### 使用场景

- 环境监测中的异常值识别
- 地质勘探中的异常点检测
- 气象数据的质量控制
- 农业采样中的异常数据清理

## 请求示例

```json
{
  "task_id": "task-20260314-001",
  "x_coords": [120.1, 120.2, 120.3, 120.4, 120.5],
  "y_coords": [30.1, 30.2, 30.3, 30.4, 30.5],
  "values": [10.5, 11.2, 10.8, 11.0, 10.7],
  "detection_method": "spatial",
  "threshold": 3.0,
  "contamination": 0.1
}
```

## 响应示例

```json
{
  "task_id": "task-20260314-001",
  "detection_method": "spatial",
  "spatial_anomalies": {
    "anomaly_count": 2,
    "anomalies": [
      {"x": 120.2, "y": 30.2, "value": 11.2, "type": "isolation_forest"},
      {"x": 120.4, "y": 30.4, "value": 11.0, "type": "elliptic_envelope"}
    ]
  },
  "value_anomalies": null,
  "anomaly_scores": [0.1, 0.8, 0.2, 0.7, 0.15],
  "statistics": {
    "total_points": 5,
    "mean": 10.84,
    "std": 0.29,
    "min": 10.5,
    "max": 11.2,
    "median": 10.8
  },
  "message": "异常检测完成"
}
```

## 错误码

- **400**: 请求数据格式错误或数据验证失败
  - 坐标和数值数据长度不一致
  - 数据点数量过少（至少需要5个点）
  - 检测方法不支持
  - 阈值或异常点比例超出有效范围
- **500**: 服务器内部错误
  - 异常检测算法执行失败

## 注意事项

1. 坐标和数值数据长度必须一致
2. 至少需要5个数据点才能进行异常检测
3. 异常点比例（contamination）应在0到0.5之间
4. 检测阈值（threshold）应大于等于1.0
5. 异常分数范围通常在0到1之间，值越大表示越异常
6. 空间异常检测会使用两种算法，结果可能不同
7. 值异常检测基于均值±threshold*标准差计算阈值
8. 对于空间异常检测，contamination参数影响异常点的识别数量
""",
    responses={
        200: {
            "description": "异常检测成功",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task-20260314-001",
                        "detection_method": "spatial",
                        "spatial_anomalies": {
                            "anomaly_count": 2,
                            "anomalies": [
                                {"x": 120.2, "y": 30.2, "value": 11.2, "type": "isolation_forest"},
                                {"x": 120.4, "y": 30.4, "value": 11.0, "type": "elliptic_envelope"}
                            ]
                        },
                        "value_anomalies": None,
                        "anomaly_scores": [0.1, 0.8, 0.2, 0.7, 0.15],
                        "statistics": {
                            "total_points": 5,
                            "mean": 10.84,
                            "std": 0.29,
                            "min": 10.5,
                            "max": 11.2,
                            "median": 10.8
                        },
                        "message": "异常检测完成"
                    }
                }
            }
        },
        400: {
            "description": "请求数据验证失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "坐标和数值数据长度不一致"
                    }
                }
            }
        },
        500: {
            "description": "服务器内部错误",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "异常检测失败: ..."
                    }
                }
            }
        }
    },
    tags=["异常检测"]
)
async def detect_anomalies(request: AnomalyDetectRequest):
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