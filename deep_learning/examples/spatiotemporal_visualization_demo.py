"""可视化示例：输出预测曲线与不确定性热图。"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from deep_learning.inference.spatiotemporal_inference import SpatioTemporalInference
from deep_learning.models.spatiotemporal import SyntheticSpatioTemporalDataset


def main() -> None:
    out_dir = Path("deep_learning/examples/output")
    out_dir.mkdir(parents=True, exist_ok=True)

    sample = SyntheticSpatioTemporalDataset(seed=77).generate(
        n_nodes=16,
        seq_len=30,
        pred_horizon=8,
        n_features=2,
        noise_std=0.04,
    )

    infer = SpatioTemporalInference()
    pred = infer.predict_batch(
        coords=sample.coords,
        series=sample.series,
        model_type="st_transformer",
        pred_horizon=8,
        uncertainty_method="mc_dropout",
        enable_memory_optimization=True,
        enable_inference_acceleration=True,
    )

    np.save(out_dir / "prediction.npy", pred.mean)
    np.save(out_dir / "variance.npy", pred.variance)
    np.save(out_dir / "targets.npy", sample.targets)

    try:
        import matplotlib.pyplot as plt  # type: ignore

        node_idx = 0
        history = sample.series[node_idx, :, 0]
        future_steps = np.arange(len(history), len(history) + pred.mean.shape[1])
        std = np.sqrt(np.maximum(pred.variance[node_idx], 1e-8))

        plt.figure(figsize=(9, 4))
        plt.plot(np.arange(len(history)), history, label="history", color="#1f77b4")
        plt.plot(future_steps, sample.targets[node_idx], label="target", color="#2ca02c")
        plt.plot(future_steps, pred.mean[node_idx], label="prediction", color="#d62728")
        plt.fill_between(
            future_steps,
            pred.mean[node_idx] - 1.96 * std,
            pred.mean[node_idx] + 1.96 * std,
            color="#d62728",
            alpha=0.2,
            label="95% interval",
        )
        plt.title("Spatiotemporal Forecast")
        plt.legend(loc="best")
        plt.tight_layout()
        plt.savefig(out_dir / "forecast_curve.png", dpi=180)
        plt.close()

        plt.figure(figsize=(8, 4))
        plt.imshow(pred.variance, aspect="auto", cmap="magma")
        plt.colorbar(label="variance")
        plt.xlabel("horizon")
        plt.ylabel("node")
        plt.title("Prediction Variance Heatmap")
        plt.tight_layout()
        plt.savefig(out_dir / "variance_heatmap.png", dpi=180)
        plt.close()

        print(f"可视化已生成: {out_dir}")
    except Exception:
        print(f"matplotlib 不可用，已输出 numpy 文件到: {out_dir}")


if __name__ == "__main__":
    main()
