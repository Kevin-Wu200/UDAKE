"""Unit tests for history comparison and trend analysis service."""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.schemas.历史对比与趋势分析模型 import (
    ArchiveSnapshotsRequest,
    ExportFormat,
    HistoryExportRequest,
    HistoryImportRequest,
    HistoryReportRequest,
    SnapshotCreateRequest,
    TimeSeriesRecord,
    TrendAnalysisRequest,
    VersionComparisonRequest,
)
from app.services.历史对比与趋势分析服务 import HistoryComparisonTrendService


def _build_records(
    count: int,
    *,
    base: float,
    slope: float,
    seasonal_amp: float = 0.0,
    anomaly_index: int | None = None,
    anomaly_delta: float = 0.0,
) -> list[TimeSeriesRecord]:
    start = datetime(2026, 1, 1)
    records: list[TimeSeriesRecord] = []
    for i in range(count):
        value = base + slope * i + seasonal_amp * math.sin(2 * math.pi * i / 7)
        if anomaly_index is not None and i == anomaly_index:
            value += anomaly_delta

        records.append(
            TimeSeriesRecord(
                timestamp=start + timedelta(days=i),
                value=float(value),
                point_id=f"p{i}",
                x=float(i % 6),
                y=float(i // 6),
                metadata={"index": i},
            )
        )
    return records


def test_snapshot_version_compare_and_heatmap(tmp_path: Path) -> None:
    service = HistoryComparisonTrendService(
        storage_dir=tmp_path / "history",
        report_dir=tmp_path / "reports",
    )

    v1 = service.create_snapshot(
        SnapshotCreateRequest(
            dataset_id="dataset_alpha",
            version_label="baseline",
            records=_build_records(24, base=10.0, slope=0.12),
        )
    )
    v2 = service.create_snapshot(
        SnapshotCreateRequest(
            dataset_id="dataset_alpha",
            version_label="after_adjustment",
            records=_build_records(24, base=10.4, slope=0.15),
        )
    )

    assert v1.version == 1
    assert v2.version == 2

    listing = service.list_snapshots("dataset_alpha")
    assert listing.total_versions == 2

    comparison = service.compare_versions(
        VersionComparisonRequest(
            dataset_id="dataset_alpha",
            from_version=1,
            to_version=2,
            heatmap_grid_size=12,
        )
    )

    assert comparison.summary.total_points == 24
    assert comparison.summary.changed_points > 0
    assert comparison.heatmap.rows == 12
    assert comparison.heatmap.cols == 12
    assert len(comparison.diffs) == 24


def test_trend_analysis_forecast_and_anomaly(tmp_path: Path) -> None:
    service = HistoryComparisonTrendService(
        storage_dir=tmp_path / "history",
        report_dir=tmp_path / "reports",
    )

    service.create_snapshot(
        SnapshotCreateRequest(
            dataset_id="dataset_trend",
            version_label="v1",
            records=_build_records(
                56,
                base=20.0,
                slope=0.35,
                seasonal_amp=1.8,
                anomaly_index=41,
                anomaly_delta=12.0,
            ),
        )
    )

    analysis = service.analyze_trend(
        TrendAnalysisRequest(dataset_id="dataset_trend", forecast_horizon=10, anomaly_z_threshold=2.3)
    )

    assert analysis.sample_size == 56
    assert analysis.linear_trend.direction == "increasing"
    assert 0.0 <= analysis.mann_kendall.p_value <= 1.0
    assert len(analysis.periodic_components) >= 1
    assert len(analysis.forecast) == 10
    assert analysis.evaluation.accuracy >= 0
    assert any(item.anomaly_type in {"zscore", "change_point"} for item in analysis.anomalies)


def test_export_import_archive_and_report(tmp_path: Path) -> None:
    service = HistoryComparisonTrendService(
        storage_dir=tmp_path / "history",
        report_dir=tmp_path / "reports",
    )

    # 报告数据集
    service.create_snapshot(
        SnapshotCreateRequest(
            dataset_id="dataset_report",
            version_label="v1",
            records=_build_records(20, base=8.0, slope=0.1),
        )
    )
    service.create_snapshot(
        SnapshotCreateRequest(
            dataset_id="dataset_report",
            version_label="v2",
            records=_build_records(20, base=8.5, slope=0.14),
        )
    )

    report = service.generate_report(
        HistoryReportRequest(
            dataset_id="dataset_report",
            from_version=1,
            to_version=2,
            forecast_horizon=6,
        )
    )
    assert report.report_id
    report_file = service.report_dir / f"{report.report_id}.json"
    assert report_file.exists()

    exported_json = service.export_history(
        HistoryExportRequest(dataset_id="dataset_report", format=ExportFormat.JSON)
    )
    assert '"snapshots"' in exported_json.content

    exported_csv = service.export_history(
        HistoryExportRequest(dataset_id="dataset_report", format=ExportFormat.CSV)
    )
    assert "timestamp,value,point_id,x,y,metadata" in exported_csv.content

    imported = service.import_history(
        HistoryImportRequest(
            dataset_id="dataset_imported",
            format=ExportFormat.CSV,
            content=exported_csv.content,
            version_label="imported_v1",
        )
    )
    assert imported.imported_version == 1
    assert imported.imported_records == 20

    # 继续生成多版本后执行归档
    service.create_snapshot(
        SnapshotCreateRequest(
            dataset_id="dataset_imported",
            version_label="v2",
            records=_build_records(20, base=9.0, slope=0.15),
        )
    )
    service.create_snapshot(
        SnapshotCreateRequest(
            dataset_id="dataset_imported",
            version_label="v3",
            records=_build_records(20, base=9.4, slope=0.18),
        )
    )

    archived = service.archive_snapshots(
        ArchiveSnapshotsRequest(dataset_id="dataset_imported", keep_latest=1)
    )
    assert archived.archived_count == 2
    assert archived.kept_count == 1
