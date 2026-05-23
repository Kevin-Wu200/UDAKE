"""时空克里金 API。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..services.spatiotemporal_kriging_service import spatiotemporal_kriging_service

router = APIRouter(prefix="/spatiotemporal", tags=["时空克里金"])


class STSeries(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    x: List[float] = Field(default_factory=list)
    y: List[float] = Field(default_factory=list)
    z: List[float] = Field(default_factory=list)
    t: List[float] = Field(default_factory=list)
    value: List[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lengths(self) -> "STSeries":
        n = len(self.x)
        if n < 3:
            raise ValueError("至少需要 3 个样本点")
        if not (len(self.y) == n and len(self.z) == n and len(self.t) == n and len(self.value) == n):
            raise ValueError("x/y/z/t/value 长度必须一致")
        return self


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

    @model_validator(mode="after")
    def validate_lengths(self) -> "STTargetPositions":
        n = len(self.x)
        if n == 0:
            raise ValueError("target_positions 不能为空")
        if not (len(self.y) == n and len(self.z) == n):
            raise ValueError("target_positions.x/y/z 长度必须一致")
        return self


class STPredictRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    target_positions: STTargetPositions
    target_times: List[float] = Field(default_factory=list)
    prediction_days: int = Field(default=1, ge=1, le=15)
    options: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_times(self) -> "STPredictRequest":
        if len(self.target_times) == 0:
            raise ValueError("target_times 不能为空")
        return self


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
    options: Dict[str, Any] = Field(default_factory=dict)


class STCacheWarmupRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str
    payloads: List[Dict[str, Any]] = Field(default_factory=list)


def _error_code_by_exception(exc: Exception) -> tuple[int, str]:
    if isinstance(exc, KeyError):
        if "模型不存在" in str(exc):
            return 404, "1001"
        return 500, "500"
    if isinstance(exc, ValueError):
        return 400, "1002"
    if "训练" in str(exc):
        return 500, "1003"
    if "预测" in str(exc):
        return 500, "1004"
    if "更新" in str(exc):
        return 500, "1005"
    return 500, "500"


def _error_response(exc: Exception, request: Request, default_message: str) -> JSONResponse:
    status_code, error_code = _error_code_by_exception(exc)
    message = str(exc) or default_message
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    details: Dict[str, Any] = {}
    if isinstance(exc, KeyError):
        details = {"resource": "model"}
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
            },
        },
    )


@router.post("/train")
async def train_spatiotemporal_kriging(payload: STTrainRequest, request: Request) -> Any:
    try:
        result = spatiotemporal_kriging_service.train_model(
            data=payload.data.model_dump(),
            model_type=payload.model_type,
            options=payload.options,
        )
        return {"success": True, "data": result, "message": "模型训练成功"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "模型训练失败")


@router.post("/predict")
async def predict_spatiotemporal_kriging(payload: STPredictRequest, request: Request) -> Any:
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
        return _error_response(exc, request, "模型预测失败")


@router.post("/auto-select")
async def auto_select_spatiotemporal_model(payload: STAutoSelectRequest, request: Request) -> Any:
    try:
        prediction_results = dict(payload.prediction_results or {})
        if "nonseparated" in prediction_results and "nonseparable" not in prediction_results:
            prediction_results["nonseparable"] = prediction_results["nonseparated"]
        result = spatiotemporal_kriging_service.auto_select_model(
            historical_data=payload.historical_data.model_dump(),
            new_samples=payload.new_samples.model_dump(),
            prediction_results=prediction_results,
            options=payload.options,
        )
        return {"success": True, "data": result, "message": "模型选择成功"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "模型自动选择失败")


@router.post("/incremental-update")
async def incremental_update_spatiotemporal_model(payload: STIncrementalUpdateRequest, request: Request) -> Any:
    try:
        result = spatiotemporal_kriging_service.incremental_update_model(
            model_id=payload.model_id,
            new_data=payload.new_data.model_dump(),
        )
        return {"success": True, "data": result, "message": "增量更新成功"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "模型增量更新失败")


@router.post("/update")
async def update_spatiotemporal_model(payload: STIncrementalUpdateRequest, request: Request) -> Any:
    try:
        result = spatiotemporal_kriging_service.update_model(
            model_id=payload.model_id,
            new_data=payload.new_data.model_dump(),
        )
        return {"success": True, "data": result, "message": "增量更新成功"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "模型增量更新失败")


@router.get("/evaluate/{model_id}")
async def evaluate_spatiotemporal_model(
    model_id: str,
    request: Request,
    metrics: str = Query(default="rmse,mae,r2,crps,bias,coverage_90,coverage_95"),
) -> Any:
    try:
        metric_list = [item.strip() for item in metrics.split(",") if item.strip()]
        result = spatiotemporal_kriging_service.evaluate_model(model_id=model_id, metrics=metric_list)
        return {"success": True, "data": result, "message": "模型评估成功"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "模型评估失败")


@router.get("/models")
async def list_spatiotemporal_models(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    model_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> Any:
    try:
        result = spatiotemporal_kriging_service.list_models(
            page=page,
            page_size=page_size,
            model_type=model_type,
            status=status,
        )
        return {"success": True, "data": result, "message": "查询成功"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "模型列表查询失败")


@router.get("/models/{model_id}")
async def get_spatiotemporal_model_detail(model_id: str, request: Request) -> Any:
    try:
        result = spatiotemporal_kriging_service.get_model_detail(model_id=model_id)
        return {"success": True, "data": result, "message": "查询成功"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "模型详情查询失败")


@router.delete("/models/{model_id}")
async def delete_spatiotemporal_model(model_id: str, request: Request) -> Any:
    try:
        result = spatiotemporal_kriging_service.delete_model(model_id=model_id)
        return {"success": True, "data": result, "message": "删除成功"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "模型删除失败")


@router.post("/cache/warmup")
async def warmup_spatiotemporal_cache(payload: STCacheWarmupRequest, request: Request) -> Any:
    try:
        result = await spatiotemporal_kriging_service.warm_prediction_cache(
            model_id=payload.model_id,
            payloads=payload.payloads,
        )
        return {"success": True, "data": result, "message": "缓存预热完成"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "缓存预热失败")


@router.get("/performance/metrics")
async def get_spatiotemporal_performance_metrics(request: Request) -> Any:
    try:
        result = spatiotemporal_kriging_service.performance_metrics()
        return {"success": True, "data": result, "message": "性能指标查询成功"}
    except Exception as exc:  # pylint: disable=broad-except
        return _error_response(exc, request, "性能指标查询失败")
