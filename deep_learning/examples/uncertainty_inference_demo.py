"""阶段4不确定性量化推理与评估示例。"""

from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import (
    UncertaintyDatasetBuilder,
    UncertaintyEvaluator,
    UncertaintySystemIntegrator,
)


def make_demo_data(n: int = 180) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(19)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 6.0) + np.cos(coords[:, 1] * 3.8) + rng.normal(0.0, 0.09, size=n)
    return coords, values


def main() -> None:
    coords, values = make_demo_data()
    dataset = UncertaintyDatasetBuilder(seed=19).create_uncertainty_dataset(coords, values)

    sample_coords = dataset.coords[:120]
    sample_values = dataset.values[:120]
    query_coords = dataset.coords[120:]
    query_true = dataset.values[120:]

    integrator = UncertaintySystemIntegrator()
    result = integrator.predict(sample_coords, sample_values, query_coords, method="deep_ensemble")

    evaluator = UncertaintyEvaluator()
    metrics = evaluator.evaluate_regression(query_true, result.mean, result.variance)
    quality = evaluator.uncertainty_quality(result.mean, result.variance, query_true)
    report = evaluator.generate_report(metrics, quality)

    print("mean uncertainty:", float(np.mean(result.variance)))
    print("metrics:", metrics)
    print(report["markdown"])


if __name__ == "__main__":
    main()
