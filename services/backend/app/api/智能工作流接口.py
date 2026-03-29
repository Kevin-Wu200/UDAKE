"""智能工作流引擎 API。"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..services.智能工作流服务 import SmartWorkflowService, smart_workflow_service
from ..workflow.schema import WorkflowValidationError

router = APIRouter()


class WorkflowValidateRequest(BaseModel):
    definition: Dict[str, Any]


class WorkflowCreateRequest(BaseModel):
    definition: Dict[str, Any]


class WorkflowUpdateRequest(BaseModel):
    updates: Dict[str, Any]
    note: str = Field(default="update", max_length=120)


class WorkflowExecuteRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    input_variables: Dict[str, Any] = Field(default_factory=dict)
    async_mode: bool = Field(default=False, alias="async")
    debug: bool = Field(default=False)
    trigger: str = Field(default="manual", max_length=80)


class WorkflowImportRequest(BaseModel):
    definition: Dict[str, Any]
    overwrite: bool = False


class CollaboratorUpdateRequest(BaseModel):
    collaborators: List[Dict[str, Any]]


class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: str = Field(default="custom", max_length=60)
    tags: List[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=500)
    shared: bool = Field(default=False)
    workflow: Dict[str, Any]


class TemplateShareRequest(BaseModel):
    shared: bool = True


class TemplateRatingRequest(BaseModel):
    rating: float = Field(..., ge=1, le=5)
    user_id: str = Field(default="anonymous", max_length=60)
    comment: str = Field(default="", max_length=500)


class TemplateInstantiateRequest(BaseModel):
    workflow_name: Optional[str] = Field(default=None, max_length=200)


class ScheduleCreateRequest(BaseModel):
    interval_seconds: int = Field(..., ge=1, le=86400)
    enabled: bool = True
    trigger_payload: Dict[str, Any] = Field(default_factory=dict)


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, WorkflowValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/workflow/health")
async def workflow_health() -> Dict[str, Any]:
    return smart_workflow_service.health_snapshot()


@router.get("/workflow/schema")
async def workflow_schema() -> Dict[str, Any]:
    return smart_workflow_service.get_schema()


@router.get("/workflow/node-types")
async def workflow_node_types() -> Dict[str, Any]:
    return smart_workflow_service.list_node_types()


@router.post("/workflow/validate")
async def validate_workflow(payload: WorkflowValidateRequest) -> Dict[str, Any]:
    try:
        return smart_workflow_service.validate_definition(payload.definition)
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow")
async def create_workflow(payload: WorkflowCreateRequest) -> Dict[str, Any]:
    try:
        record = smart_workflow_service.create_workflow(payload.definition)
        return {"workflow": record}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow")
async def list_workflows() -> Dict[str, Any]:
    items = smart_workflow_service.list_workflows()
    return {"workflows": items, "count": len(items)}


@router.get("/workflow/{workflow_id}/versions")
async def list_workflow_versions(workflow_id: str) -> Dict[str, Any]:
    try:
        versions = smart_workflow_service.list_versions(workflow_id)
        return {"workflow_id": workflow_id, "versions": versions, "count": len(versions)}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/rollback/{version}")
async def rollback_workflow(workflow_id: str, version: int) -> Dict[str, Any]:
    try:
        item = smart_workflow_service.rollback_workflow(workflow_id, version)
        return {"workflow": item}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/export")
async def export_workflow(workflow_id: str) -> Dict[str, Any]:
    try:
        definition = smart_workflow_service.export_workflow(workflow_id)
        return {"definition": definition}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/import")
async def import_workflow(payload: WorkflowImportRequest) -> Dict[str, Any]:
    try:
        record = smart_workflow_service.import_workflow(payload.definition, overwrite=payload.overwrite)
        return {"workflow": record}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.patch("/workflow/{workflow_id}/collaborators")
async def update_collaborators(workflow_id: str, payload: CollaboratorUpdateRequest) -> Dict[str, Any]:
    try:
        item = smart_workflow_service.set_collaborators(workflow_id, payload.collaborators)
        return {
            "workflow_id": workflow_id,
            "collaborators": item.get("collaborators", []),
            "count": len(item.get("collaborators", [])),
        }
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, payload: WorkflowExecuteRequest) -> Dict[str, Any]:
    try:
        result = smart_workflow_service.execute_workflow(
            workflow_id=workflow_id,
            input_variables=payload.input_variables,
            async_mode=payload.async_mode,
            trigger=payload.trigger,
            debug=payload.debug,
        )
        return result
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/runs")
async def list_workflow_runs(workflow_id: str, limit: int = Query(default=100, ge=1, le=500)) -> Dict[str, Any]:
    runs = smart_workflow_service.list_runs(workflow_id=workflow_id, limit=limit)
    return {"workflow_id": workflow_id, "runs": runs, "count": len(runs)}


@router.get("/workflow/runs/{run_id}")
async def get_workflow_run(run_id: str) -> Dict[str, Any]:
    run = smart_workflow_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/workflow/runs/{run_id}/logs")
async def get_workflow_run_logs(run_id: str) -> Dict[str, Any]:
    try:
        logs = smart_workflow_service.get_run_logs(run_id)
        return {"run_id": run_id, "logs": logs, "count": len(logs)}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/performance")
async def get_workflow_performance() -> Dict[str, Any]:
    return smart_workflow_service.get_performance_metrics()


@router.get("/workflow/templates")
async def list_workflow_templates(
    category: Optional[str] = Query(default=None),
    shared_only: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
) -> Dict[str, Any]:
    items = smart_workflow_service.list_templates(category=category, shared_only=shared_only, limit=limit)
    return {"templates": items, "count": len(items)}


@router.post("/workflow/templates")
async def create_workflow_template(payload: TemplateCreateRequest) -> Dict[str, Any]:
    try:
        template = smart_workflow_service.create_template(payload.model_dump())
        return {"template": template}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/templates/{template_id}/share")
async def share_workflow_template(template_id: str, payload: TemplateShareRequest) -> Dict[str, Any]:
    try:
        template = smart_workflow_service.share_template(template_id, shared=payload.shared)
        return {"template": template}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/templates/{template_id}/rate")
async def rate_workflow_template(template_id: str, payload: TemplateRatingRequest) -> Dict[str, Any]:
    try:
        template = smart_workflow_service.rate_template(
            template_id,
            payload.rating,
            user_id=payload.user_id,
            comment=payload.comment,
        )
        return {"template": template}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/templates/recommend")
async def recommend_workflow_templates(
    tags: Optional[str] = Query(default=None, description="逗号分隔标签"),
    category: Optional[str] = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
) -> Dict[str, Any]:
    parsed_tags = [item.strip() for item in (tags or "").split(",") if item.strip()]
    items = smart_workflow_service.recommend_templates(tags=parsed_tags, category=category, limit=limit)
    return {"recommendations": items, "count": len(items)}


@router.post("/workflow/templates/{template_id}/instantiate")
async def instantiate_template(template_id: str, payload: TemplateInstantiateRequest) -> Dict[str, Any]:
    try:
        workflow = smart_workflow_service.create_workflow_from_template(template_id, workflow_name=payload.workflow_name)
        return {"workflow": workflow}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/marketplace")
async def workflow_marketplace(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    items = smart_workflow_service.get_marketplace(limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/workflow/{workflow_id}/schedules")
async def create_workflow_schedule(workflow_id: str, payload: ScheduleCreateRequest) -> Dict[str, Any]:
    try:
        schedule = smart_workflow_service.create_schedule(
            workflow_id=workflow_id,
            interval_seconds=payload.interval_seconds,
            trigger_payload=payload.trigger_payload,
            enabled=payload.enabled,
        )
        return {"schedule": schedule}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/schedules")
async def list_workflow_schedules(workflow_id: str) -> Dict[str, Any]:
    schedules = smart_workflow_service.list_schedules(workflow_id)
    return {"workflow_id": workflow_id, "schedules": schedules, "count": len(schedules)}


@router.delete("/workflow/schedules/{schedule_id}")
async def delete_workflow_schedule(schedule_id: str) -> Dict[str, Any]:
    try:
        smart_workflow_service.delete_schedule(schedule_id)
        return {"deleted": True, "schedule_id": schedule_id}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/schedules/{schedule_id}/trigger")
async def trigger_workflow_schedule(schedule_id: str) -> Dict[str, Any]:
    try:
        run = smart_workflow_service.trigger_schedule(schedule_id)
        return {"run": run}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}")
async def get_workflow(workflow_id: str) -> Dict[str, Any]:
    item = smart_workflow_service.get_workflow(workflow_id)
    if not item:
        raise HTTPException(status_code=404, detail="workflow not found")
    return item


@router.put("/workflow/{workflow_id}")
async def update_workflow(workflow_id: str, payload: WorkflowUpdateRequest) -> Dict[str, Any]:
    try:
        item = smart_workflow_service.update_workflow(workflow_id, payload.updates, note=payload.note)
        return {"workflow": item}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.delete("/workflow/{workflow_id}")
async def delete_workflow(workflow_id: str) -> Dict[str, Any]:
    try:
        smart_workflow_service.delete_workflow(workflow_id)
        return {"deleted": True, "workflow_id": workflow_id}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


__all__ = ["router", "SmartWorkflowService", "smart_workflow_service"]
