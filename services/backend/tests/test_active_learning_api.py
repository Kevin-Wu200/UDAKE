"""API tests for active learning and semi-supervised endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api import 主动学习接口 as active_api
from app.services.active_learning_service import ActiveLearningService


def _labeled() -> list[dict]:
    return [
        {"sample_id": "l_a", "features": [0.1, 0.2, 0.3], "label": "class_0", "label_confidence": 0.92},
        {"sample_id": "l_b", "features": [0.8, 0.7, 0.6], "label": "class_1", "label_confidence": 0.86},
    ]


def _unlabeled(n: int = 10) -> list[dict]:
    return [
        {
            "sample_id": f"u_{i}",
            "features": [0.07 * i, 0.03 * i * ((-1) ** i), 0.2 + 0.01 * i],
            "gradient_norm": 0.15 + 0.01 * i,
            "loss": 0.5 + 0.02 * i,
        }
        for i in range(n)
    ]


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    active_api.active_learning_service = ActiveLearningService()
    active_api._rate_limit_bucket.clear()
    active_api.RATE_LIMIT_MAX_REQUESTS = 180
    app.include_router(active_api.router, prefix="/api")
    return TestClient(app)


def _headers(user_id: str | None = None) -> dict:
    headers = {"X-API-Key": "dev-active-learning-key"}
    if user_id:
        headers["X-User-Id"] = user_id
    return headers


def _init_session(client: TestClient, dataset: str = "api_dataset") -> str:
    resp = client.post(
        "/api/active-learning/init",
        headers=_headers("owner"),
        json={
            "dataset_id": dataset,
            "strategy": "hybrid_multi_objective",
            "labeled_samples": _labeled(),
            "unlabeled_samples": _unlabeled(14),
            "budget": {"total_budget": 30, "batch_budget": 6, "max_rounds": 5},
        },
    )
    assert resp.status_code == 200
    return resp.json()["session"]["session_id"]


def test_health_config_init_and_status(client: TestClient) -> None:
    health = client.get("/api/active-learning/health")
    assert health.status_code == 200
    assert health.json()["module"] == "active_learning_and_semi_supervised"

    strategy = client.post(
        "/api/active-learning/config/strategy",
        headers=_headers("admin"),
        json={
            "default_strategy": "hybrid_multi_objective",
            "weights": {"uncertainty": 0.45, "diversity": 0.25, "representativeness": 0.2, "committee": 0.1},
            "adaptive": {"enabled": True, "switch_patience": 2, "improvement_threshold": 0.004},
        },
    )
    assert strategy.status_code == 200
    assert strategy.json()["default_strategy"] == "hybrid_multi_objective"

    budget = client.post(
        "/api/active-learning/config/budget",
        headers=_headers("admin"),
        json={"total_budget": 80, "batch_budget": 10, "max_rounds": 8, "target_performance": 0.93},
    )
    assert budget.status_code == 200
    assert budget.json()["global_budget"]["total_budget"] == 80

    sid = _init_session(client)

    status = client.get(f"/api/active-learning/status?session_id={sid}", headers=_headers("owner"))
    assert status.status_code == 200
    assert status.json()["session_id"] == sid

    budget_status = client.get(f"/api/active-learning/config/budget?session_id={sid}", headers=_headers("owner"))
    assert budget_status.status_code == 200
    assert budget_status.json()["session_id"] == sid


def test_active_learning_annotation_and_evaluation_endpoints(client: TestClient) -> None:
    sid = _init_session(client, dataset="api_loop")

    select_resp = client.post(
        "/api/active-learning/select",
        headers=_headers("owner"),
        json={"session_id": sid, "strategy": "entropy", "top_k": 4, "selection_mode": "incremental"},
    )
    assert select_resp.status_code == 200
    assert select_resp.json()["count"] == 4

    selected = select_resp.json()["items"]
    label_resp = client.post(
        "/api/active-learning/label",
        headers=_headers("annotator"),
        json={
            "session_id": sid,
            "labels": [
                {"sample_id": item["sample_id"], "label": "class_1", "confidence": 0.82, "annotator": "ann"}
                for item in selected
            ],
        },
    )
    assert label_resp.status_code == 200
    assert label_resp.json()["accepted"] == 4

    update_resp = client.post(
        "/api/active-learning/update",
        headers=_headers("trainer"),
        json={"session_id": sid, "gain_factor": 0.9},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["round"] == 1

    ann_req = client.post(
        "/api/active-learning/annotation/request",
        headers=_headers("annotator"),
        json={"session_id": sid, "samples": selected},
    )
    assert ann_req.status_code == 200
    assert ann_req.json()["task_id"].startswith("ann_")

    ann_batch = client.post(
        "/api/active-learning/annotation/batch",
        headers=_headers("annotator"),
        json={"session_id": sid, "batch_size": 5, "shortcut_enabled": True, "template": {"label": "class_0"}},
    )
    assert ann_batch.status_code == 200
    assert ann_batch.json()["batch_size"] == 5

    sample_id = ann_batch.json()["items"][0]["sample_id"]
    ann_suggestion = client.post(
        "/api/active-learning/annotation/suggestions",
        headers=_headers("annotator"),
        json={"session_id": sid, "sample_id": sample_id},
    )
    assert ann_suggestion.status_code == 200
    assert ann_suggestion.json()["suggested_label"].startswith("class_")

    ann_quality = client.post(
        "/api/active-learning/annotation/quality",
        headers=_headers("reviewer"),
        json={
            "annotations": [
                {"sample_id": "x1", "label": "class_0", "annotator": "a"},
                {"sample_id": "x1", "label": "class_1", "annotator": "b"},
                {"sample_id": "x2", "label": "class_0", "annotator": "a"},
                {"sample_id": "x2", "label": "class_0", "annotator": "b"},
            ]
        },
    )
    assert ann_quality.status_code == 200
    assert ann_quality.json()["conflict_rate"] > 0

    eval_active = client.get(f"/api/active-learning/evaluate?session_id={sid}", headers=_headers("owner"))
    assert eval_active.status_code == 200
    assert "learning_curve" in eval_active.json()

    viz = client.get(f"/api/active-learning/visualization?session_id={sid}", headers=_headers("owner"))
    assert viz.status_code == 200
    assert "uncertainty_heatmap" in viz.json()


def test_semi_supervised_incremental_and_rate_limit(client: TestClient) -> None:
    sid = _init_session(client, dataset="api_ssl")

    pseudo = client.post(
        "/api/semi-supervised/pseudo-labels",
        headers=_headers("owner"),
        json={"session_id": sid, "confidence_threshold": 0.45, "max_items": 8, "rounds": 2, "filter": False},
    )
    assert pseudo.status_code == 200
    assert pseudo.json()["generated"] >= 1

    pseudo_list = client.get(f"/api/semi-supervised/pseudo-labels?session_id={sid}", headers=_headers("owner"))
    assert pseudo_list.status_code == 200
    assert pseudo_list.json()["count"] >= 1

    consistency = client.post(
        "/api/semi-supervised/consistency",
        headers=_headers("owner"),
        json={"session_id": sid, "augmentations": ["rotate", "flip", "noise"], "max_items": 8},
    )
    assert consistency.status_code == 200
    assert consistency.json()["consistency_loss"] >= 0

    co_training = client.post(
        "/api/semi-supervised/co-training",
        headers=_headers("owner"),
        json={"session_id": sid, "max_items": 8},
    )
    assert co_training.status_code == 200

    graph = client.post(
        "/api/semi-supervised/graph",
        headers=_headers("owner"),
        json={"session_id": sid, "graph_type": "knn", "k": 3, "iterations": 3, "label_smoothing": 0.1},
    )
    assert graph.status_code == 200

    self_train = client.post(
        "/api/semi-supervised/self-training",
        headers=_headers("owner"),
        json={"session_id": sid, "max_rounds": 3, "threshold": 0.85, "early_stop_patience": 2},
    )
    assert self_train.status_code == 200

    semi_eval = client.get(f"/api/semi-supervised/evaluate?session_id={sid}", headers=_headers("owner"))
    assert semi_eval.status_code == 200

    incremental = client.post(
        "/api/incremental/update",
        headers=_headers("trainer"),
        json={
            "session_id": sid,
            "updates": [{"features": [0.1, 0.2, 0.3], "label": "class_1"} for _ in range(18)],
            "mode": "batch",
            "batch_size": 6,
            "forgetting_protection": {"method": "ewc", "lambda_ewc": 0.35, "replay_size": 72},
            "importance_weighting": {"new_data_weight": 1.1, "old_data_weight": 0.9, "dynamic": True},
            "fine_tuning": {"strategy": "partial", "lr": 0.001, "epochs": 2, "freeze_ratio": 0.4},
        },
    )
    assert incremental.status_code == 200
    assert incremental.json()["update_id"].startswith("inc_")

    inc_eval = client.post("/api/incremental/evaluate", headers=_headers("owner"), json={"window": 10})
    assert inc_eval.status_code == 200
    assert inc_eval.json()["history_count"] >= 1

    inc_history = client.get("/api/incremental/history?limit=10", headers=_headers("owner"))
    assert inc_history.status_code == 200
    assert inc_history.json()["count"] >= 1

    active_api.RATE_LIMIT_MAX_REQUESTS = 2
    active_api._rate_limit_bucket.clear()
    h1 = client.get("/api/incremental/history", headers=_headers("owner"))
    h2 = client.get("/api/incremental/history", headers=_headers("owner"))
    h3 = client.get("/api/incremental/history", headers=_headers("owner"))
    assert h1.status_code == 200
    assert h2.status_code == 200
    assert h3.status_code == 429
