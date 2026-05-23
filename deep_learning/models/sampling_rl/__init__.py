"""阶段5：强化学习采样优化模块。"""

from .agents import (
    A2CConfig,
    ActorCriticAgent,
    DQNAgent,
    DQNConfig,
    PPOAgent,
    PPOConfig,
    PrioritizedReplayBuffer,
    flatten_observation,
    load_agent,
    save_agent,
)
from .env import ActionSpace, BaseEnv, SamplingEnv, register_to_gymnasium
from .evaluation import EvaluationMetrics, SamplingRLEvaluator
from .features import (
    RewardDecomposition,
    SamplingFeatureEngineer,
    StateActionFeatureBundle,
    TopologyFeatures,
)
from .integration import SamplingRecommendation, SamplingRLIntegrator
from .marl import AgentMessage, MultiAgentSamplingSystem
from .online import (
    AdaptiveStrategyController,
    OnlineSamplingLearner,
    OnlineUpdateResult,
    TransferMetaLearner,
)
from .optimization import (
    BatchOptimizationResult,
    BatchOptimizer,
    GPUAccelerator,
    InferenceAccelerator,
    MemoryOptimizer,
    ParallelSampler,
)
from .rewards import (
    MultiObjectiveReward,
    RewardComposer,
    RewardDebugger,
    RewardNormalizer,
    RewardWeights,
    boundary_constraint_penalty,
    budget_constraint_penalty,
    distance_constraint_penalty,
)
from .training import (
    DistributedTrainer,
    HyperparameterOptimizer,
    ModelSelector,
    SamplingRLTrainingConfig,
    TrainingMonitor,
    train_agent,
)

__all__ = [
    "A2CConfig",
    "ActorCriticAgent",
    "DQNAgent",
    "DQNConfig",
    "PPOAgent",
    "PPOConfig",
    "PrioritizedReplayBuffer",
    "flatten_observation",
    "save_agent",
    "load_agent",
    "ActionSpace",
    "BaseEnv",
    "SamplingEnv",
    "register_to_gymnasium",
    "EvaluationMetrics",
    "SamplingRLEvaluator",
    "SamplingFeatureEngineer",
    "TopologyFeatures",
    "StateActionFeatureBundle",
    "RewardDecomposition",
    "SamplingRLIntegrator",
    "SamplingRecommendation",
    "AgentMessage",
    "MultiAgentSamplingSystem",
    "AdaptiveStrategyController",
    "OnlineSamplingLearner",
    "OnlineUpdateResult",
    "TransferMetaLearner",
    "BatchOptimizationResult",
    "BatchOptimizer",
    "GPUAccelerator",
    "InferenceAccelerator",
    "MemoryOptimizer",
    "ParallelSampler",
    "MultiObjectiveReward",
    "RewardComposer",
    "RewardDebugger",
    "RewardNormalizer",
    "RewardWeights",
    "boundary_constraint_penalty",
    "budget_constraint_penalty",
    "distance_constraint_penalty",
    "DistributedTrainer",
    "HyperparameterOptimizer",
    "ModelSelector",
    "SamplingRLTrainingConfig",
    "TrainingMonitor",
    "train_agent",
]
