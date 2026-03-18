"""
模型评估报告接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
import numpy as np
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from ai_extension.模型评估报告生成 import ModelEvaluator

router = APIRouter()
evaluator = ModelEvaluator()

class ModelEvaluationRequest(BaseModel):
    """模型评估请求

    基于实际值和预测值生成模型评估报告，用于评估插值模型的性能和质量。

    Attributes:
        task_id: 任务唯一标识符
        actual_values: 实际值列表，观测的真实值
        predicted_values: 预测值列表，模型预测的值
        variance: 方差列表，预测的不确定性度量
        model_params: 可选的模型参数，包含插值方法等配置信息
        x_coords: 可选的X坐标列表，用于空间分析
        y_coords: 可选的Y坐标列表，用于空间分析
    """
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "task_id": "task-20260314-001",
                "actual_values": [10.3, 11.0, 10.9, 10.8, 10.6],
                "predicted_values": [10.5, 11.2, 10.8, 11.0, 10.7],
                "variance": [0.5, 0.8, 0.6, 0.7, 0.3],
                "model_params": {
                    "method": "kriging",
                    "variogram_model": "spherical",
                    "range": 100.0,
                    "sill": 1.0,
                    "nugget": 0.1
                },
                "x_coords": [120.1, 120.2, 120.3, 120.4, 120.5],
                "y_coords": [30.1, 30.2, 30.3, 30.4, 30.5]
            }
        }
    )
    
    task_id: str = Field(
        ...,
        description="任务ID",
        example="task-20260314-001",
        min_length=1
    )
    actual_values: List[float] = Field(
        ...,
        description="实际值列表，观测的真实值",
        example=[10.3, 11.0, 10.9, 10.8, 10.6]
    )
    predicted_values: List[float] = Field(
        ...,
        description="预测值列表，模型预测的值",
        example=[10.5, 11.2, 10.8, 11.0, 10.7]
    )
    variance: List[float] = Field(
        ...,
        description="方差列表，预测的不确定性度量",
        example=[0.5, 0.8, 0.6, 0.7, 0.3]
    )
    model_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="模型参数，包含插值方法等配置信息",
        example={
            "method": "kriging",
            "variogram_model": "spherical",
            "range": 100.0,
            "sill": 1.0,
            "nugget": 0.1
        }
    )
    x_coords: Optional[List[float]] = Field(
        default=None,
        description="X坐标列表，用于空间分析",
        example=[120.1, 120.2, 120.3, 120.4, 120.5]
    )
    y_coords: Optional[List[float]] = Field(
        default=None,
        description="Y坐标列表，用于空间分析",
        example=[30.1, 30.2, 30.3, 30.4, 30.5]
    )

class ModelEvaluationResponse(BaseModel):
    """模型评估响应

    返回模型评估结果，包括：
    - 完整评估报告
    - 误差指标
    - 相关性分析
    - 综合质量分数
    - 改进建议

    Attributes:
        task_id: 任务ID
        report: 完整评估报告，包含详细的评估结果
        error_metrics: 误差指标，包括MAE、RMSE、MAPE等
        correlation: 相关系数，表示预测值和实际值的线性相关性
        quality_score: 综合质量分数，评估模型整体性能（0-1之间）
        sample_size: 样本数量
        recommendations: 改进建议列表
        message: 操作状态消息
    """
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "task_id": "task-20260314-001",
                "report": {
                    "task_id": "task-20260314-001",
                    "evaluation_time": "2026-03-14T12:00:00Z",
                    "sample_size": 5,
                    "error_metrics": {
                        "mae": 0.12,
                        "rmse": 0.15,
                        "mape": 1.2,
                        "max_error": 0.2,
                        "mean_error": 0.1
                    },
                    "variance_metrics": {
                        "mean_variance": 0.58,
                        "variance_coverage": 0.85
                    },
                    "diagnostics": {
                        "residuals_normality": True,
                        "homoscedasticity": True,
                        "outliers": []
                    }
                },
                "error_metrics": {
                    "mae": 0.12,
                    "rmse": 0.15,
                    "mape": 1.2,
                    "max_error": 0.2,
                    "mean_error": 0.1
                },
                "correlation": 0.98,
                "quality_score": 0.92,
                "sample_size": 5,
                "recommendations": [
                    "模型性能良好，建议继续使用",
                    "考虑增加采样点以提高精度",
                    "检查高误差区域的异常情况"
                ],
                "message": "模型评估完成"
            }
        }
    )
    
    task_id: str = Field(
        ...,
        description="任务ID",
        example="task-20260314-001"
    )
    report: Dict[str, Any] = Field(
        ...,
        description="完整评估报告，包含详细的评估结果",
        example={
            "task_id": "task-20260314-001",
            "evaluation_time": "2026-03-14T12:00:00Z",
            "sample_size": 5,
            "error_metrics": {
                "mae": 0.12,
                "rmse": 0.15,
                "mape": 1.2,
                "max_error": 0.2,
                "mean_error": 0.1
            },
            "variance_metrics": {
                "mean_variance": 0.58,
                "variance_coverage": 0.85
            },
            "diagnostics": {
                "residuals_normality": True,
                "homoscedasticity": True,
                "outliers": []
            }
        }
    )
    error_metrics: Dict[str, float] = Field(
        ...,
        description="误差指标，包括MAE（平均绝对误差）、RMSE（均方根误差）、MAPE（平均绝对百分比误差）等",
        example={
            "mae": 0.12,
            "rmse": 0.15,
            "mape": 1.2,
            "max_error": 0.2,
            "mean_error": 0.1
        }
    )
    correlation: float = Field(
        ...,
        description="相关系数，表示预测值和实际值的线性相关性（-1到1之间，越接近1越好）",
        example=0.98
    )
    quality_score: float = Field(
        ...,
        description="综合质量分数，评估模型整体性能（0-1之间，越高越好）",
        ge=0.0,
        le=1.0,
        example=0.92
    )
    sample_size: int = Field(
        ...,
        description="样本数量",
        example=5
    )
    recommendations: List[str] = Field(
        ...,
        description="改进建议列表，基于评估结果提供",
        example=[
            "模型性能良好，建议继续使用",
            "考虑增加采样点以提高精度",
            "检查高误差区域的异常情况"
        ]
    )
    message: str = Field(
        ...,
        description="操作状态消息",
        example="模型评估完成"
    )

@router.post(
    "/model/evaluation",
    response_model=ModelEvaluationResponse,
    summary="模型评估",
    description="""
基于实际值和预测值生成模型评估报告，用于评估插值模型的性能和质量。

## 功能说明

该接口接收实际值、预测值和方差数据，生成详细的模型评估报告。

### 主要功能

1. **误差指标计算**：计算MAE、RMSE、MAPE等多种误差指标
2. **相关性分析**：分析预测值和实际值的相关性
3. **方差分析**：评估预测不确定性的合理性
4. **诊断检查**：检查残差正态性、同方差性等
5. **质量评分**：综合评估模型性能
6. **改进建议**：基于评估结果提供改进建议

### 误差指标

- **MAE**（Mean Absolute Error）：平均绝对误差
- **RMSE**（Root Mean Square Error）：均方根误差
- **MAPE**（Mean Absolute Percentage Error）：平均绝对百分比误差
- **Max Error**：最大误差
- **Mean Error**：平均误差（偏倚）

### 质量评分标准

- **优秀**：0.9-1.0
- **良好**：0.8-0.9
- **一般**：0.6-0.8
- **较差**：0.4-0.6
- **很差**：<0.4

### 使用场景

- 环境监测模型的性能评估
- 地质勘探插值方法的比较
- 气象预测模型的验证
- 农业采样模型的优化

## 请求示例

```json
{
  "task_id": "task-20260314-001",
  "actual_values": [10.3, 11.0, 10.9, 10.8, 10.6],
  "predicted_values": [10.5, 11.2, 10.8, 11.0, 10.7],
  "variance": [0.5, 0.8, 0.6, 0.7, 0.3],
  "model_params": {
    "method": "kriging",
    "variogram_model": "spherical",
    "range": 100.0,
    "sill": 1.0,
    "nugget": 0.1
  },
  "x_coords": [120.1, 120.2, 120.3, 120.4, 120.5],
  "y_coords": [30.1, 30.2, 30.3, 30.4, 30.5]
}
```

## 响应示例

```json
{
  "task_id": "task-20260314-001",
  "report": {
    "task_id": "task-20260314-001",
    "evaluation_time": "2026-03-14T12:00:00Z",
    "sample_size": 5,
    "error_metrics": {
      "mae": 0.12,
      "rmse": 0.15,
      "mape": 1.2,
      "max_error": 0.2,
      "mean_error": 0.1
    },
    "variance_metrics": {
      "mean_variance": 0.58,
      "variance_coverage": 0.85
    },
    "diagnostics": {
      "residuals_normality": True,
      "homoscedasticity": True,
      "outliers": []
    }
  },
  "error_metrics": {
    "mae": 0.12,
    "rmse": 0.15,
    "mape": 1.2,
    "max_error": 0.2,
    "mean_error": 0.1
  },
  "correlation": 0.98,
  "quality_score": 0.92,
  "sample_size": 5,
  "recommendations": [
    "模型性能良好，建议继续使用",
    "考虑增加采样点以提高精度",
    "检查高误差区域的异常情况"
  ],
  "message": "模型评估完成"
}
```

## 错误码

- **400**: 请求数据格式错误或数据验证失败
  - 实际值和预测值数据长度不一致
  - 实际值和方差数据长度不一致
  - 数据点数量过少（至少需要5个点）
- **500**: 服务器内部错误
  - 模型评估算法执行失败

## 注意事项

1. 实际值、预测值和方差数据长度必须一致
2. 至少需要5个数据点才能进行模型评估
3. 方差数据应为非负值
4. 相关系数范围在-1到1之间，越接近1表示相关性越好
5. 质量分数范围在0到1之间，越高表示模型性能越好
6. 模型参数是可选的，但提供这些信息可以使评估更全面
7. 坐标信息用于空间分析，如果提供可以评估空间误差分布
8. 改进建议基于评估结果自动生成，可以作为模型优化的参考
""",
    responses={
        200: {
            "description": "模型评估成功",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task-20260314-001",
                        "report": {
                            "task_id": "task-20260314-001",
                            "evaluation_time": "2026-03-14T12:00:00Z",
                            "sample_size": 5,
                            "error_metrics": {
                                "mae": 0.12,
                                "rmse": 0.15,
                                "mape": 1.2,
                                "max_error": 0.2,
                                "mean_error": 0.1
                            },
                            "variance_metrics": {
                                "mean_variance": 0.58,
                                "variance_coverage": 0.85
                            },
                            "diagnostics": {
                                "residuals_normality": True,
                                "homoscedasticity": True,
                                "outliers": []
                            }
                        },
                        "error_metrics": {
                            "mae": 0.12,
                            "rmse": 0.15,
                            "mape": 1.2,
                            "max_error": 0.2,
                            "mean_error": 0.1
                        },
                        "correlation": 0.98,
                        "quality_score": 0.92,
                        "sample_size": 5,
                        "recommendations": [
                            "模型性能良好，建议继续使用",
                            "考虑增加采样点以提高精度",
                            "检查高误差区域的异常情况"
                        ],
                        "message": "模型评估完成"
                    }
                }
            }
        },
        400: {
            "description": "请求数据验证失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "实际值和预测值数据长度不一致"
                    }
                }
            }
        },
        500: {
            "description": "服务器内部错误",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "模型评估失败: ..."
                    }
                }
            }
        }
    },
    tags=["模型评估"]
)
async def evaluate_model(request: ModelEvaluationRequest):
    try:
        # 转换为numpy数组
        actual_values = np.array(request.actual_values)
        predicted_values = np.array(request.predicted_values)
        variance = np.array(request.variance)

        # 验证数据长度
        if len(actual_values) != len(predicted_values):
            raise HTTPException(
                status_code=400,
                detail="实际值和预测值数据长度不一致"
            )

        if len(actual_values) != len(variance):
            raise HTTPException(
                status_code=400,
                detail="实际值和方差数据长度不一致"
            )

        if len(actual_values) < 5:
            raise HTTPException(
                status_code=400,
                detail="数据点数量过少，至少需要5个点"
            )

        # 添加坐标信息到模型参数
        model_params = request.model_params or {}
        if request.x_coords and request.y_coords:
            model_params.update({
                "x_coords": request.x_coords,
                "y_coords": request.y_coords
            })

        # 生成评估报告
        report = evaluator.generate_evaluation_report(
            actual_values, predicted_values, variance, model_params
        )

        return ModelEvaluationResponse(
            task_id=request.task_id,
            report=report,
            error_metrics=report["error_metrics"],
            correlation=report["correlation"],
            quality_score=report["quality_score"],
            sample_size=report["sample_size"],
            recommendations=report["recommendations"],
            message="模型评估完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型评估失败: {str(e)}")