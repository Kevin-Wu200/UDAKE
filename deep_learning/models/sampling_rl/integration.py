"""强化学习采样集成：对接现有 adaptive sampling 与服务层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .agents import ActorCriticAgent, DQNAgent, PPOAgent
from .env import SamplingEnv
from .evaluation import SamplingRLEvaluator
from .training import SamplingRLTrainingConfig, train_agent

ModelName = Literal["ppo", "dqn", "a2c", "a3c"]


@dataclass
class SamplingRecommendation:
    x: float
    y: float
    score: float
    source: str


class SamplingRLIntegrator:
    """强化学习采样优化集成器。"""

    def __init__(self, model_name: ModelName = "ppo", seed: int = 42) -> None:
        self.model_name = model_name
        self.seed = seed
        self.agent: PPOAgent | DQNAgent | ActorCriticAgent | None = None
        self.latest_training: dict[str, Any] = {}
        self.evaluator = SamplingRLEvaluator()

    def _build_env(
        self,
        uncertainty_map: np.ndarray,
        existing_points: np.ndarray | None = None,
        boundary: tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0),
        action_mode: str = "discrete",
        budget: int = 20,
    ) -> SamplingEnv:
        env = SamplingEnv(
            uncertainty_map=np.asarray(uncertainty_map, dtype=float),
            boundary=boundary,
            action_mode=action_mode,  # type: ignore[arg-type]
            budget=budget,
            max_steps=max(10, budget * 2),
            seed=self.seed,
        )
        obs = env.reset()

        # 将已有采样点注入环境状态。
        points = np.asarray(existing_points, dtype=float) if existing_points is not None else np.zeros((0, 2), dtype=float)
        if len(points) > 0:
            for x, y in points:
                row, col, _ = env._xy_to_index(float(x), float(y))
                env._apply_sampling([(row, col)])
        return env

    def _build_agent(self, action_dim: int) -> PPOAgent | DQNAgent | ActorCriticAgent:
        if self.model_name == "ppo":
            return PPOAgent(action_dim=action_dim, seed=self.seed)
        if self.model_name == "dqn":
            return DQNAgent(action_dim=action_dim, seed=self.seed)
        # a2c / a3c
        return ActorCriticAgent(action_dim=action_dim, seed=self.seed)

    def train(
        self,
        uncertainty_map: np.ndarray,
        existing_points: np.ndarray | None = None,
        boundary: tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0),
        episodes: int = 30,
        budget: int = 20,
    ) -> dict[str, Any]:
        env = self._build_env(
            uncertainty_map=uncertainty_map,
            existing_points=existing_points,
            boundary=boundary,
            action_mode="discrete",
            budget=budget,
        )
        agent = self._build_agent(action_dim=env.h * env.w)

        result = train_agent(
            env,
            agent,
            config=SamplingRLTrainingConfig(
                model_name=self.model_name,
                episodes=max(5, int(episodes)),
                max_steps_per_episode=max(8, budget),
            ),
        )

        self.agent = agent
        self.latest_training = result
        return result

    def _rule_based_candidates(
        self,
        uncertainty_map: np.ndarray,
        boundary: tuple[float, float, float, float],
        n: int,
    ) -> list[SamplingRecommendation]:
        arr = np.asarray(uncertainty_map, dtype=float)
        h, w = arr.shape
        top = np.argsort(arr.reshape(-1))[-max(1, n):][::-1]

        min_x, max_x, min_y, max_y = boundary
        recs: list[SamplingRecommendation] = []
        for idx in top:
            row, col = divmod(int(idx), w)
            x = min_x + (max_x - min_x) * (col / max(1, w - 1))
            y = min_y + (max_y - min_y) * (row / max(1, h - 1))
            recs.append(
                SamplingRecommendation(
                    x=float(x),
                    y=float(y),
                    score=float(arr[row, col]),
                    source="rule_based",
                )
            )
        return recs

    def recommend(
        self,
        uncertainty_map: np.ndarray,
        existing_points: np.ndarray | None = None,
        boundary: tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0),
        n_recommendations: int = 10,
        fusion_strategy: Literal["rl_only", "rule_only", "hybrid"] = "hybrid",
        realtime: bool = False,
    ) -> dict[str, Any]:
        arr = np.asarray(uncertainty_map, dtype=float)
        n = int(max(1, n_recommendations))

        if self.agent is None:
            self.train(arr, existing_points=existing_points, boundary=boundary, episodes=15, budget=max(10, n * 2))

        env = self._build_env(arr, existing_points=existing_points, boundary=boundary, action_mode="discrete", budget=max(10, n * 2))
        obs = env.reset()
        rl_recs: list[SamplingRecommendation] = []

        for _ in range(n * 3):
            if isinstance(self.agent, PPOAgent):
                action_idx, _, _ = self.agent.select_action(obs, deterministic=True)
            elif isinstance(self.agent, DQNAgent):
                action_idx = self.agent.select_action(obs, deterministic=True)
            else:
                action_idx, _ = self.agent.select_action(obs, deterministic=True)

            next_obs, reward, done, info = env.step(int(action_idx))
            row, col = divmod(int(action_idx), env.w)
            x, y = env._index_to_xy(row, col)
            rl_recs.append(SamplingRecommendation(x=x, y=y, score=float(info["reward_breakdown"]["raw_total_reward"]), source="rl"))
            obs = next_obs
            if done or len(rl_recs) >= n:
                break

        # 去重
        dedup: dict[tuple[int, int], SamplingRecommendation] = {}
        for rec in rl_recs:
            key = (int(round(rec.x * 1e4)), int(round(rec.y * 1e4)))
            if key not in dedup or dedup[key].score < rec.score:
                dedup[key] = rec
        rl_recs = sorted(dedup.values(), key=lambda x: x.score, reverse=True)[:n]

        rule_recs = self._rule_based_candidates(arr, boundary=boundary, n=n)

        if fusion_strategy == "rl_only":
            final = rl_recs
        elif fusion_strategy == "rule_only":
            final = rule_recs
        else:
            merged = rl_recs + rule_recs
            merged.sort(key=lambda x: x.score, reverse=True)
            seen: set[tuple[int, int]] = set()
            final = []
            for item in merged:
                key = (int(round(item.x * 1e4)), int(round(item.y * 1e4)))
                if key in seen:
                    continue
                seen.add(key)
                final.append(item)
                if len(final) >= n:
                    break

        payload = {
            "model_name": self.model_name,
            "realtime": bool(realtime),
            "fusion_strategy": fusion_strategy,
            "recommendations": [
                {
                    "x": float(rec.x),
                    "y": float(rec.y),
                    "score": float(rec.score),
                    "source": rec.source,
                }
                for rec in final
            ],
            "training_summary": self.latest_training.get("summary", {}),
        }
        return payload

    def optimize_strategy(
        self,
        uncertainty_map: np.ndarray,
        boundary: tuple[float, float, float, float] = (0.0, 1.0, 0.0, 1.0),
    ) -> dict[str, Any]:
        """采样策略优化：比较三种融合策略并返回最优策略。"""
        strategies = ["rl_only", "rule_only", "hybrid"]
        scores: dict[str, float] = {}
        for st in strategies:
            result = self.recommend(
                uncertainty_map=uncertainty_map,
                boundary=boundary,
                n_recommendations=8,
                fusion_strategy=st,  # type: ignore[arg-type]
            )
            recs = result["recommendations"]
            score = float(np.mean([r["score"] for r in recs])) if recs else 0.0
            scores[st] = score

        best = max(scores.items(), key=lambda x: x[1])[0]
        return {
            "best_strategy": best,
            "strategy_scores": scores,
        }
