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


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    owner_user_id: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)


class TeamMemberRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    role: str = Field(default="viewer", max_length=40)
    display_name: str = Field(default="", max_length=120)


class TeamBindRequest(BaseModel):
    team_id: str = Field(..., min_length=1, max_length=80)


class InviteCreateRequest(BaseModel):
    team_id: str = Field(..., min_length=1, max_length=80)
    email: str = Field(..., min_length=3, max_length=255)
    role: str = Field(default="viewer", max_length=40)
    invited_by: str = Field(default="system", max_length=80)
    ttl_hours: int = Field(default=72, ge=1, le=24 * 30)


class InviteAcceptRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    display_name: str = Field(default="", max_length=120)


class DelegationCreateRequest(BaseModel):
    from_user_id: str = Field(..., min_length=1, max_length=80)
    to_user_id: str = Field(..., min_length=1, max_length=80)
    permission: str = Field(..., min_length=1, max_length=80)
    ttl_hours: int = Field(default=24, ge=1, le=24 * 30)


class NotificationPreferenceRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    preferences: Dict[str, Any] = Field(default_factory=dict)


class CommentCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    content: str = Field(..., min_length=1, max_length=1000)
    parent_comment_id: Optional[str] = Field(default=None, max_length=80)


class CursorUpdateRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    position: Dict[str, Any] = Field(default_factory=dict)


class CollaborationOperationRequest(BaseModel):
    actor_id: str = Field(..., min_length=1, max_length=80)
    operation_id: Optional[str] = Field(default=None, max_length=80)
    base_revision: int = Field(default=0, ge=0)
    operation_type: str = Field(..., min_length=1, max_length=60)
    conflict_strategy: str = Field(default="last_write_wins", max_length=40)
    data: Dict[str, Any] = Field(default_factory=dict)


class ConflictResolveRequest(BaseModel):
    resolver_user_id: str = Field(..., min_length=1, max_length=80)
    strategy: str = Field(default="server_wins", max_length=40)
    override_value: Any = None


class ShareLinkCreateRequest(BaseModel):
    creator_user_id: str = Field(..., min_length=1, max_length=80)
    access_mode: str = Field(default="public", max_length=40)
    password: str = Field(default="", max_length=120)
    expires_in_hours: int = Field(default=24 * 7, ge=1, le=24 * 90)


class ShareAccessRequest(BaseModel):
    password: str = Field(default="", max_length=120)
    viewer_user_id: str = Field(default="", max_length=80)


class ShareRevokeRequest(BaseModel):
    operator_user_id: str = Field(..., min_length=1, max_length=80)


class WorkflowExportDataRequest(BaseModel):
    fmt: str = Field(default="json", max_length=20)
    share_link_id: Optional[str] = Field(default=None, max_length=80)


class SocialShareRequest(BaseModel):
    share_link_id: str = Field(..., min_length=1, max_length=80)
    title: Optional[str] = Field(default=None, max_length=200)


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, WorkflowValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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


@router.post("/workflow/teams")
async def create_team(payload: TeamCreateRequest) -> Dict[str, Any]:
    try:
        team = smart_workflow_service.create_team(
            name=payload.name,
            owner_user_id=payload.owner_user_id,
            description=payload.description,
        )
        return {"team": team}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/teams")
async def list_teams(user_id: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    items = smart_workflow_service.list_teams(user_id=user_id)
    return {"teams": items, "count": len(items)}


@router.post("/workflow/teams/{team_id}/members")
async def add_team_member(team_id: str, payload: TeamMemberRequest) -> Dict[str, Any]:
    try:
        team = smart_workflow_service.add_team_member(
            team_id=team_id,
            user_id=payload.user_id,
            role=payload.role,
            display_name=payload.display_name,
        )
        return {"team": team}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.delete("/workflow/teams/{team_id}/members/{user_id}")
async def remove_team_member(team_id: str, user_id: str) -> Dict[str, Any]:
    try:
        team = smart_workflow_service.remove_team_member(team_id=team_id, user_id=user_id)
        return {"team": team}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/teams")
async def bind_team(workflow_id: str, payload: TeamBindRequest) -> Dict[str, Any]:
    try:
        return smart_workflow_service.bind_team_to_workflow(workflow_id=workflow_id, team_id=payload.team_id)
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/invitations")
async def create_team_invitation(payload: InviteCreateRequest) -> Dict[str, Any]:
    try:
        invitation = smart_workflow_service.create_invitation(
            team_id=payload.team_id,
            email=payload.email,
            role=payload.role,
            invited_by=payload.invited_by,
            ttl_hours=payload.ttl_hours,
        )
        return {"invitation": invitation}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/invitations")
async def list_team_invitations(
    team_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    items = smart_workflow_service.list_invitations(team_id=team_id, status=status)
    return {"invitations": items, "count": len(items)}


@router.post("/workflow/invitations/{invite_id}/accept")
async def accept_team_invitation(invite_id: str, payload: InviteAcceptRequest) -> Dict[str, Any]:
    try:
        result = smart_workflow_service.accept_invitation(
            invite_id=invite_id,
            user_id=payload.user_id,
            display_name=payload.display_name,
        )
        return result
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/permissions/{user_id}")
async def get_workflow_permissions(workflow_id: str, user_id: str) -> Dict[str, Any]:
    try:
        return smart_workflow_service.get_effective_permissions(workflow_id=workflow_id, user_id=user_id)
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/delegations")
async def create_workflow_delegation(workflow_id: str, payload: DelegationCreateRequest) -> Dict[str, Any]:
    try:
        delegation = smart_workflow_service.create_permission_delegation(
            workflow_id=workflow_id,
            from_user_id=payload.from_user_id,
            to_user_id=payload.to_user_id,
            permission=payload.permission,
            ttl_hours=payload.ttl_hours,
        )
        return {"delegation": delegation}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/delegations")
async def list_workflow_delegations(
    workflow_id: str,
    user_id: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
) -> Dict[str, Any]:
    items = smart_workflow_service.list_permission_delegations(
        workflow_id=workflow_id,
        user_id=user_id,
        active_only=active_only,
    )
    return {"delegations": items, "count": len(items)}


@router.post("/workflow/delegations/{delegation_id}/revoke")
async def revoke_workflow_delegation(delegation_id: str) -> Dict[str, Any]:
    try:
        delegation = smart_workflow_service.revoke_permission_delegation(delegation_id=delegation_id)
        return {"delegation": delegation}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/collaboration/operations")
async def apply_collaboration_operation(workflow_id: str, payload: CollaborationOperationRequest) -> Dict[str, Any]:
    try:
        return smart_workflow_service.apply_collaboration_operation(workflow_id=workflow_id, payload=payload.model_dump())
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/collaboration/conflicts")
async def list_collaboration_conflicts(
    workflow_id: str,
    unresolved_only: bool = Query(default=False),
) -> Dict[str, Any]:
    try:
        return smart_workflow_service.list_collaboration_conflicts(
            workflow_id=workflow_id,
            unresolved_only=unresolved_only,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/collaboration/conflicts/{conflict_id}/resolve")
async def resolve_collaboration_conflict(
    workflow_id: str,
    conflict_id: str,
    payload: ConflictResolveRequest,
) -> Dict[str, Any]:
    try:
        conflict = smart_workflow_service.resolve_collaboration_conflict(
            workflow_id=workflow_id,
            conflict_id=conflict_id,
            resolver_user_id=payload.resolver_user_id,
            strategy=payload.strategy,
            override_value=payload.override_value,
        )
        return {"conflict": conflict}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/collaboration/cursors")
async def update_collaboration_cursor(workflow_id: str, payload: CursorUpdateRequest) -> Dict[str, Any]:
    try:
        return smart_workflow_service.update_collaboration_cursor(
            workflow_id=workflow_id,
            user_id=payload.user_id,
            position=payload.position,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/collaboration/cursors")
async def list_collaboration_cursors(
    workflow_id: str,
    active_seconds: int = Query(default=30, ge=1, le=3600),
) -> Dict[str, Any]:
    try:
        return smart_workflow_service.list_collaboration_cursors(
            workflow_id=workflow_id,
            active_seconds=active_seconds,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/comments")
async def create_comment(workflow_id: str, payload: CommentCreateRequest) -> Dict[str, Any]:
    try:
        comment = smart_workflow_service.add_comment(
            workflow_id=workflow_id,
            user_id=payload.user_id,
            content=payload.content,
            parent_comment_id=payload.parent_comment_id,
        )
        return {"comment": comment}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/comments")
async def list_comments(workflow_id: str, limit: int = Query(default=200, ge=1, le=1000)) -> Dict[str, Any]:
    try:
        return smart_workflow_service.list_comments(workflow_id=workflow_id, limit=limit)
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.put("/workflow/{workflow_id}/notifications/preferences")
async def set_notification_preferences(workflow_id: str, payload: NotificationPreferenceRequest) -> Dict[str, Any]:
    try:
        return smart_workflow_service.set_notification_preferences(
            workflow_id=workflow_id,
            user_id=payload.user_id,
            preferences=payload.preferences,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/notifications/preferences")
async def get_notification_preferences(workflow_id: str, user_id: str = Query(..., min_length=1)) -> Dict[str, Any]:
    try:
        return smart_workflow_service.get_notification_preferences(workflow_id=workflow_id, user_id=user_id)
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/notifications")
async def list_notifications(
    workflow_id: str,
    user_id: str = Query(..., min_length=1),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> Dict[str, Any]:
    try:
        return smart_workflow_service.list_notifications(
            workflow_id=workflow_id,
            user_id=user_id,
            unread_only=unread_only,
            limit=limit,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/notifications/{notification_id}/read")
async def mark_notification_read(
    workflow_id: str,
    notification_id: str,
    user_id: str = Query(..., min_length=1),
) -> Dict[str, Any]:
    try:
        notification = smart_workflow_service.mark_notification_read(
            workflow_id=workflow_id,
            user_id=user_id,
            notification_id=notification_id,
        )
        return {"notification": notification}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/share-links")
async def create_share_link(workflow_id: str, payload: ShareLinkCreateRequest) -> Dict[str, Any]:
    try:
        share_link = smart_workflow_service.create_share_link(
            workflow_id=workflow_id,
            creator_user_id=payload.creator_user_id,
            access_mode=payload.access_mode,
            password=payload.password,
            expires_in_hours=payload.expires_in_hours,
        )
        return {"share_link": share_link}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/share-links")
async def list_share_links(workflow_id: str) -> Dict[str, Any]:
    try:
        return smart_workflow_service.list_share_links(workflow_id=workflow_id)
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/share/{share_link_id}")
async def access_share_link(share_link_id: str, payload: ShareAccessRequest) -> Dict[str, Any]:
    try:
        return smart_workflow_service.access_share_link(
            share_link_id=share_link_id,
            password=payload.password,
            viewer_user_id=payload.viewer_user_id,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/share-links/{share_link_id}/revoke")
async def revoke_share_link(workflow_id: str, share_link_id: str, payload: ShareRevokeRequest) -> Dict[str, Any]:
    try:
        share_link = smart_workflow_service.revoke_share_link(
            workflow_id=workflow_id,
            share_link_id=share_link_id,
            operator_user_id=payload.operator_user_id,
        )
        return {"share_link": share_link}
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/share-stats")
async def get_share_stats(workflow_id: str) -> Dict[str, Any]:
    try:
        return smart_workflow_service.get_share_statistics(workflow_id=workflow_id)
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/export-data")
async def export_workflow_data(workflow_id: str, payload: WorkflowExportDataRequest) -> Dict[str, Any]:
    try:
        return smart_workflow_service.export_workflow_data(
            workflow_id=workflow_id,
            fmt=payload.fmt,
            share_link_id=payload.share_link_id,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.post("/workflow/{workflow_id}/social-share")
async def social_share(workflow_id: str, payload: SocialShareRequest) -> Dict[str, Any]:
    try:
        return smart_workflow_service.generate_social_share_links(
            workflow_id=workflow_id,
            share_link_id=payload.share_link_id,
            title=payload.title,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _handle_error(exc)


@router.get("/workflow/{workflow_id}/collaboration/analytics")
async def collaboration_analytics(workflow_id: str) -> Dict[str, Any]:
    try:
        return smart_workflow_service.get_collaboration_analytics(workflow_id=workflow_id)
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
