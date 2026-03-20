"""Unit tests for data quality service."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.data_quality_service import DataQualityService


@pytest.fixture
def service() -> DataQualityService:
    return DataQualityService()


@pytest.fixture
def sample_records() -> list[dict]:
    return [
        {
            "id": "P001",
            "x": 120.1,
            "y": 30.1,
            "value": 12.3,
            "timestamp": "2026-03-01T00:00:00",
            "status": "verified",
            "quality_level": "high",
            "source": "sensor",
            "category": "soil",
        },
        {
            "id": "P002",
            "x": 120.2,
            "y": 30.2,
            "value": 12.8,
            "timestamp": "2026-03-02T00:00:00",
            "status": "raw",
            "quality_level": "medium",
            "source": "sensor",
            "category": "soil",
        },
        {
            "id": "P002",
            "x": 120.2,
            "y": 30.2,
            "value": 5000000,
            "timestamp": "2026-03-10T00:00:00",
            "status": "verified",
            "quality_level": "low",
            "source": "manual",
            "category": "soil",
        },
        {
            "id": "",
            "x": 200,
            "y": 95,
            "value": None,
            "timestamp": "bad-date",
            "status": "unknown",
            "quality_level": "bad",
            "source": "third-party",
            "category": "***",
        },
        {
            "id": "P005",
            "x": 120.5,
            "y": 30.5,
            "value": 11.9,
            "timestamp": "2026-03-03T00:00:00",
            "status": "verified",
            "quality_level": "medium",
            "source": "import",
            "category": "soil",
        },
    ]


def test_preset_rule_count(service: DataQualityService) -> None:
    rules = service.list_rules()
    assert len(rules) >= 20


def test_evaluate_returns_report(service: DataQualityService, sample_records: list[dict]) -> None:
    report = service.evaluate(
        {
            "dataset_id": "dataset_alpha",
            "records": sample_records,
            "value_field": "value",
            "x_field": "x",
            "y_field": "y",
        }
    )

    assert report["dataset_id"] == "dataset_alpha"
    assert 0 <= report["overall_score"] <= 100
    assert report["grade"] in {"A", "B", "C", "D", "E"}
    assert "completeness" in report["dimension_scores"]
    assert "accuracy" in report["dimension_scores"]
    assert len(report["violations"]) > 0
    assert isinstance(report["suggestions"], list)

    history = service.get_history("dataset_alpha")
    assert len(history) == 1
    assert history[0]["report_id"] == report["report_id"]


def test_rule_crud_versioning(service: DataQualityService) -> None:
    rule = service.create_rule(
        {
            "name": "custom-required-owner",
            "dimension": "completeness",
            "rule_type": "required",
            "field": "owner",
            "config": {},
            "priority": 88,
        }
    )

    rule_id = rule["rule_id"]
    assert rule["version"] == 1

    updated = service.update_rule(rule_id, {"enabled": False, "description": "custom"})
    assert updated["enabled"] is False
    assert updated["version"] == 2

    toggled = service.set_rule_enabled(rule_id, True)
    assert toggled["enabled"] is True
    assert toggled["version"] == 3

    service.delete_rule(rule_id)
    all_ids = {item["rule_id"] for item in service.list_rules()}
    assert rule_id not in all_ids


def test_export_formats(service: DataQualityService, sample_records: list[dict]) -> None:
    report = service.evaluate({"dataset_id": "dataset_export", "records": sample_records})
    report_id = report["report_id"]

    exported_json = service.export_report(report_id, "json")
    exported_md = service.export_report(report_id, "markdown")
    exported_html = service.export_report(report_id, "html")

    assert exported_json["format"] == "json"
    assert "overall_score" in exported_json["content"]
    assert exported_md["format"] == "markdown"
    assert "# Data Quality Report" in exported_md["content"]
    assert exported_html["format"] == "html"
    assert "<html>" in exported_html["content"]

    with pytest.raises(ValueError):
        service.export_report(report_id, "pdf")
