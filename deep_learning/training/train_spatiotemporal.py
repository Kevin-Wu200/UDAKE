"""Stage-6 training script for spatiotemporal forecasting models."""

from __future__ import annotations

import argparse
import json

import numpy as np

from deep_learning.models.spatiotemporal import (
    SlidingWindowDataLoader,
    SpatioTemporalSystemIntegrator,
    SpatioTemporalTrainingConfig,
    SyntheticSpatioTemporalDataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="时空预测模型训练")
    parser.add_argument("--model", type=str, default="st_transformer", choices=["st_transformer", "gcn_lstm", "convlstm", "stgcn"])
    parser.add_argument("--nodes", type=int, default=20)
    parser.add_argument("--steps", type=int, default=96)
    parser.add_argument("--features", type=int, default=2)
    parser.add_argument("--seq-len", type=int, default=24)
    parser.add_argument("--horizon", type=int, default=6)
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()

    seed_dataset = SyntheticSpatioTemporalDataset(seed=42).generate(
        n_nodes=args.nodes,
        seq_len=args.steps - args.horizon,
        pred_horizon=args.horizon,
        n_features=args.features,
        noise_std=0.04,
    )

    # Build long-series for sliding windows by stitching input and target.
    long_series = seed_dataset.series
    target = np.repeat(seed_dataset.targets[:, :, None], long_series.shape[2], axis=2)
    long_series = np.concatenate([long_series, target], axis=1)

    loader = SlidingWindowDataLoader(
        coords=seed_dataset.coords,
        long_series=long_series,
        seq_len=args.seq_len,
        pred_horizon=args.horizon,
        batch_size=16,
        shuffle=True,
    )
    train_set, val_set, _ = loader.split(train_ratio=0.7, val_ratio=0.2)

    train_dataset = [
        {
            "coords": item.coords,
            "series": item.series,
            "targets": item.targets,
            "adjacency": item.adjacency,
        }
        for item in train_set
    ]
    val_dataset = [
        {
            "coords": item.coords,
            "series": item.series,
            "targets": item.targets,
            "adjacency": item.adjacency,
        }
        for item in val_set
    ]

    integrator = SpatioTemporalSystemIntegrator(cache_ttl_seconds=30)
    result = integrator.train(
        model_type=args.model,  # type: ignore[arg-type]
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        config=SpatioTemporalTrainingConfig(
            seq_len=args.seq_len,
            pred_horizon=args.horizon,
            max_epochs=args.epochs,
            learning_rate=0.02,
            warmup_epochs=3,
            early_stopping_patience=5,
            gradient_clip_norm=1.0,
        ),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
