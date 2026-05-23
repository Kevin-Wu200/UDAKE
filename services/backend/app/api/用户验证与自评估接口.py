"""User validation and model self-evaluation API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..config import settings
from ..services.self_evaluation_service import self_evaluation_service

router = APIRouter()

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 240
_rate_limit_bucket: Dict[str, List[datetime]] = {}


def _enforce_rate_limit(identity: str) -> None:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    logs = _rate_limit_bucket.setdefault(identity, [])
    logs[:] = [item for item in logs if item >= window_start]
    if len(logs) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    logs.append(now)


class AuthContext(BaseModel):
    user_id: str
    api_key: str


def _auth(required_scope: str):
    def dep(
        request: Request,
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
        x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    ) -> AuthContext:
        if settings.is_development or settings.is_testing:
            return AuthContext(user_id=x_user_id or "dev_user", api_key=x_api_key or "dev_key")

        if not x_api_key:
             raise HTTPException(status_code=401, detail="X-API-Key header is required")

        try:
            _enforce_rate_limit(x_api_key)
            self_evaluation_service.verify_api_key(x_api_key, required_scope=required_scope)
            _ = request
            return AuthContext(user_id=self_evaluation_service.resolve_user_id(x_user_id), api_key=x_api_key)
        except HTTPException:
            raise
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dep


read_auth = _auth("read")
write_auth = _auth("write")


class RealtimeRecord(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    evaluation_id: Optional[str] = None
    dataset_id: Optional[str] = None
    model_id: Optional[str] = None
    module: Optional[str] = None
    timestamp: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    region: Optional[str] = None
    predicted_value: float
    actual_value: float
    result: str = Field(default="accept", pattern="^(accept|reject|correct)$")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: Optional[float] = Field(default=None, ge=0.0)
    corrected_value: Optional[float] = None
    response_time_seconds: float = Field(default=0.0, ge=0.0)
    verification_time_seconds: float = Field(default=0.0, ge=0.0)
    class_label: Optional[str] = None
    predicted_label: Optional[str] = None
    actual_label: Optional[str] = None
    features: List[float] = Field(default_factory=list)
    interval_lower: Optional[float] = None
    interval_upper: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RealtimeEvaluationRequest(BaseModel):
    records: List[RealtimeRecord] = Field(default_factory=list)
    window_minutes: int = Field(default=120, ge=1, le=10080)
    sample_size: int = Field(default=500, ge=1, le=50000)


class CandidateModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_id: str = Field(..., min_length=1, max_length=128)
    model_name: Optional[str] = None
    version: str = Field(default="v1", max_length=64)
    performance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty_score: float = Field(default=0.5, ge=0.0, le=1.0)
    scenario_score: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelSelectRequest(BaseModel):
    candidates: List[CandidateModel] = Field(default_factory=list)
    auto_switch: bool = True
    force_switch: bool = False
    switch_min_gain: float = Field(default=0.02, ge=0.0, le=1.0)
    switch_strategy: str = Field(default="smooth", pattern="^(smooth|immediate)$")
    switch_reason: str = Field(default="auto_selection", max_length=128)
    weights: Dict[str, float] = Field(default_factory=dict)
    validation: Dict[str, float] = Field(default_factory=dict)
    ab_test: Optional[Dict[str, Any]] = None


class ModelSwitchRequest(BaseModel):
    target_model_id: str = Field(..., min_length=1)
    strategy: str = Field(default="smooth", pattern="^(smooth|immediate)$")
    reason: str = Field(default="manual_switch", max_length=128)
    validation: Dict[str, float] = Field(default_factory=dict)


class ModelRollbackRequest(BaseModel):
    target_model_id: Optional[str] = None
    reason: str = Field(default="manual_rollback", max_length=128)


class OptimizationTriggerRequest(BaseModel):
    trigger_type: str = Field(
        default="manual",
        pattern="^(periodic|performance_degradation|data_accumulation|user_feedback|manual)$",
    )
    async_mode: bool = Field(default=False, alias="async")
    retrain_mode: str = Field(default="incremental", max_length=32)
    hyperparameter_search: bool = True
    architecture_search: bool = False
    feature_optimization: bool = True
    anomaly_update: bool = True
    expected_performance_delta: float = Field(default=0.03)
    data_volume: int = Field(default=0, ge=0)
    negative_feedback_ratio: float = Field(default=0.0, ge=0.0, le=1.0)

    model_config = {"populate_by_name": True}


class OptimizationCancelRequest(BaseModel):
    task_id: str = Field(..., min_length=1)


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(default="evaluation", pattern="^(performance|evaluation|optimization|all)$")
    format: str = Field(default="json", pattern="^(json|markdown)$")
    window_minutes: int = Field(default=120, ge=1, le=10080)
    sample_size: int = Field(default=500, ge=1, le=50000)


@router.post("/evaluation/realtime")
async def run_realtime_evaluation(
    payload: RealtimeEvaluationRequest,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return self_evaluation_service.evaluate_realtime(payload.model_dump(by_alias=True), ctx.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/evaluation/performance")
async def get_evaluation_performance(
    window_minutes: int = Query(default=120, ge=1, le=10080),
    sample_size: int = Query(default=500, ge=1, le=50000),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    return self_evaluation_service.get_performance_metrics(window_minutes=window_minutes, sample_size=sample_size)


@router.get("/evaluation/errors")
async def get_evaluation_errors(
    window_minutes: int = Query(default=120, ge=1, le=10080),
    sample_size: int = Query(default=500, ge=1, le=50000),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    return self_evaluation_service.get_error_analysis(window_minutes=window_minutes, sample_size=sample_size)


@router.get("/evaluation/uncertainty")
async def get_evaluation_uncertainty(
    window_minutes: int = Query(default=120, ge=1, le=10080),
    sample_size: int = Query(default=500, ge=1, le=50000),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    return self_evaluation_service.get_uncertainty_assessment(window_minutes=window_minutes, sample_size=sample_size)


@router.post("/model-selection/select")
async def select_best_model(
    payload: ModelSelectRequest,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return self_evaluation_service.select_best_model(payload.model_dump(), ctx.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/model-selection/status")
async def get_model_selection_status(ctx: AuthContext = Depends(read_auth)) -> Dict[str, Any]:
    _ = ctx
    return self_evaluation_service.get_model_status()


@router.post("/model-selection/switch")
async def switch_model(
    payload: ModelSwitchRequest,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return self_evaluation_service.switch_model(payload.model_dump(), ctx.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/model-selection/rollback")
async def rollback_model(
    payload: ModelRollbackRequest,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return self_evaluation_service.rollback_model(payload.model_dump(exclude_none=True), ctx.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/optimization/trigger")
async def trigger_optimization(
    payload: OptimizationTriggerRequest,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return self_evaluation_service.trigger_optimization(payload.model_dump(by_alias=True), ctx.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/optimization/status")
async def get_optimization_status(
    task_id: Optional[str] = Query(default=None),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    try:
        return self_evaluation_service.get_optimization_status(task_id=task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/optimization/cancel")
async def cancel_optimization(
    payload: OptimizationCancelRequest,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return self_evaluation_service.cancel_optimization(payload.model_dump(), ctx.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reports/performance")
async def get_performance_report(
    window_minutes: int = Query(default=120, ge=1, le=10080),
    sample_size: int = Query(default=500, ge=1, le=50000),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    return self_evaluation_service.get_performance_report(window_minutes=window_minutes, sample_size=sample_size)


@router.get("/reports/evaluation")
async def get_evaluation_report(
    window_minutes: int = Query(default=120, ge=1, le=10080),
    sample_size: int = Query(default=500, ge=1, le=50000),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    return self_evaluation_service.get_evaluation_report(window_minutes=window_minutes, sample_size=sample_size)


@router.get("/reports/optimization")
async def get_optimization_report(ctx: AuthContext = Depends(read_auth)) -> Dict[str, Any]:
    _ = ctx
    return self_evaluation_service.get_optimization_report()


@router.post("/reports/generate")
async def generate_report(
    payload: ReportGenerateRequest,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return self_evaluation_service.generate_report(payload.model_dump(), ctx.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
