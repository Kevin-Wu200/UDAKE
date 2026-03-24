"""API tests for feedback collection endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api import 数据反馈接口 as feedback_api
from app.services.feedback_service import FeedbackService


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    feedback_api.feedback_service = FeedbackService()
    feedback_api._rate_limit_bucket.clear()
    feedback_api.RATE_LIMIT_MAX_REQUESTS = 120
    app.include_router(feedback_api.router, prefix="/api")
    return TestClient(app)


def _headers(user_id: str | None = None, token: str | None = None) -> dict:
    headers = {"X-API-Key": "dev-feedback-key"}
    if user_id:
        headers["X-User-Id"] = user_id
    if token:
        headers["X-Session-Token"] = token
    return headers


def _create_user(client: TestClient, username: str) -> tuple[str, str]:
    reg = client.post(
        "/api/users/register",
        json={
            "username": username,
            "password": "pass1234",
            "role": "contributor",
            "display_name": username,
            "domain": "environment",
        },
    )
    assert reg.status_code == 200
    user_id = reg.json()["user"]["user_id"]

    login = client.post("/api/users/login", json={"username": username, "password": "pass1234"})
    assert login.status_code == 200
    token = login.json()["token"]
    return user_id, token


def test_health_and_auth_flow(client: TestClient) -> None:
    health = client.get("/api/feedback/health")
    assert health.status_code == 200
    assert health.json()["module"] == "feedback_collection"

    user_id, token = _create_user(client, "api_user_1")

    me = client.get(f"/api/users/{user_id}", headers=_headers(token=token))
    assert me.status_code == 200
    assert me.json()["user"]["user_id"] == user_id


def test_input_modification_validation_annotation_and_query(client: TestClient) -> None:
    user_a, token_a = _create_user(client, "api_user_2")
    user_b, token_b = _create_user(client, "api_user_3")

    input_resp = client.post(
        "/api/feedback/input",
        headers=_headers(token=token_a),
        json={
            "dataset_id": "api_dataset",
            "x": 120.15,
            "y": 30.25,
            "z": 0,
            "value": 15.5,
            "timestamp": "2026-03-20T10:00:00+00:00",
            "device": "s-1",
            "method": "manual",
            "source": "sensor",
            "quality_flag": "good",
            "metadata": {"scene": "api"},
        },
    )
    assert input_resp.status_code == 200
    record_id = input_resp.json()["record"]["id"]

    mod_a = client.post(
        "/api/feedback/modification",
        headers=_headers(token=token_a),
        json={
            "target_record_id": record_id,
            "new_value": 16.0,
            "reason": "update",
            "note": "A",
        },
    )
    assert mod_a.status_code == 200

    mod_b = client.post(
        "/api/feedback/modification",
        headers=_headers(token=token_b),
        json={
            "target_record_id": record_id,
            "new_value": 18.0,
            "reason": "correction",
            "note": "B",
        },
    )
    assert mod_b.status_code == 200

    val_resp = client.post(
        "/api/feedback/validation",
        headers=_headers(token=token_a),
        json={
            "target_record_id": record_id,
            "predicted_value": 15.9,
            "result": "accept",
            "confidence": 0.9,
            "context": {"position": "p1"},
        },
    )
    assert val_resp.status_code == 200

    ann_resp = client.post(
        "/api/feedback/annotation",
        headers=_headers(token=token_b),
        json={
            "target_record_id": record_id,
            "anomaly_type": "manual_flag",
            "severity": 3,
            "quality_grade": "B",
            "label": "manual",
            "reason": "review",
        },
    )
    assert ann_resp.status_code == 200

    query = client.get("/api/feedback/data?dataset_id=api_dataset", headers=_headers(token=token_a))
    assert query.status_code == 200
    assert query.json()["count"] >= 4

    quality = client.get(f"/api/feedback/quality?record_id={record_id}", headers=_headers(token=token_a))
    assert quality.status_code == 200
    assert "quality" in quality.json()

    history = client.get(f"/api/feedback/history?entity_id={record_id}", headers=_headers(token=token_a))
    assert history.status_code == 200
    assert history.json()["count"] >= 2

    conflict_list = client.get("/api/feedback/conflicts?unresolved_only=true", headers=_headers(token=token_a))
    assert conflict_list.status_code == 200
    assert conflict_list.json()["count"] >= 1


def test_conflict_resolve_export_stats_and_backup(client: TestClient) -> None:
    user_id, token = _create_user(client, "api_user_4")
    _ = user_id

    created = client.post(
        "/api/feedback/input",
        headers=_headers(token=token),
        json={
            "dataset_id": "backup_dataset",
            "x": 121.01,
            "y": 31.01,
            "z": 0,
            "value": 21.2,
            "timestamp": "2026-03-12T10:00:00+00:00",
            "device": "s-2",
            "method": "manual",
            "source": "sensor",
            "quality_flag": "good",
            "metadata": {},
        },
    )
    assert created.status_code == 200
    record_id = created.json()["record"]["id"]

    # 通过第二个用户创建冲突
    user2, token2 = _create_user(client, "api_user_5")
    _ = user2
    client.post(
        "/api/feedback/modification",
        headers=_headers(token=token),
        json={"target_record_id": record_id, "new_value": 20.0, "reason": "update", "note": "A"},
    )
    client.post(
        "/api/feedback/modification",
        headers=_headers(token=token2),
        json={"target_record_id": record_id, "new_value": 24.0, "reason": "update", "note": "B"},
    )

    conflicts = client.get("/api/feedback/conflicts?unresolved_only=true", headers=_headers(token=token))
    assert conflicts.status_code == 200
    conflict_id = conflicts.json()["items"][0]["conflict_id"]

    # admin 登录后解决冲突
    admin_login = client.post("/api/users/login", json={"username": "admin", "password": "admin123"})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["token"]

    resolved = client.post(
        f"/api/feedback/conflicts/{conflict_id}/resolve",
        headers=_headers(token=admin_token),
        json={"strategy": "latest"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["conflict"]["status"] == "resolved"

    stats = client.get("/api/feedback/stats?dataset_id=backup_dataset", headers=_headers(token=token))
    assert stats.status_code == 200
    assert stats.json()["table_counts"]["input"] >= 1

    export_csv = client.get(
        "/api/feedback/export?fmt=csv&dataset_id=backup_dataset&record_type=input",
        headers=_headers(token=admin_token),
    )
    assert export_csv.status_code == 200
    assert export_csv.json()["format"] == "csv"

    backup = client.post("/api/feedback/backup", headers=_headers(token=admin_token), json={"mode": "full"})
    assert backup.status_code == 200
    backup_id = backup.json()["backup_id"]

    restore = client.post(f"/api/feedback/backup/{backup_id}/restore", headers=_headers(token=admin_token))
    assert restore.status_code == 200

    archive = client.post(
        "/api/feedback/archive",
        headers=_headers(token=admin_token),
        json={"before": "2027-01-01T00:00:00+00:00"},
    )
    assert archive.status_code == 200


def test_batch_import_and_user_endpoints(client: TestClient) -> None:
    user_id, token = _create_user(client, "api_user_6")

    batch = client.post(
        "/api/feedback/batch",
        headers=_headers(token=token),
        json={
            "dataset_id": "batch_dataset",
            "format": "csv",
            "content": (
                "dataset_id,x,y,z,value,timestamp,source,device,method,quality_flag\n"
                "batch_dataset,120.3,30.4,0,12.3,2026-03-01T00:00:00+00:00,csv,s1,batch,good\n"
                "batch_dataset,120.4,30.5,0,12.5,2026-03-02T00:00:00+00:00,csv,s2,batch,good\n"
            ),
            "mapping": {},
        },
    )
    assert batch.status_code == 200
    assert batch.json()["imported"] == 2

    reliability = client.get(f"/api/users/{user_id}/reliability", headers=_headers(token=token))
    assert reliability.status_code == 200

    contributions = client.get(f"/api/users/{user_id}/contributions", headers=_headers(token=token))
    assert contributions.status_code == 200

    leaderboard = client.get("/api/users/leaderboard?metric=contribution", headers=_headers(token=token))
    assert leaderboard.status_code == 200
    assert leaderboard.json()["count"] >= 1


def test_api_key_management_and_rate_limit(client: TestClient) -> None:
    admin_login = client.post("/api/users/login", json={"username": "admin", "password": "admin123"})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["token"]

    list_resp = client.get("/api/feedback/api-keys", headers=_headers(token=admin_token))
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] >= 1

    create_resp = client.post(
        "/api/feedback/api-keys",
        headers=_headers(token=admin_token),
        json={"owner": "qa", "scopes": ["read", "write"]},
    )
    assert create_resp.status_code == 200

    feedback_api.RATE_LIMIT_MAX_REQUESTS = 2
    feedback_api._rate_limit_bucket.clear()

    h1 = client.get("/api/feedback/data", headers={"X-API-Key": "dev-feedback-key", "X-Session-Token": admin_token})
    h2 = client.get("/api/feedback/data", headers={"X-API-Key": "dev-feedback-key", "X-Session-Token": admin_token})
    h3 = client.get("/api/feedback/data", headers={"X-API-Key": "dev-feedback-key", "X-Session-Token": admin_token})

    assert h1.status_code in {200, 400}
    assert h2.status_code in {200, 400}
    assert h3.status_code == 429
