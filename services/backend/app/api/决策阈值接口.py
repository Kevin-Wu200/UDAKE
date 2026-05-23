"""
决策阈值分析接口
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.utils.type_converter import numpy_to_python

from uncertainty_dashboard.决策阈值分析 import DecisionThresholdAnalyzer

router = APIRouter()
analyzer = DecisionThresholdAnalyzer()

class DecisionThresholdRequest(BaseModel):
    """决策阈值分析请求

    基于预测结果和方差数据，分析不同决策阈值的效果，为决策提供科学依据。

    Attributes:
        task_id: 任务唯一标识符
        prediction: 预测结果矩阵，二维数组表示空间预测值
        variance: 方差数据矩阵，二维数组表示预测不确定性
        x_coords: X坐标列表，对应方差矩阵的列
        y_coords: Y坐标列表，对应方差矩阵的行
        decision_goal: 决策目标，描述阈值分析的用途
        custom_thresholds: 可选的自定义阈值列表，覆盖默认生成的阈值
        risk_tolerance: 风险容忍度，用于评估阈值风险（0-1之间）
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
    decision_goal: str = Field(
        ...,
        description="决策目标，描述阈值分析的用途和背景",
        examples=["确定污染物预警阈值"])
    custom_thresholds: Optional[List[float]] = Field(
        default=None,
        description="自定义阈值列表，如果提供则覆盖默认生成的阈值",
        examples=[[10.0, 10.5, 11.0, 11.5, 12.0]])
    risk_tolerance: float = Field(
        default=0.1,
        description="风险容忍度 (0-1之间，默认0.1)，用于评估阈值风险",
        ge=0.0,
        le=1.0,
        examples=[0.1])

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
                "decision_goal": "确定污染物预警阈值",
                "custom_thresholds": [10.0, 10.5, 11.0, 11.5, 12.0],
                "risk_tolerance": 0.1
            }
        }
    }

class DecisionThresholdResponse(BaseModel):
    """决策阈值分析响应

    返回决策阈值分析结果，包括：
    - 各阈值分析结果
    - 推荐的最优阈值
    - 风险评估
    - 阈值建议列表

    Attributes:
        task_id: 任务ID
        decision_goal: 决策目标
        threshold_analyses: 各阈值分析结果，包含不同阈值的效果评估
        recommended_threshold: 推荐的最优阈值
        risk_assessment: 风险评估结果，包含风险等级和风险描述
        recommendations: 阈值建议列表，包含多个备选阈值及其理由
        message: 操作状态消息
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        examples=["task-20260314-001"])
    decision_goal: str = Field(
        ...,
        description="决策目标",
        examples=["确定污染物预警阈值"])
    threshold_analyses: Dict[str, Any] = Field(
        ...,
        description="各阈值分析结果，包含不同阈值的效果评估",
        examples=[{
            "threshold_10.0": {
                "threshold": 10.0,
                "coverage": 45.0,
                "risk_level": "low",
                "confidence": 0.92
            },
            "threshold_11.0": {
                "threshold": 11.0,
                "coverage": 65.0,
                "risk_level": "medium",
                "confidence": 0.88
            }
        }])
    recommended_threshold: float = Field(
        ...,
        description="推荐的最优阈值",
        examples=[10.8])
    risk_assessment: Dict[str, Any] = Field(
        ...,
        description="风险评估结果，包含风险等级和风险描述",
        examples=[{
            "risk_level": "low",
            "risk_score": 0.15,
            "description": "推荐阈值风险较低，适合使用"
        }])
    recommendations: List[Dict[str, Any]] = Field(
        ...,
        description="阈值建议列表，包含多个备选阈值及其理由",
        examples=[[
            {
                "threshold": 10.8,
                "priority": "high",
                "reason": "平衡了覆盖率和风险",
                "expected_accuracy": 0.90
            },
            {
                "threshold": 11.0,
                "priority": "medium",
                "reason": "保守选择，覆盖率较高",
                "expected_accuracy": 0.88
            }
        ]])
    message: str = Field(
        ...,
        description="操作状态消息",
        examples=["决策阈值分析完成"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-20260314-001",
                "decision_goal": "确定污染物预警阈值",
                "threshold_analyses": {
                    "threshold_10.0": {
                        "threshold": 10.0,
                        "coverage": 45.0,
                        "risk_level": "low",
                        "confidence": 0.92
                    },
                    "threshold_11.0": {
                        "threshold": 11.0,
                        "coverage": 65.0,
                        "risk_level": "medium",
                        "confidence": 0.88
                    }
                },
                "recommended_threshold": 10.8,
                "risk_assessment": {
                    "risk_level": "low",
                    "risk_score": 0.15,
                    "description": "推荐阈值风险较低，适合使用"
                },
                "recommendations": [
                    {
                        "threshold": 10.8,
                        "priority": "high",
                        "reason": "平衡了覆盖率和风险",
                        "expected_accuracy": 0.90
                    },
                    {
                        "threshold": 11.0,
                        "priority": "medium",
                        "reason": "保守选择，覆盖率较高",
                        "expected_accuracy": 0.88
                    }
                ],
                "message": "决策阈值分析完成"
            }
        }
    }

@router.post(
    "/decision/thresholds",
    response_model=DecisionThresholdResponse,
    summary="决策阈值分析",
    description="""
基于预测结果和方差数据，分析不同决策阈值的效果。

## 功能说明

该接口接收预测结果和对应的方差数据，分析不同决策阈值的效果，为决策提供科学依据。

### 主要功能

1. **阈值生成**：基于预测值分位数自动生成候选阈值
2. **阈值评估**：分析每个阈值的覆盖率、风险等级和置信度
3. **最优阈值推荐**：综合考虑多个指标推荐最优阈值
4. **风险评估**：评估推荐阈值的风险水平
5. **建议列表**：提供多个备选阈值及其理由

### 阈值评估指标

- **覆盖率**：阈值覆盖的区域百分比
- **风险等级**：基于方差和阈值距离的风险评估
- **置信度**：预测值的不确定性度量

### 风险等级划分

- **低风险**：风险得分 < 0.3
- **中等风险**：0.3 ≤ 风险得分 < 0.6
- **高风险**：风险得分 ≥ 0.6

### 使用场景

- 环境监测中的预警阈值设定
- 地质勘探中的决策边界确定
- 气象预测中的临界值分析
- 农业采样中的管理阈值设定

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
  "decision_goal": "确定污染物预警阈值",
  "custom_thresholds": [10.0, 10.5, 11.0, 11.5, 12.0],
  "risk_tolerance": 0.1
}
```

## 响应示例

```json
{
  "task_id": "task-20260314-001",
  "decision_goal": "确定污染物预警阈值",
  "threshold_analyses": {
    "threshold_10.0": {
      "threshold": 10.0,
      "coverage": 45.0,
      "risk_level": "low",
      "confidence": 0.92
    },
    "threshold_11.0": {
      "threshold": 11.0,
      "coverage": 65.0,
      "risk_level": "medium",
      "confidence": 0.88
    }
  },
  "recommended_threshold": 10.8,
  "risk_assessment": {
    "risk_level": "low",
    "risk_score": 0.15,
    "description": "推荐阈值风险较低，适合使用"
  },
  "recommendations": [
    {
      "threshold": 10.8,
      "priority": "high",
      "reason": "平衡了覆盖率和风险",
      "expected_accuracy": 0.90
    },
    {
      "threshold": 11.0,
      "priority": "medium",
      "reason": "保守选择，覆盖率较高",
      "expected_accuracy": 0.88
    }
  ],
  "message": "决策阈值分析完成"
}
```

## 错误码

- **400**: 请求数据格式错误或数据验证失败
  - 预测结果和方差数据形状不匹配
  - 坐标与数据形状不匹配
  - 风险容忍度超出有效范围（0-1）
- **500**: 服务器内部错误
  - 决策阈值分析算法执行失败

## 注意事项

1. 方差数据必须为非负值
2. 预测结果和方差数据的形状必须一致
3. 坐标列表长度必须与数据矩阵的维度匹配
4. 风险容忍度必须在0到1之间
5. 自定义阈值应为递增序列
6. 如果不提供自定义阈值，系统将基于预测值分位数自动生成5个候选阈值
7. 推荐阈值的综合考虑覆盖率、风险水平和置信度等多个指标
""",
    responses={
        200: {
            "description": "决策阈值分析成功",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task-20260314-001",
                        "decision_goal": "确定污染物预警阈值",
                        "threshold_analyses": {
                            "threshold_10.0": {
                                "threshold": 10.0,
                                "coverage": 45.0,
                                "risk_level": "low",
                                "confidence": 0.92
                            }
                        },
                        "recommended_threshold": 10.8,
                        "risk_assessment": {
                            "risk_level": "low",
                            "risk_score": 0.15,
                            "description": "推荐阈值风险较低，适合使用"
                        },
                        "recommendations": [
                            {
                                "threshold": 10.8,
                                "priority": "high",
                                "reason": "平衡了覆盖率和风险",
                                "expected_accuracy": 0.90
                            }
                        ],
                        "message": "决策阈值分析完成"
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
                        "detail": "决策阈值分析失败: ..."
                    }
                }
            }
        }
    },
    tags=["决策阈值"]
)
async def analyze_decision_thresholds(request: DecisionThresholdRequest):
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

        # 生成默认阈值或使用自定义阈值
        if request.custom_thresholds:
            thresholds = request.custom_thresholds
        else:
            # 基于预测值分位数生成5个阈值
            percentiles = [20, 40, 50, 60, 80]
            thresholds = [float(np.percentile(prediction, p)) for p in percentiles]

        # 分析阈值
        threshold_analyses = analyzer.analyze_thresholds(
            prediction, variance, thresholds
        )

        # 推荐阈值
        recommended_threshold = threshold_analyses["recommended_threshold"]

        # 风险评估
        risk_assessment = analyzer.calculate_decision_risk(
            prediction, variance, recommended_threshold, request.risk_tolerance
        )

        # 生成阈值建议
        recommendations = analyzer.generate_threshold_recommendations(
            prediction, variance, n_thresholds=5
        )

        # 转换numpy类型为Python原生类型，防止Pydantic序列化错误
        threshold_analyses = numpy_to_python(threshold_analyses)
        risk_assessment = numpy_to_python(risk_assessment)
        recommendations = numpy_to_python(recommendations)

        return DecisionThresholdResponse(
            task_id=request.task_id,
            decision_goal=request.decision_goal,
            threshold_analyses=threshold_analyses,
            recommended_threshold=recommended_threshold,
            risk_assessment=risk_assessment,
            recommendations=recommendations,
            message="决策阈值分析完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"决策阈值分析失败: {str(e)}")
