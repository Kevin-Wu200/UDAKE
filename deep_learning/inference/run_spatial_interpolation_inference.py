"""Inference demo script for stage-2 spatial interpolation models."""

from __future__ import annotations

import argparse

from deep_learning.inference.spatial_interpolation_inference import SpatialInterpolationInference
from deep_learning.models.spatial_interpolation.evaluation import evaluate_metrics
from deep_learning.utils.spatial_interpolation_data import SyntheticSpatialDataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Run spatial interpolation inference")
    parser.add_argument("--model", choices=["gnn", "attention", "residual"], default="gnn")
    parser.add_argument("--grid-size", type=int, default=16)
    args = parser.parse_args()

    data = SyntheticSpatialDataset(seed=9).generate(n_points=80, noise_std=0.02)
    inference = SpatialInterpolationInference()

    batch_result = inference.predict_batch(
        sample_coords=data["coords"],
        sample_values=data["values"],
        query_coords=data["coords"],
        model_type=args.model,
    )

    metrics = evaluate_metrics(data["targets"], batch_result.mean, batch_result.variance)
    mesh_x, mesh_y, grid_pred = inference.predict_grid(
        sample_coords=data["coords"],
        sample_values=data["values"],
        x_bounds=(0.0, 1.0),
        y_bounds=(0.0, 1.0),
        grid_size=args.grid_size,
        model_type=args.model,
    )

    print(
        {
            "model": args.model,
            "metrics": metrics.__dict__,
            "grid_shape": list(grid_pred.shape),
            "x_span": [float(mesh_x.min()), float(mesh_x.max())],
            "y_span": [float(mesh_y.min()), float(mesh_y.max())],
        }
    )


if __name__ == "__main__":
    main()
