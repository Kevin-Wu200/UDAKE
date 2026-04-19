"""Data feedback collection API endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..services.feedback_service import feedback_service

router = APIRouter()

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 120
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
        x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    ) -> AuthContext:
        if settings.is_development or settings.is_testing:
            return AuthContext(user_id=x_user_id or "dev_user", api_key=x_api_key or "dev_key")
        
        if not x_api_key:
             raise HTTPException(status_code=401, detail="X-API-Key header is required")
             
        try:
            _enforce_rate_limit(x_api_key)
            feedback_service.verify_api_key(x_api_key, required_scope=required_scope)
            user_id = feedback_service.resolve_user_id(x_user_id, x_session_token)
            feedback_service.log_request(
                {
                    "path": request.url.path,
                    "method": request.method,
                    "status": "ok",
                    "api_key": x_api_key,
                    "user_id": user_id,
                }
            )
            return AuthContext(user_id=user_id, api_key=x_api_key)
        except HTTPException:
            feedback_service.log_request(
                {
                    "path": request.url.path,
                    "method": request.method,
                    "status": "rate_limited",
                    "api_key": x_api_key,
                    "user_id": x_user_id,
                }
            )
            raise
        except PermissionError as exc:
            feedback_service.log_request(
                {
                    "path": request.url.path,
                    "method": request.method,
                    "status": "denied",
                    "api_key": x_api_key,
                    "user_id": x_user_id,
                    "error": str(exc),
                }
            )
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            feedback_service.log_request(
                {
                    "path": request.url.path,
                    "method": request.method,
                    "status": "error",
                    "api_key": x_api_key,
                    "user_id": x_user_id,
                    "error": str(exc),
                }
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return dep


read_auth = _auth("read")
write_auth = _auth("write")
admin_auth = _auth("admin")


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    role: Literal["admin", "reviewer", "contributor", "viewer"] = "contributor"
    display_name: Optional[str] = Field(default=None, max_length=64)
    domain: Optional[str] = Field(default="general", max_length=64)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class InputRecordRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, max_length=128)
    x: float
    y: float
    z: float = 0.0
    value: float
    observed_value: Optional[float] = None
    measured_value: Optional[float] = None
    timestamp: str
    device: str = "unknown"
    method: str = "manual"
    source: str = "manual"
    quality_flag: str = "unknown"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModificationRequest(BaseModel):
    target_record_id: str = Field(..., min_length=1)
    new_value: Optional[float] = None
    reason: Literal["correction", "update", "delete"] = "update"
    note: str = ""


class ValidationRequest(BaseModel):
    target_record_id: str = Field(..., min_length=1)
    predicted_value: float
    result: Literal["accept", "reject", "correct"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    context: Dict[str, Any] = Field(default_factory=dict)
    corrected_value: Optional[float] = None


class AnnotationRequest(BaseModel):
    target_record_id: Optional[str] = None
    dataset_id: Optional[str] = None
    anomaly_type: str = Field(..., min_length=1, max_length=128)
    severity: int = Field(default=3, ge=1, le=5)
    quality_grade: str = Field(default="C", min_length=1, max_length=4)
    label: str = Field(default="general", min_length=1, max_length=64)
    reason: str = Field(default="", max_length=500)


class BatchImportRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, max_length=128)
    format: Literal["csv", "geojson", "excel"]
    content: Optional[Any] = None
    rows: Optional[List[Dict[str, Any]]] = None
    mapping: Dict[str, str] = Field(default_factory=dict)


class ConflictResolveRequest(BaseModel):
    strategy: Literal["latest", "quality", "manual"]
    manual_modification_id: Optional[str] = None


class ApiKeyCreateRequest(BaseModel):
    owner: str = Field(..., min_length=1, max_length=128)
    scopes: List[Literal["read", "write", "admin"]] = Field(..., min_length=1)


class BackupRequest(BaseModel):
    mode: Literal["full", "incremental"] = "full"


class ArchiveRequest(BaseModel):
    before: str = Field(..., description="ISO8601 timestamp")


@router.get("/feedback/health")
async def feedback_health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "module": "feedback_collection",
        "rate_limit": {
            "window_seconds": RATE_LIMIT_WINDOW_SECONDS,
            "max_requests": RATE_LIMIT_MAX_REQUESTS,
        },
    }


@router.post("/users/register")
async def register_user(payload: UserRegisterRequest) -> Dict[str, Any]:
    try:
        user = feedback_service.register_user(payload.model_dump())
        return {"user": user}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/users/login")
async def login_user(payload: UserLoginRequest) -> Dict[str, Any]:
    try:
        session = feedback_service.authenticate_user(payload.username, payload.password)
        return session
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/users/leaderboard")
async def get_leaderboard(
    metric: Literal["contribution", "reliability", "points", "quality"] = Query(default="contribution"),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    try:
        data = feedback_service.get_leaderboard(metric=metric, top_n=limit)
        return {"metric": metric, "count": len(data), "items": data}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/users/{user_id}")
async def get_user(user_id: str, ctx: AuthContext = Depends(read_auth)) -> Dict[str, Any]:
    try:
        return {"user": feedback_service.get_user(user_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/users/{user_id}/reliability")
async def get_user_reliability(user_id: str, ctx: AuthContext = Depends(read_auth)) -> Dict[str, Any]:
    try:
        return feedback_service.get_user_reliability(user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/users/{user_id}/contributions")
async def get_user_contributions(user_id: str, ctx: AuthContext = Depends(read_auth)) -> Dict[str, Any]:
    try:
        return feedback_service.get_user_contributions(user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/feedback/input")
async def create_feedback_input(payload: InputRecordRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        item = feedback_service.submit_input(payload.model_dump(), ctx.user_id)
        return {"record": item}
    except (ValueError, KeyError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback/modification")
async def create_feedback_modification(payload: ModificationRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        item = feedback_service.submit_modification(payload.model_dump(), ctx.user_id)
        return {"record": item}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback/validation")
async def create_feedback_validation(payload: ValidationRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        item = feedback_service.submit_validation(payload.model_dump(), ctx.user_id)
        return {"record": item}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback/annotation")
async def create_feedback_annotation(payload: AnnotationRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        item = feedback_service.submit_annotation(payload.model_dump(), ctx.user_id)
        return {"record": item}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback/batch")
async def import_feedback_batch(payload: BatchImportRequest, ctx: AuthContext = Depends(write_auth)) -> Dict[str, Any]:
    try:
        result = feedback_service.import_batch(payload.model_dump(), ctx.user_id)
        return result
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/feedback/data")
async def query_feedback_data(
    dataset_id: Optional[str] = None,
    record_type: Optional[Literal["input", "modification", "validation", "annotation"]] = None,
    user_id: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    region: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include_private: bool = Query(default=False),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    try:
        return feedback_service.query_data(
            {
                "dataset_id": dataset_id,
                "record_type": record_type,
                "user_id": user_id,
                "start": start,
                "end": end,
                "region": region,
                "status": status,
                "limit": limit,
                "offset": offset,
            },
            user_id=ctx.user_id,
            include_private=include_private,
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/feedback/history")
async def get_feedback_history(
    entity_id: str = Query(..., min_length=1),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    try:
        return feedback_service.get_history(entity_id, user_id=ctx.user_id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/feedback/history/compare")
async def compare_feedback_history(
    entity_id: str = Query(..., min_length=1),
    from_version: int = Query(..., ge=1),
    to_version: int = Query(..., ge=1),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    try:
        return feedback_service.compare_versions(entity_id, from_version, to_version, user_id=ctx.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback/history/{entity_id}/rollback")
async def rollback_feedback_history(
    entity_id: str,
    version: int = Query(..., ge=1),
    ctx: AuthContext = Depends(admin_auth),
) -> Dict[str, Any]:
    try:
        return {"record": feedback_service.rollback_version(entity_id, version, user_id=ctx.user_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/feedback/stats")
async def get_feedback_stats(
    dataset_id: Optional[str] = None,
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    return feedback_service.get_statistics(dataset_id=dataset_id, user_id=ctx.user_id)


@router.get("/feedback/quality")
async def get_feedback_quality(
    dataset_id: Optional[str] = None,
    record_id: Optional[str] = None,
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    try:
        return feedback_service.get_quality_report(user_id=ctx.user_id, dataset_id=dataset_id, record_id=record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/feedback/conflicts")
async def get_feedback_conflicts(
    unresolved_only: bool = Query(default=False),
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    return feedback_service.get_conflicts(user_id=ctx.user_id, unresolved_only=unresolved_only)


@router.post("/feedback/conflicts/{conflict_id}/resolve")
async def resolve_feedback_conflict(
    conflict_id: str,
    payload: ConflictResolveRequest,
    ctx: AuthContext = Depends(admin_auth),
) -> Dict[str, Any]:
    try:
        result = feedback_service.resolve_conflict(
            conflict_id=conflict_id,
            strategy=payload.strategy,
            user_id=ctx.user_id,
            manual_modification_id=payload.manual_modification_id,
        )
        return {"conflict": result}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/feedback/export")
async def export_feedback_data(
    fmt: Literal["json", "csv", "geojson", "excel"] = Query(default="json"),
    dataset_id: Optional[str] = None,
    record_type: Optional[Literal["input", "modification", "validation", "annotation"]] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    ctx: AuthContext = Depends(read_auth),
) -> Dict[str, Any]:
    try:
        return feedback_service.export_data(
            fmt=fmt,
            filters={
                "dataset_id": dataset_id,
                "record_type": record_type,
                "start": start,
                "end": end,
                "limit": 500,
                "offset": 0,
            },
            user_id=ctx.user_id,
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback/backup")
async def backup_feedback(payload: BackupRequest, ctx: AuthContext = Depends(admin_auth)) -> Dict[str, Any]:
    try:
        return feedback_service.create_backup(mode=payload.mode, user_id=ctx.user_id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback/backup/{backup_id}/restore")
async def restore_feedback_backup(backup_id: str, ctx: AuthContext = Depends(admin_auth)) -> Dict[str, Any]:
    try:
        return feedback_service.restore_backup(backup_id=backup_id, user_id=ctx.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback/archive")
async def archive_feedback(payload: ArchiveRequest, ctx: AuthContext = Depends(admin_auth)) -> Dict[str, Any]:
    try:
        return feedback_service.archive_before(before=payload.before, user_id=ctx.user_id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/feedback/integration/{module}")
async def ingest_module_feedback(
    module: str,
    payload: Dict[str, Any],
    ctx: AuthContext = Depends(write_auth),
) -> Dict[str, Any]:
    try:
        return feedback_service.ingest_integration_feedback(module, payload, user_id=ctx.user_id)
    except (ValueError, KeyError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/feedback/api-keys")
async def list_api_keys(ctx: AuthContext = Depends(admin_auth)) -> Dict[str, Any]:
    try:
        items = feedback_service.list_api_keys(user_id=ctx.user_id)
        return {"count": len(items), "items": items}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/feedback/api-keys")
async def create_api_key(payload: ApiKeyCreateRequest, ctx: AuthContext = Depends(admin_auth)) -> Dict[str, Any]:
    try:
        item = feedback_service.create_api_key(payload.owner, payload.scopes, created_by=ctx.user_id)
        return {"api_key": item}
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
