"""阶段4不确定性量化模块。"""

from .aggregation import AggregationResult, UncertaintyAggregator
from .bnn import (
    BayesianConvLayer,
    BayesianDenseLayer,
    BayesianNeuralRegressor,
    ELBOLoss,
    GaussianMixturePrior,
    GaussianPrior,
)
from .calibration import IsotonicModel, PlattModel, UncertaintyCalibrator
from .common import ActivationType, DropoutType, PredictiveMoments
from .data_pipeline import UncertaintyDataset, UncertaintyDatasetBuilder
from .deep_ensemble import DeepEnsembleRegressor, EnsembleMemberMetadata
from .edl import EDLClassifier, EDLConfig
from .evaluation import UQMetricResult, UncertaintyEvaluator
from .integration import IntegratedUQResult, UncertaintySystemIntegrator
from .mc_dropout import DropoutLayer, MCDropoutConfig, MCDropoutRegressor
from .training_pipeline import UQTrainingConfig, UQTrainingManager

__all__ = [
    "ActivationType",
    "DropoutType",
    "PredictiveMoments",
    "GaussianPrior",
    "GaussianMixturePrior",
    "BayesianDenseLayer",
    "BayesianConvLayer",
    "ELBOLoss",
    "BayesianNeuralRegressor",
    "MCDropoutConfig",
    "DropoutLayer",
    "MCDropoutRegressor",
    "DeepEnsembleRegressor",
    "EnsembleMemberMetadata",
    "EDLConfig",
    "EDLClassifier",
    "AggregationResult",
    "UncertaintyAggregator",
    "IsotonicModel",
    "PlattModel",
    "UncertaintyCalibrator",
    "UQMetricResult",
    "UncertaintyEvaluator",
    "UncertaintyDataset",
    "UncertaintyDatasetBuilder",
    "UQTrainingConfig",
    "UQTrainingManager",
    "IntegratedUQResult",
    "UncertaintySystemIntegrator",
]
