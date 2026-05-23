"""Auth DB benchmark for concurrency and response-time metrics."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List

from sqlalchemy import create_engine, text


@dataclass
class BenchmarkResult:
    users: int
    total_requests: int
    success_requests: int
    failed_requests: int
    p95_ms: float
    avg_ms: float
    simple_query_avg_ms: float
    complex_query_avg_ms: float
    batch_op_avg_ms: float


def _prepare_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS perf_workflows (
                    id INTEGER PRIMARY KEY,
                    owner_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        conn.execute(text("DELETE FROM perf_workflows"))
        for i in range(1, 2001):
            conn.execute(
                text(
                    "INSERT INTO perf_workflows (id, owner_id, name, status, created_at) "
                    "VALUES (:id, :owner_id, :name, :status, :created_at)"
                ),
                {
                    "id": i,
                    "owner_id": (i % 50) + 1,
                    "name": f"wf-{i}",
                    "status": "active" if i % 2 == 0 else "draft",
                    "created_at": "2026-04-01T00:00:00+00:00",
                },
            )


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = int(max(0, min(len(sorted_values) - 1, round((len(sorted_values) - 1) * pct))))
    return sorted_values[idx]


def run_benchmark(database_url: str, users: int, requests_per_user: int = 20) -> BenchmarkResult:
    engine = create_engine(database_url, future=True)
    _prepare_schema(engine)

    latencies: List[float] = []
    simple_latencies: List[float] = []
    complex_latencies: List[float] = []
    batch_latencies: List[float] = []
    success = 0
    failed = 0

    def _worker(user_idx: int) -> Dict[str, List[float]]:
        worker_lat: List[float] = []
        worker_simple: List[float] = []
        worker_complex: List[float] = []
        worker_batch: List[float] = []
        with engine.connect() as conn:
            for i in range(requests_per_user):
                started = time.perf_counter()
                conn.execute(
                    text("SELECT id, name FROM perf_workflows WHERE id = :id"),
                    {"id": ((user_idx * requests_per_user + i) % 2000) + 1},
                ).fetchone()
                worker_simple.append((time.perf_counter() - started) * 1000)

                started = time.perf_counter()
                conn.execute(
                    text(
                        "SELECT owner_id, status, COUNT(*) AS cnt "
                        "FROM perf_workflows GROUP BY owner_id, status HAVING COUNT(*) >= 1"
                    )
                ).fetchall()
                worker_complex.append((time.perf_counter() - started) * 1000)

                started = time.perf_counter()
                conn.execute(
                    text("UPDATE perf_workflows SET status='active' WHERE id BETWEEN :l AND :r"),
                    {"l": 1 + (i % 50), "r": 10 + (i % 50)},
                )
                conn.commit()
                worker_batch.append((time.perf_counter() - started) * 1000)

                worker_lat.append((time.perf_counter() - started) * 1000)
        return {
            "latencies": worker_lat,
            "simple": worker_simple,
            "complex": worker_complex,
            "batch": worker_batch,
        }

    with ThreadPoolExecutor(max_workers=users) as executor:
        futures = [executor.submit(_worker, idx) for idx in range(users)]
        for future in as_completed(futures):
            try:
                data = future.result()
                success += requests_per_user
                latencies.extend(data["latencies"])
                simple_latencies.extend(data["simple"])
                complex_latencies.extend(data["complex"])
                batch_latencies.extend(data["batch"])
            except Exception:
                failed += requests_per_user

    engine.dispose()
    return BenchmarkResult(
        users=users,
        total_requests=users * requests_per_user,
        success_requests=success,
        failed_requests=failed,
        p95_ms=round(_percentile(latencies, 0.95), 2),
        avg_ms=round(mean(latencies) if latencies else 0.0, 2),
        simple_query_avg_ms=round(mean(simple_latencies) if simple_latencies else 0.0, 2),
        complex_query_avg_ms=round(mean(complex_latencies) if complex_latencies else 0.0, 2),
        batch_op_avg_ms=round(mean(batch_latencies) if batch_latencies else 0.0, 2),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run auth DB concurrency benchmark.")
    parser.add_argument("--database-url", default="sqlite+pysqlite:////tmp/auth_db_benchmark.sqlite")
    parser.add_argument("--levels", default="100,500,1000")
    parser.add_argument("--requests-per-user", type=int, default=20)
    parser.add_argument("--output", default="services/backend/reports/auth_db_benchmark_report.json")
    args = parser.parse_args()

    levels = [int(item.strip()) for item in str(args.levels).split(",") if item.strip()]
    results = [asdict(run_benchmark(args.database_url, level, args.requests_per_user)) for level in levels]

    summary = {
        "generated_at": int(time.time()),
        "database_url": args.database_url,
        "results": results,
        "thresholds": {
            "query_response_ms": 100,
            "concurrency_users": 1000,
            "stability_target": 99.9,
        },
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote benchmark report: {output_path}")


if __name__ == "__main__":
    main()
