from __future__ import annotations

from pathlib import Path

from deep_learning.monitoring import DashboardBuilder
from deep_learning.utils.logger import StructuredLogger
from deep_learning.utils.monitoring import (
    AlertManager,
    AlertRule,
    MetricMonitor,
    SystemResourceMonitor,
)


def test_monitoring_alert_dashboard(tmp_path: Path) -> None:
    monitor = MetricMonitor()
    monitor.log("loss", 0.8)
    monitor.log("loss", 0.4)
    summary = monitor.summary("loss")
    assert summary["count"] == 2.0

    resource = SystemResourceMonitor().collect()
    assert "cpu_percent" in resource

    alerts = AlertManager([AlertRule(metric="loss", threshold=0.7, operator=">=")]).evaluate({"loss": 0.8})
    assert alerts

    dashboard = DashboardBuilder(output_path=str(tmp_path / "dashboard.json"))
    out = dashboard.build({"loss": summary}, resource, alerts)
    assert Path(out).exists()


def test_structured_logger_aggregate() -> None:
    logger = StructuredLogger("dl-test")
    logger.log("info", "training started", stage="start")
    logger.log("warning", "high memory", usage="92")
    agg = logger.aggregate()
    assert agg["info"] == 1
    assert agg["warning"] == 1
