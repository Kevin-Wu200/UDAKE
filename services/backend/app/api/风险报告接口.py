"""
空间风险报告生成接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import numpy as np
import sys
from pathlib import Path
import json

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from uncertainty_dashboard.空间风险报告生成 import SpatialRiskReporter

router = APIRouter()
reporter = SpatialRiskReporter()

class RiskReportRequest(BaseModel):
    """风险报告生成请求

    基于预测结果、方差数据和风险指数生成完整的空间风险报告。

    Attributes:
        task_id: 任务唯一标识符
        prediction: 预测结果矩阵，二维数组表示空间预测值
        variance: 方差数据矩阵，二维数组表示预测不确定性
        risk_index: 风险指数矩阵，二维数组表示风险评估值
        x_coords: X坐标列表，对应方差矩阵的列
        y_coords: Y坐标列表，对应方差矩阵的行
        uncertainty_levels: 可选的不确定性等级信息
        threshold_analysis: 可选的阈值分析结果
        metadata: 可选的元数据，包含任务相关的额外信息
        save_to_file: 是否将报告保存到文件
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
    risk_index: List[List[float]] = Field(
        ...,
        description="风险指数矩阵 (NxM 二维数组，形状需与prediction一致)",
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
    uncertainty_levels: Optional[Dict[str, Any]] = Field(
        default=None,
        description="不确定性等级信息，包含各等级的统计和分布",
        examples=[{
            "level_1": {"count": 5, "percentage": 55.56},
            "level_2": {"count": 3, "percentage": 33.33},
            "level_3": {"count": 1, "percentage": 11.11}
        }])
    threshold_analysis: Optional[Dict[str, Any]] = Field(
        default=None,
        description="阈值分析结果，包含推荐的阈值和风险评估",
        examples=[{
            "recommended_threshold": 10.8,
            "risk_level": "low",
            "coverage": 65.0
        }])
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="元数据，包含任务相关的额外信息",
        examples=[{
            "project_name": "环境监测项目",
            "location": "杭州市",
            "date": "2026-03-14"
        }])
    save_to_file: bool = Field(
        default=True,
        description="是否将报告保存到文件",
        examples=[True])

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
                "risk_index": [
                    [0.5, 0.8, 0.6],
                    [0.7, 0.9, 0.4],
                    [0.3, 0.6, 0.5]
                ],
                "x_coords": [120.1, 120.2, 120.3],
                "y_coords": [30.1, 30.2, 30.3],
                "uncertainty_levels": {
                    "level_1": {"count": 5, "percentage": 55.56},
                    "level_2": {"count": 3, "percentage": 33.33},
                    "level_3": {"count": 1, "percentage": 11.11}
                },
                "threshold_analysis": {
                    "recommended_threshold": 10.8,
                    "risk_level": "low",
                    "coverage": 65.0
                },
                "metadata": {
                    "project_name": "环境监测项目",
                    "location": "杭州市",
                    "date": "2026-03-14"
                },
                "save_to_file": True
            }
        }
    }

class RiskReportResponse(BaseModel):
    """风险报告生成响应

    返回空间风险报告生成结果，包括：
    - 完整报告内容
    - 报告ID
    - 生成时间
    - 文件路径（如果保存）

    Attributes:
        task_id: 任务ID
        report: 完整报告内容，包含执行摘要、风险评估、阈值分析等
        report_id: 报告唯一标识符
        generated_at: 报告生成时间（ISO 8601格式）
        file_path: 报告文件保存路径（如果save_to_file为True）
        message: 操作状态消息
    """
    task_id: str = Field(
        ...,
        description="任务ID",
        examples=["task-20260314-001"])
    report: Dict[str, Any] = Field(
        ...,
        description="完整报告内容，包含执行摘要、风险评估、阈值分析、空间统计信息和建议",
        examples=[{
            "report_id": "report-20260314-001",
            "task_id": "task-20260314-001",
            "generated_at": "2026-03-14T12:00:00Z",
            "summary": {
                "total_points": 9,
                "mean_risk": 0.6,
                "high_risk_percentage": 11.11,
                "overall_rating": "低风险"
            },
            "risk_assessment": {
                "mean_risk_index": 0.6,
                "std_risk_index": 0.2,
                "risk_distribution": {
                    "low": 5,
                    "medium": 3,
                    "high": 1,
                    "critical": 0
                }
            },
            "threshold_analysis": {
                "recommended_threshold": 10.8,
                "risk_level": "low",
                "coverage": 65.0
            },
            "spatial_statistics": {
                "mean_prediction": 10.9,
                "mean_variance": 0.6,
                "grid_shape": [3, 3]
            },
            "recommendations": [
                "重点关注高风险区域",
                "建议增加采样密度"
            ]
        }])
    report_id: str = Field(
        ...,
        description="报告唯一标识符",
        examples=["report-20260314-001"])
    generated_at: str = Field(
        ...,
        description="报告生成时间（ISO 8601格式）",
        examples=["2026-03-14T12:00:00Z"])
    file_path: Optional[str] = Field(
        default=None,
        description="报告文件保存路径（如果save_to_file为True）",
        examples=["/Users/wuchenkai/UDAKE/services/backend/app/结果文件/risk_report_task-20260314-001.json"])
    message: str = Field(
        ...,
        description="操作状态消息",
        examples=["风险报告生成完成"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "task_id": "task-20260314-001",
                "report": {
                    "report_id": "report-20260314-001",
                    "task_id": "task-20260314-001",
                    "generated_at": "2026-03-14T12:00:00Z",
                    "summary": {
                        "total_points": 9,
                        "mean_risk": 0.6,
                        "high_risk_percentage": 11.11,
                        "overall_rating": "低风险"
                    },
                    "risk_assessment": {
                        "mean_risk_index": 0.6,
                        "std_risk_index": 0.2,
                        "risk_distribution": {
                            "low": 5,
                            "medium": 3,
                            "high": 1,
                            "critical": 0
                        }
                    },
                    "threshold_analysis": {
                        "recommended_threshold": 10.8,
                        "risk_level": "low",
                        "coverage": 65.0
                    },
                    "spatial_statistics": {
                        "mean_prediction": 10.9,
                        "mean_variance": 0.6,
                        "grid_shape": [3, 3]
                    },
                    "recommendations": [
                        "重点关注高风险区域",
                        "建议增加采样密度"
                    ]
                },
                "report_id": "report-20260314-001",
                "generated_at": "2026-03-14T12:00:00Z",
                "file_path": "/Users/wuchenkai/UDAKE/services/backend/app/结果文件/risk_report_task-20260314-001.json",
                "message": "风险报告生成完成"
            }
        }
    }

@router.post(
    "/risk/report",
    response_model=RiskReportResponse,
    summary="空间风险报告生成",
    description="""
基于预测结果、方差数据和风险指数生成完整的空间风险报告。

## 功能说明

该接口接收预测结果、方差数据和风险指数，生成完整的空间风险报告，包含执行摘要、风险评估、阈值分析、空间统计信息和建议等内容。

### 主要功能

1. **报告生成**：整合多种分析结果生成完整报告
2. **执行摘要**：提供关键指标和总体评估
3. **风险评估**：详细的风险分析和等级划分
4. **阈值分析**：包含推荐阈值和风险评估
5. **空间统计**：提供空间分布的统计信息
6. **建议生成**：基于分析结果提供改进建议
7. **文件保存**：可选将报告保存到JSON文件

### 报告内容结构

- **report_id**: 报告唯一标识符
- **task_id**: 关联的任务ID
- **generated_at**: 报告生成时间
- **summary**: 执行摘要，包含关键指标
- **risk_assessment**: 风险评估，包含风险指数统计和分布
- **threshold_analysis**: 阈值分析结果
- **spatial_statistics**: 空间统计信息
- **recommendations**: 改进建议列表

### 使用场景

- 环境监测项目的风险报告生成
- 地质勘探项目的结果总结
- 气象预测报告的编制
- 农业采样项目的风险评估报告

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
  "risk_index": [
    [0.5, 0.8, 0.6],
    [0.7, 0.9, 0.4],
    [0.3, 0.6, 0.5]
  ],
  "x_coords": [120.1, 120.2, 120.3],
  "y_coords": [30.1, 30.2, 30.3],
  "uncertainty_levels": {
    "level_1": {"count": 5, "percentage": 55.56},
    "level_2": {"count": 3, "percentage": 33.33},
    "level_3": {"count": 1, "percentage": 11.11}
  },
  "threshold_analysis": {
    "recommended_threshold": 10.8,
    "risk_level": "low",
    "coverage": 65.0
  },
  "metadata": {
    "project_name": "环境监测项目",
    "location": "杭州市",
    "date": "2026-03-14"
  },
  "save_to_file": True
}
```

## 响应示例

```json
{
  "task_id": "task-20260314-001",
  "report": {
    "report_id": "report-20260314-001",
    "task_id": "task-20260314-001",
    "generated_at": "2026-03-14T12:00:00Z",
    "summary": {
      "total_points": 9,
      "mean_risk": 0.6,
      "high_risk_percentage": 11.11,
      "overall_rating": "低风险"
    },
    "risk_assessment": {
      "mean_risk_index": 0.6,
      "std_risk_index": 0.2,
      "risk_distribution": {
        "low": 5,
        "medium": 3,
        "high": 1,
        "critical": 0
      }
    },
    "threshold_analysis": {
      "recommended_threshold": 10.8,
      "risk_level": "low",
      "coverage": 65.0
    },
    "spatial_statistics": {
      "mean_prediction": 10.9,
      "mean_variance": 0.6,
      "grid_shape": [3, 3]
    },
    "recommendations": [
      "重点关注高风险区域",
      "建议增加采样密度"
    ]
  },
  "report_id": "report-20260314-001",
  "generated_at": "2026-03-14T12:00:00Z",
  "file_path": "/Users/wuchenkai/UDAKE/services/backend/app/结果文件/risk_report_task-20260314-001.json",
  "message": "风险报告生成完成"
}
```

## 错误码

- **400**: 请求数据格式错误或数据验证失败
  - 预测结果和方差数据形状不匹配
  - 预测结果和风险指数形状不匹配
  - 坐标与数据形状不匹配
- **500**: 服务器内部错误
  - 风险报告生成失败
  - 文件保存失败

## 注意事项

1. 所有矩阵数据（prediction、variance、risk_index）的形状必须一致
2. 坐标列表长度必须与数据矩阵的维度匹配
3. 不确定性等级和阈值分析是可选的，但提供这些信息会使报告更完整
4. 元数据可以包含任何与任务相关的额外信息
5. 当save_to_file为True时，报告将保存到services/backend/app/结果文件/目录
6. 文件名格式为：risk_report_{task_id}.json
7. 如果保存文件失败，报告仍会在响应中返回，但file_path为null
""",
    responses={
        200: {
            "description": "风险报告生成成功",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task-20260314-001",
                        "report": {
                            "report_id": "report-20260314-001",
                            "task_id": "task-20260314-001",
                            "generated_at": "2026-03-14T12:00:00Z",
                            "summary": {
                                "total_points": 9,
                                "mean_risk": 0.6,
                                "high_risk_percentage": 11.11,
                                "overall_rating": "低风险"
                            },
                            "risk_assessment": {
                                "mean_risk_index": 0.6,
                                "std_risk_index": 0.2,
                                "risk_distribution": {
                                    "low": 5,
                                    "medium": 3,
                                    "high": 1,
                                    "critical": 0
                                }
                            },
                            "threshold_analysis": {
                                "recommended_threshold": 10.8,
                                "risk_level": "low",
                                "coverage": 65.0
                            },
                            "spatial_statistics": {
                                "mean_prediction": 10.9,
                                "mean_variance": 0.6,
                                "grid_shape": [3, 3]
                            },
                            "recommendations": [
                                "重点关注高风险区域",
                                "建议增加采样密度"
                            ]
                        },
                        "report_id": "report-20260314-001",
                        "generated_at": "2026-03-14T12:00:00Z",
                        "file_path": "/Users/wuchenkai/UDAKE/services/backend/app/结果文件/risk_report_task-20260314-001.json",
                        "message": "风险报告生成完成"
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
                        "detail": "风险报告生成失败: ..."
                    }
                }
            }
        }
    },
    tags=["风险报告"]
)
async def generate_risk_report(request: RiskReportRequest):
    try:
        # 转换为numpy数组
        variance = np.array(request.variance)
        prediction = np.array(request.prediction)
        risk_index = np.array(request.risk_index)
        x_coords = np.array(request.x_coords)
        y_coords = np.array(request.y_coords)

        # 验证数据形状
        if variance.shape != prediction.shape:
            raise HTTPException(
                status_code=400,
                detail="预测结果和方差数据形状不匹配"
            )

        if variance.shape != risk_index.shape:
            raise HTTPException(
                status_code=400,
                detail="预测结果和风险指数形状不匹配"
            )

        if len(x_coords) != variance.shape[1] or len(y_coords) != variance.shape[0]:
            raise HTTPException(
                status_code=400,
                detail="坐标与数据形状不匹配"
            )

        # 添加坐标信息到元数据
        metadata = request.metadata or {}
        metadata.update({
            "x_coords": x_coords.tolist(),
            "y_coords": y_coords.tolist(),
            "grid_shape": prediction.shape
        })

        # 生成报告
        report = reporter.generate_risk_report(
            task_id=request.task_id,
            prediction=prediction,
            variance=variance,
            risk_index=risk_index,
            uncertainty_levels=request.uncertainty_levels or {},
            threshold_analysis=request.threshold_analysis or {},
            metadata=metadata
        )

        # 保存到文件
        file_path = None
        if request.save_to_file:
            results_dir = Path(__file__).parent.parent / "结果文件"
            file_path = results_dir / f"risk_report_{request.task_id}.json"
            reporter.save_report(report, file_path)
            file_path = str(file_path)

        return RiskReportResponse(
            task_id=request.task_id,
            report=report,
            report_id=report["report_id"],
            generated_at=report["generated_at"],
            file_path=file_path,
            message="风险报告生成完成"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风险报告生成失败: {str(e)}")