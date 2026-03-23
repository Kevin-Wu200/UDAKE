"""Model management and model domains."""

from .registry import ModelRegistry, ModelVersioning, ModelSerializer, ModelExporter, ModelQuantizer
from .spatial_interpolation import AttentionKrigingModel, GNNKrigingModel, ResidualKrigingModel
from .anomaly_detection import (
    ContrastiveAnomalyDetector,
    GANAnomalyDetector,
    GCAEAnomalyDetector,
    VAEAnomalyDetector,
)

__all__ = [
    "ModelRegistry",
    "ModelVersioning",
    "ModelSerializer",
    "ModelExporter",
    "ModelQuantizer",
    "GNNKrigingModel",
    "AttentionKrigingModel",
    "ResidualKrigingModel",
    "VAEAnomalyDetector",
    "GCAEAnomalyDetector",
    "GANAnomalyDetector",
    "ContrastiveAnomalyDetector",
]
