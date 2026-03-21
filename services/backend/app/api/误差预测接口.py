"""
误差预测接口
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

from ai_extension.误差预测模型 import ErrorPredictor

router = APIRouter()
predictor = ErrorPredictor()

class ErrorPredictRequest(BaseModel):
    """误差预测请求

    基于采样点位置和预测值预测插值误差，可选择训练模型以提高预测精度。

    Attributes:
        task_id: 任务唯一标识符
        x_coords: X坐标列表
        y_coords: Y坐标列表
        predicted_values: 预测值列表，对应每个采样点的预测结果
        actual_values: 实际值列表，用于训练模型（如果train_model为True）
        train_model: 是否训练模型，训练后可提高预测精度
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        examples=["task-20260314-001"],
        min_length=1
    )
    x_coords: List[float] = Field(
        ...,
        description="X坐标列表",
        examples=[[120.1, 120.2, 120.3, 120.4, 120.5]])
    y_coords: List[float] = Field(
        ...,
        description="Y坐标列表",
        examples=[[30.1, 30.2, 30.3, 30.4, 30.5]])
    predicted_values: List[float] = Field(
        ...,
        description="预测值列表，对应每个采样点的预测结果",
        examples=[[10.5, 11.2, 10.8, 11.0, 10.7]])
    actual_values: Optional[List[float]] = Field(
        default=None,
        description="实际值列表，用于训练模型（如果train_model为True）",
        examples=[[10.3, 11.0, 10.9, 10.8, 10.6]])
    train_model: bool = Field(
        default=False,
        description="是否训练模型，训练后可提高预测精度",
        examples=[False])

    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-20260314-001",
                "x_coords": [120.1, 120.2, 120.3, 120.4, 120.5],
                "y_coords": [30.1, 30.2, 30.3, 30.4, 30.5],
                "predicted_values": [10.5, 11.2, 10.8, 11.0, 10.7],
                "actual_values": [10.3, 11.0, 10.9, 10.8, 10.6],
                "train_model": True
            }
        }
    }

class ErrorPredictResponse(BaseModel):
    """误差预测响应

    返回误差预测结果，包括：
    - 预测误差分布
    - 置信度分数
    - 统计信息
    - 模型训练结果（如果训练）

    Attributes:
        task_id: 任务ID
        predicted_errors: 预测误差列表，每个采样点的预测误差值
        confidence_scores: 置信度分数列表，每个预测的置信度（0-1之间）
        statistics: 统计信息，包含误差的均值、标准差等
        training_results: 模型训练结果（如果进行了训练）
        message: 操作状态消息
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        examples=["task-20260314-001"])
    predicted_errors: List[float] = Field(
        ...,
        description="预测误差列表，每个采样点的预测误差值",
        examples=[[0.2, 0.1, -0.1, 0.2, 0.1]])
    confidence_scores: List[float] = Field(
        ...,
        description="置信度分数列表，每个预测的置信度（0-1之间，越高越可信）",
        examples=[[0.85, 0.92, 0.88, 0.90, 0.87]])
    statistics: Dict[str, float] = Field(
        ...,
        description="统计信息，包含误差的均值、标准差、最小值、最大值、中位数和平均置信度",
        examples=[{
            "total_points": 5,
            "mean_error": 0.1,
            "std_error": 0.13,
            "min_error": -0.1,
            "max_error": 0.2,
            "median_error": 0.1,
            "mean_confidence": 0.88
        }])
    training_results: Optional[Dict[str, Any]] = Field(
        default=None,
        description="模型训练结果，包含训练指标和模型信息",
        examples=[{
            "model_type": "random_forest",
            "training_score": 0.92,
            "feature_importance": {
                "x_coordinate": 0.45,
                "y_coordinate": 0.35,
                "predicted_value": 0.20
            },
            "training_samples": 5
        }])
    message: str = Field(
        ...,
        description="操作状态消息",
        examples=["误差预测完成"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-20260314-001",
                "predicted_errors": [0.2, 0.1, -0.1, 0.2, 0.1],
                "confidence_scores": [0.85, 0.92, 0.88, 0.90, 0.87],
                "statistics": {
                    "total_points": 5,
                    "mean_error": 0.1,
                    "std_error": 0.13,
                    "min_error": -0.1,
                    "max_error": 0.2,
                    "median_error": 0.1,
                    "mean_confidence": 0.88
                },
                "training_results": {
                    "model_type": "random_forest",
                    "training_score": 0.92,
                    "feature_importance": {
                        "x_coordinate": 0.45,
                        "y_coordinate": 0.35,
                        "predicted_value": 0.20
                    },
                    "training_samples": 5
                },
                "message": "误差预测完成"
            }
        }
    }

@router.post(
    "/error/predict",
    response_model=ErrorPredictResponse,
    summary="误差预测",
    description="""
基于采样点位置和预测值预测插值误差，可选择训练模型以提高预测精度。

## 功能说明

该接口接收采样点的坐标和预测值，预测每个位置的插值误差。

### 主要功能

1. **误差预测**：基于位置和预测值预测插值误差
2. **置信度估计**：为每个预测提供置信度评分
3. **模型训练**：可选训练自定义模型以提高预测精度
4. **统计分析**：提供误差的完整统计信息
5. **特征重要性**：训练后提供各特征的重要性分析

### 误差预测方法

- **默认模型**：使用预训练的通用误差预测模型
- **自定义模型**：基于实际值训练专用模型，精度更高

### 置信度评估

- 置信度分数范围：0-1
- 高置信度（≥0.8）：预测结果可信
- 中置信度（0.5-0.8）：预测结果可信度一般
- 低置信度（<0.5）：预测结果可信度较低

### 使用场景

- 环境监测中的预测精度评估
- 地质勘探中的误差分析
- 气象预测中的不确定性量化
- 农业采样中的预测可靠性评估

## 请求示例

```json
{
  "task_id": "task-20260314-001",
  "x_coords": [120.1, 120.2, 120.3, 120.4, 120.5],
  "y_coords": [30.1, 30.2, 30.3, 30.4, 30.5],
  "predicted_values": [10.5, 11.2, 10.8, 11.0, 10.7],
  "actual_values": [10.3, 11.0, 10.9, 10.8, 10.6],
  "train_model": True
}
```

## 响应示例

```json
{
  "task_id": "task-20260314-001",
  "predicted_errors": [0.2, 0.1, -0.1, 0.2, 0.1],
  "confidence_scores": [0.85, 0.92, 0.88, 0.90, 0.87],
  "statistics": {
    "total_points": 5,
    "mean_error": 0.1,
    "std_error": 0.13,
    "min_error": -0.1,
    "max_error": 0.2,
    "median_error": 0.1,
    "mean_confidence": 0.88
  },
  "training_results": {
    "model_type": "random_forest",
    "training_score": 0.92,
    "feature_importance": {
      "x_coordinate": 0.45,
      "y_coordinate": 0.35,
      "predicted_value": 0.20
    },
    "training_samples": 5
  },
  "message": "误差预测完成"
}
```

## 错误码

- **400**: 请求数据格式错误或数据验证失败
  - 坐标和预测值数据长度不一致
  - 数据点数量过少（至少需要10个点）
  - 训练模型时未提供实际值
  - 实际值和预测值数据长度不一致
- **500**: 服务器内部错误
  - 误差预测算法执行失败
  - 模型训练失败

## 注意事项

1. 坐标和预测值数据长度必须一致
2. 至少需要10个数据点才能进行误差预测
3. 如果需要训练模型，必须提供实际值数据
4. 训练模型需要实际值和预测值长度一致
5. 预测误差可以是正值或负值，表示预测值偏高或偏低
6. 置信度分数越高，表示预测结果越可信
7. 训练模型可以提高预测精度，但需要实际值数据
8. 特征重要性可以帮助理解哪些因素对误差影响最大
""",
    responses={
        200: {
            "description": "误差预测成功",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task-20260314-001",
                        "predicted_errors": [0.2, 0.1, -0.1, 0.2, 0.1],
                        "confidence_scores": [0.85, 0.92, 0.88, 0.90, 0.87],
                        "statistics": {
                            "total_points": 5,
                            "mean_error": 0.1,
                            "std_error": 0.13,
                            "min_error": -0.1,
                            "max_error": 0.2,
                            "median_error": 0.1,
                            "mean_confidence": 0.88
                        },
                        "training_results": {
                            "model_type": "random_forest",
                            "training_score": 0.92,
                            "feature_importance": {
                                "x_coordinate": 0.45,
                                "y_coordinate": 0.35,
                                "predicted_value": 0.20
                            },
                            "training_samples": 5
                        },
                        "message": "误差预测完成"
                    }
                }
            }
        },
        400: {
            "description": "请求数据验证失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "坐标和预测值数据长度不一致"
                    }
                }
            }
        },
        500: {
            "description": "服务器内部错误",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "误差预测失败: ..."
                    }
                }
            }
        }
    },
    tags=["误差预测"]
)
async def predict_errors(request: ErrorPredictRequest):
    try:
        # 转换为numpy数组
        x = np.array(request.x_coords)
        y = np.array(request.y_coords)
        predicted_values = np.array(request.predicted_values)

        # 验证数据长度
        if len(x) != len(y) or len(x) != len(predicted_values):
            raise HTTPException(
                status_code=400,
                detail="坐标和预测值数据长度不一致"
            )

        if len(x) < 10:
            raise HTTPException(
                status_code=400,
                detail="数据点数量过少，至少需要10个点"
            )

        training_results = None

        # 如果需要训练模型
        if request.train_model:
            if request.actual_values is None:
                raise HTTPException(
                    status_code=400,
                    detail="训练模型需要提供实际值"
                )

            actual_values = np.array(request.actual_values)

            if len(actual_values) != len(predicted_values):
                raise HTTPException(
                    status_code=400,
                    detail="实际值和预测值数据长度不一致"
                )

            # 训练模型
            training_results = predictor.train(
                x, y, actual_values, predicted_values
            )

        # 预测误差
        predicted_errors = predictor.predict_error(x, y, predicted_values)

        # 估计置信度
        confidence_scores = predictor.estimate_confidence(
            x, y, predicted_values
        )

        # 统计信息
        statistics = {
            "total_points": len(predicted_errors),
            "mean_error": float(np.mean(predicted_errors)),
            "std_error": float(np.std(predicted_errors)),
            "min_error": float(np.min(predicted_errors)),
            "max_error": float(np.max(predicted_errors)),
            "median_error": float(np.median(predicted_errors)),
            "mean_confidence": float(np.mean(confidence_scores))
        }

        return ErrorPredictResponse(
            task_id=request.task_id,
            predicted_errors=predicted_errors.tolist(),
            confidence_scores=confidence_scores.tolist(),
            statistics=statistics,
            training_results=training_results,
            message="误差预测完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"误差预测失败: {str(e)}")