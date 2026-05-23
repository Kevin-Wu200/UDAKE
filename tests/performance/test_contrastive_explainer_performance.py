from __future__ import annotations

import time

import numpy as np

from deep_learning.models.anomaly_detection import ContrastiveAnomalyDetector
from services.backend.app.dl_services.contrastive_anomaly_explainer import (
    ContrastiveExplanationConfig,
    ContrastiveLimeAdapter,
)


def _make_data(n: int = 140, seed: int = 23) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 6.0) + np.cos(coords[:, 1] * 4.0) + rng.normal(0.0, 0.05, size=n)
    values[::15] += 1.0
    values[4::21] -= 0.6
    return coords, values


def test_contrastive_lime_cache_speedup_benchmark() -> None:
    coords, values = _make_data()
    model = ContrastiveAnomalyDetector()
    model.fit(coords, values, epochs=16)

    adapter = ContrastiveLimeAdapter(config=ContrastiveExplanationConfig(lime_num_samples=360, parallel_workers=2))

    t1 = time.perf_counter()
    first_out = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=8, num_samples=320)
    first = time.perf_counter() - t1

    t2 = time.perf_counter()
    cached = adapter.explain(model=model, coords=coords, values=values, top_k=5, max_explain_nodes=8, num_samples=320)
    second = time.perf_counter() - t2

    assert first_out["performance"]["duration_ms"] < 10000.0
    assert cached["performance"]["cache_hit"] is True
    assert second <= first * 0.7
