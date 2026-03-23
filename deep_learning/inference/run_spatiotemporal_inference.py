"""Stage-6 inference script for spatiotemporal forecasting."""

from __future__ import annotations

import argparse
import json

import numpy as np

from deep_learning.inference.spatiotemporal_inference import SpatioTemporalInference
from deep_learning.models.spatiotemporal import SyntheticSpatioTemporalDataset


def main() -> None:
    parser = argparse.ArgumentParser(description="时空预测推理")
    parser.add_argument("--model", type=str, default="st_transformer", choices=["st_transformer", "gcn_lstm", "convlstm", "stgcn"])
    parser.add_argument("--nodes", type=int, default=16)
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--horizon", type=int, default=6)
    parser.add_argument("--features", type=int, default=2)
    parser.add_argument("--fusion", type=str, default="gating", choices=["concat", "add", "gating"])
    args = parser.parse_args()

    sample = SyntheticSpatioTemporalDataset(seed=7).generate(
        n_nodes=args.nodes,
        seq_len=args.seq_len,
        pred_horizon=args.horizon,
        n_features=args.features,
    )

    inference = SpatioTemporalInference()
    pred = inference.predict_batch(
        coords=sample.coords,
        series=sample.series,
        model_type=args.model,  # type: ignore[arg-type]
        pred_horizon=args.horizon,
        fusion_strategy=args.fusion,
    )

    baseline = np.repeat(sample.series[:, -1, 0:1], args.horizon, axis=1)
    mae = float(np.mean(np.abs(pred.mean - sample.targets)))
    baseline_mae = float(np.mean(np.abs(baseline - sample.targets)))

    payload = {
        "model": args.model,
        "prediction": pred.mean.tolist(),
        "variance": pred.variance.tolist(),
        "source": pred.source,
        "mae": mae,
        "baseline_mae": baseline_mae,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
