"""阶段3异常检测推理与评估示例脚本。"""

from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import (
    AnomalyDatasetBuilder,
    AnomalyEnsembleIntegrator,
    AnomalyEvaluator,
    ContrastiveAnomalyDetector,
    GANAnomalyDetector,
    GCAEAnomalyDetector,
    VAEAnomalyDetector,
)


def make_demo_data(n: int = 140) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(123)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.0) + np.cos(coords[:, 1] * 4.0) + rng.normal(0.0, 0.08, size=n)
    return coords, values


def main() -> None:
    coords, values = make_demo_data()
    dataset = AnomalyDatasetBuilder(random_state=123).build(coords, values, include_synthetic=True)

    detectors = {
        "vae": VAEAnomalyDetector(),
        "gcae": GCAEAnomalyDetector(),
        "gan": GANAnomalyDetector(),
        "contrastive": ContrastiveAnomalyDetector(),
    }

    for name, detector in detectors.items():
        if name == "contrastive":
            detector.fit(dataset.coords, dataset.values, epochs=20)
        else:
            detector.fit(dataset.coords, dataset.values)

    fused = AnomalyEnsembleIntegrator(detectors).detect(dataset.coords, dataset.values)
    scores = np.asarray(fused["fused_scores"], dtype=float)

    evaluator = AnomalyEvaluator()
    metrics = evaluator.evaluate(dataset.labels, scores, threshold=fused["threshold"])
    report = evaluator.generate_report("Ensemble", metrics)

    print("metrics:", metrics)
    print("anomaly_count:", fused["anomaly_count"])
    print(report["markdown"])


if __name__ == "__main__":
    main()
