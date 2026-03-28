"""API tests for history comparison and trend analysis endpoints."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.api import 历史对比与趋势分析接口 as history_api
from app.services.历史对比与趋势分析服务 import HistoryComparisonTrendService


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = FastAPI()
    history_api.history_comparison_trend_service = HistoryComparisonTrendService(
        storage_dir=tmp_path / "history",
        report_dir=tmp_path / "reports",
    )
    app.include_router(history_api.router, prefix="/api")
    return TestClient(app)


def _records_payload(count: int, base: float, slope: float) -> list[dict]:
    start = datetime(2026, 1, 1)
    payload: list[dict] = []
    for idx in range(count):
        payload.append(
            {
                "timestamp": (start + timedelta(days=idx)).isoformat(),
                "value": base + slope * idx,
                "point_id": f"api-p{idx}",
                "x": idx % 5,
                "y": idx // 5,
                "metadata": {"idx": idx},
            }
        )
    return payload


def test_history_analysis_api_flow(client: TestClient) -> None:
    create_v1 = client.post(
        "/api/history-analysis/snapshots",
        json={
            "dataset_id": "api_dataset",
            "version_label": "v1",
            "records": _records_payload(18, 5.0, 0.2),
        },
    )
    assert create_v1.status_code == 200
    assert create_v1.json()["snapshot"]["version"] == 1

    create_v2 = client.post(
        "/api/history-analysis/snapshots",
        json={
            "dataset_id": "api_dataset",
            "version_label": "v2",
            "records": _records_payload(18, 5.6, 0.25),
        },
    )
    assert create_v2.status_code == 200
    assert create_v2.json()["snapshot"]["version"] == 2

    listing = client.get("/api/history-analysis/snapshots/api_dataset")
    assert listing.status_code == 200
    assert listing.json()["total_versions"] == 2

    comparison = client.post(
        "/api/history-analysis/compare",
        json={
            "dataset_id": "api_dataset",
            "from_version": 1,
            "to_version": 2,
            "heatmap_grid_size": 10,
        },
    )
    assert comparison.status_code == 200
    assert comparison.json()["summary"]["changed_points"] > 0

    trend = client.post(
        "/api/history-analysis/trend",
        json={
            "dataset_id": "api_dataset",
            "version": 2,
            "forecast_horizon": 5,
        },
    )
    assert trend.status_code == 200
    assert len(trend.json()["forecast"]) == 5

    report = client.post(
        "/api/history-analysis/report",
        json={
            "dataset_id": "api_dataset",
            "from_version": 1,
            "to_version": 2,
            "forecast_horizon": 4,
        },
    )
    assert report.status_code == 200
    assert report.json()["download_url"].endswith(".json")

    export_csv = client.post(
        "/api/history-analysis/export",
        json={"dataset_id": "api_dataset", "format": "csv"},
    )
    assert export_csv.status_code == 200
    assert "timestamp,value,point_id,x,y,metadata" in export_csv.json()["content"]

    imported = client.post(
        "/api/history-analysis/import",
        json={
            "dataset_id": "api_dataset_imported",
            "format": "csv",
            "content": export_csv.json()["content"],
        },
    )
    assert imported.status_code == 200
    assert imported.json()["imported_version"] == 1

    # 继续创建版本后归档
    client.post(
        "/api/history-analysis/snapshots",
        json={
            "dataset_id": "api_dataset_imported",
            "version_label": "v2",
            "records": _records_payload(10, 7.0, 0.1),
        },
    )
    client.post(
        "/api/history-analysis/snapshots",
        json={
            "dataset_id": "api_dataset_imported",
            "version_label": "v3",
            "records": _records_payload(10, 7.5, 0.12),
        },
    )

    archive = client.post(
        "/api/history-analysis/archive",
        json={"dataset_id": "api_dataset_imported", "keep_latest": 1},
    )
    assert archive.status_code == 200
    assert archive.json()["archived_count"] == 2
