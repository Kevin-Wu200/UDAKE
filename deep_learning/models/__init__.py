"""Model management and model domains."""

from __future__ import annotations

from typing import Any

_SYMBOL_MODULES: dict[str, str] = {
    "ModelRegistry": ".registry",
    "ModelVersioning": ".registry",
    "ModelSerializer": ".registry",
    "ModelExporter": ".registry",
    "ModelQuantizer": ".registry",
    "GNNKrigingModel": ".spatial_interpolation",
    "AttentionKrigingModel": ".spatial_interpolation",
    "ResidualKrigingModel": ".spatial_interpolation",
    "VAEAnomalyDetector": ".anomaly_detection",
    "GCAEAnomalyDetector": ".anomaly_detection",
    "GANAnomalyDetector": ".anomaly_detection",
    "ContrastiveAnomalyDetector": ".anomaly_detection",
    "BayesianNeuralRegressor": ".uncertainty",
    "MCDropoutRegressor": ".uncertainty",
    "DeepEnsembleRegressor": ".uncertainty",
    "EDLClassifier": ".uncertainty",
    "UncertaintyEvaluator": ".uncertainty",
    "UQTrainingManager": ".uncertainty",
    "UncertaintySystemIntegrator": ".uncertainty",
    "PPOAgent": ".sampling_rl",
    "DQNAgent": ".sampling_rl",
    "ActorCriticAgent": ".sampling_rl",
    "SamplingRLIntegrator": ".sampling_rl",
    "SpatioTemporalTransformer": ".spatiotemporal",
    "GCNLSTMModel": ".spatiotemporal",
    "ConvLSTMModel": ".spatiotemporal",
    "STGCNModel": ".spatiotemporal",
    "SpatioTemporalSystemIntegrator": ".spatiotemporal",
}

__all__ = sorted(_SYMBOL_MODULES.keys())


def __getattr__(name: str) -> Any:
    if name not in _SYMBOL_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = __import__(f"{__name__}{_SYMBOL_MODULES[name]}", fromlist=[name])
    return getattr(module, name)
