"""时空克里金 API。"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from .common import raise_api_error
from ..services.spatiotemporal_kriging_service import spatiotemporal_kriging_service

router = APIRouter(prefix="/spatiotemporal", tags=["时空克里金"])


class STSeries(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    x: List[float] = Field(default_factory=list)
    y: List[float] = Field(default_factory=list)
    z: List[float] = Field(default_factory=list)
    t: List[float] = Field(default_factory=list)
    value: List[float] = Field(default_factory=list)


class STTrainRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    data: STSeries
    model_type: Literal["separated", "product", "nonseparable"] = "separated"
    options: Dict[str, Any] = Field(default_factory=dict)


class STTargetPositions(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    x: List[float] = Field(default_factory=list)
    y: List[float] = Field(default_factory=list)
    z: List[float] = Field(default_factory=list)


class STPredictRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    target_positions: STTargetPositions
    target_times: List[float] = Field(default_factory=list)
    prediction_days: int = Field(default=1, ge=1, le=15)
    options: Dict[str, Any] = Field(default_factory=dict)


class STAutoSelectRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    historical_data: STSeries
    new_samples: STSeries
    prediction_results: Optional[Dict[str, List[Dict[str, float]]]] = None
    options: Dict[str, Any] = Field(default_factory=dict)

class STIncrementalUpdateRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    new_data: STSeries


@router.post("/train")
async def train_spatiotemporal_kriging(payload: STTrainRequest) -> Dict[str, Any]:
    try:
        result = spatiotemporal_kriging_service.train_model(
            data=payload.data.model_dump(),
            model_type=payload.model_type,
            options=payload.options,
        )
        return {"success": True, "data": result, "message": "模型训练成功"}
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="模型训练失败")


@router.post("/predict")
async def predict_spatiotemporal_kriging(payload: STPredictRequest) -> Dict[str, Any]:
    try:
        result = await spatiotemporal_kriging_service.predict(
            model_id=payload.model_id,
            target_positions=payload.target_positions.model_dump(),
            target_times=payload.target_times,
            prediction_days=payload.prediction_days,
            options=payload.options,
        )
        return {"success": True, "data": result, "message": "预测成功"}
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="模型预测失败")


@router.post("/auto-select")
async def auto_select_spatiotemporal_model(payload: STAutoSelectRequest) -> Dict[str, Any]:
    try:
        result = spatiotemporal_kriging_service.auto_select_model(
            historical_data=payload.historical_data.model_dump(),
            new_samples=payload.new_samples.model_dump(),
            prediction_results=payload.prediction_results,
            options=payload.options,
        )
        return {"success": True, "data": result, "message": "模型自动选择完成"}
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="模型自动选择失败")


@router.post("/incremental-update")
async def incremental_update_spatiotemporal_model(payload: STIncrementalUpdateRequest) -> Dict[str, Any]:
    try:
        result = spatiotemporal_kriging_service.incremental_update_model(
            model_id=payload.model_id,
            new_data=payload.new_data.model_dump(),
        )
        return {"success": True, "data": result, "message": "增量更新成功"}
    except Exception as exc:  # pylint: disable=broad-except
        raise_api_error(exc, default_message="模型增量更新失败")
