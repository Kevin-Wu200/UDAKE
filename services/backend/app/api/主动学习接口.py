"""Active learning and semi-supervised API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..services.active_learning_service import active_learning_service

router = APIRouter()

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 180
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
        x_api_key: str = Header(..., alias="X-API-Key"),
        x_user_id: Optional[str] = Header(default=None, alias="X-User-Id"),
    ) -> AuthContext:
        try:
            _enforce_rate_limit(x_api_key)
            active_learning_service.verify_api_key(x_api_key, required_scope=required_scope)
            user_id = active_learning_service.resolve_user_id(x_user_id)
            _ = request
            return AuthContext(user_id=user_id, api_key=x_api_key)
        except HTTPException:
            raise
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dep


read_auth = _auth("read")
write_auth = _auth("write")
admin_auth = _auth("admin")


class ActiveLearningInitRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, max_length=128)
    session_id: Optional[str] = Field(default=None, max_length=128)
    strategy: Optional[str] = Field(default=None, max_length=128)
    labeled_samples: List[Dict[str, Any]] = Field(default_factory=list)
    unlabeled_samples: List[Dict[str, Any]] = Field(default_factory=list)
    budget: Dict[str, Any] = Field(default_factory=dict)


class ActiveLearningSelectRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    strategy: Optional[str] = Field(default=None, max_length=128)
    top_k: int = Field(default=20, ge=1, le=500)
    selection_mode: str = Field(default="batch", pattern="^(batch|incremental)$")


class ActiveLearningLabelItem(BaseModel):
    sample_id: str = Field(..., min_length=1)
    label: Any
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    annotator: Optional[str] = Field(default=None, max_length=128)


class ActiveLearningLabelRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    labels: List[ActiveLearningLabelItem] = Field(..., min_length=1)


class ActiveLearningUpdateRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    gain_factor: float = Field(default=0.5, ge=0.1, le=2.0)


class StrategyConfigRequest(BaseModel):
    default_strategy: Optional[str] = Field(default=None, max_length=128)
    weights: Dict[str, float] = Field(default_factory=dict)
    adaptive: Dict[str, Any] = Field(default_factory=dict)
    committee: Dict[str, Any] = Field(default_factory=dict)


class BudgetConfigRequest(BaseModel):
    total_budget: Optional[int] = Field(default=None, ge=1)
    batch_budget: Optional[int] = Field(default=None, ge=1)
    max_rounds: Optional[int] = Field(default=None, ge=1)
    target_performance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    min_improvement: Optional[float] = Field(default=None, ge=0.0)
    uncertainty_threshold: Optional[float] = Field(default=None, ge=0.0)


class PseudoLabelRequest(BaseModel):
    session_id: Optional[str] = Field(default=None)
    dataset_id: Optional[str] = Field(default=None)
    samples: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    max_items: int = Field(default=50, ge=1, le=1000)
    rounds: int = Field(default=1, ge=1, le=20)
    filter: bool = True


class ConsistencyRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    augmentations: List[str] = Field(default_factory=lambda: ["rotate", "flip", "noise"])
    max_items: int = Field(default=40, ge=1, le=500)


class CoTrainingRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    max_items: int = Field(default=30, ge=1, le=500)


class GraphSemiSupervisedRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    graph_type: str = Field(default="knn", pattern="^(knn|radius)$")
    k: int = Field(default=5, ge=1, le=50)
    radius: float = Field(default=0.8, ge=0.01)
    iterations: int = Field(default=5, ge=1, le=50)
    label_smoothing: float = Field(default=0.1, ge=0.0, le=1.0)


class SelfTrainingRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    max_rounds: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    early_stop_patience: int = Field(default=2, ge=1, le=10)


class IncrementalUpdateRequest(BaseModel):
    session_id: Optional[str] = Field(default=None)
    updates: List[Dict[str, Any]] = Field(default_factory=list)
    mode: str = Field(default="online", pattern="^(online|stream|batch)$")
    batch_size: int = Field(default=16, ge=1, le=500)
    forgetting_protection: Dict[str, Any] = Field(default_factory=dict)
    importance_weighting: Dict[str, Any] = Field(default_factory=dict)
    fine_tuning: Dict[str, Any] = Field(default_factory=dict)


class IncrementalEvaluateRequest(BaseModel):
    window: int = Field(default=10, ge=1, le=200)


class AnnotationRequestPayload(BaseModel):
    session_id: str = Field(..., min_length=1)
    samples: List[Dict[str, Any]] = Field(default_factory=list)


class AnnotationBatchPayload(BaseModel):
    session_id: str = Field(..., min_length=1)
    batch_size: int = Field(default=20, ge=1, le=500)
    shortcut_enabled: bool = True
    template: Dict[str, Any] = Field(default_factory=dict)


class AnnotationSuggestionPayload(BaseModel):
    session_id: str = Field(..., min_length=1)
    sample_id: str = Field(..., min_length=1)


class AnnotationQualityPayload(BaseModel):
    annotations: List[Dict[str, Any]] = Field(default_factory=list)


@router.get("/active-learning/health")
async def active_learning_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "module": "active_learning_and_semi_supervised",
        "rate_limit": {
            "window_seconds": RATE_LIMIT_WINDOW_SECONDS,
            "max_requests": RATE_LIMIT_MAX_REQUESTS,
        },
    }


@router.post("/active-learning/init")
async def init_active_learning(payload: ActiveLearningInitRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        data = active_learning_service.init_active_learning(payload.model_dump(), ctx.user_id)
        return {"session": data}
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/active-learning/select")
async def select_active_learning_samples(
    payload: ActiveLearningSelectRequest, ctx: AuthContext = Depends(write_auth)
) -> Dict[str, Any]:
    try:
        data = active_learning_service.select_samples(payload.model_dump(), ctx.user_id)
        return data
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/active-learning/label")
async def submit_active_learning_labels(
    payload: ActiveLearningLabelRequest, ctx: AuthContext = Depends(write_auth)
) -> Dict[str, Any]:
    try:
        data = active_learning_service.submit_labels(payload.model_dump(), ctx.user_id)
        return data
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/active-learning/update")
async def update_active_learning_model(
    payload: ActiveLearningUpdateRequest, ctx: AuthContext = Depends(write_auth)
) -> Dict[str, Any]:
    try:
        data = active_learning_service.update_model(payload.model_dump(), ctx.user_id)
        return data
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/active-learning/status")
async def get_active_learning_status(
    session_id: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    try:
        _ = ctx
        return active_learning_service.get_status(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/active-learning/config/strategy")
async def set_strategy_config(payload: StrategyConfigRequest, ctx: AuthContext = Depends(admin_auth)) -> Dict[str, Any]:
    try:
        return active_learning_service.configure_strategy(payload.model_dump(exclude_none=True), ctx.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/active-learning/config/strategy")
async def get_strategy_config(ctx: AuthContext = Depends(read_auth)) -> Dict[str, Any]:
    _ = ctx
    return active_learning_service.get_strategy_config()


@router.post("/active-learning/config/budget")
async def set_budget_config(payload: BudgetConfigRequest, ctx: AuthContext = Depends(admin_auth)) -> Dict[str, Any]:
    return active_learning_service.configure_budget(payload.model_dump(exclude_none=True), ctx.user_id)


@router.get("/active-learning/config/budget")
async def get_budget_config(
    session_id: Optional[str] = Query(default=None),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    try:
        return active_learning_service.get_budget_info(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/semi-supervised/pseudo-labels")
async def create_pseudo_labels(payload: PseudoLabelRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        return active_learning_service.generate_pseudo_labels(payload.model_dump(), ctx.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/semi-supervised/pseudo-labels")
async def list_pseudo_labels(
    session_id: Optional[str] = Query(default=None),
    dataset_id: Optional[str] = Query(default=None),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    return active_learning_service.get_pseudo_labels(session_id=session_id, dataset_id=dataset_id)


@router.post("/semi-supervised/consistency")
async def run_consistency_regularization(
    payload: ConsistencyRequest,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return active_learning_service.consistency_regularization(payload.model_dump(), ctx.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/semi-supervised/co-training")
async def run_co_training(payload: CoTrainingRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        return active_learning_service.co_training(payload.model_dump(), ctx.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/semi-supervised/graph")
async def run_graph_ssl(payload: GraphSemiSupervisedRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        return active_learning_service.graph_semi_supervised(payload.model_dump(), ctx.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/semi-supervised/self-training")
async def run_self_training(payload: SelfTrainingRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        return active_learning_service.self_training(payload.model_dump(), ctx.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/incremental/update")
async def run_incremental_update(payload: IncrementalUpdateRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        return active_learning_service.incremental_update(payload.model_dump(), ctx.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/incremental/evaluate")
async def evaluate_incremental(payload: IncrementalEvaluateRequest, ctx: AuthContext = Depends(read_auth)) -> Dict[str, Any]:
    _ = ctx
    return active_learning_service.evaluate_incremental(payload.model_dump())


@router.get("/incremental/history")
async def get_incremental_history(
    limit: int = Query(default=20, ge=1, le=200),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    return active_learning_service.get_incremental_history(limit)


@router.post("/active-learning/annotation/request")
async def create_annotation_request(
    payload: AnnotationRequestPayload,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return active_learning_service.create_annotation_requests(payload.model_dump(), ctx.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/active-learning/annotation/batch")
async def create_batch_annotation(
    payload: AnnotationBatchPayload,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return active_learning_service.create_batch_annotation(payload.model_dump(), ctx.user_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/active-learning/annotation/suggestions")
async def get_annotation_suggestions(
    payload: AnnotationSuggestionPayload,
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return active_learning_service.get_annotation_suggestions(payload.model_dump(), ctx.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/active-learning/annotation/quality")
async def assess_annotation_quality(
    payload: AnnotationQualityPayload,
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    return active_learning_service.assess_annotation_quality(payload.model_dump())


@router.get("/active-learning/evaluate")
async def evaluate_active_learning(
    session_id: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    try:
        return active_learning_service.evaluate_active_learning(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/semi-supervised/evaluate")
async def evaluate_semi_supervised(
    session_id: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    try:
        return active_learning_service.evaluate_semi_supervised(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/active-learning/visualization")
async def get_visualization_payload(
    session_id: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    _ = ctx
    try:
        return active_learning_service.visualization_payload(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
