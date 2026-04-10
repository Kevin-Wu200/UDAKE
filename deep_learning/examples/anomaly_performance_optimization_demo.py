"""异常检测性能优化示例（采样预算 + 缓存命中）。"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from anomaly_examples_common import build_demo_dataset, create_model, train_model


def timed_call(fn: Any, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    start = time.perf_counter()
    out = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return out, elapsed_ms


def main() -> None:
    dataset = build_demo_dataset(n=120, seed=808)
    coords = dataset.coords
    values = dataset.values

    batches: list[tuple[np.ndarray, np.ndarray]] = []
    for i in range(0, len(values), 24):
        j = min(i + 24, len(values))
        batches.append((coords[i:j], values[i:j]))

    def baseline_pipeline() -> int:
        total = 0
        for c_batch, v_batch in batches:
            model = create_model("gan")
            train_model("gan", model, c_batch, v_batch, epochs=8)
            pred = model.predict(c_batch, v_batch, threshold_method="percentile", percentile=92.0, k=2.2)
            total += int(pred.get("anomaly_count", 0))
        return total

    def optimized_pipeline() -> int:
        model = create_model("gan")
        train_model("gan", model, coords, values, epochs=15)
        total = 0
        for c_batch, v_batch in batches:
            pred = model.predict(c_batch, v_batch, threshold_method="percentile", percentile=92.0, k=2.2)
            total += int(pred.get("anomaly_count", 0))
        return total

    baseline_count, baseline_ms = timed_call(baseline_pipeline)
    optimized_count, optimized_ms = timed_call(optimized_pipeline)

    print("=== 性能优化对比（GAN 批处理）===")
    print(f"baseline_ms={baseline_ms:.2f}, anomaly_count={baseline_count}")
    print(f"optimized_ms={optimized_ms:.2f}, anomaly_count={optimized_count}")
    if optimized_ms > 0:
        print(f"speedup={baseline_ms / optimized_ms:.2f}x")


if __name__ == "__main__":
    main()
