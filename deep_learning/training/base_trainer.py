"""训练器基类定义。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class TrainingConfig:
    max_epochs: int = 20
    learning_rate: float = 1e-3
    early_stopping_patience: int = 5
    gradient_clip_norm: float = 1.0
    mixed_precision: bool = False
    use_distributed: bool = False
    lr_decay: float = 1.0


class BaseTrainer(ABC):
    def __init__(self, config: TrainingConfig | None = None) -> None:
        self.config = config or TrainingConfig()
        self.history: list[dict[str, float]] = []

    @abstractmethod
    def train(self, model: Any, train_loader: Any, val_loader: Any | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_checkpoint(self, model: Any, path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_checkpoint(self, model: Any, path: str) -> Any:
        raise NotImplementedError
