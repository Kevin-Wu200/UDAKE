"""Unit tests for active learning and semi-supervised service."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.active_learning_service import ActiveLearningService


def _labeled() -> list[dict]:
    return [
        {"sample_id": "l_1", "features": [0.1, 0.3, 0.2], "label": "class_0", "label_confidence": 0.95},
        {"sample_id": "l_2", "features": [1.0, 0.8, 0.7], "label": "class_1", "label_confidence": 0.87},
        {"sample_id": "l_3", "features": [0.5, -0.2, 0.4], "label": "class_2", "label_confidence": 0.9},
    ]


def _unlabeled(size: int = 12) -> list[dict]:
    rows = []
    for i in range(size):
        rows.append(
            {
                "sample_id": f"u_{i}",
                "features": [0.1 * i, ((-1) ** i) * 0.05 * i, 0.2 + 0.03 * i],
                "gradient_norm": 0.2 + 0.01 * i,
                "loss": 0.5 + 0.02 * i,
            }
        )
    return rows


@pytest.fixture
def service() -> ActiveLearningService:
    return ActiveLearningService()


def test_active_learning_loop_selection_label_and_update(service: ActiveLearningService) -> None:
    session = service.init_active_learning(
        {
            "dataset_id": "dataset_stage10",
            "strategy": "hybrid_multi_objective",
            "labeled_samples": _labeled(),
            "unlabeled_samples": _unlabeled(16),
            "budget": {"total_budget": 40, "batch_budget": 6, "max_rounds": 5},
        },
        user_id="tester_1",
    )
    session_id = session["session_id"]

    selected = service.select_samples(
        {
            "session_id": session_id,
            "strategy": "entropy",
            "top_k": 5,
            "selection_mode": "incremental",
        },
        user_id="tester_1",
    )
    assert selected["count"] == 5
    assert selected["items"][0]["details"]["uncertainty"] >= 0

    request_task = service.create_annotation_requests({"session_id": session_id, "samples": selected["items"]}, user_id="annotator")
    assert request_task["task_id"].startswith("ann_")

    suggestion = service.get_annotation_suggestions(
        {"session_id": session_id, "sample_id": selected["items"][0]["sample_id"]},
        user_id="annotator",
    )
    assert suggestion["suggested_label"].startswith("class_")

    label_payload = {
        "session_id": session_id,
        "labels": [
            {
                "sample_id": item["sample_id"],
                "label": "class_1",
                "confidence": 0.86,
                "annotator": "annotator",
            }
            for item in selected["items"]
        ],
    }
    labeled = service.submit_labels(label_payload, user_id="annotator")
    assert labeled["accepted"] == 5
    assert labeled["used_budget"] == 5

    updated = service.update_model({"session_id": session_id, "gain_factor": 0.8}, user_id="trainer")
    assert updated["round"] == 1
    assert updated["performance"]["current"] >= updated["performance"]["previous"]

    status = service.get_status(session_id)
    assert status["labeled_count"] >= len(_labeled()) + 5
    assert status["round"] == 1


def test_strategy_budget_and_semi_supervised_methods(service: ActiveLearningService) -> None:
    strategy = service.configure_strategy(
        {
            "default_strategy": "hybrid_multi_objective",
            "weights": {"uncertainty": 0.5, "diversity": 0.2, "representativeness": 0.2, "committee": 0.1},
            "adaptive": {"enabled": True, "switch_patience": 2, "improvement_threshold": 0.003},
        },
        user_id="admin",
    )
    assert strategy["default_strategy"] == "hybrid_multi_objective"

    budget = service.configure_budget(
        {
            "total_budget": 60,
            "batch_budget": 8,
            "max_rounds": 6,
            "target_performance": 0.92,
            "uncertainty_threshold": 0.12,
        },
        user_id="admin",
    )
    assert budget["global_budget"]["batch_budget"] == 8

    init = service.init_active_learning(
        {
            "dataset_id": "dataset_ssl",
            "labeled_samples": _labeled(),
            "unlabeled_samples": _unlabeled(20),
            "strategy": "uncertainty_diversity_hybrid",
        }
    )
    sid = init["session_id"]

    pseudo = service.generate_pseudo_labels(
        {
            "session_id": sid,
            "confidence_threshold": 0.6,
            "max_items": 10,
            "rounds": 2,
            "filter": True,
        }
    )
    assert pseudo["generated"] >= 1

    listed = service.get_pseudo_labels(session_id=sid)
    assert listed["count"] == pseudo["generated"]

    consistency = service.consistency_regularization(
        {"session_id": sid, "augmentations": ["rotate", "flip", "noise"], "max_items": 12}
    )
    assert consistency["consistency_loss"] >= 0

    co_train = service.co_training({"session_id": sid, "max_items": 10})
    assert 0 <= co_train["agreement_rate"] <= 1

    graph = service.graph_semi_supervised({"session_id": sid, "graph_type": "knn", "k": 4, "iterations": 4})
    assert graph["node_count"] >= 1

    self_train = service.self_training({"session_id": sid, "max_rounds": 4, "threshold": 0.85})
    assert self_train["final_threshold"] <= 0.85

    evaluation = service.evaluate_active_learning(sid)
    assert "learning_curve" in evaluation

    semi_eval = service.evaluate_semi_supervised(sid)
    assert "pseudo_label_quality" in semi_eval

    viz = service.visualization_payload(sid)
    assert "uncertainty_heatmap" in viz


def test_incremental_update_history_and_annotation_quality(service: ActiveLearningService) -> None:
    init = service.init_active_learning(
        {
            "dataset_id": "dataset_inc",
            "labeled_samples": _labeled(),
            "unlabeled_samples": _unlabeled(9),
        }
    )
    sid = init["session_id"]

    inc = service.incremental_update(
        {
            "session_id": sid,
            "updates": [{"features": [0.2, 0.1, 0.3], "label": "class_1"} for _ in range(25)],
            "mode": "stream",
            "batch_size": 5,
            "forgetting_protection": {"method": "ewc", "lambda_ewc": 0.4, "replay_size": 80},
            "importance_weighting": {"new_data_weight": 1.2, "old_data_weight": 0.8, "dynamic": True},
            "fine_tuning": {"strategy": "partial", "lr": 0.001, "epochs": 3, "freeze_ratio": 0.5},
        },
        user_id="trainer",
    )
    assert inc["update_id"].startswith("inc_")

    metrics = service.evaluate_incremental({"window": 10})
    assert metrics["history_count"] >= 1
    assert metrics["overall_performance"] >= 0

    history = service.get_incremental_history(limit=5)
    assert history["count"] >= 1

    batch = service.create_batch_annotation(
        {"session_id": sid, "batch_size": 4, "shortcut_enabled": True, "template": {"label": "class_0"}},
        user_id="annotator",
    )
    assert batch["batch_size"] == 4

    quality = service.assess_annotation_quality(
        {
            "annotations": [
                {"sample_id": "u_1", "label": "class_0", "annotator": "a"},
                {"sample_id": "u_1", "label": "class_1", "annotator": "b"},
                {"sample_id": "u_2", "label": "class_0", "annotator": "a"},
                {"sample_id": "u_2", "label": "class_0", "annotator": "b"},
            ]
        }
    )
    assert quality["conflict_rate"] > 0


def test_api_key_validation(service: ActiveLearningService) -> None:
    valid = service.verify_api_key("dev-active-learning-key", required_scope="read")
    assert valid["key"] == "dev-active-learning-key"

    with pytest.raises(PermissionError):
        service.verify_api_key("invalid", required_scope="read")
