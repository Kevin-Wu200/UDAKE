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
from .features import (
    BNN_FEATURE_KEYS,
    DEEP_ENSEMBLE_FEATURE_KEYS,
    EDL_FEATURE_KEYS,
    MC_DROPOUT_FEATURE_KEYS,
    ModelType,
    UncertaintyFeatureSpec,
    decompose_uncertainty_sources,
    extract_model_features,
    feature_name_mapping,
    model_feature_keys,
    uncertainty_feature_registry,
)
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
    "ModelType",
    "UncertaintyFeatureSpec",
    "BNN_FEATURE_KEYS",
    "MC_DROPOUT_FEATURE_KEYS",
    "DEEP_ENSEMBLE_FEATURE_KEYS",
    "EDL_FEATURE_KEYS",
    "uncertainty_feature_registry",
    "feature_name_mapping",
    "model_feature_keys",
    "extract_model_features",
    "decompose_uncertainty_sources",
    "UncertaintyDataset",
    "UncertaintyDatasetBuilder",
    "UQTrainingConfig",
    "UQTrainingManager",
    "IntegratedUQResult",
    "UncertaintySystemIntegrator",
]
