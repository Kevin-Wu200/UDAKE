"""强化学习采样奖励模块。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class RewardWeights:
    """奖励权重配置。"""

    uncertainty_reduction: float = 0.40
    accuracy_improvement: float = 0.25
    spatial_coverage: float = 0.20
    sampling_cost: float = 0.08
    boundary_constraint: float = 0.04
    distance_constraint: float = 0.03


class RewardNormalizer:
    """奖励归一化器，支持在线更新。"""

    def __init__(self, momentum: float = 0.95, eps: float = 1e-6) -> None:
        self.momentum = float(np.clip(momentum, 0.0, 0.999))
        self.eps = float(max(eps, 1e-12))
        self.mean = 0.0
        self.var = 1.0
        self.ready = False

    def update(self, value: float) -> float:
        x = float(value)
        if not self.ready:
            self.mean = x
            self.var = 1.0
            self.ready = True
            return 0.0

        self.mean = self.momentum * self.mean + (1.0 - self.momentum) * x
        delta = x - self.mean
        self.var = self.momentum * self.var + (1.0 - self.momentum) * (delta * delta)
        return float((x - self.mean) / (np.sqrt(self.var) + self.eps))


class RewardDebugger:
    """奖励调试器：记录每步奖励组件并输出统计摘要。"""

    def __init__(self) -> None:
        self.records: list[dict[str, float]] = []

    def log(self, components: dict[str, float]) -> None:
        payload = {k: float(v) for k, v in components.items()}
        self.records.append(payload)

    def summary(self) -> dict[str, float]:
        if not self.records:
            return {
                "steps": 0.0,
                "mean_total_reward": 0.0,
                "std_total_reward": 0.0,
            }

        totals = np.asarray([item.get("total_reward", 0.0) for item in self.records], dtype=float)
        return {
            "steps": float(len(self.records)),
            "mean_total_reward": float(np.mean(totals)),
            "std_total_reward": float(np.std(totals)),
            "mean_uncertainty_reduction": float(np.mean([x.get("uncertainty_reduction", 0.0) for x in self.records])),
            "mean_accuracy_improvement": float(np.mean([x.get("accuracy_improvement", 0.0) for x in self.records])),
            "mean_spatial_coverage": float(np.mean([x.get("spatial_coverage", 0.0) for x in self.records])),
            "mean_sampling_cost_penalty": float(np.mean([x.get("sampling_cost_penalty", 0.0) for x in self.records])),
            "mean_boundary_penalty": float(np.mean([x.get("boundary_penalty", 0.0) for x in self.records])),
            "mean_distance_penalty": float(np.mean([x.get("distance_penalty", 0.0) for x in self.records])),
        }


class MultiObjectiveReward:
    """多目标奖励工具：加权和、帕累托前沿、奖励塑形。"""

    def weighted_sum(self, objectives: dict[str, float], weights: dict[str, float]) -> float:
        total = 0.0
        for key, value in objectives.items():
            total += float(weights.get(key, 0.0)) * float(value)
        return float(total)

    def pareto_front(self, objective_vectors: list[dict[str, float]]) -> list[dict[str, float]]:
        """返回非支配解集合。"""
        if not objective_vectors:
            return []

        keys = list(objective_vectors[0].keys())
        arr = np.asarray([[float(vec[k]) for k in keys] for vec in objective_vectors], dtype=float)

        front_indices: list[int] = []
        for i in range(len(arr)):
            dominated = False
            for j in range(len(arr)):
                if i == j:
                    continue
                better_or_equal = np.all(arr[j] >= arr[i])
                strictly_better = np.any(arr[j] > arr[i])
                if better_or_equal and strictly_better:
                    dominated = True
                    break
            if not dominated:
                front_indices.append(i)

        return [objective_vectors[i] for i in front_indices]

    def shape_reward(self, reward: float, potential_prev: float, potential_now: float, gamma: float = 0.99) -> float:
        return float(reward + gamma * potential_now - potential_prev)


def boundary_constraint_penalty(is_outside: bool, magnitude: float = 1.0) -> float:
    return float(magnitude if is_outside else 0.0)


def distance_constraint_penalty(min_distance_ok: bool, magnitude: float = 1.0) -> float:
    return float(0.0 if min_distance_ok else magnitude)


def budget_constraint_penalty(remaining_budget: int, required_budget: int = 1) -> float:
    return float(max(0, required_budget - remaining_budget))


@dataclass
class RewardComposer:
    """综合奖励函数。"""

    weights: RewardWeights = field(default_factory=RewardWeights)
    normalizer: RewardNormalizer | None = None

    def compose(
        self,
        uncertainty_reduction: float,
        accuracy_improvement: float,
        spatial_coverage: float,
        sampling_cost_penalty: float,
        boundary_penalty: float,
        distance_penalty: float,
    ) -> dict[str, float]:
        raw_total = (
            self.weights.uncertainty_reduction * float(uncertainty_reduction)
            + self.weights.accuracy_improvement * float(accuracy_improvement)
            + self.weights.spatial_coverage * float(spatial_coverage)
            - self.weights.sampling_cost * float(sampling_cost_penalty)
            - self.weights.boundary_constraint * float(boundary_penalty)
            - self.weights.distance_constraint * float(distance_penalty)
        )

        normalized_total = self.normalizer.update(raw_total) if self.normalizer is not None else raw_total

        return {
            "uncertainty_reduction": float(uncertainty_reduction),
            "accuracy_improvement": float(accuracy_improvement),
            "spatial_coverage": float(spatial_coverage),
            "sampling_cost_penalty": float(sampling_cost_penalty),
            "boundary_penalty": float(boundary_penalty),
            "distance_penalty": float(distance_penalty),
            "raw_total_reward": float(raw_total),
            "total_reward": float(normalized_total),
        }


def reward_to_debug_row(components: dict[str, Any]) -> dict[str, float]:
    return {k: float(v) for k, v in components.items() if np.isscalar(v)}
