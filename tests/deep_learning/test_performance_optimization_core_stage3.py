from __future__ import annotations

from services.backend.app.core.performance_optimization import (
    ConnectionPoolOrchestrator,
    DatabaseQueryOptimizer,
    PerformanceMetricsCollector,
)


def test_database_query_optimizer_full_cycle_stage3() -> None:
    optimizer = DatabaseQueryOptimizer(slow_query_ms=50.0, cache_ttl_seconds=30.0, cache_size=16)
    logs = [
        {"sql": "SELECT * FROM users WHERE id = :id", "elapsed_ms": 18.0},
        {"sql": "SELECT * FROM users WHERE status = :status ORDER BY created_at DESC", "elapsed_ms": 91.0},
        {"sql": "SELECT name FROM users WHERE status = :status", "elapsed_ms": 53.0},
    ]

    report = optimizer.analyze_query_bottlenecks(logs, top_n=5)
    assert report["total_queries"] == 3
    assert len(report["slow_queries"]) >= 2
    assert report["p95_elapsed_ms"] >= report["avg_elapsed_ms"]

    slow_advice = optimizer.optimize_slow_query(
        "SELECT * FROM users WHERE status = :status ORDER BY created_at DESC",
        elapsed_ms=91.0,
        filters=["status", "created_at"],
    )
    assert slow_advice["is_slow"] is True
    assert "SELECT id" in slow_advice["rewritten_sql"]

    idx = optimizer.add_query_indexes("users", ["status", "created_at", "status"])
    assert idx["created"] == 2
    assert idx["total_indexes"] >= 2

    plan = optimizer.optimize_query_plan(
        "SELECT id FROM users WHERE status = :status ORDER BY created_at DESC",
        explain_rows=[
            {"plan": "Seq Scan on users"},
            {"plan": "Sort Method: external merge"},
        ],
    )
    assert plan["plan_steps"] == 2
    assert len(plan["recommendations"]) >= 1

    calls = {"count": 0}

    def executor(sql: str, params: dict) -> dict:
        calls["count"] += 1
        return {"sql": sql, "params": params, "rows": [1, 2, 3]}

    queries = [
        {"sql": "SELECT id FROM users WHERE id = :id", "params": {"id": 1}},
        {"sql": "SELECT id FROM users WHERE id = :id", "params": {"id": 1}},
        {"sql": "SELECT id FROM users WHERE id = :id", "params": {"id": 2}},
    ]
    batch = optimizer.optimize_batch_queries(queries, executor, batch_size=2)
    assert batch["total"] == 3
    assert batch["cache_hits"] >= 1
    assert calls["count"] <= 2

    analyzer = optimizer.query_analyzer(top_n=3)
    assert analyzer["tracked"] >= 3
    assert analyzer["cache"]["hits"] >= 1


def test_connection_pool_orchestrator_lifecycle_stage3() -> None:
    unhealthy = {"conn-2"}

    def checker(conn_id: str, _row: dict) -> bool:
        return conn_id not in unhealthy

    pool = ConnectionPoolOrchestrator(min_size=2, max_size=6, scale_step=2, health_check=checker)
    snap = pool.create_pool(initial_size=2)
    assert snap["total"] == 2
    assert snap["idle"] == 2

    sched = pool.schedule(request_count=3)
    assert sched["assigned_count"] >= 2

    health = pool.health_check()
    assert health["failed"] >= 1
    assert health["unhealthy"] >= 1

    for cid in sched["assigned"]:
        pool.release(cid)

    scaled_up = pool.scale_pool(5)
    assert scaled_up["total"] >= 4

    optimized = pool.optimize_pool_performance(high_watermark=0.5, low_watermark=0.1)
    assert optimized["action"] in {"none", "scale_up", "scale_down"}

    final = pool.monitor()
    assert final["metrics"]["created"] >= 2
    assert final["metrics"]["acquired"] >= sched["assigned_count"]


def test_performance_metrics_collector_collect_aggregate_visualize_stage3() -> None:
    collector = PerformanceMetricsCollector(retention=128)

    arch = collector.design_metrics_architecture()
    assert "aggregation" in arch

    for i in range(1, 11):
        collector.collect_metric("inference_ms", float(i * 10), category="latency", tags={"model": "fusion"}, timestamp=1000 + i)

    agg = collector.aggregate_metrics("inference_ms", window=10)
    assert agg["count"] == 10
    assert agg["max"] == 100.0
    assert agg["p95"] >= agg["avg"]

    stored = collector.store_metrics(metric_names=["inference_ms"])
    assert stored["stored_metrics"] == 1

    viz = collector.visualize_metrics("inference_ms", bins=5)
    assert len(viz["timeline"]) == 10
    assert len(viz["histogram"]) == 5

    analysis = collector.analyze_metrics("inference_ms", window=10)
    assert analysis["trend"] in {"up", "down", "flat"}
    assert analysis["latest"] == 100.0

    doc = collector.usage_documentation()
    assert "collect_metric" in doc
    assert "analyze_metrics" in doc
