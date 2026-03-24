"""API tests for user validation and model self-evaluation endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api import 用户验证与自评估接口 as eval_api
from app.services.self_evaluation_service import SelfEvaluationService


def _headers(user_id: str | None = None) -> dict[str, str]:
    headers = {"X-API-Key": "dev-evaluation-key"}
    if user_id:
        headers["X-User-Id"] = user_id
    return headers


def _records(size: int = 12) -> list[dict]:
    rows = []
    for i in range(size):
        pred = 8.0 + 0.3 * i
        actual = pred + (0.1 if i % 2 == 0 else -0.15)
        rows.append(
            {
                "evaluation_id": f"api_ev_{i}",
                "dataset_id": "api_stage11",
                "model_id": "st_transformer",
                "module": "realtime_interpolation",
                "x": 121.0 + i * 0.01,
                "y": 31.0 + i * 0.01,
                "predicted_value": pred,
                "actual_value": actual,
                "result": "accept" if i % 3 else "correct",
                "confidence": 0.60 + 0.02 * (i % 5),
                "uncertainty": 0.12 + 0.01 * (i % 4),
                "response_time_seconds": 0.8 + 0.1 * i,
                "verification_time_seconds": 1.0 + 0.12 * i,
                "features": [0.2 * i, 0.1 * i],
                "interval_lower": pred - 0.35,
                "interval_upper": pred + 0.35,
            }
        )
    return rows


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    eval_api.self_evaluation_service = SelfEvaluationService()
    eval_api._rate_limit_bucket.clear()
    eval_api.RATE_LIMIT_MAX_REQUESTS = 240
    app.include_router(eval_api.router, prefix="/api")
    return TestClient(app)


def test_evaluation_endpoints(client: TestClient) -> None:
    realtime = client.post(
        "/api/evaluation/realtime",
        headers=_headers("analyst"),
        json={"records": _records(15), "window_minutes": 180, "sample_size": 500},
    )
    assert realtime.status_code == 200
    assert realtime.json()["accepted"] == 15

    perf = client.get("/api/evaluation/performance?window_minutes=180&sample_size=500", headers=_headers("analyst"))
    assert perf.status_code == 200
    assert perf.json()["event_count"] == 15

    errs = client.get("/api/evaluation/errors", headers=_headers("analyst"))
    assert errs.status_code == 200
    assert "error_statistics" in errs.json()

    unc = client.get("/api/evaluation/uncertainty", headers=_headers("analyst"))
    assert unc.status_code == 200
    assert "ece" in unc.json()


def test_model_selection_and_switch_endpoints(client: TestClient) -> None:
    select = client.post(
        "/api/model-selection/select",
        headers=_headers("ml_admin"),
        json={
            "candidates": [
                {
                    "model_id": "m1",
                    "model_name": "Model-1",
                    "version": "v1",
                    "performance_score": 0.73,
                    "uncertainty_score": 0.24,
                    "scenario_score": 0.62,
                },
                {
                    "model_id": "m2",
                    "model_name": "Model-2",
                    "version": "v2",
                    "performance_score": 0.82,
                    "uncertainty_score": 0.19,
                    "scenario_score": 0.70,
                },
            ],
            "auto_switch": True,
            "switch_min_gain": 0.01,
            "ab_test": {"effect_size": 0.05},
        },
    )
    assert select.status_code == 200
    assert select.json()["selected_model"]["model_id"] in {"m1", "m2"}

    status = client.get("/api/model-selection/status", headers=_headers("ml_admin"))
    assert status.status_code == 200
    assert status.json()["model_count"] == 2

    switched = client.post(
        "/api/model-selection/switch",
        headers=_headers("ml_admin"),
        json={
            "target_model_id": "m1",
            "strategy": "immediate",
            "reason": "manual",
            "validation": {"min_accuracy": 0.6, "max_mae": 1.0, "actual_accuracy": 0.75, "actual_mae": 0.3},
        },
    )
    assert switched.status_code == 200
    assert switched.json()["to_model_id"] == "m1"

    rollback = client.post(
        "/api/model-selection/rollback",
        headers=_headers("ml_admin"),
        json={"reason": "regression"},
    )
    assert rollback.status_code == 200
    assert rollback.json()["rollback_id"].startswith("rbk_")


def test_optimization_and_report_endpoints(client: TestClient) -> None:
    client.post(
        "/api/evaluation/realtime",
        headers=_headers("ops"),
        json={"records": _records(10), "window_minutes": 120, "sample_size": 300},
    )

    trigger_done = client.post(
        "/api/optimization/trigger",
        headers=_headers("ops"),
        json={
            "trigger_type": "manual",
            "async": False,
            "expected_performance_delta": 0.04,
            "data_volume": 100,
        },
    )
    assert trigger_done.status_code == 200
    assert trigger_done.json()["status"] == "completed"

    trigger_running = client.post(
        "/api/optimization/trigger",
        headers=_headers("ops"),
        json={
            "trigger_type": "performance_degradation",
            "async": True,
            "negative_feedback_ratio": 0.2,
            "data_volume": 180,
        },
    )
    assert trigger_running.status_code == 200
    assert trigger_running.json()["status"] == "running"
    task_id = trigger_running.json()["task_id"]

    opt_status = client.get("/api/optimization/status", headers=_headers("ops"))
    assert opt_status.status_code == 200
    assert opt_status.json()["count"] >= 2

    cancel = client.post(
        "/api/optimization/cancel",
        headers=_headers("ops"),
        json={"task_id": task_id},
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"

    report_perf = client.get("/api/reports/performance", headers=_headers("ops"))
    report_eval = client.get("/api/reports/evaluation", headers=_headers("ops"))
    report_opt = client.get("/api/reports/optimization", headers=_headers("ops"))
    assert report_perf.status_code == 200
    assert report_eval.status_code == 200
    assert report_opt.status_code == 200

    generated = client.post(
        "/api/reports/generate",
        headers=_headers("ops"),
        json={"report_type": "all", "format": "markdown", "window_minutes": 120, "sample_size": 200},
    )
    assert generated.status_code == 200
    assert generated.json()["report_id"].startswith("rep_")


def test_rate_limit(client: TestClient) -> None:
    eval_api.RATE_LIMIT_MAX_REQUESTS = 2
    eval_api._rate_limit_bucket.clear()

    r1 = client.get("/api/evaluation/performance", headers=_headers("rate_user"))
    r2 = client.get("/api/evaluation/performance", headers=_headers("rate_user"))
    r3 = client.get("/api/evaluation/performance", headers=_headers("rate_user"))

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
