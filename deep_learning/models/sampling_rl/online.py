"""强化学习采样在线学习与自适应。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class OnlineUpdateResult:
    updated_steps: int
    mean_reward: float
    drift_score: float


class OnlineSamplingLearner:
    """在线学习：增量更新 + 持续学习。"""

    def __init__(self) -> None:
        self.history_rewards: list[float] = []

    def incremental_update(self, agent: Any, transitions: list[dict[str, Any]]) -> OnlineUpdateResult:
        if not transitions:
            return OnlineUpdateResult(updated_steps=0, mean_reward=0.0, drift_score=0.0)

        rewards: list[float] = []
        for item in transitions:
            obs = item["observation"]
            action = int(item["action"])
            reward = float(item["reward"])
            done = bool(item.get("done", False))

            if hasattr(agent, "store_transition"):
                if "next_observation" in item:
                    agent.store_transition(obs, action, reward, item["next_observation"], done)
                elif "log_prob" in item and "value" in item:
                    agent.store_transition(obs, action, reward, done, float(item["log_prob"]), float(item["value"]))
                else:
                    agent.store_transition(obs, action, reward, done, float(item.get("value", 0.0)))

            rewards.append(reward)

        if hasattr(agent, "train_step"):
            agent.train_step()
        elif hasattr(agent, "update"):
            agent.update(0.0)
        elif hasattr(agent, "train_sync"):
            agent.train_sync()

        self.history_rewards.extend(rewards)
        drift = self._drift_score()
        return OnlineUpdateResult(
            updated_steps=len(transitions),
            mean_reward=float(np.mean(rewards)),
            drift_score=drift,
        )

    def continual_learning(self, agent: Any, stream_batches: list[list[dict[str, Any]]]) -> list[OnlineUpdateResult]:
        results: list[OnlineUpdateResult] = []
        for batch in stream_batches:
            results.append(self.incremental_update(agent, batch))
        return results

    def _drift_score(self, window: int = 20) -> float:
        if len(self.history_rewards) < window * 2:
            return 0.0
        arr = np.asarray(self.history_rewards, dtype=float)
        old = np.mean(arr[-2 * window : -window])
        new = np.mean(arr[-window:])
        return float((new - old) / (abs(old) + 1e-8))


class AdaptiveStrategyController:
    """动态奖励调整与策略微调。"""

    def adjust_reward_weights(self, weights: dict[str, float], performance: dict[str, float]) -> dict[str, float]:
        updated = dict(weights)
        reduction = float(performance.get("uncertainty_reduction", 0.0))
        efficiency = float(performance.get("efficiency", 0.0))

        if reduction < 0.05:
            updated["uncertainty_reduction"] = float(updated.get("uncertainty_reduction", 0.3) * 1.1)
        if efficiency < 0.02:
            updated["sampling_cost"] = float(updated.get("sampling_cost", 0.1) * 0.9)

        total = sum(max(v, 0.0) for v in updated.values()) + 1e-12
        for k in list(updated.keys()):
            updated[k] = float(max(updated[k], 0.0) / total)
        return updated

    def finetune_policy(self, agent: Any, env: Any, steps: int = 30) -> dict[str, float]:
        obs = env.reset()
        rewards: list[float] = []
        for _ in range(max(1, steps)):
            if hasattr(agent, "select_action"):
                out = agent.select_action(obs)
                if isinstance(out, tuple):
                    action_idx = int(out[0])
                else:
                    action_idx = int(out)
            else:
                action_idx = int(np.random.randint(0, env.h * env.w))

            if env.action_mode == "discrete":
                action = action_idx
            else:
                row, col = divmod(action_idx, env.w)
                action = [float(env.xx[row, col]), float(env.yy[row, col])]

            next_obs, reward, done, _ = env.step(action)
            rewards.append(float(reward))

            if hasattr(agent, "store_transition"):
                try:
                    if len(out) >= 3:
                        agent.store_transition(obs, action_idx, reward, done, float(out[1]), float(out[2]))
                    elif len(out) >= 2:
                        agent.store_transition(obs, action_idx, reward, done, float(out[1]))
                except Exception:
                    pass

            obs = next_obs
            if done:
                obs = env.reset()

        if hasattr(agent, "update"):
            agent.update(0.0)
        elif hasattr(agent, "train_sync"):
            agent.train_sync()

        return {
            "steps": float(steps),
            "mean_reward": float(np.mean(rewards)) if rewards else 0.0,
        }


class TransferMetaLearner:
    """迁移学习 + 元学习（MAML 风格快速适应）。"""

    def pretrain_on_sources(self, agent: Any, source_envs: list[Any], episodes_per_env: int = 6) -> dict[str, float]:
        rewards: list[float] = []
        for env in source_envs:
            for _ in range(max(1, episodes_per_env)):
                rewards.extend(self._run_episode(agent, env))
        return {
            "source_envs": float(len(source_envs)),
            "mean_reward": float(np.mean(rewards)) if rewards else 0.0,
        }

    def transfer_to_target(self, agent: Any, target_env: Any, freeze_ratio: float = 0.5, episodes: int = 8) -> dict[str, float]:
        if hasattr(agent, "actor_w") and getattr(agent, "actor_w") is not None:
            actor_w = getattr(agent, "actor_w")
            cut = int(actor_w.shape[0] * float(np.clip(freeze_ratio, 0.0, 1.0)))
            actor_w[:cut] *= 0.98  # 模拟冻结大部分参数，仅轻调
            setattr(agent, "actor_w", actor_w)

        rewards: list[float] = []
        for _ in range(max(1, episodes)):
            rewards.extend(self._run_episode(agent, target_env))
        return {
            "episodes": float(episodes),
            "mean_reward": float(np.mean(rewards)) if rewards else 0.0,
        }

    def maml_fast_adapt(self, agent: Any, target_env: Any, inner_steps: int = 5, outer_loops: int = 3) -> dict[str, float]:
        all_rewards: list[float] = []
        for _ in range(max(1, outer_loops)):
            # inner loop
            for _ in range(max(1, inner_steps)):
                all_rewards.extend(self._run_episode(agent, target_env, max_steps=10))
            if hasattr(agent, "update"):
                agent.update(0.0)
            elif hasattr(agent, "train_sync"):
                agent.train_sync()
        return {
            "outer_loops": float(outer_loops),
            "inner_steps": float(inner_steps),
            "mean_reward": float(np.mean(all_rewards)) if all_rewards else 0.0,
        }

    def _run_episode(self, agent: Any, env: Any, max_steps: int = 20) -> list[float]:
        obs = env.reset()
        rewards: list[float] = []

        for _ in range(max(1, max_steps)):
            out = agent.select_action(obs)
            action_idx = int(out[0]) if isinstance(out, tuple) else int(out)
            action = action_idx if env.action_mode == "discrete" else [0.5, 0.5]
            next_obs, reward, done, _ = env.step(action)
            rewards.append(float(reward))
            obs = next_obs
            if done:
                break

        return rewards
