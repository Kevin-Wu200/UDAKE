"""阶段7：模型融合与系统集成模块。"""

from .adaptive import AdaptiveFusionSystem
from .common import (
    AdaptiveLearningMode,
    FusionConfig,
    FusionProfile,
    FusionResult,
    FusionStrategy,
    HybridFusionMode,
    ModelMetric,
    ModelPrediction,
    MultiModalStrategy,
    WeightMethod,
)
from .engine import ModelFusionEngine
from .evaluation import FusionEvaluator
from .hybrid import HybridFusionBridge, MultiModalFusion
from .model_management import FusionModelManager
from .service import FusionPlatformService, fusion_platform_service
from .weighting import FusionWeightCalculator

__all__ = [
    "AdaptiveFusionSystem",
    "AdaptiveLearningMode",
    "FusionConfig",
    "FusionEvaluator",
    "FusionModelManager",
    "FusionPlatformService",
    "FusionProfile",
    "FusionResult",
    "FusionStrategy",
    "FusionWeightCalculator",
    "HybridFusionBridge",
    "HybridFusionMode",
    "ModelFusionEngine",
    "ModelMetric",
    "ModelPrediction",
    "MultiModalFusion",
    "MultiModalStrategy",
    "WeightMethod",
    "fusion_platform_service",
]
