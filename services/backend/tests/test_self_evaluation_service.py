"""Unit tests for user validation and self-evaluation service."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.self_evaluation_service import SelfEvaluationService


def _records(size: int = 16) -> list[dict]:
    rows: list[dict] = []
    for i in range(size):
        predicted = 10.0 + i * 0.2
        actual = predicted + (0.15 if i % 3 else -0.1)
        result = "accept" if abs(actual - predicted) <= 0.2 else "reject"
        if i % 5 == 0:
            result = "correct"
        rows.append(
            {
                "evaluation_id": f"ev_{i}",
                "dataset_id": "stage11_ds",
                "model_id": "st_transformer",
                "module": "realtime_interpolation" if i % 2 == 0 else "adaptive_sampling",
                "x": 120.0 + 0.02 * i,
                "y": 30.0 + 0.03 * i,
                "predicted_value": predicted,
                "actual_value": actual,
                "result": result,
                "confidence": 0.55 + 0.02 * (i % 8),
                "uncertainty": 0.15 + 0.01 * (i % 6),
                "response_time_seconds": 1.0 + 0.2 * i,
                "verification_time_seconds": 2.0 + 0.15 * i,
                "features": [0.1 * i, 0.2 * i, 0.05 * i],
                "interval_lower": predicted - 0.4,
                "interval_upper": predicted + 0.4,
            }
        )
    return rows


@pytest.fixture
def service() -> SelfEvaluationService:
    return SelfEvaluationService()


def test_realtime_evaluation_and_metrics(service: SelfEvaluationService) -> None:
    result = service.evaluate_realtime(
        {
            "records": _records(18),
            "window_minutes": 180,
            "sample_size": 500,
        },
        user_id="tester",
    )

    assert result["accepted"] == 18
    assert result["performance"]["event_count"] == 18
    assert 0 <= result["performance"]["overall_accuracy"] <= 1
    assert result["performance"]["regression_accuracy"]["mae"] >= 0
    assert len(result["errors"]["error_distribution"]) >= 1
    assert len(result["uncertainty"]["reliability_diagram"]) == 10
    assert "drift" in result["drift"]


def test_model_selection_switch_and_rollback(service: SelfEvaluationService) -> None:
    select = service.select_best_model(
        {
            "candidates": [
                {
                    "model_id": "m_a",
                    "model_name": "Model-A",
                    "version": "v1",
                    "performance_score": 0.72,
                    "uncertainty_score": 0.28,
                    "scenario_score": 0.62,
                },
                {
                    "model_id": "m_b",
                    "model_name": "Model-B",
                    "version": "v2",
                    "performance_score": 0.84,
                    "uncertainty_score": 0.22,
                    "scenario_score": 0.70,
                },
                {
                    "model_id": "m_c",
                    "model_name": "Model-C",
                    "version": "v1",
                    "performance_score": 0.78,
                    "uncertainty_score": 0.18,
                    "scenario_score": 0.60,
                },
            ],
            "auto_switch": True,
            "switch_min_gain": 0.01,
            "switch_strategy": "smooth",
            "ab_test": {"effect_size": 0.04},
        },
        user_id="ml_admin",
    )

    assert select["selected_model"]["model_id"] in {"m_a", "m_b", "m_c"}
    assert select["current_model_id"] is not None
    assert len(select["ranking"]) == 3

    switched = service.switch_model(
        {
            "target_model_id": "m_c",
            "strategy": "immediate",
            "reason": "manual_override",
            "validation": {"min_accuracy": 0.6, "max_mae": 1.0, "actual_accuracy": 0.8, "actual_mae": 0.3},
        },
        user_id="ml_admin",
    )
    assert switched["switched"] is True
    assert switched["to_model_id"] == "m_c"

    rolled = service.rollback_model({"reason": "switch_regression"}, user_id="ml_admin")
    assert rolled["to_model_id"] in {"m_a", "m_b", "m_c"}

    status = service.get_model_status()
    assert status["model_count"] == 3
    assert status["switch_history_count"] >= 1


def test_optimization_and_reports(service: SelfEvaluationService) -> None:
    service.evaluate_realtime({"records": _records(10)}, user_id="reporter")

    task_done = service.trigger_optimization(
        {
            "trigger_type": "manual",
            "async": False,
            "retrain_mode": "incremental",
            "expected_performance_delta": 0.05,
        },
        user_id="ops",
    )
    assert task_done["status"] == "completed"

    task_running = service.trigger_optimization(
        {
            "trigger_type": "performance_degradation",
            "async": True,
            "data_volume": 250,
            "negative_feedback_ratio": 0.22,
        },
        user_id="ops",
    )
    assert task_running["status"] == "running"

    summary = service.get_optimization_status()
    assert summary["count"] >= 2

    canceled = service.cancel_optimization({"task_id": task_running["task_id"]}, user_id="ops")
    assert canceled["canceled"] is True

    performance_report = service.get_performance_report(window_minutes=120, sample_size=200)
    evaluation_report = service.get_evaluation_report(window_minutes=120, sample_size=200)
    optimization_report = service.get_optimization_report()
    assert performance_report["type"] == "performance"
    assert evaluation_report["type"] == "evaluation"
    assert optimization_report["type"] == "optimization"

    generated = service.generate_report(
        {
            "report_type": "all",
            "format": "markdown",
            "window_minutes": 120,
            "sample_size": 200,
        },
        user_id="ops",
    )
    assert generated["report_id"].startswith("rep_")
    assert generated["format"] == "markdown"
