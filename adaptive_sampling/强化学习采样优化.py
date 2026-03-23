"""自适应采样：强化学习优化桥接模块。"""

from __future__ import annotations

from typing import Any

import numpy as np

from deep_learning.models.sampling_rl import SamplingRLIntegrator


class RLSamplingOptimizer:
    """将阶段5 RL 采样能力集成到 adaptive_sampling。"""

    def __init__(self, model_name: str = "ppo") -> None:
        self.integrator = SamplingRLIntegrator(model_name=model_name)  # type: ignore[arg-type]

    def optimize(
        self,
        variance: np.ndarray,
        existing_points: np.ndarray | None = None,
        n_recommendations: int = 20,
        realtime: bool = True,
    ) -> dict[str, Any]:
        uncertainty = np.asarray(variance, dtype=float)
        points = np.asarray(existing_points, dtype=float) if existing_points is not None else None

        result = self.integrator.recommend(
            uncertainty_map=uncertainty,
            existing_points=points,
            n_recommendations=max(1, int(n_recommendations)),
            fusion_strategy="hybrid",
            realtime=realtime,
        )

        recs = result.get("recommendations", [])
        return {
            "strategy": "reinforcement_learning",
            "n_recommendations": len(recs),
            "recommendations": [
                {
                    "id": i + 1,
                    "x": float(item["x"]),
                    "y": float(item["y"]),
                    "score": float(item["score"]),
                    "source": item.get("source", "rl"),
                }
                for i, item in enumerate(recs)
            ],
            "training_summary": result.get("training_summary", {}),
        }
