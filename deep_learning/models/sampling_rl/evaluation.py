"""强化学习采样评估与对比。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np


@dataclass
class EvaluationMetrics:
    cumulative_reward: float
    uncertainty_reduction_rate: float
    prediction_accuracy_improvement: float
    sampling_efficiency: float
    convergence_speed: float


class SamplingRLEvaluator:
    """模型评估、可视化数据生成、基准与消融实验。"""

    def evaluate_metrics(
        self,
        reward_curve: list[float],
        uncertainty_before: np.ndarray,
        uncertainty_after: np.ndarray,
        baseline_error: float,
        current_error: float,
        n_samples: int,
    ) -> EvaluationMetrics:
        rewards = np.asarray(reward_curve, dtype=float)
        before = np.asarray(uncertainty_before, dtype=float)
        after = np.asarray(uncertainty_after, dtype=float)

        cumulative_reward = float(np.sum(rewards))
        reduction = float(np.mean(before) - np.mean(after))
        reduction_rate = float(reduction / (np.mean(before) + 1e-8))

        acc_improve = float((baseline_error - current_error) / (abs(baseline_error) + 1e-8))
        efficiency = float(reduction / max(1, n_samples))

        convergence_speed = self._convergence_speed(rewards)
        return EvaluationMetrics(
            cumulative_reward=cumulative_reward,
            uncertainty_reduction_rate=reduction_rate,
            prediction_accuracy_improvement=acc_improve,
            sampling_efficiency=efficiency,
            convergence_speed=convergence_speed,
        )

    def _convergence_speed(self, rewards: np.ndarray) -> float:
        if len(rewards) <= 2:
            return 0.0
        smooth = np.convolve(rewards, np.ones(3) / 3.0, mode="valid")
        peak = np.max(smooth)
        threshold = 0.9 * peak
        for i, val in enumerate(smooth):
            if val >= threshold:
                return float(i + 1)
        return float(len(smooth))

    def visualization_payload(self, env_render: dict[str, Any], attention_weights: np.ndarray | None = None) -> dict[str, Any]:
        return {
            "sampling_points": env_render.get("sample_points", []),
            "learning_curve": env_render.get("reward_curve", []),
            "uncertainty_map": env_render.get("uncertainty_map"),
            "policy_visualization": {
                "selected_points_count": len(env_render.get("sample_points", [])),
            },
            "attention_weights": None if attention_weights is None else np.asarray(attention_weights, dtype=float).tolist(),
        }

    def benchmark_against_baselines(
        self,
        runner: Callable[[str], dict[str, float]],
    ) -> dict[str, dict[str, float]]:
        baseline_names = ["random", "rule_based", "adaptive", "optimization", "rl"]
        result: dict[str, dict[str, float]] = {}
        for name in baseline_names:
            result[name] = runner(name)
        return result

    def ablation_study(
        self,
        runner: Callable[[dict[str, Any]], dict[str, float]],
        variants: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, float]]:
        outputs: dict[str, dict[str, float]] = {}
        for variant, params in variants.items():
            outputs[variant] = runner(params)
        return outputs

    def generate_report(
        self,
        model_name: str,
        metrics: EvaluationMetrics,
        benchmark: dict[str, dict[str, float]],
        ablation: dict[str, dict[str, float]],
    ) -> dict[str, Any]:
        lines = [
            f"# 强化学习采样评估报告 - {model_name}",
            "",
            "## 核心指标",
            f"- 累积奖励: {metrics.cumulative_reward:.4f}",
            f"- 不确定性减少率: {metrics.uncertainty_reduction_rate:.4f}",
            f"- 预测精度提升: {metrics.prediction_accuracy_improvement:.4f}",
            f"- 采样效率: {metrics.sampling_efficiency:.4f}",
            f"- 收敛速度: {metrics.convergence_speed:.2f}",
            "",
            "## 基准对比",
        ]

        for name, value in benchmark.items():
            lines.append(
                f"- {name}: reward={value.get('reward', 0.0):.4f}, reduction={value.get('uncertainty_reduction', 0.0):.4f}, efficiency={value.get('efficiency', 0.0):.4f}"
            )

        lines.append("")
        lines.append("## 消融实验")
        for name, value in ablation.items():
            lines.append(
                f"- {name}: reward={value.get('reward', 0.0):.4f}, reduction={value.get('uncertainty_reduction', 0.0):.4f}, entropy={value.get('entropy', 0.0):.4f}"
            )

        return {
            "markdown": "\n".join(lines),
            "metrics": {
                "cumulative_reward": metrics.cumulative_reward,
                "uncertainty_reduction_rate": metrics.uncertainty_reduction_rate,
                "prediction_accuracy_improvement": metrics.prediction_accuracy_improvement,
                "sampling_efficiency": metrics.sampling_efficiency,
                "convergence_speed": metrics.convergence_speed,
            },
            "benchmark": benchmark,
            "ablation": ablation,
        }
