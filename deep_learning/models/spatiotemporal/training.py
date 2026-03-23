"""Training utilities for spatiotemporal forecasting models."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any, Callable
import random

import numpy as np

from deep_learning.models.registry import ModelSerializer


@dataclass
class SpatioTemporalTrainingConfig:
    seq_len: int = 24
    pred_horizon: int = 6
    max_epochs: int = 40
    learning_rate: float = 0.02
    warmup_epochs: int = 4
    early_stopping_patience: int = 6
    gradient_clip_norm: float = 1.0
    search_space: dict[str, list[float]] = field(
        default_factory=lambda: {
            "learning_rate": [0.01, 0.02, 0.03],
            "dim": [16, 24, 32],
            "num_heads": [2, 4],
        }
    )


class SpatioTemporalTrainingMonitor:
    def __init__(self) -> None:
        self.train_curve: list[float] = []
        self.val_curve: list[float] = []
        self.lr_curve: list[float] = []

    def update(self, train_loss: float, val_loss: float, lr: float) -> None:
        self.train_curve.append(float(train_loss))
        self.val_curve.append(float(val_loss))
        self.lr_curve.append(float(lr))

    def summary(self) -> dict[str, float]:
        return {
            "best_train_loss": float(np.min(self.train_curve)) if self.train_curve else 0.0,
            "best_val_loss": float(np.min(self.val_curve)) if self.val_curve else 0.0,
            "final_lr": float(self.lr_curve[-1]) if self.lr_curve else 0.0,
        }


class SpatioTemporalHyperparameterOptimizer:
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
        n_trials: int = 8,
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


class SpatioTemporalModelManager:
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


def cosine_with_warmup(base_lr: float, epoch: int, total_epochs: int, warmup_epochs: int) -> float:
    base = float(base_lr)
    if epoch < warmup_epochs:
        return base * float(epoch + 1) / float(max(1, warmup_epochs))
    progress = (epoch - warmup_epochs) / float(max(1, total_epochs - warmup_epochs))
    return base * 0.5 * (1.0 + np.cos(np.pi * progress))


def train_spatiotemporal_model(
    model: Any,
    train_dataset: list[dict[str, np.ndarray]],
    val_dataset: list[dict[str, np.ndarray]],
    config: SpatioTemporalTrainingConfig | None = None,
) -> dict[str, Any]:
    cfg = config or SpatioTemporalTrainingConfig()
    monitor = SpatioTemporalTrainingMonitor()

    best_val = float("inf")
    best_epoch = -1
    wait = 0
    history: list[dict[str, float]] = []

    for epoch in range(cfg.max_epochs):
        lr = cosine_with_warmup(cfg.learning_rate, epoch, cfg.max_epochs, cfg.warmup_epochs)

        # Gradient clipping proxy: cap effective LR when loss is high.
        train_loss = float(model.train_step(train_dataset, lr=lr, mixed_precision=True))
        effective_lr = lr / max(1.0, train_loss / max(cfg.gradient_clip_norm, 1e-6))

        val_loss = float(model.val_step(val_dataset))
        monitor.update(train_loss=train_loss, val_loss=val_loss, lr=effective_lr)
        history.append({"epoch": float(epoch), "train_loss": train_loss, "val_loss": val_loss, "lr": effective_lr})

        if val_loss < best_val:
            best_val = val_loss
            best_epoch = epoch
            wait = 0
        else:
            wait += 1

        if wait >= cfg.early_stopping_patience:
            break

    return {
        "training": {
            "best_val_loss": float(best_val),
            "best_epoch": int(best_epoch),
            "epochs_ran": int(len(history)),
            "config": cfg.__dict__,
        },
        "history": history,
        "monitor": monitor.summary(),
    }
