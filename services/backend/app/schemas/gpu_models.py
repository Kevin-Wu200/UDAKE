"""GPU加速接口数据模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class GPUConfigUpdateRequest(BaseModel):
    enable_gpu: Optional[bool] = Field(default=None, description="是否启用GPU")
    auto_switch: Optional[bool] = Field(default=None, description="是否启用自动切换")
    min_size_for_gpu: Optional[int] = Field(default=None, ge=1, description="自动切换阈值")


class MatrixMultiplyRequest(BaseModel):
    matrix_a: List[List[float]]
    matrix_b: List[List[float]]
    prefer_gpu: bool = True


class MatrixSingleRequest(BaseModel):
    matrix: List[List[float]]
    prefer_gpu: bool = True


class LinearSolveRequest(BaseModel):
    matrix_a: List[List[float]]
    matrix_b: Union[List[float], List[List[float]]]
    prefer_gpu: bool = True


class VectorBinaryRequest(BaseModel):
    vector_a: List[float]
    vector_b: List[float]
    prefer_gpu: bool = True


class VectorSingleRequest(BaseModel):
    vector: List[float]
    prefer_gpu: bool = True


class KrigingSemivariogramRequest(BaseModel):
    points: List[List[float]] = Field(..., description="采样点坐标")
    values: List[float] = Field(..., description="采样值")
    bins: int = Field(default=12, ge=4, le=200)
    max_range: Optional[float] = Field(default=None, gt=0)
    prefer_gpu: bool = True


class KrigingPredictRequest(BaseModel):
    sample_points: List[List[float]]
    sample_values: List[float]
    target_points: List[List[float]]
    sill: float = Field(default=1.0, gt=0)
    range_: float = Field(default=1.0, gt=0)
    nugget: float = Field(default=0.0, ge=0)
    prefer_gpu: bool = True


class GPUComputeResponse(BaseModel):
    task_id: str
    backend: str
    elapsed_ms: float
    result: Dict[str, Any]
