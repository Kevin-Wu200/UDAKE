"""
不确定性分级接口
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

from uncertainty_dashboard.不确定性分级模型 import UncertaintyClassifier

router = APIRouter()
classifier = UncertaintyClassifier()

class UncertaintyClassifyRequest(BaseModel):
    """不确定性分级请求

    用于对空间预测结果进行不确定性分级分析。
    通过分析预测方差数据，将区域划分为不同不确定性等级，
    识别高风险区域，为决策提供支持。

    Attributes:
        task_id: 任务唯一标识符
        prediction: 预测结果矩阵，二维数组表示空间预测值
        variance: 方差数据矩阵，二维数组表示预测不确定性
        x_coords: X坐标列表，对应方差矩阵的列
        y_coords: Y坐标列表，对应方差矩阵的行
        custom_thresholds: 可选的自定义阈值，覆盖默认分级阈值
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        examples=["task-20260314-001"],
        min_length=1
    )
    prediction: List[List[float]] = Field(
        ...,
        description="预测结果矩阵 (NxM 二维数组)",
        examples=[[
            [10.5, 11.2, 10.8],
            [11.0, 10.9, 11.3],
            [10.7, 11.1, 10.6]
        ]])
    variance: List[List[float]] = Field(
        ...,
        description="方差数据矩阵 (NxM 二维数组，形状需与prediction一致)",
        examples=[[
            [0.5, 0.8, 0.6],
            [0.7, 0.9, 0.4],
            [0.3, 0.6, 0.5]
        ]])
    x_coords: List[float] = Field(
        ...,
        description="X坐标列表 (长度为M)",
        examples=[[120.1, 120.2, 120.3]])
    y_coords: List[float] = Field(
        ...,
        description="Y坐标列表 (长度为N)",
        examples=[[30.1, 30.2, 30.3]])
    custom_thresholds: Optional[Dict[str, float]] = Field(
        default=None,
        description="自定义阈值，键为等级名称，值为阈值",
        examples=[{
            "low": 0.5,
            "medium": 1.0,
            "high": 1.5,
            "critical": 2.0
        }])

    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-20260314-001",
                "prediction": [
                    [10.5, 11.2, 10.8],
                    [11.0, 10.9, 11.3],
                    [10.7, 11.1, 10.6]
                ],
                "variance": [
                    [0.5, 0.8, 0.6],
                    [0.7, 0.9, 0.4],
                    [0.3, 0.6, 0.5]
                ],
                "x_coords": [120.1, 120.2, 120.3],
                "y_coords": [30.1, 30.2, 30.3],
                "custom_thresholds": {
                    "low": 0.5,
                    "medium": 1.0,
                    "high": 1.5,
                    "critical": 2.0
                }
            }
        }
    }

class UncertaintyClassifyResponse(BaseModel):
    """不确定性分级响应

    返回不确定性分级分析结果，包括：
    - 各等级的统计信息（面积、百分比、平均方差等）
    - 颜色映射表（用于可视化）
    - 关键高风险区域列表
    - 操作状态消息

    Attributes:
        task_id: 任务ID
        statistics: 各等级统计信息
        color_map: 不确定性等级到颜色的映射
        critical_zones: 关键高风险区域列表
        message: 操作状态消息
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        examples=["task-20260314-001"])
    statistics: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="各等级统计信息，包括count（数量）、percentage（百分比）、mean_variance（平均方差）等",
        examples=[{
            "level_1": {
                "count": 5,
                "percentage": 55.56,
                "mean_variance": 0.42,
                "description": "低不确定性"
            },
            "level_2": {
                "count": 3,
                "percentage": 33.33,
                "mean_variance": 0.77,
                "description": "中等不确定性"
            },
            "level_3": {
                "count": 1,
                "percentage": 11.11,
                "mean_variance": 0.90,
                "description": "高不确定性"
            }
        }])
    color_map: Dict[int, str] = Field(
        ...,
        description="不确定性等级到颜色的映射（十六进制颜色代码）",
        examples=[{
            1: "#4CAF50",  # 绿色 - 低不确定性
            2: "#FFC107",  # 黄色 - 中等不确定性
            3: "#FF5722",  # 橙色 - 高不确定性
            4: "#F44336"   # 红色 - 极高不确定性
        }])
    critical_zones: List[Dict[str, Any]] = Field(
        ...,
        description="关键高风险区域列表，包含区域中心坐标、范围、不确定性等级等信息",
        examples=[[
            {
                "center": {"x": 120.2, "y": 30.2},
                "level": 3,
                "variance": 0.9,
                "area": 100,
                "description": "高不确定性区域"
            }
        ]])
    message: str = Field(
        ...,
        description="操作状态消息",
        examples=["不确定性分级完成"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-20260314-001",
                "statistics": {
                    "level_1": {
                        "count": 5,
                        "percentage": 55.56,
                        "mean_variance": 0.42,
                        "description": "低不确定性"
                    },
                    "level_2": {
                        "count": 3,
                        "percentage": 33.33,
                        "mean_variance": 0.77,
                        "description": "中等不确定性"
                    },
                    "level_3": {
                        "count": 1,
                        "percentage": 11.11,
                        "mean_variance": 0.90,
                        "description": "高不确定性"
                    }
                },
                "color_map": {
                    1: "#4CAF50",
                    2: "#FFC107",
                    3: "#FF5722",
                    4: "#F44336"
                },
                "critical_zones": [
                    {
                        "center": {"x": 120.2, "y": 30.2},
                        "level": 3,
                        "variance": 0.9,
                        "area": 100,
                        "description": "高不确定性区域"
                    }
                ],
                "message": "不确定性分级完成"
            }
        }
    }

@router.post(
    "/uncertainty/classify",
    response_model=UncertaintyClassifyResponse,
    summary="不确定性分级分析",
    description="""
对空间预测结果进行不确定性分级分析。

## 功能说明

该接口接收预测结果和对应的方差数据，通过分析方差分布将区域划分为不同不确定性等级。

### 主要功能

1. **不确定性分级**：根据方差值将区域划分为4个等级（低、中、高、极高）
2. **统计分析**：计算各等级的数量、百分比、平均方差等统计指标
3. **关键区域识别**：识别高风险区域，提供区域中心、范围等信息
4. **可视化支持**：提供颜色映射表，便于在地图上展示

### 不确定性等级

- **等级1 (低)**：方差 < 0.5，绿色 (#4CAF50)
- **等级2 (中)**：0.5 ≤ 方差 < 1.0，黄色 (#FFC107)
- **等级3 (高)**：1.0 ≤ 方差 < 1.5，橙色 (#FF5722)
- **等级4 (极高)**：方差 ≥ 1.5，红色 (#F44336)

### 使用场景

- 环境监测中的不确定性区域识别
- 地质勘探中的风险评估
- 气象预测中的置信度分析
- 农业采样中的不确定性评估

## 请求示例

```json
{
  "task_id": "task-20260314-001",
  "prediction": [
    [10.5, 11.2, 10.8],
    [11.0, 10.9, 11.3],
    [10.7, 11.1, 10.6]
  ],
  "variance": [
    [0.5, 0.8, 0.6],
    [0.7, 0.9, 0.4],
    [0.3, 0.6, 0.5]
  ],
  "x_coords": [120.1, 120.2, 120.3],
  "y_coords": [30.1, 30.2, 30.3]
}
```

## 响应示例

```json
{
  "task_id": "task-20260314-001",
  "statistics": {
    "level_1": {
      "count": 5,
      "percentage": 55.56,
      "mean_variance": 0.42
    },
    "level_2": {
      "count": 3,
      "percentage": 33.33,
      "mean_variance": 0.77
    },
    "level_3": {
      "count": 1,
      "percentage": 11.11,
      "mean_variance": 0.90
    }
  },
  "color_map": {
    "1": "#4CAF50",
    "2": "#FFC107",
    "3": "#FF5722",
    "4": "#F44336"
  },
  "critical_zones": [
    {
      "center": {"x": 120.2, "y": 30.2},
      "level": 3,
      "variance": 0.9,
      "area": 100
    }
  ],
  "message": "不确定性分级完成"
}
```

## 错误码

- **400**: 请求数据格式错误或数据验证失败
  - 预测结果和方差数据形状不匹配
  - 坐标与数据形状不匹配
- **500**: 服务器内部错误
  - 不确定性分级算法执行失败

## 注意事项

1. 方差数据必须为非负值
2. 预测结果和方差数据的形状必须一致
3. 坐标列表长度必须与数据矩阵的维度匹配
4. 自定义阈值时，阈值应为递增序列
5. 返回的关键区域数量限制为100个，避免响应过大
""",
    responses={
        200: {
            "description": "不确定性分级成功",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task-20260314-001",
                        "statistics": {
                            "level_1": {
                                "count": 5,
                                "percentage": 55.56,
                                "mean_variance": 0.42
                            }
                        },
                        "color_map": {
                            "1": "#4CAF50",
                            "2": "#FFC107",
                            "3": "#FF5722",
                            "4": "#F44336"
                        },
                        "critical_zones": [],
                        "message": "不确定性分级完成"
                    }
                }
            }
        },
        400: {
            "description": "请求数据验证失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "预测结果和方差数据形状不匹配"
                    }
                }
            }
        },
        500: {
            "description": "服务器内部错误",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "不确定性分级失败: ..."
                    }
                }
            }
        }
    },
    tags=["不确定性分级"]
)
async def classify_uncertainty(request: UncertaintyClassifyRequest):
    try:
        # 转换为numpy数组
        variance = np.array(request.variance)
        prediction = np.array(request.prediction)
        x_coords = np.array(request.x_coords)
        y_coords = np.array(request.y_coords)

        # 验证数据形状
        if variance.shape != prediction.shape:
            raise HTTPException(
                status_code=400,
                detail="预测结果和方差数据形状不匹配"
            )

        if len(x_coords) != variance.shape[1] or len(y_coords) != variance.shape[0]:
            raise HTTPException(
                status_code=400,
                detail="坐标与数据形状不匹配"
            )

        # 设置自定义阈值
        if request.custom_thresholds:
            classifier.thresholds.update(request.custom_thresholds)

        # 获取统计信息
        statistics = classifier.get_level_statistics(variance)

        # 生成不确定性地图
        uncertainty_map = classifier.generate_uncertainty_map(
            variance, x_coords, y_coords
        )

        # 识别关键区域
        critical_zones = classifier.identify_critical_zones(
            variance, x_coords, y_coords, critical_level=3
        )

        return UncertaintyClassifyResponse(
            task_id=request.task_id,
            statistics=statistics,
            color_map=uncertainty_map["color_map"],
            critical_zones=critical_zones[:100],  # 限制返回数量
            message="不确定性分级完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"不确定性分级失败: {str(e)}")