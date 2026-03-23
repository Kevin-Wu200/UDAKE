"""Training pipeline for spatial interpolation neural models."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any, Callable
import random

import numpy as np

from deep_learning.models.registry import ModelSerializer
from deep_learning.training import LightningTrainer, TrainingConfig


@dataclass
class SpatialTrainingConfig:
    max_epochs: int = 40
    learning_rate: float = 0.03
    early_stopping_patience: int = 6
    optimizer: str = "sgd"
    search_space: dict[str, list[float]] = field(
        default_factory=lambda: {
            "learning_rate": [0.01, 0.03, 0.05],
            "hidden_dim": [12, 16, 24],
        }
    )


class HyperparameterOptimizer:
    """Support grid/random/bayesian-like/optuna search strategies."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def grid_search(self, search_space: dict[str, list[Any]], scorer: Callable[[dict[str, Any]], float]) -> tuple[dict[str, Any], float]:
        keys = list(search_space.keys())
        best_params: dict[str, Any] = {}
        best_score = float("inf")

        for values in product(*[search_space[k] for k in keys]):
            params = {k: v for k, v in zip(keys, values)}
            score = float(scorer(params))
            if score < best_score:
                best_score = score
                best_params = params
        return best_params, best_score

    def random_search(
        self,
        search_space: dict[str, list[Any]],
        scorer: Callable[[dict[str, Any]], float],
        n_trials: int = 12,
    ) -> tuple[dict[str, Any], float]:
        keys = list(search_space.keys())
        best_params: dict[str, Any] = {}
        best_score = float("inf")

        for _ in range(max(1, n_trials)):
            params = {k: self.rng.choice(search_space[k]) for k in keys}
            score = float(scorer(params))
            if score < best_score:
                best_score = score
                best_params = params
        return best_params, best_score

    def bayesian_search(
        self,
        search_space: dict[str, list[Any]],
        scorer: Callable[[dict[str, Any]], float],
        n_trials: int = 10,
    ) -> tuple[dict[str, Any], float]:
        # Lightweight surrogate: weighted random search biased by historical best.
        history: list[tuple[dict[str, Any], float]] = []
        keys = list(search_space.keys())

        for _ in range(max(1, n_trials)):
            if not history:
                params = {k: self.rng.choice(search_space[k]) for k in keys}
            else:
                best = min(history, key=lambda x: x[1])[0]
                params = {}
                for k in keys:
                    candidates = search_space[k]
                    if self.rng.random() < 0.6 and best[k] in candidates:
                        params[k] = best[k]
                    else:
                        params[k] = self.rng.choice(candidates)

            score = float(scorer(params))
            history.append((params, score))

        best_params, best_score = min(history, key=lambda x: x[1])
        return best_params, best_score

    def optuna_search(
        self,
        search_space: dict[str, list[Any]],
        scorer: Callable[[dict[str, Any]], float],
        n_trials: int = 10,
    ) -> tuple[dict[str, Any], float]:
        try:
            import optuna  # type: ignore
        except Exception:
            return self.random_search(search_space=search_space, scorer=scorer, n_trials=n_trials)

        keys = list(search_space.keys())

        def objective(trial: Any) -> float:
            params = {k: trial.suggest_categorical(k, search_space[k]) for k in keys}
            return float(scorer(params))

        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=max(1, n_trials))
        return dict(study.best_params), float(study.best_value)


class ModelSelector:
    """Cross-validation and early-stop based model selection."""

    def cross_validate(
        self,
        model_builder: Callable[[], Any],
        dataset: list[dict[str, Any]],
        folds: int = 3,
        config: TrainingConfig | None = None,
    ) -> dict[str, float]:
        if folds <= 1:
            raise ValueError("folds must be greater than 1")
        if len(dataset) < folds:
            raise ValueError("dataset size must be >= folds")

        fold_size = len(dataset) // folds
        val_losses: list[float] = []

        for i in range(folds):
            start = i * fold_size
            end = len(dataset) if i == folds - 1 else (i + 1) * fold_size
            val = dataset[start:end]
            train = dataset[:start] + dataset[end:]

            model = model_builder()
            trainer = LightningTrainer(config or TrainingConfig(max_epochs=20, learning_rate=0.02, early_stopping_patience=4))
            trainer.train(model, [train], [val])
            val_losses.append(float(trainer.history[-1]["val_loss"]))

        return {
            "cv_mean_val_loss": float(np.mean(val_losses)),
            "cv_std_val_loss": float(np.std(val_losses)),
        }


class TrainingMonitor:
    """Collect and summarize training signals."""

    def __init__(self) -> None:
        self.loss_curve: list[float] = []
        self.val_curve: list[float] = []
        self.grad_curve: list[float] = []
        self.lr_curve: list[float] = []

    def update(self, train_loss: float, val_loss: float, grad_norm: float, lr: float) -> None:
        self.loss_curve.append(float(train_loss))
        self.val_curve.append(float(val_loss))
        self.grad_curve.append(float(grad_norm))
        self.lr_curve.append(float(lr))

    def summary(self) -> dict[str, float]:
        return {
            "best_train_loss": float(np.min(self.loss_curve)) if self.loss_curve else 0.0,
            "best_val_loss": float(np.min(self.val_curve)) if self.val_curve else 0.0,
            "max_grad_norm": float(np.max(self.grad_curve)) if self.grad_curve else 0.0,
            "final_lr": float(self.lr_curve[-1]) if self.lr_curve else 0.0,
        }


class SpatialModelManager:
    """Model save/load helper for spatial interpolation models."""

    def __init__(self) -> None:
        self.serializer = ModelSerializer()

    def save(self, model: Any, path: str) -> None:
        state = model.get_state() if hasattr(model, "get_state") else model.__dict__
        self.serializer.save(state, path)

    def load(self, model: Any, path: str) -> Any:
        state = self.serializer.load(path)
        if hasattr(model, "load_state"):
            model.load_state(state)
        else:
            model.__dict__.update(state)
        return model


def train_spatial_model(
    model: Any,
    train_dataset: list[dict[str, Any]],
    val_dataset: list[dict[str, Any]],
    config: SpatialTrainingConfig | None = None,
) -> dict[str, Any]:
    cfg = config or SpatialTrainingConfig()
    trainer = LightningTrainer(
        TrainingConfig(
            max_epochs=cfg.max_epochs,
            learning_rate=cfg.learning_rate,
            early_stopping_patience=cfg.early_stopping_patience,
            lr_decay=0.95,
            mixed_precision=True,
        )
    )
    result = trainer.train(model, [train_dataset], [val_dataset])
    return {
        "training": result,
        "history": trainer.history,
    }
