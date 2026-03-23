"""强化学习采样训练与优化。"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Callable
import random

import numpy as np

from .agents import ActorCriticAgent, DQNAgent, PPOAgent


@dataclass
class SamplingRLTrainingConfig:
    model_name: str = "ppo"
    episodes: int = 50
    max_steps_per_episode: int = 40
    learning_rate: float = 0.02
    optimizer: str = "adam"
    reward_target: float = 1.0
    early_stopping_patience: int = 8
    distributed_workers: int = 2
    search_space: dict[str, list[float]] = field(
        default_factory=lambda: {
            "learning_rate": [0.01, 0.02, 0.03],
            "gamma": [0.95, 0.98, 0.99],
            "entropy_coef": [0.005, 0.01, 0.02],
        }
    )


class HyperparameterOptimizer:
    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def grid_search(self, search_space: dict[str, list[Any]], scorer: Callable[[dict[str, Any]], float]) -> tuple[dict[str, Any], float]:
        keys = list(search_space.keys())
        best_params: dict[str, Any] = {}
        best_score = float("-inf")

        for values in product(*[search_space[k] for k in keys]):
            params = {k: v for k, v in zip(keys, values)}
            score = float(scorer(params))
            if score > best_score:
                best_score = score
                best_params = params

        return best_params, best_score

    def random_search(
        self,
        search_space: dict[str, list[Any]],
        scorer: Callable[[dict[str, Any]], float],
        n_trials: int = 12,
    ) -> tuple[dict[str, Any], float]:
        keys = list(search_space.keys())
        best_params: dict[str, Any] = {}
        best_score = float("-inf")

        for _ in range(max(1, n_trials)):
            params = {k: self.rng.choice(search_space[k]) for k in keys}
            score = float(scorer(params))
            if score > best_score:
                best_score = score
                best_params = params

        return best_params, best_score

    def bayesian_search(
        self,
        search_space: dict[str, list[Any]],
        scorer: Callable[[dict[str, Any]], float],
        n_trials: int = 10,
    ) -> tuple[dict[str, Any], float]:
        history: list[tuple[dict[str, Any], float]] = []
        keys = list(search_space.keys())

        for _ in range(max(1, n_trials)):
            if not history:
                params = {k: self.rng.choice(search_space[k]) for k in keys}
            else:
                best = max(history, key=lambda x: x[1])[0]
                params = {}
                for k in keys:
                    candidates = search_space[k]
                    if self.rng.random() < 0.7 and best[k] in candidates:
                        params[k] = best[k]
                    else:
                        params[k] = self.rng.choice(candidates)
            score = float(scorer(params))
            history.append((params, score))

        best_params, best_score = max(history, key=lambda x: x[1])
        return best_params, best_score


class TrainingMonitor:
    def __init__(self) -> None:
        self.reward_curve: list[float] = []
        self.loss_curve: list[float] = []
        self.entropy_curve: list[float] = []
        self.value_curve: list[float] = []

    def update(self, reward: float, loss: float, entropy: float, value: float) -> None:
        self.reward_curve.append(float(reward))
        self.loss_curve.append(float(loss))
        self.entropy_curve.append(float(entropy))
        self.value_curve.append(float(value))

    def summary(self) -> dict[str, float]:
        return {
            "episodes": float(len(self.reward_curve)),
            "best_reward": float(np.max(self.reward_curve)) if self.reward_curve else 0.0,
            "mean_reward": float(np.mean(self.reward_curve)) if self.reward_curve else 0.0,
            "final_reward": float(self.reward_curve[-1]) if self.reward_curve else 0.0,
            "best_loss": float(np.min(self.loss_curve)) if self.loss_curve else 0.0,
            "final_entropy": float(self.entropy_curve[-1]) if self.entropy_curve else 0.0,
            "final_value": float(self.value_curve[-1]) if self.value_curve else 0.0,
        }


class ModelSelector:
    """验证集评估 + 早停。"""

    def __init__(self) -> None:
        self.best_reward = float("-inf")
        self.no_improve_rounds = 0

    def update(self, val_reward: float, patience: int) -> bool:
        if val_reward > self.best_reward:
            self.best_reward = float(val_reward)
            self.no_improve_rounds = 0
            return False
        self.no_improve_rounds += 1
        return self.no_improve_rounds >= int(max(1, patience))


class DistributedTrainer:
    """多进程训练：并行评估配置（轻量实现）。"""

    def __init__(self, max_workers: int = 2) -> None:
        self.max_workers = int(max(1, max_workers))

    def run_parallel(self, items: list[dict[str, Any]], scorer: Callable[[dict[str, Any]], float]) -> list[dict[str, float]]:
        if not items:
            return []

        # scorer 可能不可序列化，优先串行回退，保证兼容。
        try:
            results: list[dict[str, float]] = []
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(_score_worker, item, scorer) for item in items]
                for fut in as_completed(futures):
                    results.append({"score": float(fut.result())})
            return results
        except Exception:
            return [{"score": float(scorer(item))} for item in items]


def _score_worker(item: dict[str, Any], scorer: Callable[[dict[str, Any]], float]) -> float:
    return float(scorer(item))


def _action_from_discrete(action_idx: int, env: Any) -> Any:
    if getattr(env, "action_mode", "discrete") == "discrete":
        return int(action_idx)

    h = getattr(env, "h", 1)
    w = getattr(env, "w", 1)
    row, col = divmod(int(action_idx), int(max(1, w)))
    x = float(env.xx[int(np.clip(row, 0, h - 1)), int(np.clip(col, 0, w - 1))])
    y = float(env.yy[int(np.clip(row, 0, h - 1)), int(np.clip(col, 0, w - 1))])

    if getattr(env, "action_mode", "discrete") == "continuous":
        return [x, y]

    return {"position": [x, y], "sample_count": 1}


def train_agent(
    env: Any,
    agent: Any,
    config: SamplingRLTrainingConfig | None = None,
    monitor: TrainingMonitor | None = None,
) -> dict[str, Any]:
    cfg = config or SamplingRLTrainingConfig()
    mon = monitor or TrainingMonitor()
    selector = ModelSelector()

    best_reward = float("-inf")
    best_episode = -1

    for ep in range(int(max(1, cfg.episodes))):
        obs = env.reset()
        ep_reward = 0.0
        ep_losses: list[float] = []
        entropy = 0.0
        value_est = 0.0

        for _ in range(int(max(1, cfg.max_steps_per_episode))):
            if isinstance(agent, PPOAgent):
                a_idx, logp, value = agent.select_action(obs)
                action = _action_from_discrete(a_idx, env)
                next_obs, reward, done, info = env.step(action)
                agent.store_transition(obs, a_idx, reward, done, logp, value)
                obs = next_obs
                ep_reward += float(reward)
                value_est = float(value)
                if done:
                    break

            elif isinstance(agent, DQNAgent):
                a_idx = agent.select_action(obs)
                action = _action_from_discrete(a_idx, env)
                next_obs, reward, done, info = env.step(action)
                agent.store_transition(obs, a_idx, reward, next_obs, done)
                out = agent.train_step()
                ep_losses.append(float(out.get("loss", 0.0)))
                obs = next_obs
                ep_reward += float(reward)
                if done:
                    break

            elif isinstance(agent, ActorCriticAgent):
                a_idx, value = agent.select_action(obs)
                action = _action_from_discrete(a_idx, env)
                next_obs, reward, done, info = env.step(action)
                agent.store_transition(obs, a_idx, reward, done, value)
                obs = next_obs
                ep_reward += float(reward)
                value_est = float(value)
                if done:
                    break

            else:
                raise ValueError("不支持的智能体类型")

        if isinstance(agent, PPOAgent):
            update_out = agent.update(last_value=0.0)
            ep_losses.append(float(update_out.get("policy_loss", 0.0) + update_out.get("value_loss", 0.0)))
            entropy = float(update_out.get("entropy", 0.0))
        elif isinstance(agent, ActorCriticAgent):
            update_out = agent.train_sync()
            ep_losses.append(float(update_out.get("actor_loss", 0.0) + update_out.get("critic_loss", 0.0)))
            entropy = float(update_out.get("entropy", 0.0))

        mean_loss = float(np.mean(ep_losses)) if ep_losses else 0.0
        mon.update(ep_reward, mean_loss, entropy, value_est)

        val_reward = float(ep_reward)
        early_stop = selector.update(val_reward, patience=cfg.early_stopping_patience)

        if ep_reward > best_reward:
            best_reward = float(ep_reward)
            best_episode = ep

        if early_stop and ep >= 4:
            break

    return {
        "model_name": cfg.model_name,
        "best_reward": best_reward,
        "best_episode": float(best_episode),
        "summary": mon.summary(),
        "history": {
            "reward_curve": mon.reward_curve,
            "loss_curve": mon.loss_curve,
            "entropy_curve": mon.entropy_curve,
            "value_curve": mon.value_curve,
        },
    }
