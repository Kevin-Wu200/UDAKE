"""智能工作流 API 测试。"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import 智能工作流接口 as workflow_api
from app.services.智能工作流服务 import SmartWorkflowService


def _basic_workflow_definition() -> dict:
    return {
        "name": "api-basic-workflow",
        "nodes": [
            {
                "node_id": "input",
                "kind": "input",
                "node_type": "input.constant",
                "params": {"value": [1, 2, 3, 4]},
            },
            {
                "node_id": "sample",
                "kind": "process",
                "node_type": "process.sample",
                "params": {"step": 2},
            },
            {
                "node_id": "sum",
                "kind": "process",
                "node_type": "process.transform",
                "params": {"operation": "sum", "source": "{{nodes.sample}}"},
            },
            {
                "node_id": "output",
                "kind": "output",
                "node_type": "output.collect",
                "params": {"fields": ["sample", "sum"]},
            },
        ],
        "edges": [
            {"source": "input", "target": "sample"},
            {"source": "sample", "target": "sum"},
            {"source": "sum", "target": "output"},
        ],
    }


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    service = SmartWorkflowService(auto_start_scheduler=False)
    workflow_api.smart_workflow_service = service
    app.include_router(workflow_api.router, prefix="/api")

    with TestClient(app) as test_client:
        yield test_client

    service.stop_scheduler()


def _wait_run_completed(client: TestClient, run_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/workflow/runs/{run_id}")
        assert resp.status_code == 200
        run = resp.json()
        if run["status"] in {"completed", "failed"}:
            return run
        time.sleep(0.05)
    raise TimeoutError(f"run timeout: {run_id}")


def _create_workflow_and_set_admin(client: TestClient, admin_user_id: str = "alice") -> str:
    create_resp = client.post("/api/workflow", json={"definition": _basic_workflow_definition()})
    assert create_resp.status_code == 200
    workflow_id = create_resp.json()["workflow"]["workflow_id"]
    collaborators_resp = client.patch(
        f"/api/workflow/{workflow_id}/collaborators",
        json={
            "collaborators": [
                {"user_id": admin_user_id, "role": "admin", "display_name": admin_user_id},
            ]
        },
    )
    assert collaborators_resp.status_code == 200
    return workflow_id


def test_workflow_health_and_template_library(client: TestClient) -> None:
    health = client.get("/api/workflow/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    templates = client.get("/api/workflow/templates")
    assert templates.status_code == 200
    assert templates.json()["count"] >= 20

    marketplace = client.get("/api/workflow/marketplace?limit=5")
    assert marketplace.status_code == 200
    assert 1 <= marketplace.json()["count"] <= 5


def test_create_validate_execute_and_logs(client: TestClient) -> None:
    definition = _basic_workflow_definition()

    validate_resp = client.post("/api/workflow/validate", json={"definition": definition})
    assert validate_resp.status_code == 200
    assert validate_resp.json()["valid"] is True

    create_resp = client.post("/api/workflow", json={"definition": definition})
    assert create_resp.status_code == 200
    workflow = create_resp.json()["workflow"]
    workflow_id = workflow["workflow_id"]

    execute_resp = client.post(
        f"/api/workflow/{workflow_id}/execute",
        json={"async": True, "input_variables": {"tenant": "test"}},
    )
    assert execute_resp.status_code == 200
    run_id = execute_resp.json()["run_id"]

    run = _wait_run_completed(client, run_id)
    assert run["status"] == "completed"
    assert run["node_outputs"]["sum"] == 4

    logs_resp = client.get(f"/api/workflow/runs/{run_id}/logs")
    assert logs_resp.status_code == 200
    assert logs_resp.json()["count"] >= 1

    list_runs = client.get(f"/api/workflow/{workflow_id}/runs")
    assert list_runs.status_code == 200
    assert list_runs.json()["count"] >= 1


def test_version_rollback_schedule_and_recommendation(client: TestClient) -> None:
    create_resp = client.post("/api/workflow", json={"definition": _basic_workflow_definition()})
    assert create_resp.status_code == 200
    workflow_id = create_resp.json()["workflow"]["workflow_id"]

    update_resp = client.put(
        f"/api/workflow/{workflow_id}",
        json={
            "updates": {"description": "new-version"},
            "note": "for-test",
        },
    )
    assert update_resp.status_code == 200

    versions_resp = client.get(f"/api/workflow/{workflow_id}/versions")
    assert versions_resp.status_code == 200
    versions = versions_resp.json()["versions"]
    assert len(versions) >= 2

    rollback_resp = client.post(f"/api/workflow/{workflow_id}/rollback/1")
    assert rollback_resp.status_code == 200

    recommend_resp = client.get("/api/workflow/templates/recommend?tags=采样,插值&limit=3")
    assert recommend_resp.status_code == 200
    assert 1 <= recommend_resp.json()["count"] <= 3

    schedule_resp = client.post(
        f"/api/workflow/{workflow_id}/schedules",
        json={"interval_seconds": 60, "trigger_payload": {"source": "schedule"}},
    )
    assert schedule_resp.status_code == 200
    schedule_id = schedule_resp.json()["schedule"]["schedule_id"]

    trigger_resp = client.post(f"/api/workflow/schedules/{schedule_id}/trigger")
    assert trigger_resp.status_code == 200
    run_id = trigger_resp.json()["run"]["run_id"]

    run = _wait_run_completed(client, run_id)
    assert run["status"] == "completed"

    perf_resp = client.get("/api/workflow/performance")
    assert perf_resp.status_code == 200
    assert perf_resp.json()["total_runs"] >= 1


def test_team_invitation_and_permission_delegation(client: TestClient) -> None:
    workflow_id = _create_workflow_and_set_admin(client, admin_user_id="alice")

    team_resp = client.post(
        "/api/workflow/teams",
        json={"name": "协作团队A", "owner_user_id": "alice", "description": "测试团队"},
    )
    assert team_resp.status_code == 200
    team_id = team_resp.json()["team"]["team_id"]

    invite_resp = client.post(
        "/api/workflow/invitations",
        json={"team_id": team_id, "email": "bob@example.com", "role": "viewer", "invited_by": "alice"},
    )
    assert invite_resp.status_code == 200
    invite_id = invite_resp.json()["invitation"]["invite_id"]

    accept_resp = client.post(
        f"/api/workflow/invitations/{invite_id}/accept",
        json={"user_id": "bob", "display_name": "Bob"},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["invitation"]["status"] == "accepted"

    bind_resp = client.post(f"/api/workflow/{workflow_id}/teams", json={"team_id": team_id})
    assert bind_resp.status_code == 200
    assert team_id in bind_resp.json()["team_ids"]

    bob_perm_before = client.get(f"/api/workflow/{workflow_id}/permissions/bob")
    assert bob_perm_before.status_code == 200
    assert "view_workflow" in bob_perm_before.json()["permissions"]
    assert "edit_workflow" not in bob_perm_before.json()["permissions"]

    delegation_resp = client.post(
        f"/api/workflow/{workflow_id}/delegations",
        json={
            "from_user_id": "alice",
            "to_user_id": "bob",
            "permission": "edit_workflow",
            "ttl_hours": 24,
        },
    )
    assert delegation_resp.status_code == 200

    bob_perm_after = client.get(f"/api/workflow/{workflow_id}/permissions/bob")
    assert bob_perm_after.status_code == 200
    assert "edit_workflow" in bob_perm_after.json()["permissions"]


def test_collaboration_ot_conflict_comment_cursor_notification(client: TestClient) -> None:
    workflow_id = _create_workflow_and_set_admin(client, admin_user_id="alice")
    workflow_api.smart_workflow_service._email_service._send_sync = lambda task: None  # type: ignore[attr-defined]
    collaborators_resp = client.patch(
        f"/api/workflow/{workflow_id}/collaborators",
        json={
            "collaborators": [
                {"user_id": "alice", "role": "admin"},
                {"user_id": "bob", "role": "editor"},
                {"user_id": "charlie", "role": "commenter"},
            ]
        },
    )
    assert collaborators_resp.status_code == 200

    op1 = client.post(
        f"/api/workflow/{workflow_id}/collaboration/operations",
        json={
            "actor_id": "bob",
            "base_revision": 0,
            "operation_type": "set_node_param",
            "data": {"node_id": "sample", "param_key": "step", "param_value": 3},
        },
    )
    assert op1.status_code == 200
    assert op1.json()["applied"] is True

    op2 = client.post(
        f"/api/workflow/{workflow_id}/collaboration/operations",
        json={
            "actor_id": "bob",
            "base_revision": 0,
            "operation_type": "set_node_param",
            "conflict_strategy": "manual",
            "data": {"node_id": "sample", "param_key": "step", "param_value": 5},
        },
    )
    assert op2.status_code == 200
    assert op2.json()["applied"] is False
    conflict = op2.json()["conflict"]
    assert conflict is not None

    conflicts_resp = client.get(f"/api/workflow/{workflow_id}/collaboration/conflicts?unresolved_only=true")
    assert conflicts_resp.status_code == 200
    assert conflicts_resp.json()["count"] >= 1

    resolve_resp = client.post(
        f"/api/workflow/{workflow_id}/collaboration/conflicts/{conflict['conflict_id']}/resolve",
        json={"resolver_user_id": "alice", "strategy": "custom", "override_value": 4},
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["conflict"]["status"] == "resolved"

    cursor_resp = client.post(
        f"/api/workflow/{workflow_id}/collaboration/cursors",
        json={"user_id": "bob", "position": {"node_id": "sample", "x": 100, "y": 120}},
    )
    assert cursor_resp.status_code == 200
    online_users_resp = client.get(f"/api/workflow/{workflow_id}/online-users")
    assert online_users_resp.status_code == 200
    assert online_users_resp.json()["count"] >= 1

    comment_resp = client.post(
        f"/api/workflow/{workflow_id}/comments",
        json={"user_id": "bob", "content": "请 @charlie 复核这个参数"},
    )
    assert comment_resp.status_code == 200
    assert "charlie" in comment_resp.json()["comment"]["mentions"]

    pref_set_for_email_resp = client.put(
        f"/api/workflow/{workflow_id}/notifications/preferences",
        json={
            "user_id": "charlie",
            "preferences": {"email": True, "email_address": "charlie@example.com"},
        },
    )
    assert pref_set_for_email_resp.status_code == 200

    comment_resp2 = client.post(
        f"/api/workflow/{workflow_id}/comments",
        json={"user_id": "bob", "content": "再请 @charlie 看一下"},
    )
    assert comment_resp2.status_code == 200

    notif_resp = client.get(f"/api/workflow/{workflow_id}/notifications?user_id=charlie")
    assert notif_resp.status_code == 200
    assert notif_resp.json()["count"] >= 1
    assert notif_resp.json()["notifications"][0]["event_type"] == "mention"
    assert notif_resp.json()["notifications"][0]["channels"]["email"] is True
    assert notif_resp.json()["notifications"][0]["channels"].get("email_message_id")

    pref_set_resp = client.put(
        f"/api/workflow/{workflow_id}/notifications/preferences",
        json={
            "user_id": "charlie",
            "preferences": {"mention_only": True, "muted_event_types": ["comment_created"]},
        },
    )
    assert pref_set_resp.status_code == 200
    pref_get_resp = client.get(f"/api/workflow/{workflow_id}/notifications/preferences?user_id=charlie")
    assert pref_get_resp.status_code == 200
    assert pref_get_resp.json()["preferences"]["mention_only"] is True


def test_share_export_social_and_collaboration_analytics(client: TestClient) -> None:
    workflow_id = _create_workflow_and_set_admin(client, admin_user_id="alice")

    share_resp = client.post(
        f"/api/workflow/{workflow_id}/share-links",
        json={"creator_user_id": "alice", "access_mode": "public", "expires_in_hours": 24},
    )
    assert share_resp.status_code == 200
    share_link_id = share_resp.json()["share_link"]["share_link_id"]

    access_resp = client.post(f"/api/workflow/share/{share_link_id}", json={})
    assert access_resp.status_code == 200
    assert access_resp.json()["workflow"]["workflow_id"] == workflow_id

    export_resp = client.post(
        f"/api/workflow/{workflow_id}/export-data",
        json={"fmt": "csv", "share_link_id": share_link_id},
    )
    assert export_resp.status_code == 200
    assert export_resp.json()["format"] == "csv"
    assert export_resp.json()["size"] > 0

    share_stats_resp = client.get(f"/api/workflow/{workflow_id}/share-stats")
    assert share_stats_resp.status_code == 200
    assert share_stats_resp.json()["total_views"] >= 1
    assert share_stats_resp.json()["total_downloads"] >= 1

    social_resp = client.post(
        f"/api/workflow/{workflow_id}/social-share",
        json={"share_link_id": share_link_id, "title": "测试分享"},
    )
    assert social_resp.status_code == 200
    assert "x" in social_resp.json()["platform_links"]

    analytics_resp = client.get(f"/api/workflow/{workflow_id}/collaboration/analytics")
    assert analytics_resp.status_code == 200
    assert analytics_resp.json()["analytics"]["share_views"] >= 1
    assert analytics_resp.json()["analytics"]["share_downloads"] >= 1

    cache_metrics_resp = client.get("/api/workflow/cache/metrics")
    assert cache_metrics_resp.status_code == 200
    assert "hit_rate" in cache_metrics_resp.json()


def test_smtp_validate_and_email_logs_api(client: TestClient) -> None:
    workflow_api.smart_workflow_service._email_service._send_sync = lambda task: None  # type: ignore[attr-defined]
    validate_resp = client.post("/api/workflow/notifications/smtp/validate", json={"test_recipient": ""})
    assert validate_resp.status_code == 200
    assert "enabled" in validate_resp.json()

    logs_resp = client.get("/api/workflow/notifications/email-logs?limit=10")
    assert logs_resp.status_code == 200
    assert "logs" in logs_resp.json()
