"""阶段4不确定性量化训练示例。"""

from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import UQTrainingConfig, UQTrainingManager, UncertaintyDatasetBuilder


def make_demo_data(n: int = 150) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(2026)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.5) + np.cos(coords[:, 1] * 4.2) + rng.normal(0.0, 0.08, size=n)
    return coords, values


def main() -> None:
    coords, values = make_demo_data()
    dataset = UncertaintyDatasetBuilder(seed=7).create_uncertainty_dataset(coords, values)

    manager = UQTrainingManager()
    x = dataset.features
    y = dataset.values

    for name in ["bnn", "mc_dropout", "deep_ensemble", "edl"]:
        cfg = UQTrainingConfig(model_name=name, max_epochs=120, hidden_dim=28)
        result = manager.train(cfg, x, y)
        print(f"[{name}] training={result['training']}")
        print(f"[{name}] monitor={result['monitor']}")


if __name__ == "__main__":
    main()
