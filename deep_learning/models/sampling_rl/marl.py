"""多智能体强化学习采样模块（MARL）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np


@dataclass
class AgentMessage:
    agent_id: int
    local_uncertainty: float
    suggested_action: int


class MultiAgentSamplingSystem:
    """支持协作/竞争采样策略与 QMIX/MADDPG 轻量实现。"""

    def __init__(self, n_agents: int = 3, seed: int = 42) -> None:
        self.n_agents = int(max(2, n_agents))
        self.rng = np.random.default_rng(seed)

    def communicate(self, uncertainty_map: np.ndarray, candidate_actions: list[int]) -> list[AgentMessage]:
        flat = np.asarray(uncertainty_map, dtype=float).reshape(-1)
        if len(flat) == 0:
            return []

        messages: list[AgentMessage] = []
        for i in range(self.n_agents):
            action = int(candidate_actions[i % len(candidate_actions)])
            action = int(np.clip(action, 0, len(flat) - 1))
            messages.append(
                AgentMessage(
                    agent_id=i,
                    local_uncertainty=float(flat[action]),
                    suggested_action=action,
                )
            )
        return messages

    def cooperative_strategy(self, uncertainty_map: np.ndarray, top_k: int = 6) -> list[int]:
        flat = np.asarray(uncertainty_map, dtype=float).reshape(-1)
        if len(flat) == 0:
            return []
        k = int(max(self.n_agents, top_k))
        best = np.argsort(flat)[-k:][::-1]
        return [int(x) for x in best[: self.n_agents]]

    def competitive_strategy(self, uncertainty_map: np.ndarray) -> list[int]:
        flat = np.asarray(uncertainty_map, dtype=float).reshape(-1)
        if len(flat) == 0:
            return []

        actions: list[int] = []
        for i in range(self.n_agents):
            noise = self.rng.normal(0.0, 0.02, size=len(flat))
            score = flat + noise
            actions.append(int(np.argmax(score)))
            # 竞争模式下避免动作完全重合
            flat[actions[-1]] *= 0.9
        return actions

    def qmix(self, agent_q_values: np.ndarray, state_features: np.ndarray) -> dict[str, Any]:
        """QMIX：将 agent Q 混合为全局 Q。"""
        q = np.asarray(agent_q_values, dtype=float)
        state = np.asarray(state_features, dtype=float).reshape(-1)

        if q.ndim != 2:
            raise ValueError("agent_q_values 需要形状 [n_agents, action_dim]")

        state_scale = float(np.tanh(np.mean(state)) if len(state) > 0 else 0.0)
        weights = np.exp(np.linspace(0.0, 1.0 + state_scale, q.shape[0]))
        weights = weights / (np.sum(weights) + 1e-12)

        mixed_q = np.sum(weights[:, None] * q, axis=0)
        best_action = int(np.argmax(mixed_q))
        return {
            "mixed_q": mixed_q,
            "best_action": best_action,
            "mixing_weights": weights,
        }

    def maddpg(
        self,
        actor_actions: np.ndarray,
        critic_gradients: np.ndarray,
        lr: float = 0.03,
    ) -> dict[str, Any]:
        """MADDPG：连续动作近似更新（轻量）。"""
        actions = np.asarray(actor_actions, dtype=float)
        grads = np.asarray(critic_gradients, dtype=float)

        if actions.shape != grads.shape:
            raise ValueError("actor_actions 与 critic_gradients 形状需一致")

        updated = actions + float(lr) * grads
        updated = np.clip(updated, 0.0, 1.0)
        return {
            "updated_actions": updated,
            "mean_action": float(np.mean(updated)),
            "mean_gradient": float(np.mean(grads)),
        }

    def train_step(
        self,
        mode: Literal["qmix", "maddpg"],
        uncertainty_map: np.ndarray,
        state_features: np.ndarray,
    ) -> dict[str, Any]:
        if mode == "qmix":
            action_dim = max(8, uncertainty_map.size)
            q_values = self.rng.normal(0.0, 1.0, size=(self.n_agents, action_dim))
            result = self.qmix(q_values, state_features)
            result["mode"] = "qmix"
            return result

        actions = self.rng.uniform(0.0, 1.0, size=(self.n_agents, 2))
        gradients = self.rng.normal(0.0, 0.1, size=(self.n_agents, 2))
        result = self.maddpg(actions, gradients, lr=0.05)
        result["mode"] = "maddpg"
        return result
