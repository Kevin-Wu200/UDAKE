"""
风险指数计算接口
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

from uncertainty_dashboard.风险指数计算 import RiskIndexCalculator

router = APIRouter()
calculator = RiskIndexCalculator()

class RiskCalculateRequest(BaseModel):
    """风险指数计算请求

    基于预测结果和方差数据计算空间风险指数，用于评估空间预测的可靠性。

    Attributes:
        task_id: 任务唯一标识符
        prediction: 预测结果矩阵，二维数组表示空间预测值
        variance: 方差数据矩阵，二维数组表示预测不确定性
        x_coords: X坐标列表，对应方差矩阵的列
        y_coords: Y坐标列表，对应方差矩阵的行
        confidence_level: 置信度水平，用于计算置信区间（0-1之间）
        threshold_values: 可选的自定义阈值，覆盖默认风险分级阈值
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        example="task-20260314-001",
        min_length=1
    )
    prediction: List[List[float]] = Field(
        ...,
        description="预测结果矩阵 (NxM 二维数组)",
        example=[
            [10.5, 11.2, 10.8],
            [11.0, 10.9, 11.3],
            [10.7, 11.1, 10.6]
        ]
    )
    variance: List[List[float]] = Field(
        ...,
        description="方差数据矩阵 (NxM 二维数组，形状需与prediction一致)",
        example=[
            [0.5, 0.8, 0.6],
            [0.7, 0.9, 0.4],
            [0.3, 0.6, 0.5]
        ]
    )
    x_coords: List[float] = Field(
        ...,
        description="X坐标列表 (长度为M)",
        example=[120.1, 120.2, 120.3]
    )
    y_coords: List[float] = Field(
        ...,
        description="Y坐标列表 (长度为N)",
        example=[30.1, 30.2, 30.3]
    )
    confidence_level: float = Field(
        default=0.95,
        description="置信度水平 (0-1之间，默认0.95)",
        ge=0.0,
        le=1.0,
        example=0.95
    )
    threshold_values: Optional[Dict[str, float]] = Field(
        default=None,
        description="自定义阈值配置，键为阈值名称，值为阈值数值",
        example={
            "low": 0.3,
            "medium": 0.6,
            "high": 0.9,
            "critical": 1.2
        }
    )

    class Config:
        json_schema_extra = {
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
                "confidence_level": 0.95,
                "threshold_values": {
                    "low": 0.3,
                    "medium": 0.6,
                    "high": 0.9,
                    "critical": 1.2
                }
            }
        }

class RiskCalculateResponse(BaseModel):
    """风险指数计算响应

    返回空间风险指数计算结果，包括：
    - 风险指数矩阵
    - 统计信息
    - 风险等级分布
    - 高风险区域统计
    - 综合风险评级

    Attributes:
        task_id: 任务ID
        risk_index: 风险指数矩阵，每个位置的风险评估值
        statistics: 统计信息，包括均值、标准差等
        risk_levels: 各风险等级的数量统计
        high_risk_area: 高风险区域面积（单位数）
        high_risk_percentage: 高风险区域百分比
        risk_rating: 综合风险评级（低风险、中等风险、高风险）
        message: 操作状态消息
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        example="task-20260314-001"
    )
    risk_index: List[List[float]] = Field(
        ...,
        description="风险指数矩阵 (NxM 二维数组，每个值表示该位置的风险程度)",
        example=[
            [0.5, 0.8, 0.6],
            [0.7, 0.9, 0.4],
            [0.3, 0.6, 0.5]
        ]
    )
    statistics: Dict[str, float] = Field(
        ...,
        description="统计信息，包括mean（均值）、std（标准差）、min（最小值）、max（最大值）等",
        example={
            "mean": 0.6,
            "std": 0.2,
            "min": 0.3,
            "max": 0.9,
            "median": 0.6
        }
    )
    risk_levels: Dict[str, int] = Field(
        ...,
        description="各风险等级的数量统计，键为等级名称，值为该等级的网格数量",
        example={
            "low": 5,
            "medium": 3,
            "high": 1,
            "critical": 0
        }
    )
    high_risk_area: int = Field(
        ...,
        description="高风险区域面积（网格单元数量）",
        example=1
    )
    high_risk_percentage: float = Field(
        ...,
        description="高风险区域百分比（0-100之间）",
        example=11.11
    )
    risk_rating: str = Field(
        ...,
        description="综合风险评级，根据高风险区域百分比确定",
        example="低风险"
    )
    message: str = Field(
        ...,
        description="操作状态消息",
        example="风险指数计算完成"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task-20260314-001",
                "risk_index": [
                    [0.5, 0.8, 0.6],
                    [0.7, 0.9, 0.4],
                    [0.3, 0.6, 0.5]
                ],
                "statistics": {
                    "mean": 0.6,
                    "std": 0.2,
                    "min": 0.3,
                    "max": 0.9,
                    "median": 0.6
                },
                "risk_levels": {
                    "low": 5,
                    "medium": 3,
                    "high": 1,
                    "critical": 0
                },
                "high_risk_area": 1,
                "high_risk_percentage": 11.11,
                "risk_rating": "低风险",
                "message": "风险指数计算完成"
            }
        }

@router.post(
    "/risk/calculate",
    response_model=RiskCalculateResponse,
    summary="风险指数计算",
    description="""
基于预测结果和方差数据计算空间风险指数。

## 功能说明

该接口接收预测结果和对应的方差数据，通过分析预测不确定性计算空间风险指数。

### 主要功能

1. **风险指数计算**：基于预测值和方差数据计算每个位置的风险指数
2. **统计分析**：计算风险指数的均值、标准差、中位数等统计指标
3. **风险等级划分**：将风险指数划分为不同等级（低、中、高、极高）
4. **综合风险评级**：根据高风险区域占比给出整体风险评级

### 风险等级划分

- **低风险**：风险指数 < 0.3
- **中等风险**：0.3 ≤ 风险指数 < 0.6
- **高风险**：0.6 ≤ 风险指数 < 0.9
- **极高风险**：风险指数 ≥ 0.9

### 综合风险评级标准

- **低风险**：高风险区域占比 ≤ 15%
- **中等风险**：15% < 高风险区域占比 ≤ 30%
- **高风险**：高风险区域占比 > 30%

### 使用场景

- 环境监测中的风险评估
- 地质勘探中的不确定性量化
- 气象预测中的可靠性分析
- 农业采样中的风险区域识别

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
  "y_coords": [30.1, 30.2, 30.3],
  "confidence_level": 0.95,
  "threshold_values": {
    "low": 0.3,
    "medium": 0.6,
    "high": 0.9,
    "critical": 1.2
  }
}
```

## 响应示例

```json
{
  "task_id": "task-20260314-001",
  "risk_index": [
    [0.5, 0.8, 0.6],
    [0.7, 0.9, 0.4],
    [0.3, 0.6, 0.5]
  ],
  "statistics": {
    "mean": 0.6,
    "std": 0.2,
    "min": 0.3,
    "max": 0.9,
    "median": 0.6
  },
  "risk_levels": {
    "low": 5,
    "medium": 3,
    "high": 1,
    "critical": 0
  },
  "high_risk_area": 1,
  "high_risk_percentage": 11.11,
  "risk_rating": "低风险",
  "message": "风险指数计算完成"
}
```

## 错误码

- **400**: 请求数据格式错误或数据验证失败
  - 预测结果和方差数据形状不匹配
  - 坐标与数据形状不匹配
  - 置信度水平超出有效范围（0-1）
- **500**: 服务器内部错误
  - 风险指数计算算法执行失败

## 注意事项

1. 方差数据必须为非负值
2. 预测结果和方差数据的形状必须一致
3. 坐标列表长度必须与数据矩阵的维度匹配
4. 置信度水平必须在0到1之间
5. 自定义阈值时，阈值应为递增序列
6. 风险指数矩阵的值范围通常在0到1之间
""",
    responses={
        200: {
            "description": "风险指数计算成功",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task-20260314-001",
                        "risk_index": [
                            [0.5, 0.8, 0.6],
                            [0.7, 0.9, 0.4],
                            [0.3, 0.6, 0.5]
                        ],
                        "statistics": {
                            "mean": 0.6,
                            "std": 0.2,
                            "min": 0.3,
                            "max": 0.9,
                            "median": 0.6
                        },
                        "risk_levels": {
                            "low": 5,
                            "medium": 3,
                            "high": 1,
                            "critical": 0
                        },
                        "high_risk_area": 1,
                        "high_risk_percentage": 11.11,
                        "risk_rating": "低风险",
                        "message": "风险指数计算完成"
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
                        "detail": "风险指数计算失败: ..."
                    }
                }
            }
        }
    },
    tags=["风险指数"]
)
async def calculate_risk(request: RiskCalculateRequest):
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

        # 计算空间风险
        spatial_risk = calculator.calculate_spatial_risk(
            variance, prediction, x_coords, y_coords
        )

        # 确定风险评级
        high_risk_pct = spatial_risk["high_risk_percentage"]
        if high_risk_pct > 30:
            risk_rating = "高风险"
        elif high_risk_pct > 15:
            risk_rating = "中等风险"
        else:
            risk_rating = "低风险"

        return RiskCalculateResponse(
            task_id=request.task_id,
            risk_index=spatial_risk["risk_index"].tolist(),
            statistics=spatial_risk["statistics"],
            risk_levels=spatial_risk["risk_levels"],
            high_risk_area=spatial_risk["high_risk_area"],
            high_risk_percentage=spatial_risk["high_risk_percentage"],
            risk_rating=risk_rating,
            message="风险指数计算完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风险指数计算失败: {str(e)}")