"""API tests for data quality endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api import 数据质量接口 as data_quality_api
from app.services.data_quality_service import DataQualityService


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    data_quality_api.data_quality_service = DataQualityService()
    app.include_router(data_quality_api.router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def payload() -> dict:
    return {
        "dataset_id": "api_dataset",
        "records": [
            {
                "id": "A001",
                "x": 120.1,
                "y": 30.1,
                "value": 10.5,
                "timestamp": "2026-03-01T00:00:00",
                "status": "verified",
                "quality_level": "high",
                "source": "sensor",
                "category": "soil",
            },
            {
                "id": "A001",
                "x": 121.1,
                "y": 31.1,
                "value": 9999999,
                "timestamp": "2026-03-10T00:00:00",
                "status": "unknown",
                "quality_level": "bad",
                "source": "manual",
                "category": "***",
            },
            {
                "id": "A003",
                "x": 120.2,
                "y": 30.2,
                "value": 11.5,
                "timestamp": "2026-03-02T00:00:00",
                "status": "raw",
                "quality_level": "medium",
                "source": "sensor",
                "category": "soil",
            },
            {
                "id": "A004",
                "x": 120.3,
                "y": 30.3,
                "value": 11.6,
                "timestamp": "2026-03-03T00:00:00",
                "status": "raw",
                "quality_level": "medium",
                "source": "sensor",
                "category": "soil",
            },
            {
                "id": "A005",
                "x": 120.4,
                "y": 30.4,
                "value": 11.7,
                "timestamp": "2026-03-04T00:00:00",
                "status": "raw",
                "quality_level": "medium",
                "source": "sensor",
                "category": "soil",
            },
        ],
    }


def test_health(client: TestClient) -> None:
    resp = client.get("/api/data-quality/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["preset_rule_count"] >= 20


def test_evaluate_and_query_report(client: TestClient, payload: dict) -> None:
    evaluate_resp = client.post("/api/data-quality/evaluate", json=payload)
    assert evaluate_resp.status_code == 200
    summary = evaluate_resp.json()
    assert summary["dataset_id"] == "api_dataset"
    assert 0 <= summary["overall_score"] <= 100

    report_id = summary["report_id"]

    report_resp = client.get(f"/api/data-quality/reports/{report_id}")
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["report_id"] == report_id
    assert isinstance(report["violations"], list)

    anomalies_resp = client.get(f"/api/data-quality/reports/{report_id}/anomalies")
    assert anomalies_resp.status_code == 200
    assert "count" in anomalies_resp.json()

    suggestions_resp = client.get(f"/api/data-quality/reports/{report_id}/suggestions")
    assert suggestions_resp.status_code == 200
    assert suggestions_resp.json()["count"] >= 1

    history_resp = client.get("/api/data-quality/history/api_dataset")
    assert history_resp.status_code == 200
    assert history_resp.json()["count"] == 1


def test_rule_crud_api(client: TestClient) -> None:
    create_resp = client.post(
        "/api/data-quality/rules",
        json={
            "name": "owner required",
            "dimension": "completeness",
            "rule_type": "required",
            "field": "owner",
            "config": {},
            "priority": 90,
        },
    )
    assert create_resp.status_code == 200
    rule_id = create_resp.json()["rule"]["rule_id"]

    toggle_resp = client.patch(
        f"/api/data-quality/rules/{rule_id}/enabled",
        json={"enabled": False},
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["rule"]["enabled"] is False

    update_resp = client.put(
        f"/api/data-quality/rules/{rule_id}",
        json={"description": "api-updated"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["rule"]["description"] == "api-updated"

    delete_resp = client.delete(f"/api/data-quality/rules/{rule_id}")
    assert delete_resp.status_code == 200

    list_resp = client.get("/api/data-quality/rules")
    assert list_resp.status_code == 200
    remaining_ids = {item["rule_id"] for item in list_resp.json()["rules"]}
    assert rule_id not in remaining_ids


def test_export_report(client: TestClient, payload: dict) -> None:
    summary = client.post("/api/data-quality/evaluate", json=payload).json()
    report_id = summary["report_id"]

    html_resp = client.get(f"/api/data-quality/reports/{report_id}/export?fmt=html")
    assert html_resp.status_code == 200
    assert html_resp.json()["format"] == "html"

    md_resp = client.get(f"/api/data-quality/reports/{report_id}/export?fmt=markdown")
    assert md_resp.status_code == 200
    assert md_resp.json()["format"] == "markdown"
