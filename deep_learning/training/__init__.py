"""Training framework module."""

from deep_learning.models.spatiotemporal.training import (
    SpatioTemporalHyperparameterOptimizer,
    SpatioTemporalModelManager,
    SpatioTemporalTrainingConfig,
    SpatioTemporalTrainingMonitor,
    cosine_with_warmup,
    train_spatiotemporal_model,
)

from .base_trainer import BaseTrainer, TrainingConfig
from .lightning_trainer import LightningTrainer
from .spatial_interpolation_trainer import (
    HyperparameterOptimizer,
    ModelSelector,
    SpatialModelManager,
    SpatialTrainingConfig,
    TrainingMonitor,
    train_spatial_model,
)

__all__ = [
    "BaseTrainer",
    "TrainingConfig",
    "LightningTrainer",
    "HyperparameterOptimizer",
    "ModelSelector",
    "SpatialModelManager",
    "SpatialTrainingConfig",
    "TrainingMonitor",
    "train_spatial_model",
    "SpatioTemporalHyperparameterOptimizer",
    "SpatioTemporalModelManager",
    "SpatioTemporalTrainingConfig",
    "SpatioTemporalTrainingMonitor",
    "cosine_with_warmup",
    "train_spatiotemporal_model",
]
