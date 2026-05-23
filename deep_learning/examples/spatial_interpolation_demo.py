"""Stage-2 spatial interpolation demo."""

from __future__ import annotations

from deep_learning.inference import SpatialInterpolationInference
from deep_learning.models.spatial_interpolation import GNNKrigingModel
from deep_learning.training import SpatialTrainingConfig, train_spatial_model
from deep_learning.utils.spatial_interpolation_data import SyntheticSpatialDataset

if __name__ == "__main__":
    dataset = SyntheticSpatialDataset(seed=21).generate(n_points=72, noise_std=0.03)
    sample = {
        "coords": dataset["coords"],
        "values": dataset["values"],
        "targets": dataset["targets"],
    }

    model = GNNKrigingModel(hidden_dim=16)
    train_result = train_spatial_model(
        model,
        train_dataset=[sample] * 4,
        val_dataset=[sample] * 2,
        config=SpatialTrainingConfig(max_epochs=20, learning_rate=0.03),
    )

    inference = SpatialInterpolationInference()
    pred = inference.predict_batch(
        sample_coords=dataset["coords"],
        sample_values=dataset["values"],
        query_coords=dataset["coords"],
        model_type="gnn",
    )

    print(
        {
            "training": train_result["training"],
            "prediction_head": pred.mean[:5].tolist(),
            "variance_head": pred.variance[:5].tolist(),
        }
    )
