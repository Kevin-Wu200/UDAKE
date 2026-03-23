"""训练框架模块。"""

from .base_trainer import BaseTrainer, TrainingConfig
from .lightning_trainer import LightningTrainer

__all__ = ["BaseTrainer", "TrainingConfig", "LightningTrainer"]
