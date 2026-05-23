from __future__ import annotations

from services.backend.app.core.performance_optimization import (
    PerformanceMonitoringFramework,
    ResultPreloader,
)


def test_performance_monitoring_framework_full_cycle_stage2() -> None:
    monitor = PerformanceMonitoringFramework(history_window=64)
    monitor.register_metric(
        "inference_ms",
        unit="ms",
        category="latency",
        thresholds={"warning": 5.0, "critical": 20.0},
        description="单次推理耗时",
    )

    with monitor.measure_execution("inference_ms", tags={"model": "fusion"}):
        _ = sum(range(5000))
    monitor.monitor_resources(context={"worker": "a"})

    monitor.record_metric("inference_ms", 8.0, tags={"model": "fusion"})
    monitor.record_metric("inference_ms", 15.0, tags={"model": "fusion"})
    monitor.record_metric("inference_ms", 25.0, tags={"model": "fusion"})

    bottlenecks = monitor.identify_bottlenecks(top_k=3)
    assert any(item["metric"] == "inference_ms" for item in bottlenecks)

    trend = monitor.trend_analysis("inference_ms", window=16)
    assert trend["metric"] == "inference_ms"
    assert trend["samples"] >= 3

    alerts = monitor.recent_alerts(limit=20)
    assert any(item["metric"] == "inference_ms" for item in alerts)

    report = monitor.generate_report()
    assert "metrics" in report
    assert "inference_ms" in report["metrics"]
    assert "bottlenecks" in report
    assert "alerts" in report
    assert "trends" in report


def test_result_preloader_hotspot_schedule_retry_and_cache_stage2() -> None:
    preloader = ResultPreloader(cache_ttl_seconds=30.0, cache_size=8, max_retries=2, retry_backoff_seconds=0.05)

    for _ in range(3):
        preloader.record_access("geo:a", latency_ms=12.0)
    for _ in range(2):
        preloader.record_access("geo:b", latency_ms=8.0)
    preloader.record_access("geo:c", latency_ms=3.0)

    hot_rows = preloader.identify_hot_data(limit=5, min_hits=2)
    assert [row["key"] for row in hot_rows][:2] == ["geo:a", "geo:b"]

    plans = preloader.design_strategy(hot_rows)
    assert plans[0]["priority"] >= plans[1]["priority"]

    out = preloader.schedule_preload(plans + [plans[0]])
    assert out["queued"] >= 2
    assert out["deduplicated"] >= 1

    attempts = {"geo:b": 0}

    def loader(key: str, payload: dict) -> dict:
        if key == "geo:b":
            attempts["geo:b"] += 1
            if attempts["geo:b"] == 1:
                raise RuntimeError("temporary")
        return {"key": key, "payload": payload, "value": [1, 2, 3]}

    run1 = preloader.run_scheduler(loader, budget=4, now=100.0)
    assert run1["loaded"] >= 1
    assert run1["retried"] >= 1

    run2 = preloader.run_scheduler(loader, budget=4, now=100.2)
    assert run2["loaded"] >= 1

    cached_a = preloader.get_preloaded("geo:a")
    cached_b = preloader.get_preloaded("geo:b")
    assert cached_a is not None
    assert cached_b is not None

    optimized = preloader.optimize_preload_performance()
    assert optimized["queue_after"] <= optimized["queue_before"]

    stats = preloader.stats()
    assert stats["loaded"] >= 2
    assert stats["cache_hits"] >= 2
