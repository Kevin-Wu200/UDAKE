"""Tests for auth DB performance helpers."""

from __future__ import annotations

from app.auth_db.performance import (
    QueryStatsCollector,
    ReadWriteSessionRouter,
    ReplicaSyncMonitor,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def test_query_stats_collector_report() -> None:
    collector = QueryStatsCollector(slow_ms=50, max_samples=10)
    collector.record("SELECT * FROM users WHERE id = 1", 10)
    collector.record("SELECT * FROM users WHERE id = 1", 12)
    collector.record("SELECT * FROM workflows WHERE owner_id = 2", 77)

    report = collector.report(top_n=5)
    assert report["frequent_queries"][0]["count"] == 2
    assert report["slow_queries"][0]["elapsed_ms"] >= 77


def test_read_write_session_router_transaction_read_fallback_primary() -> None:
    primary = create_engine("sqlite+pysqlite:///:memory:", future=True)
    replica = create_engine("sqlite+pysqlite:///:memory:", future=True)

    with primary.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))
        conn.execute(text("INSERT INTO t (id, v) VALUES (1, 'primary')"))
    with replica.begin() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)"))

    router = ReadWriteSessionRouter(
        primary_session_factory=sessionmaker(bind=primary, future=True),
        replica_session_factories=[sessionmaker(bind=replica, future=True)],
    )

    with router.read_session() as session:
        row = session.execute(text("SELECT v FROM t WHERE id = 1")).scalar_one_or_none()
    assert row is None

    with router.transaction() as session:
        row = session.execute(text("SELECT v FROM t WHERE id = 1")).scalar_one_or_none()
        assert row == "primary"


def test_replica_sync_monitor_snapshot() -> None:
    monitor = ReplicaSyncMonitor(
        check_fn=lambda: [
            {"replica": "r1", "healthy": True, "lag_seconds": 1.2},
            {"replica": "r2", "healthy": False, "lag_seconds": 8.6},
        ],
        lag_warn_seconds=5,
    )
    snapshot = monitor.snapshot()
    assert snapshot["healthy"] is False
    assert snapshot["max_lag_seconds"] == 8.6
