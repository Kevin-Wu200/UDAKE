"""Spatial interpolation neural models and supporting components."""

from .attention_kriging import (
    AttentionKrigingModel,
    AttentionKrigingOutput,
    TransformerEncoderBlock,
)
from .baselines import OrdinaryKrigingBaseline, UniversalKrigingBaseline
from .evaluation import (
    MetricResult,
    evaluate_metrics,
    generate_evaluation_report,
    hyperparam_sensitivity,
    prediction_comparison,
)
from .feature_extractors import (
    CovarianceFeatureExtractor,
    SpatialFeatureExtractor,
    TrendFeatureExtractor,
)
from .gnn_kriging import GNNKrigingModel, GNNKrigingOutput
from .graph_builder import GraphData, SpatialGraphBuilder
from .graph_layers import EdgeConvLayer, GATLayer, GCNLayer
from .heads import MultiTaskHead, RegressionHead, UncertaintyHead
from .integration import FusionResult, SpatialInterpolationIntegrator
from .losses import (
    combined_spatial_loss,
    gaussian_nll_loss,
    gradient_smoothness_loss,
    mae_loss,
    mse_loss,
    physical_constraint_loss,
)
from .optimization import (
    BatchOptimizationResult,
    BatchOptimizer,
    ComputeGraphOptimizer,
    GPUAccelerator,
    InferenceAccelerator,
    MemoryOptimizer,
    ModelCompressor,
)
from .position_encoding import (
    LearnablePositionEncoding,
    relative_position_encoding,
    sinusoidal_position_encoding,
)
from .residual_kriging import ResidualKrigingModel, ResidualKrigingOutput

__all__ = [
    "AttentionKrigingModel",
    "AttentionKrigingOutput",
    "TransformerEncoderBlock",
    "OrdinaryKrigingBaseline",
    "UniversalKrigingBaseline",
    "MetricResult",
    "evaluate_metrics",
    "generate_evaluation_report",
    "hyperparam_sensitivity",
    "prediction_comparison",
    "CovarianceFeatureExtractor",
    "SpatialFeatureExtractor",
    "TrendFeatureExtractor",
    "GNNKrigingModel",
    "GNNKrigingOutput",
    "GraphData",
    "SpatialGraphBuilder",
    "EdgeConvLayer",
    "GATLayer",
    "GCNLayer",
    "MultiTaskHead",
    "RegressionHead",
    "UncertaintyHead",
    "FusionResult",
    "SpatialInterpolationIntegrator",
    "combined_spatial_loss",
    "gaussian_nll_loss",
    "gradient_smoothness_loss",
    "mae_loss",
    "mse_loss",
    "physical_constraint_loss",
    "BatchOptimizationResult",
    "BatchOptimizer",
    "ComputeGraphOptimizer",
    "GPUAccelerator",
    "InferenceAccelerator",
    "MemoryOptimizer",
    "ModelCompressor",
    "LearnablePositionEncoding",
    "relative_position_encoding",
    "sinusoidal_position_encoding",
    "ResidualKrigingModel",
    "ResidualKrigingOutput",
]
