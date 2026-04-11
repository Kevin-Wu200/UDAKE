"""强化学习采样集成：对接现有 adaptive sampling 与服务层。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from .agents import ActorCriticAgent, DQNAgent, PPOAgent
from .env import SamplingEnv
from .evaluation import SamplingRLEvaluator
from .marl import MultiAgentSamplingSystem
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
        self.policy_history: list[dict[str, Any]] = []
        self._recommend_iteration = 0
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

    def _build_sampling_region_visualization(
        self,
        *,
        recs: list[SamplingRecommendation],
        uncertainty_map: np.ndarray,
        boundary: tuple[float, float, float, float],
    ) -> dict[str, Any]:
        arr = np.asarray(uncertainty_map, dtype=float)
        h, w = arr.shape
        region_map = np.zeros((h, w), dtype=float)
        region_points: list[dict[str, Any]] = []
        min_x, max_x, min_y, max_y = boundary

        for idx, rec in enumerate(recs):
            row, col = self._xy_to_grid(rec.x, rec.y, boundary=boundary, h=h, w=w)
            influence = max(0.1, float(rec.score))
            for rr in range(max(0, row - 1), min(h, row + 2)):
                for cc in range(max(0, col - 1), min(w, col + 2)):
                    dist = abs(rr - row) + abs(cc - col)
                    weight = 1.0 if dist == 0 else (0.6 if dist == 1 else 0.3)
                    region_map[rr, cc] += influence * weight
            region_points.append(
                {
                    "rank": int(idx + 1),
                    "x": float(rec.x),
                    "y": float(rec.y),
                    "row": int(row),
                    "col": int(col),
                    "source": str(rec.source),
                    "score": float(rec.score),
                }
            )

        max_region = float(np.max(region_map)) if region_map.size else 0.0
        norm_region = region_map / max(1e-8, max_region)
        contour_levels = [0.25, 0.5, 0.75]
        contours: list[dict[str, Any]] = []
        for level in contour_levels:
            idxs = np.argwhere(norm_region >= level)
            if idxs.size == 0:
                contours.append({"level": float(level), "cells": []})
                continue
            cells = []
            for row, col in idxs[:48]:
                x = min_x + (max_x - min_x) * (int(col) / max(1, w - 1))
                y = min_y + (max_y - min_y) * (int(row) / max(1, h - 1))
                cells.append({"row": int(row), "col": int(col), "x": float(x), "y": float(y)})
            contours.append({"level": float(level), "cells": cells})

        return {
            "summary": {
                "region_peak": max_region,
                "region_mean": float(np.mean(region_map)) if region_map.size else 0.0,
                "region_coverage_ratio": float(np.count_nonzero(norm_region >= 0.25) / max(1, h * w)),
                "recommended_region_count": int(len(region_points)),
            },
            "recommended_regions": region_points,
            "region_intensity_map": [[float(v) for v in row.tolist()] for row in norm_region],
            "region_contours": contours,
        }

    def _build_sampling_effect_evaluation(
        self,
        *,
        recs: list[SamplingRecommendation],
        uncertainty_map: np.ndarray,
        existing_points: np.ndarray,
        boundary: tuple[float, float, float, float],
    ) -> dict[str, Any]:
        arr = np.asarray(uncertainty_map, dtype=float)
        h, w = arr.shape
        before_mean = float(np.mean(arr))
        after_map = arr.copy()

        for rec in recs:
            row, col = self._xy_to_grid(rec.x, rec.y, boundary=boundary, h=h, w=w)
            for rr in range(max(0, row - 1), min(h, row + 2)):
                for cc in range(max(0, col - 1), min(w, col + 2)):
                    dist = abs(rr - row) + abs(cc - col)
                    decay = 0.2 if dist == 0 else (0.1 if dist == 1 else 0.05)
                    after_map[rr, cc] = max(1e-6, float(after_map[rr, cc]) * (1.0 - decay))

        after_mean = float(np.mean(after_map))
        reduction = float(before_mean - after_mean)
        reduction_ratio = float(reduction / max(1e-6, before_mean))
        expected_gain = float(np.mean([rec.score for rec in recs])) if recs else 0.0

        total_points = int(existing_points.shape[0]) + int(len(recs)) if existing_points.ndim == 2 else int(len(recs))
        sampling_efficiency = float(reduction / max(1, len(recs)))
        quality_score = float(np.clip(0.45 * reduction_ratio + 0.35 * expected_gain + 0.2 * min(1.0, total_points / 30.0), 0.0, 1.0))

        return {
            "summary": {
                "uncertainty_before_mean": before_mean,
                "uncertainty_after_mean": after_mean,
                "uncertainty_reduction": reduction,
                "uncertainty_reduction_ratio": reduction_ratio,
                "expected_information_gain": expected_gain,
                "sampling_efficiency": sampling_efficiency,
                "quality_score": quality_score,
            },
            "before_uncertainty_map": [[float(v) for v in row.tolist()] for row in arr],
            "after_uncertainty_map": [[float(v) for v in row.tolist()] for row in after_map],
            "evaluation_notes": [
                "基于推荐点邻域衰减估计采样后的不确定性变化。",
                "质量评分综合考虑不确定性下降、信息增益与样本规模。",
            ],
        }

    def _build_strategy_comparison_analysis(
        self,
        *,
        fusion_strategy: str,
        rl_recs: list[SamplingRecommendation],
        rule_recs: list[SamplingRecommendation],
        final_recs: list[SamplingRecommendation],
        uncertainty_map: np.ndarray,
        boundary: tuple[float, float, float, float],
    ) -> dict[str, Any]:
        arr = np.asarray(uncertainty_map, dtype=float)
        h, w = arr.shape
        top_threshold = float(np.quantile(arr.reshape(-1), 0.8))

        def _stats(name: str, recs: list[SamplingRecommendation]) -> dict[str, Any]:
            scores = np.asarray([float(r.score) for r in recs], dtype=float)
            if scores.size == 0:
                return {
                    "strategy": name,
                    "count": 0,
                    "mean_score": 0.0,
                    "std_score": 0.0,
                    "best_score": 0.0,
                    "spatial_diversity": 0.0,
                    "high_uncertainty_hit_ratio": 0.0,
                }

            hits = 0
            for rec in recs:
                row, col = self._xy_to_grid(rec.x, rec.y, boundary=boundary, h=h, w=w)
                if float(arr[row, col]) >= top_threshold:
                    hits += 1
            return {
                "strategy": name,
                "count": int(scores.size),
                "mean_score": float(np.mean(scores)),
                "std_score": float(np.std(scores)),
                "best_score": float(np.max(scores)),
                "spatial_diversity": self._estimate_spatial_diversity(recs),
                "high_uncertainty_hit_ratio": float(hits / max(1, scores.size)),
            }

        rl_stats = _stats("rl_only", rl_recs)
        rule_stats = _stats("rule_only", rule_recs)
        final_stats = _stats(fusion_strategy, final_recs)
        candidates = [rl_stats, rule_stats, final_stats]
        best_mean = max(candidates, key=lambda x: x["mean_score"])["strategy"]
        best_peak = max(candidates, key=lambda x: x["best_score"])["strategy"]

        return {
            "summary": {
                "selected_strategy": fusion_strategy,
                "best_by_mean_score": best_mean,
                "best_by_peak_score": best_peak,
                "final_mean_score": float(final_stats["mean_score"]),
                "final_high_uncertainty_hit_ratio": float(final_stats["high_uncertainty_hit_ratio"]),
            },
            "strategy_metrics": [rl_stats, rule_stats, final_stats],
        }

    def _build_sampling_efficiency_evaluation(
        self,
        *,
        recs: list[SamplingRecommendation],
        effect_evaluation: dict[str, Any],
        density_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        effect_summary = effect_evaluation.get("summary", {})
        density_summary = density_analysis.get("summary", {})
        reduction = float(effect_summary.get("uncertainty_reduction", 0.0))
        reduction_ratio = float(effect_summary.get("uncertainty_reduction_ratio", 0.0))
        info_gain = float(effect_summary.get("expected_information_gain", 0.0))
        coverage_ratio = float(density_summary.get("coverage_ratio", 0.0))
        point_count = max(1, len(recs))

        marginal_gain = float(reduction / point_count)
        coverage_eff = float(coverage_ratio / point_count)
        combined_eff = float(np.clip(0.5 * reduction_ratio + 0.35 * info_gain + 0.15 * min(1.0, coverage_ratio), 0.0, 1.0))

        level = "high" if combined_eff >= 0.65 else ("medium" if combined_eff >= 0.4 else "low")
        return {
            "summary": {
                "sample_count": int(point_count),
                "marginal_uncertainty_reduction": marginal_gain,
                "coverage_efficiency": coverage_eff,
                "combined_efficiency_score": combined_eff,
                "efficiency_level": level,
            },
            "cost_benefit": {
                "uncertainty_reduction": reduction,
                "uncertainty_reduction_ratio": reduction_ratio,
                "expected_information_gain": info_gain,
                "coverage_ratio": coverage_ratio,
            },
        }

    def _build_long_term_value_prediction(
        self,
        *,
        recs: list[SamplingRecommendation],
        effect_evaluation: dict[str, Any],
    ) -> dict[str, Any]:
        effect_summary = effect_evaluation.get("summary", {})
        base_gain = float(effect_summary.get("expected_information_gain", 0.0))
        reduction_ratio = float(effect_summary.get("uncertainty_reduction_ratio", 0.0))
        quality_score = float(effect_summary.get("quality_score", 0.0))
        count_factor = min(1.0, len(recs) / 10.0)
        stability = float(np.clip(0.55 * quality_score + 0.45 * count_factor, 0.0, 1.0))

        horizons = [3, 5, 10]
        curve: list[dict[str, Any]] = []
        for step in horizons:
            decay = 0.92 ** step
            cumulative_value = float(base_gain * step * (0.75 + 0.25 * stability) * decay)
            projected_reduction = float(np.clip(reduction_ratio * np.sqrt(step) * (0.8 + 0.2 * stability), 0.0, 1.0))
            curve.append(
                {
                    "horizon_steps": int(step),
                    "projected_cumulative_value": cumulative_value,
                    "projected_uncertainty_reduction_ratio": projected_reduction,
                }
            )

        return {
            "summary": {
                "base_information_gain": base_gain,
                "stability_factor": stability,
                "long_term_value_score": float(np.mean([x["projected_cumulative_value"] for x in curve])) if curve else 0.0,
            },
            "prediction_curve": curve,
        }

    def _build_policy_robustness_analysis(
        self,
        *,
        final_recs: list[SamplingRecommendation],
        uncertainty_map: np.ndarray,
        boundary: tuple[float, float, float, float],
    ) -> dict[str, Any]:
        arr = np.asarray(uncertainty_map, dtype=float)
        h, w = arr.shape
        if not final_recs:
            return {
                "summary": {
                    "robustness_score": 0.0,
                    "sensitivity_index": 1.0,
                    "stability_level": "low",
                },
                "perturbation_tests": [],
            }

        scales = [0.02, 0.05, 0.1]
        rng = np.random.default_rng(self.seed)
        tests: list[dict[str, Any]] = []
        stability_scores: list[float] = []
        topk = max(1, len(final_recs))
        for scale in scales:
            noise = rng.normal(0.0, scale, size=arr.shape)
            perturbed = np.clip(arr + noise, 1e-6, None)
            top_idx = np.argsort(perturbed.reshape(-1))[::-1][:topk]
            top_cells = {(int(idx) // w, int(idx) % w) for idx in top_idx.tolist()}

            hits = 0
            score_shift: list[float] = []
            for rec in final_recs:
                row, col = self._xy_to_grid(rec.x, rec.y, boundary=boundary, h=h, w=w)
                if (row, col) in top_cells:
                    hits += 1
                score_shift.append(abs(float(perturbed[row, col]) - float(arr[row, col])))

            retention = float(hits / max(1, len(final_recs)))
            mean_shift = float(np.mean(score_shift)) if score_shift else 0.0
            stability = float(np.clip(retention - mean_shift, 0.0, 1.0))
            stability_scores.append(stability)
            tests.append(
                {
                    "noise_scale": float(scale),
                    "topk_retention_ratio": retention,
                    "mean_score_shift": mean_shift,
                    "stability_score": stability,
                }
            )

        robustness = float(np.mean(stability_scores)) if stability_scores else 0.0
        sensitivity = float(1.0 - robustness)
        level = "high" if robustness >= 0.65 else ("medium" if robustness >= 0.4 else "low")
        return {
            "summary": {
                "robustness_score": robustness,
                "sensitivity_index": sensitivity,
                "stability_level": level,
            },
            "perturbation_tests": tests,
        }

    def _record_policy_history(
        self,
        *,
        fusion_strategy: str,
        rl_recs: list[SamplingRecommendation],
        rule_recs: list[SamplingRecommendation],
        final_recs: list[SamplingRecommendation],
        density_analysis: dict[str, Any],
        effect_evaluation: dict[str, Any],
        long_term_value_prediction: dict[str, Any],
        policy_robustness_analysis: dict[str, Any],
    ) -> None:
        self._recommend_iteration += 1
        density_summary = density_analysis.get("summary", {})
        effect_summary = effect_evaluation.get("summary", {})
        long_term_summary = long_term_value_prediction.get("summary", {})
        robust_summary = policy_robustness_analysis.get("summary", {})

        rl_scores = np.asarray([float(r.score) for r in rl_recs], dtype=float)
        rule_scores = np.asarray([float(r.score) for r in rule_recs], dtype=float)
        final_scores = np.asarray([float(r.score) for r in final_recs], dtype=float)

        self.policy_history.append(
            {
                "step": int(self._recommend_iteration),
                "model_name": self.model_name,
                "fusion_strategy": fusion_strategy,
                "recommendation_count": int(len(final_recs)),
                "rl_mean_score": float(np.mean(rl_scores)) if rl_scores.size else 0.0,
                "rule_mean_score": float(np.mean(rule_scores)) if rule_scores.size else 0.0,
                "final_mean_score": float(np.mean(final_scores)) if final_scores.size else 0.0,
                "coverage_ratio": float(density_summary.get("coverage_ratio", 0.0)),
                "quality_score": float(effect_summary.get("quality_score", 0.0)),
                "reduction_ratio": float(effect_summary.get("uncertainty_reduction_ratio", 0.0)),
                "long_term_value_score": float(long_term_summary.get("long_term_value_score", 0.0)),
                "robustness_score": float(robust_summary.get("robustness_score", 0.0)),
            }
        )
        self.policy_history = self.policy_history[-30:]

    def _build_policy_history_record(self) -> dict[str, Any]:
        if not self.policy_history:
            return {
                "summary": {
                    "history_count": 0,
                    "latest_strategy": "none",
                    "mean_quality_score": 0.0,
                    "mean_robustness_score": 0.0,
                    "trend": "stable",
                },
                "history": [],
                "trend_analysis": {"quality_slope": 0.0, "value_slope": 0.0},
            }

        history = self.policy_history[-12:]
        quality = np.asarray([float(item.get("quality_score", 0.0)) for item in history], dtype=float)
        value = np.asarray([float(item.get("long_term_value_score", 0.0)) for item in history], dtype=float)
        robustness = np.asarray([float(item.get("robustness_score", 0.0)) for item in history], dtype=float)

        if len(history) >= 2:
            x = np.arange(len(history), dtype=float)
            quality_slope = float(np.polyfit(x, quality, deg=1)[0])
            value_slope = float(np.polyfit(x, value, deg=1)[0])
        else:
            quality_slope = 0.0
            value_slope = 0.0

        if quality_slope > 0.01:
            trend = "improving"
        elif quality_slope < -0.01:
            trend = "declining"
        else:
            trend = "stable"

        return {
            "summary": {
                "history_count": int(len(history)),
                "latest_strategy": str(history[-1].get("fusion_strategy", "unknown")),
                "mean_quality_score": float(np.mean(quality)) if quality.size else 0.0,
                "mean_robustness_score": float(np.mean(robustness)) if robustness.size else 0.0,
                "trend": trend,
            },
            "history": history,
            "trend_analysis": {
                "quality_slope": quality_slope,
                "value_slope": value_slope,
            },
        }

    def _build_policy_effect_prediction(
        self,
        *,
        sampling_efficiency_evaluation: dict[str, Any],
        long_term_value_prediction: dict[str, Any],
        policy_robustness_analysis: dict[str, Any],
        policy_history_record: dict[str, Any],
    ) -> dict[str, Any]:
        eff_summary = sampling_efficiency_evaluation.get("summary", {})
        value_summary = long_term_value_prediction.get("summary", {})
        robust_summary = policy_robustness_analysis.get("summary", {})
        trend_analysis = policy_history_record.get("trend_analysis", {})

        efficiency = float(eff_summary.get("combined_efficiency_score", 0.0))
        long_term_value = float(value_summary.get("long_term_value_score", 0.0))
        robustness = float(robust_summary.get("robustness_score", 0.0))
        quality_slope = float(trend_analysis.get("quality_slope", 0.0))
        value_slope = float(trend_analysis.get("value_slope", 0.0))

        trend_gain = float(np.clip(0.5 + 2.5 * quality_slope + 0.8 * value_slope, 0.0, 1.0))
        current_effectiveness = float(np.clip(0.45 * efficiency + 0.3 * robustness + 0.25 * trend_gain, 0.0, 1.0))
        base_future = float(np.clip(0.4 * efficiency + 0.35 * robustness + 0.25 * trend_gain, 0.0, 1.0))

        scenarios = [
            {
                "scenario": "optimistic",
                "expected_effect_score": float(np.clip(base_future + 0.12, 0.0, 1.0)),
                "description": "覆盖率与鲁棒性同步提升，策略收益稳步增长。",
            },
            {
                "scenario": "baseline",
                "expected_effect_score": base_future,
                "description": "维持当前融合策略，收益按当前趋势缓慢变化。",
            },
            {
                "scenario": "conservative",
                "expected_effect_score": float(np.clip(base_future - 0.15, 0.0, 1.0)),
                "description": "扰动增强或采样预算不足时，策略效果可能回落。",
            },
        ]

        risk_level = "low" if base_future >= 0.65 else ("medium" if base_future >= 0.4 else "high")
        return {
            "summary": {
                "current_effectiveness_score": current_effectiveness,
                "future_effect_score": base_future,
                "risk_level": risk_level,
                "confidence": float(np.clip(0.4 + 0.6 * robustness, 0.0, 1.0)),
                "reference_long_term_value": long_term_value,
            },
            "drivers": {
                "efficiency_score": efficiency,
                "robustness_score": robustness,
                "trend_gain": trend_gain,
            },
            "forecast_scenarios": scenarios,
        }

    def _build_multi_agent_collaboration_analysis(
        self,
        *,
        final_recs: list[SamplingRecommendation],
        uncertainty_map: np.ndarray,
        boundary: tuple[float, float, float, float],
    ) -> dict[str, Any]:
        arr = np.asarray(uncertainty_map, dtype=float)
        h, w = arr.shape
        if len(final_recs) < 2 or arr.size == 0:
            return {
                "summary": {
                    "applicable": False,
                    "reason": "推荐点不足或不确定性地图为空，跳过多智能体协作分析。",
                },
                "agent_messages": [],
                "cooperation_plan": [],
                "competition_plan": [],
            }

        n_agents = int(min(4, max(2, len(final_recs))))
        marl = MultiAgentSamplingSystem(n_agents=n_agents, seed=self.seed)

        final_cells: list[tuple[int, int]] = []
        final_actions: list[int] = []
        for rec in final_recs:
            row, col = self._xy_to_grid(rec.x, rec.y, boundary=boundary, h=h, w=w)
            final_cells.append((row, col))
            final_actions.append(int(row * w + col))

        coop_actions = marl.cooperative_strategy(arr, top_k=max(6, n_agents * 2))
        comp_actions = marl.competitive_strategy(arr)
        messages = marl.communicate(arr, coop_actions if coop_actions else final_actions)
        state_features = arr.reshape(-1)[: min(64, arr.size)]
        qmix_out = marl.train_step("qmix", uncertainty_map=arr, state_features=state_features)
        maddpg_out = marl.train_step("maddpg", uncertainty_map=arr, state_features=state_features)

        final_cell_set = set(final_cells)
        coop_cells = {(int(idx) // w, int(idx) % w) for idx in coop_actions}
        coop_overlap = float(len(final_cell_set & coop_cells) / max(1, len(final_cell_set)))
        comp_diversity = float(len(set(comp_actions)) / max(1, len(comp_actions)))

        flat = arr.reshape(-1)
        coop_gain = float(np.mean([flat[idx] for idx in coop_actions])) if coop_actions else 0.0
        final_gain = float(np.mean([flat[idx] for idx in final_actions])) if final_actions else 0.0

        return {
            "summary": {
                "applicable": True,
                "agent_count": n_agents,
                "cooperation_overlap_ratio": coop_overlap,
                "competition_diversity": comp_diversity,
                "collaboration_gain": float(coop_gain - final_gain),
            },
            "agent_messages": [
                {
                    "agent_id": int(msg.agent_id),
                    "suggested_action": int(msg.suggested_action),
                    "suggested_row": int(msg.suggested_action // w),
                    "suggested_col": int(msg.suggested_action % w),
                    "local_uncertainty": float(msg.local_uncertainty),
                }
                for msg in messages
            ],
            "cooperation_plan": [int(x) for x in coop_actions],
            "competition_plan": [int(x) for x in comp_actions],
            "coordination_training": {
                "qmix": {
                    "best_action": int(qmix_out.get("best_action", 0)),
                    "mixing_weights": [float(x) for x in np.asarray(qmix_out.get("mixing_weights", []), dtype=float).tolist()],
                },
                "maddpg": {
                    "mean_action": float(maddpg_out.get("mean_action", 0.0)),
                    "mean_gradient": float(maddpg_out.get("mean_gradient", 0.0)),
                },
            },
        }

    def _build_sampling_optimization_suggestions(
        self,
        *,
        recs: list[SamplingRecommendation],
        density_analysis: dict[str, Any],
        effect_evaluation: dict[str, Any],
    ) -> dict[str, Any]:
        summary_density = density_analysis.get("summary", {})
        summary_effect = effect_evaluation.get("summary", {})
        coverage_ratio = float(summary_density.get("coverage_ratio", 0.0))
        mean_density = float(summary_density.get("mean_density", 0.0))
        reduction_ratio = float(summary_effect.get("uncertainty_reduction_ratio", 0.0))
        quality_score = float(summary_effect.get("quality_score", 0.0))

        suggestions: list[dict[str, Any]] = []
        if coverage_ratio < 0.2:
            suggestions.append(
                {
                    "category": "coverage",
                    "priority": "high",
                    "title": "扩大采样覆盖范围",
                    "detail": "当前覆盖率偏低，建议在稀疏热点区域增加采样点以避免局部过拟合。",
                }
            )
        if mean_density > 0.9:
            suggestions.append(
                {
                    "category": "density_balance",
                    "priority": "medium",
                    "title": "控制局部采样密度",
                    "detail": "局部密度较高，建议降低密集区采样频率并向边缘高不确定性区域转移。",
                }
            )
        if reduction_ratio < 0.08:
            suggestions.append(
                {
                    "category": "effectiveness",
                    "priority": "high",
                    "title": "调整融合策略",
                    "detail": "当前预估降不确定性幅度有限，建议优先启用 hybrid 或 rule_only 进行对比。",
                }
            )
        if quality_score < 0.45:
            suggestions.append(
                {
                    "category": "model_feedback",
                    "priority": "medium",
                    "title": "提升策略学习稳定性",
                    "detail": "建议增加训练回合或扩展历史轨迹，提升策略网络在高不确定性区域的识别能力。",
                }
            )
        if not suggestions:
            suggestions.append(
                {
                    "category": "status",
                    "priority": "low",
                    "title": "维持当前采样计划",
                    "detail": "当前覆盖与效果表现稳定，可按现有推荐节奏持续采样并定期复评。",
                }
            )

        return {
            "summary": {
                "suggestion_count": int(len(suggestions)),
                "high_priority_count": int(sum(1 for s in suggestions if s["priority"] == "high")),
                "recommended_next_step": suggestions[0]["title"],
                "reference_points": int(len(recs)),
            },
            "suggestions": suggestions,
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
        region_visualization = self._build_sampling_region_visualization(
            recs=final,
            uncertainty_map=arr,
            boundary=boundary,
        )
        effect_evaluation = self._build_sampling_effect_evaluation(
            recs=final,
            uncertainty_map=arr,
            existing_points=existing_arr,
            boundary=boundary,
        )
        optimization_suggestions = self._build_sampling_optimization_suggestions(
            recs=final,
            density_analysis=density_analysis,
            effect_evaluation=effect_evaluation,
        )
        strategy_comparison_analysis = self._build_strategy_comparison_analysis(
            fusion_strategy=fusion_strategy,
            rl_recs=rl_recs,
            rule_recs=rule_recs,
            final_recs=final,
            uncertainty_map=arr,
            boundary=boundary,
        )
        sampling_efficiency_evaluation = self._build_sampling_efficiency_evaluation(
            recs=final,
            effect_evaluation=effect_evaluation,
            density_analysis=density_analysis,
        )
        long_term_value_prediction = self._build_long_term_value_prediction(
            recs=final,
            effect_evaluation=effect_evaluation,
        )
        policy_robustness_analysis = self._build_policy_robustness_analysis(
            final_recs=final,
            uncertainty_map=arr,
            boundary=boundary,
        )
        self._record_policy_history(
            fusion_strategy=fusion_strategy,
            rl_recs=rl_recs,
            rule_recs=rule_recs,
            final_recs=final,
            density_analysis=density_analysis,
            effect_evaluation=effect_evaluation,
            long_term_value_prediction=long_term_value_prediction,
            policy_robustness_analysis=policy_robustness_analysis,
        )
        policy_history_record = self._build_policy_history_record()
        policy_effect_prediction = self._build_policy_effect_prediction(
            sampling_efficiency_evaluation=sampling_efficiency_evaluation,
            long_term_value_prediction=long_term_value_prediction,
            policy_robustness_analysis=policy_robustness_analysis,
            policy_history_record=policy_history_record,
        )
        multi_agent_collaboration_analysis = self._build_multi_agent_collaboration_analysis(
            final_recs=final,
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
                "sampling_region_visualization": region_visualization,
                "sampling_effect_evaluation": effect_evaluation,
                "sampling_optimization_suggestions": optimization_suggestions,
                "strategy_comparison_analysis": strategy_comparison_analysis,
                "sampling_efficiency_evaluation": sampling_efficiency_evaluation,
                "long_term_value_prediction": long_term_value_prediction,
                "policy_robustness_analysis": policy_robustness_analysis,
                "policy_history_record": policy_history_record,
                "policy_effect_prediction": policy_effect_prediction,
                "multi_agent_collaboration_analysis": multi_agent_collaboration_analysis,
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
