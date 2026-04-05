"""时空克里金性能基准脚本（手动运行）。"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

services_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(services_root))

from backend.app.services.spatiotemporal_core import STDataset, SpatiotemporalKrigingSolver, SpatiotemporalVariogramModeler


def build_dataset(n_points: int) -> STDataset:
    rng = np.random.default_rng(42)
    x = rng.uniform(120.0, 121.0, size=n_points)
    y = rng.uniform(30.0, 31.0, size=n_points)
    z = rng.uniform(5.0, 30.0, size=n_points)
    t = np.linspace(1711929600, 1711929600 + 86400 * 120, n_points)
    value = 80.0 + 5.0 * np.sin(np.linspace(0, 8, n_points)) + rng.normal(0, 0.6, n_points)
    return STDataset(x=x, y=y, z=z, t=t, value=value)


def run_case(name: str, n_points: int, n_targets: int, n_times: int) -> None:
    data = build_dataset(n_points)
    modeler = SpatiotemporalVariogramModeler()
    params = modeler.fit(data, "product")["parameters"]
    solver = SpatiotemporalKrigingSolver(block_size=500, temporal_window_size=30, low_rank=100)

    targets = {
        "x": np.linspace(120.1, 120.9, n_targets).tolist(),
        "y": np.linspace(30.1, 30.9, n_targets).tolist(),
        "z": np.linspace(8.0, 20.0, n_targets).tolist(),
    }
    times = np.linspace(float(np.min(data.t)), float(np.max(data.t)), n_times).tolist()

    started = time.perf_counter()
    result = solver.predict(
        train_data=data,
        targets=targets,
        target_times=times,
        params=params,
        model_type="product",
        covariance_builder=modeler.build_covariance_function,
    )
    elapsed = time.perf_counter() - started

    print(f"[{name}] points={n_points}, targets={n_targets}x{n_times}, elapsed={elapsed:.3f}s, low_rank={result['solver_info']['low_rank_used']}")


def main() -> None:
    run_case("small", n_points=500, n_targets=12, n_times=5)
    run_case("medium", n_points=1200, n_targets=20, n_times=8)


if __name__ == "__main__":
    main()
