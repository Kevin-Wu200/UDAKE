"""阶段3异常检测训练示例脚本。"""

from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import (
    AnomalyDatasetBuilder,
    AnomalyTrainingConfig,
    AnomalyTrainingManager,
)


def make_demo_data(n: int = 120) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(42)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 6.0) + np.cos(coords[:, 1] * 7.0) + rng.normal(0.0, 0.08, size=n)
    return coords, values


def main() -> None:
    coords, values = make_demo_data()
    dataset = AnomalyDatasetBuilder(random_state=42).build(coords, values, include_synthetic=True)

    manager = AnomalyTrainingManager()
    for model_name in ["vae", "gcae", "gan", "contrastive"]:
        cfg = AnomalyTrainingConfig(model_name=model_name, max_epochs=25)
        result = manager.train(cfg, dataset.coords, dataset.values)
        print(f"[{model_name}] training={result['training']}")


if __name__ == "__main__":
    main()
