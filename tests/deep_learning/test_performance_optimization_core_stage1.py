from __future__ import annotations

import numpy as np

from services.backend.app.core.performance_optimization import (
    AdaptiveSamplingOptimizer,
    BatchExplanationOptimizer,
    MemoryOptimizationManager,
    ModelPerformanceCache,
    PredictionReuseManager,
)


def test_model_performance_cache_key_hit_warmup_and_invalidate_stage1() -> None:
    cache = ModelPerformanceCache(max_size=2)
    key = cache.build_cache_key(
        model_name="fusion",
        model_version="v1",
        payload={"x": [1, 2, 3], "top_k": 4},
        namespace="prediction",
    )
    cache.set_prediction(key, {"value": [0.1, 0.2]})
    assert cache.get_prediction(key) == {"value": [0.1, 0.2]}
    assert cache.get_prediction("missing") is None

    warm = cache.warmup(
        [
            {"namespace": "explanation", "key": "exp:k1", "value": {"score": 1}},
            {"namespace": "prediction", "key": "pred:k2", "value": {"pred": 2}},
        ]
    )
    assert warm["succeeded"] == 2

    removed = cache.invalidate(namespace="prediction", key_prefix="pred:")
    assert removed["prediction"] >= 1
    stats = cache.stats()
    assert stats["hit_rate"] > 0.0
    assert stats["warmups"] >= 2


def test_model_performance_cache_size_limit_stage1() -> None:
    cache = ModelPerformanceCache(max_size=2)
    cache.set_prediction("k1", {"v": 1})
    cache.set_prediction("k2", {"v": 2})
    cache.set_prediction("k3", {"v": 3})

    assert cache.get_prediction("k1") is None
    assert cache.get_prediction("k3") == {"v": 3}
    assert cache.stats()["evictions"] >= 1


def test_batch_explanation_optimizer_parallel_schedule_progress_and_aggregation_stage1() -> None:
    optimizer = BatchExplanationOptimizer()
    tasks = [
        {"task_id": "t1", "priority": 1, "payload": {"max_explain_nodes": 4, "num_samples": 90}},
        {"task_id": "t2", "priority": 3, "payload": {"max_explain_nodes": 6, "num_samples": 120}},
        {"task_id": "t3", "priority": 2, "payload": {"max_explain_nodes": 5, "num_samples": 100}},
    ]

    report = optimizer.analyze_bottleneck(tasks)
    assert report["estimated_total_cost"] > 0

    def worker(task: dict) -> dict:
        return {"task_id": task["task_id"], "ok": True, "weight": task["payload"]["max_explain_nodes"]}

    out = optimizer.run(tasks, worker, max_workers=2)
    assert out["summary"]["succeeded"] == 3
    assert out["summary"]["progress"] == 1.0
    assert len(out["progress_trace"]) == 3
    assert out["aggregation"]["success_rate"] == 1.0


def test_prediction_reuse_index_retrieve_consistency_version_and_strategy_stage1() -> None:
    manager = PredictionReuseManager()
    payload = {"pred": [0.3, 0.4, 0.5]}
    manager.index_prediction(
        model_name="bnn",
        model_version="v3",
        query_fingerprint="q:abc",
        prediction=payload,
        metadata={"seed": 11},
    )

    hit = manager.retrieve_prediction(
        model_name="bnn",
        model_version="v3",
        query_fingerprint="q:abc",
        expected_signature=PredictionReuseManager._signature(payload),
    )
    miss = manager.retrieve_prediction(
        model_name="bnn",
        model_version="v3",
        query_fingerprint="q:missing",
    )

    assert hit is not None
    assert miss is None
    strategy = manager.optimize_reuse_strategy()
    assert strategy["strategy"] in {"reuse_first", "compute_first"}
    assert "bnn" in strategy["version_map"]


def test_memory_optimization_analysis_pool_monitor_recycle_and_leak_stage1() -> None:
    manager = MemoryOptimizationManager(monitor_window=6)

    analysis = manager.analyze_memory_usage(
        {
            "arr": np.ones((16, 16), dtype=np.float64),
            "meta": {"id": "x", "tags": ["a", "b"]},
        }
    )
    assert analysis["total_bytes"] > 0

    buf = manager.acquire_buffer((8, 8), np.float32)
    manager.release_buffer(buf)
    buf2 = manager.acquire_buffer((8, 8), np.float32)
    assert buf2.shape == (8, 8)

    snap1 = manager.monitor({"arr": np.ones((8, 8), dtype=np.float32)})
    snap2 = manager.monitor({"arr": np.ones((16, 16), dtype=np.float32)})
    snap3 = manager.monitor({"arr": np.ones((32, 32), dtype=np.float32)})
    assert snap3["memory_bytes"] >= snap1["memory_bytes"]

    leak = manager.detect_memory_leak(min_growth_bytes=16)
    assert leak["samples"] >= 3

    removed = manager.recycle_pool(max_idle_seconds=-1.0)
    assert removed >= 0

    optimized = manager.optimize_large_object(np.ones((4, 4), dtype=np.float64), target_dtype=np.float32)
    assert optimized.dtype == np.float32


def test_adaptive_sampling_density_quality_history_and_parameter_adaptation_stage1() -> None:
    sampler = AdaptiveSamplingOptimizer(base_density=1.0)
    rng = np.random.default_rng(23)
    candidates = rng.uniform(0.0, 1.0, size=(20, 2))
    uncertainties = rng.uniform(0.1, 1.0, size=20)

    out1 = sampler.sample(candidates=candidates, uncertainties=uncertainties, target_count=6)
    out2 = sampler.sample(candidates=candidates, uncertainties=uncertainties * 0.5, target_count=6)

    assert out1["history_size"] == 1
    assert out2["history_size"] == 2
    assert len(out1["indices"]) == 6
    assert 0.2 <= out1["density"] <= 3.0

    params = sampler.adapt_parameters(window=2)
    assert 0.2 <= params["explore_weight"] <= 0.9
    assert len(sampler.history()) == 2
