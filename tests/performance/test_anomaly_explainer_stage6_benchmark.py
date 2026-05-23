from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from deep_learning.models.anomaly_detection import (
    ContrastiveAnomalyDetector,
    GANAnomalyDetector,
    GCAEAnomalyDetector,
    VAEAnomalyDetector,
)
from deep_learning.utils.testing import TestReportGenerator
from services.backend.app.dl_services.contrastive_anomaly_explainer import (
    ContrastiveExplanationConfig,
    ContrastiveLimeAdapter,
)
from services.backend.app.dl_services.gan_anomaly_explainer import (
    GANAnomalyLimeAdapter,
    GANExplanationConfig,
)
from services.backend.app.dl_services.gcae_anomaly_explainer import (
    GCAEExplanationConfig,
    GCAELimeAdapter,
)
from services.backend.app.dl_services.vae_anomaly_explainer import (
    VAEAnomalyLIMEAdapter,
    VAEExplanationConfig,
)

PERF_PLAN = {
    "single_sample_ms": 10_000.0,
    "batch_latency_ms": 10_000.0,
    "concurrency_latency_ms": 10_000.0,
    "batch_explain_nodes": 8,
    "concurrency": 4,
}


def _make_data(n: int = 180, seed: int = 67) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 6.0) + np.cos(coords[:, 1] * 4.0) + rng.normal(0.0, 0.05, size=n)
    values[::15] += 1.0
    values[4::21] -= 0.6
    return coords, values


@pytest.fixture(scope="module")
def benchmark_suite() -> dict[str, tuple[object, object, np.ndarray, np.ndarray]]:
    coords, values = _make_data()

    vae = VAEAnomalyDetector()
    vae.fit(coords, values)
    vae_adapter = VAEAnomalyLIMEAdapter(config=VAEExplanationConfig(lime_num_samples=180, max_explain_nodes=8))

    gcae = GCAEAnomalyDetector()
    gcae.fit(coords, values)
    gcae_adapter = GCAELimeAdapter(config=GCAEExplanationConfig(lime_num_samples=200, parallel_workers=2, max_explain_nodes=8))

    gan = GANAnomalyDetector()
    gan.fit(coords, values)
    gan_adapter = GANAnomalyLimeAdapter(config=GANExplanationConfig(lime_num_samples=200, parallel_workers=2, max_explain_nodes=8))

    contrastive = ContrastiveAnomalyDetector()
    contrastive.fit(coords, values, epochs=16)
    contrastive_adapter = ContrastiveLimeAdapter(
        config=ContrastiveExplanationConfig(lime_num_samples=200, parallel_workers=2, max_explain_nodes=8)
    )

    return {
        "vae": (vae, vae_adapter, coords, values),
        "gcae": (gcae, gcae_adapter, coords, values),
        "gan": (gan, gan_adapter, coords, values),
        "contrastive": (contrastive, contrastive_adapter, coords, values),
    }


def test_stage6_performance_plan_defined() -> None:
    assert PERF_PLAN["single_sample_ms"] <= 10_000.0
    assert PERF_PLAN["batch_latency_ms"] <= 10_000.0
    assert PERF_PLAN["concurrency_latency_ms"] <= 10_000.0
    assert PERF_PLAN["batch_explain_nodes"] >= 4
    assert PERF_PLAN["concurrency"] >= 2


@pytest.mark.parametrize("model_name", ["vae", "gcae", "gan", "contrastive"])
def test_stage6_single_sample_explain_latency(benchmark_suite, model_name: str) -> None:
    model, adapter, coords, values = benchmark_suite[model_name]

    started = time.perf_counter()
    out = adapter.explain(
        model=model,
        coords=coords,
        values=values,
        top_k=5,
        max_explain_nodes=1,
        num_samples=160,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert elapsed_ms < PERF_PLAN["single_sample_ms"]
    assert out["performance"]["duration_ms"] < PERF_PLAN["single_sample_ms"]


def test_stage6_batch_performance_and_memory_usage(benchmark_suite) -> None:
    metrics: dict[str, dict[str, float]] = {}

    for model_name, (model, adapter, coords, values) in benchmark_suite.items():
        started = time.perf_counter()
        out = adapter.explain(
            model=model,
            coords=coords,
            values=values,
            top_k=5,
            max_explain_nodes=PERF_PLAN["batch_explain_nodes"],
            num_samples=220,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000

        assert elapsed_ms < PERF_PLAN["batch_latency_ms"]
        assert len(out["batch_explanations"]) == PERF_PLAN["batch_explain_nodes"]
        assert out["summary"]["explained_nodes"] == PERF_PLAN["batch_explain_nodes"]

        perf = out.get("performance", {})
        if "memory_bytes" in perf:
            assert perf["memory_bytes"] > 0

        metrics[model_name] = {
            "duration_ms": float(perf.get("duration_ms", elapsed_ms)),
            "cache_hit": 1.0 if bool(perf.get("cache_hit", False)) else 0.0,
            "memory_bytes": float(perf.get("memory_bytes", 0.0)),
        }

    # VAE 的阶段6优化：LIME 训练样本压缩 + 内存统计字段
    vae_model, vae_adapter, coords, values = benchmark_suite["vae"]
    vae_out = vae_adapter.explain(
        model=vae_model,
        coords=coords,
        values=values,
        top_k=5,
        max_explain_nodes=PERF_PLAN["batch_explain_nodes"],
        num_samples=220,
    )
    assert vae_out["performance"]["memory_bytes"] > 0
    assert 8 <= vae_out["performance"]["lime_training_size"] <= 96
    assert vae_out["performance"]["lime_sampling_budget"] >= 80

    # 生成性能报告（JSON）
    report_payload = {
        "suite": "anomaly_stage6_performance",
        "plan": PERF_PLAN,
        "metrics": metrics,
    }
    report_path = TestReportGenerator().write_json(
        "tests/reports/stage6-anomaly-performance-benchmark.json",
        report_payload,
    )
    assert report_path.endswith("stage6-anomaly-performance-benchmark.json")


def test_stage6_concurrency_performance(benchmark_suite) -> None:
    model, adapter, coords, values = benchmark_suite["gan"]

    # 预热一次，后续并发请求走缓存路径，评估并发吞吐与稳定性
    _ = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, num_samples=180)

    def _run_once() -> dict[str, object]:
        started = time.perf_counter()
        out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=6, num_samples=180)
        return {
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "cache_hit": bool(out["performance"].get("cache_hit", False)),
            "duration_ms": float(out["performance"].get("duration_ms", 0.0)),
        }

    with ThreadPoolExecutor(max_workers=PERF_PLAN["concurrency"]) as executor:
        results = list(executor.map(lambda _: _run_once(), range(PERF_PLAN["concurrency"])))

    assert len(results) == PERF_PLAN["concurrency"]
    assert max(item["elapsed_ms"] for item in results) < PERF_PLAN["concurrency_latency_ms"]
    assert all(item["cache_hit"] for item in results)
    assert all(item["duration_ms"] < PERF_PLAN["concurrency_latency_ms"] for item in results)
