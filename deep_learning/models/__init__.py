"""Model management and model domains."""

from .registry import ModelRegistry, ModelVersioning, ModelSerializer, ModelExporter, ModelQuantizer
from .spatial_interpolation import AttentionKrigingModel, GNNKrigingModel, ResidualKrigingModel
from .anomaly_detection import (
    ContrastiveAnomalyDetector,
    GANAnomalyDetector,
    GCAEAnomalyDetector,
    VAEAnomalyDetector,
)
from .uncertainty import (
    BayesianNeuralRegressor,
    DeepEnsembleRegressor,
    EDLClassifier,
    MCDropoutRegressor,
    UQTrainingManager,
    UncertaintyEvaluator,
    UncertaintySystemIntegrator,
)
from .sampling_rl import ActorCriticAgent, DQNAgent, PPOAgent, SamplingRLIntegrator

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
    "BayesianNeuralRegressor",
    "MCDropoutRegressor",
    "DeepEnsembleRegressor",
    "EDLClassifier",
    "UncertaintyEvaluator",
    "UQTrainingManager",
    "UncertaintySystemIntegrator",
    "PPOAgent",
    "DQNAgent",
    "ActorCriticAgent",
    "SamplingRLIntegrator",
]
