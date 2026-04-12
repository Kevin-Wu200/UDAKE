"""后端启动优化（第六章）性能基准脚本。"""

from __future__ import annotations

import argparse
import argparse as _argparse
import importlib
import json
import os
import sys
import tracemalloc
from pathlib import Path
from statistics import mean
from time import perf_counter
from types import ModuleType, SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_run_module():
    import run

    return importlib.reload(run)


def _make_args(**overrides):
    data = {
        "env": "development",
        "redis_timeout": 0.1,
        "redis_retries": 1,
        "port": 8000,
        "port_strategy": "auto",
        "port_scan_limit": 10,
    }
    data.update(overrides)
    return _argparse.Namespace(**data)


def _install_fake_settings(host: str = "127.0.0.1", port: int = 8000):
    fake_config = ModuleType("app.config")
    fake_config.settings = SimpleNamespace(
        PORT=port,
        HOST=host,
        DEBUG=False,
        APP_NAME="UDAKE-Backend-Benchmark",
    )
    sys.modules["app.config"] = fake_config


def _bench_startup_pipeline(run_module, iterations: int) -> list[float]:
    costs_ms = []
    for _ in range(iterations):
        _install_fake_settings()
        run_module._RUNTIME_CLEANED_UP = False
        run_module._select_environment = lambda args: "development"
        run_module._resolve_port_conflict = lambda **kwargs: 8001
        run_module.ensure_redis_running = lambda **kwargs: True
        run_module.uvicorn.run = lambda *args, **kwargs: None
        run_module._cleanup_runtime_resources = lambda: None

        started = perf_counter()
        exit_code = run_module.run_backend(_make_args())
        elapsed_ms = (perf_counter() - started) * 1000
        if exit_code != 0:
            raise RuntimeError(f"run_backend 返回非 0: {exit_code}")
        costs_ms.append(elapsed_ms)
    return costs_ms


def _bench_legacy_pipeline(run_module, iterations: int) -> list[float]:
    costs_ms = []
    for _ in range(iterations):
        _install_fake_settings()
        from app.config import settings

        run_module.uvicorn.run = lambda *args, **kwargs: None
        started = perf_counter()
        run_module.uvicorn.run(
            "app.main:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            log_level="info",
        )
        costs_ms.append((perf_counter() - started) * 1000)
    return costs_ms


def _bench_redis_probe(run_module, iterations: int) -> list[float]:
    costs_ms = []
    original = run_module._is_redis_running
    try:
        run_module._is_redis_running = lambda *args, **kwargs: True
        for _ in range(iterations):
            started = perf_counter()
            ok = run_module.ensure_redis_running(startup_timeout=0.1, retries=1)
            elapsed_ms = (perf_counter() - started) * 1000
            if not ok:
                raise RuntimeError("ensure_redis_running 返回 False")
            costs_ms.append(elapsed_ms)
    finally:
        run_module._is_redis_running = original
    return costs_ms


def _measure_memory_kib(run_module) -> dict[str, float]:
    _install_fake_settings()
    run_module._RUNTIME_CLEANED_UP = False
    run_module._select_environment = lambda args: "development"
    run_module._resolve_port_conflict = lambda **kwargs: 8001
    run_module.ensure_redis_running = lambda **kwargs: True
    run_module.uvicorn.run = lambda *args, **kwargs: None
    run_module._cleanup_runtime_resources = lambda: None

    tracemalloc.start()
    run_module.run_backend(_make_args())
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "current_kib": current / 1024,
        "peak_kib": peak / 1024,
    }


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "mean_ms": mean(values),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def run_benchmark(iterations: int) -> dict:
    run_module = _load_run_module()

    optimized = _bench_startup_pipeline(run_module, iterations)
    legacy = _bench_legacy_pipeline(run_module, iterations)
    redis_probe = _bench_redis_probe(run_module, iterations)
    memory = _measure_memory_kib(run_module)

    optimized_summary = _summary(optimized)
    legacy_summary = _summary(legacy)
    redis_summary = _summary(redis_probe)

    delta_ms = optimized_summary["mean_ms"] - legacy_summary["mean_ms"]
    delta_ratio = (
        optimized_summary["mean_ms"] / legacy_summary["mean_ms"]
        if legacy_summary["mean_ms"] > 0
        else None
    )

    return {
        "iterations": iterations,
        "startup_time_compare": {
            "legacy_baseline": legacy_summary,
            "optimized_pipeline": optimized_summary,
            "delta_ms": delta_ms,
            "ratio": delta_ratio,
        },
        "redis_connection_performance": redis_summary,
        "memory_usage_kib": memory,
    }


def _write_reports(result: dict, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "backend_startup_stage6_performance.json"
    md_path = output_dir / "backend_startup_stage6_performance.md"

    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    compare = result["startup_time_compare"]
    redis_perf = result["redis_connection_performance"]
    memory = result["memory_usage_kib"]

    md_lines = [
        "# 后端服务启动优化第六章性能报告",
        "",
        f"- 迭代次数: {result['iterations']}",
        f"- 启动时间对比（legacy vs optimized）: {compare['legacy_baseline']['mean_ms']:.3f}ms -> {compare['optimized_pipeline']['mean_ms']:.3f}ms",
        f"- 启动链路差值: {compare['delta_ms']:.3f}ms",
        f"- Redis 连接检测均值: {redis_perf['mean_ms']:.3f}ms",
        f"- 内存峰值: {memory['peak_kib']:.2f} KiB",
        "",
        "## 明细",
        "",
        "```json",
        json.dumps(result, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="后端服务启动优化第六章性能基准")
    parser.add_argument("--iterations", type=int, default=30, help="每项基准迭代次数")
    parser.add_argument(
        "--output-dir",
        default="tests/reports",
        help="报告输出目录（相对于 services/backend）",
    )
    args = parser.parse_args()

    os.chdir(BACKEND_ROOT)
    result = run_benchmark(iterations=args.iterations)
    json_path, md_path = _write_reports(result, Path(args.output_dir))

    print("后端启动优化第六章性能基准完成")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
