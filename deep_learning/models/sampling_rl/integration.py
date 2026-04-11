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

    @staticmethod
    def _xy_to_grid(
        x: float,
        y: float,
        *,
        boundary: tuple[float, float, float, float],
        h: int,
        w: int,
    ) -> tuple[int, int]:
        min_x, max_x, min_y, max_y = boundary
        col = int(np.clip(round((float(x) - min_x) / max(1e-8, max_x - min_x) * max(1, w - 1)), 0, max(0, w - 1)))
        row = int(np.clip(round((float(y) - min_y) / max(1e-8, max_y - min_y) * max(1, h - 1)), 0, max(0, h - 1)))
        return row, col

    def _estimate_spatial_diversity(self, recs: list[SamplingRecommendation]) -> float:
        if len(recs) < 2:
            return 0.0
        pts = np.asarray([[float(r.x), float(r.y)] for r in recs], dtype=float)
        dmat = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2)
        upper = dmat[np.triu_indices(len(recs), k=1)]
        return float(np.mean(upper)) if upper.size else 0.0

    def _build_policy_decision_explanation(
        self,
        *,
        fusion_strategy: str,
        rl_recs: list[SamplingRecommendation],
        rule_recs: list[SamplingRecommendation],
        final_recs: list[SamplingRecommendation],
        uncertainty_map: np.ndarray,
    ) -> dict[str, Any]:
        rl_scores = np.asarray([float(r.score) for r in rl_recs], dtype=float)
        rule_scores = np.asarray([float(r.score) for r in rule_recs], dtype=float)
        final_scores = np.asarray([float(r.score) for r in final_recs], dtype=float)

        rl_mean = float(np.mean(rl_scores)) if rl_scores.size else 0.0
        rule_mean = float(np.mean(rule_scores)) if rule_scores.size else 0.0
        final_mean = float(np.mean(final_scores)) if final_scores.size else 0.0
        uncertainty_mean = float(np.mean(np.asarray(uncertainty_map, dtype=float)))

        if fusion_strategy == "rl_only":
            reason = "使用强化学习策略，优先考虑长期累计收益与策略稳定性。"
        elif fusion_strategy == "rule_only":
            reason = "使用规则策略，优先选择不确定性峰值点，保证可解释性与确定性。"
        elif rl_mean >= rule_mean:
            reason = "混合策略中 RL 候选平均得分更高，最终结果偏向策略网络决策。"
        else:
            reason = "混合策略中规则候选平均得分更高，最终结果偏向高不确定性区域。"

        source_count: dict[str, int] = {}
        for rec in final_recs:
            source = str(rec.source)
            source_count[source] = int(source_count.get(source, 0) + 1)
        total = max(1, len(final_recs))

        confidence = float(np.clip((final_mean / max(1e-6, uncertainty_mean + 0.05)), 0.0, 2.0) / 2.0)

        return {
            "summary": {
                "strategy": fusion_strategy,
                "decision_reason": reason,
                "decision_confidence": confidence,
                "uncertainty_mean": uncertainty_mean,
                "final_mean_score": final_mean,
                "final_score_std": float(np.std(final_scores)) if final_scores.size else 0.0,
            },
            "strategy_comparison": {
                "rl_candidate_mean": rl_mean,
                "rule_candidate_mean": rule_mean,
                "rl_candidate_best": float(np.max(rl_scores)) if rl_scores.size else 0.0,
                "rule_candidate_best": float(np.max(rule_scores)) if rule_scores.size else 0.0,
                "rl_spatial_diversity": self._estimate_spatial_diversity(rl_recs),
                "rule_spatial_diversity": self._estimate_spatial_diversity(rule_recs),
            },
            "source_contribution": [
                {
                    "source": src,
                    "count": int(cnt),
                    "ratio": float(cnt / total),
                }
                for src, cnt in sorted(source_count.items(), key=lambda x: x[1], reverse=True)
            ],
        }

    def _build_action_value_visualization(
        self,
        *,
        recs: list[SamplingRecommendation],
        boundary: tuple[float, float, float, float],
        h: int,
        w: int,
    ) -> dict[str, Any]:
        values = np.asarray([float(r.score) for r in recs], dtype=float)
        if values.size == 0:
            return {
                "summary": {"point_count": 0, "value_min": 0.0, "value_max": 0.0, "value_mean": 0.0},
                "action_value_points": [],
                "value_histogram": {"counts": [], "bin_edges": []},
                "value_heatmap": [],
            }

        vmin = float(np.min(values))
        vmax = float(np.max(values))
        span = max(1e-8, vmax - vmin)
        heatmap = np.zeros((h, w), dtype=float)
        points: list[dict[str, Any]] = []
        for idx, rec in enumerate(recs):
            row, col = self._xy_to_grid(rec.x, rec.y, boundary=boundary, h=h, w=w)
            normalized = float(np.clip((float(rec.score) - vmin) / span, 0.0, 1.0))
            heatmap[row, col] = max(float(heatmap[row, col]), float(rec.score))
            points.append(
                {
                    "rank": int(idx + 1),
                    "x": float(rec.x),
                    "y": float(rec.y),
                    "row": int(row),
                    "col": int(col),
                    "action_index": int(row * w + col),
                    "value": float(rec.score),
                    "normalized_value": normalized,
                    "source": str(rec.source),
                }
            )

        hist_counts, hist_edges = np.histogram(values, bins=min(10, max(4, int(np.sqrt(values.size)))))
        return {
            "summary": {
                "point_count": int(values.size),
                "value_min": vmin,
                "value_max": vmax,
                "value_mean": float(np.mean(values)),
                "value_std": float(np.std(values)),
            },
            "action_value_points": points,
            "value_histogram": {
                "counts": [int(x) for x in hist_counts.tolist()],
                "bin_edges": [float(x) for x in hist_edges.tolist()],
            },
            "value_heatmap": [[float(v) for v in row.tolist()] for row in heatmap],
        }

    def _build_sampling_point_recommendation_explanation(
        self,
        *,
        recs: list[SamplingRecommendation],
        uncertainty_map: np.ndarray,
        existing_points: np.ndarray,
        boundary: tuple[float, float, float, float],
    ) -> dict[str, Any]:
        arr = np.asarray(uncertainty_map, dtype=float)
        h, w = arr.shape
        ranked_uncertainty = np.argsort(arr.reshape(-1))[::-1]
        rank_map = np.empty_like(ranked_uncertainty)
        rank_map[ranked_uncertainty] = np.arange(1, ranked_uncertainty.size + 1)

        mean_uncertainty = float(np.mean(arr))
        details: list[dict[str, Any]] = []
        for idx, rec in enumerate(recs):
            row, col = self._xy_to_grid(rec.x, rec.y, boundary=boundary, h=h, w=w)
            cell_uncertainty = float(arr[row, col])
            uncertainty_rank = int(rank_map[row * w + col])
            if existing_points.size > 0:
                dists = np.linalg.norm(existing_points - np.asarray([rec.x, rec.y], dtype=float), axis=1)
                nearest_dist = float(np.min(dists))
            else:
                nearest_dist = 1.0
            novelty = float(np.clip(nearest_dist / 0.25, 0.0, 1.0))

            tags: list[str] = []
            if cell_uncertainty >= mean_uncertainty:
                tags.append("high_uncertainty")
            if novelty >= 0.5:
                tags.append("coverage_gap")
            tags.append("rl_policy" if rec.source == "rl" else "rule_peak")

            details.append(
                {
                    "rank": int(idx + 1),
                    "x": float(rec.x),
                    "y": float(rec.y),
                    "source": str(rec.source),
                    "score": float(rec.score),
                    "uncertainty_value": cell_uncertainty,
                    "uncertainty_rank": uncertainty_rank,
                    "nearest_existing_distance": nearest_dist,
                    "novelty_score": novelty,
                    "reason_tags": tags,
                    "reason_text": f"点位不确定性排名第 {uncertainty_rank}，与最近已有点距离 {nearest_dist:.3f}，来源 {rec.source}。",
                }
            )

        return {
            "summary": {
                "recommended_points": int(len(details)),
                "mean_uncertainty_at_points": float(np.mean([d["uncertainty_value"] for d in details])) if details else 0.0,
                "mean_novelty_score": float(np.mean([d["novelty_score"] for d in details])) if details else 0.0,
            },
            "point_explanations": details,
        }

    def _build_sampling_density_analysis(
        self,
        *,
        existing_points: np.ndarray,
        recs: list[SamplingRecommendation],
        uncertainty_map: np.ndarray,
        boundary: tuple[float, float, float, float],
    ) -> dict[str, Any]:
        arr = np.asarray(uncertainty_map, dtype=float)
        h, w = arr.shape
        density = np.zeros((h, w), dtype=float)

        for point in np.asarray(existing_points, dtype=float):
            row, col = self._xy_to_grid(float(point[0]), float(point[1]), boundary=boundary, h=h, w=w)
            density[row, col] += 1.0
        for rec in recs:
            row, col = self._xy_to_grid(rec.x, rec.y, boundary=boundary, h=h, w=w)
            density[row, col] += 1.5

        kernel = np.array(
            [
                [0.05, 0.1, 0.05],
                [0.1, 0.4, 0.1],
                [0.05, 0.1, 0.05],
            ],
            dtype=float,
        )
        smoothed = density.copy()
        for r in range(1, h - 1):
            for c in range(1, w - 1):
                smoothed[r, c] = float(np.sum(density[r - 1 : r + 2, c - 1 : c + 2] * kernel))

        occupied = int(np.count_nonzero(smoothed > 1e-8))
        total = int(h * w)
        max_density = float(np.max(smoothed)) if smoothed.size else 0.0
        density_norm = smoothed / max(1e-8, max_density)
        priority = arr * (1.0 - density_norm)
        top_idx = np.argsort(priority.reshape(-1))[::-1][: min(8, total)]
        hotspots: list[dict[str, Any]] = []
        min_x, max_x, min_y, max_y = boundary
        for idx in top_idx.tolist():
            row, col = divmod(int(idx), w)
            x = min_x + (max_x - min_x) * (col / max(1, w - 1))
            y = min_y + (max_y - min_y) * (row / max(1, h - 1))
            hotspots.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "row": int(row),
                    "col": int(col),
                    "density": float(smoothed[row, col]),
                    "uncertainty": float(arr[row, col]),
                    "priority": float(priority[row, col]),
                }
            )

        return {
            "summary": {
                "coverage_ratio": float(occupied / max(1, total)),
                "mean_density": float(np.mean(smoothed)) if smoothed.size else 0.0,
                "max_density": max_density,
                "min_nonzero_density": float(np.min(smoothed[smoothed > 0])) if np.any(smoothed > 0) else 0.0,
                "existing_point_count": int(existing_points.shape[0]) if existing_points.ndim == 2 else 0,
                "recommended_point_count": int(len(recs)),
            },
            "density_map": [[float(v) for v in row.tolist()] for row in smoothed],
            "sparse_hotspots": hotspots,
        }

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
        existing_arr = np.asarray(existing_points, dtype=float) if existing_points is not None else np.zeros((0, 2), dtype=float)

        if self.agent is None:
            self.train(arr, existing_points=existing_arr, boundary=boundary, episodes=15, budget=max(10, n * 2))

        env = self._build_env(arr, existing_points=existing_arr, boundary=boundary, action_mode="discrete", budget=max(10, n * 2))
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

        policy_decision = self._build_policy_decision_explanation(
            fusion_strategy=fusion_strategy,
            rl_recs=rl_recs,
            rule_recs=rule_recs,
            final_recs=final,
            uncertainty_map=arr,
        )
        action_value_vis = self._build_action_value_visualization(
            recs=rl_recs if rl_recs else final,
            boundary=boundary,
            h=arr.shape[0],
            w=arr.shape[1],
        )
        point_rec_explain = self._build_sampling_point_recommendation_explanation(
            recs=final,
            uncertainty_map=arr,
            existing_points=existing_arr,
            boundary=boundary,
        )
        density_analysis = self._build_sampling_density_analysis(
            existing_points=existing_arr,
            recs=final,
            uncertainty_map=arr,
            boundary=boundary,
        )

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
            "explanations": {
                "policy_decision": policy_decision,
                "action_value_visualization": action_value_vis,
                "sampling_point_recommendation": point_rec_explain,
                "sampling_density_analysis": density_analysis,
            },
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
