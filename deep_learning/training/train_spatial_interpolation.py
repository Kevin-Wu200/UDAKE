"""Training script for stage-2 spatial interpolation neural models."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from deep_learning.models.spatial_interpolation import AttentionKrigingModel, GNNKrigingModel, ResidualKrigingModel
from deep_learning.training.spatial_interpolation_trainer import (
    HyperparameterOptimizer,
    ModelSelector,
    SpatialModelManager,
    SpatialTrainingConfig,
    train_spatial_model,
)
from deep_learning.utils.spatial_interpolation_data import SyntheticSpatialDataset


def _build_model(model_type: str, hidden_dim: int = 16):
    if model_type == "gnn":
        return GNNKrigingModel(hidden_dim=hidden_dim)
    if model_type == "attention":
        return AttentionKrigingModel(dim=max(16, hidden_dim))
    if model_type == "residual":
        return ResidualKrigingModel(architecture="hybrid")
    raise ValueError(f"unsupported model_type: {model_type}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train spatial interpolation model")
    parser.add_argument("--model", choices=["gnn", "attention", "residual"], default="gnn")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--save", type=str, default="deep_learning/models/repository/spatial_interpolation/stage2.pkl")
    args = parser.parse_args()

    data = SyntheticSpatialDataset(seed=7).generate(n_points=96, noise_std=0.03)
    sample = {
        "coords": data["coords"],
        "values": data["values"],
        "targets": data["targets"],
    }

    dataset = [sample for _ in range(6)]
    train_set = dataset[:4]
    val_set = dataset[4:]

    search = HyperparameterOptimizer(seed=7)

    def scorer(params):
        model = _build_model(args.model, hidden_dim=int(params.get("hidden_dim", 16)))
        cfg = SpatialTrainingConfig(
            max_epochs=max(10, min(args.epochs, 40)),
            learning_rate=float(params.get("learning_rate", 0.03)),
            early_stopping_patience=5,
        )
        result = train_spatial_model(model, train_set, val_set, config=cfg)
        return float(result["training"]["best_val_loss"])

    best_params, best_score = search.bayesian_search(
        search_space={"learning_rate": [0.01, 0.03, 0.05], "hidden_dim": [12, 16, 20]},
        scorer=scorer,
        n_trials=8,
    )

    model = _build_model(args.model, hidden_dim=int(best_params.get("hidden_dim", 16)))
    train_result = train_spatial_model(
        model,
        train_set,
        val_set,
        config=SpatialTrainingConfig(
            max_epochs=args.epochs,
            learning_rate=float(best_params.get("learning_rate", 0.03)),
            early_stopping_patience=5,
        ),
    )

    selector = ModelSelector()
    cv = selector.cross_validate(lambda: _build_model(args.model, hidden_dim=int(best_params.get("hidden_dim", 16))), dataset, folds=3)

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    SpatialModelManager().save(model, str(save_path))

    print(
        {
            "model": args.model,
            "best_hparams": best_params,
            "hparam_score": best_score,
            "training": train_result["training"],
            "cross_validation": cv,
            "saved_to": str(save_path),
        }
    )


if __name__ == "__main__":
    main()
