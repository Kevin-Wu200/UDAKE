"""独立运行示例：阶段6时空预测（含不确定性与优化参数）。"""

from __future__ import annotations

import json

import numpy as np

from deep_learning.inference.spatiotemporal_inference import SpatioTemporalInference
from deep_learning.models.spatiotemporal import SyntheticSpatioTemporalDataset


def main() -> None:
    sample = SyntheticSpatioTemporalDataset(seed=2026).generate(
        n_nodes=12,
        seq_len=28,
        pred_horizon=6,
        n_features=2,
        noise_std=0.03,
    )

    inference = SpatioTemporalInference()
    result = inference.predict_batch(
        coords=sample.coords,
        series=sample.series,
        model_type="st_transformer",
        pred_horizon=6,
        fusion_strategy="gating",
        uncertainty_method="deep_ensemble",
        enable_memory_optimization=True,
        enable_inference_acceleration=True,
        enable_long_sequence_optimization=False,
    )

    baseline = np.repeat(sample.series[:, -1, 0:1], 6, axis=1)
    mae = float(np.mean(np.abs(result.mean - sample.targets)))
    baseline_mae = float(np.mean(np.abs(baseline - sample.targets)))
    variance_mean = float(np.mean(result.variance))

    print(
        json.dumps(
            {
                "model": "st_transformer",
                "source": result.source,
                "uncertainty_method": result.uncertainty_method,
                "mae": mae,
                "baseline_mae": baseline_mae,
                "avg_variance": variance_mean,
                "optimization": result.optimization,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
