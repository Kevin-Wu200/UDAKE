from __future__ import annotations

from app.auth_db.performance import SlowQueryMonitor


def test_slow_query_monitor_snapshot_and_alerts():
    monitor = SlowQueryMonitor(threshold_ms=100, max_samples=200, alert_p95_ms=300, alert_slow_ratio=0.2)

    for _ in range(60):
        monitor.observe(statement="SELECT 1", elapsed_ms=30)
    for _ in range(30):
        monitor.observe(statement="SELECT * FROM product_keys WHERE product_key = ?", elapsed_ms=450)

    snapshot = monitor.snapshot(top_n=5)
    assert snapshot["total_queries"] == 90
    assert snapshot["slow_queries"] == 30
    assert snapshot["p95_ms"] >= 300
    assert snapshot["slow_top_sql"]
    assert snapshot["alerts"]
