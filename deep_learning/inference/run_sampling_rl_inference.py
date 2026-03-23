"""阶段5推理脚本：实时采样推荐。"""

from __future__ import annotations

import argparse
import json

import numpy as np

from deep_learning.models.sampling_rl import SamplingRLIntegrator


def synthetic_uncertainty(size: int = 24, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    field = 0.5 + 0.25 * np.sin(xx * 3.0 + yy * 2.0) + 0.2 * np.cos(yy * 4.0)
    noise = rng.normal(0.0, 0.04, size=(size, size))
    return np.clip(field + noise, 0.01, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="强化学习采样优化推理")
    parser.add_argument("--model", type=str, default="ppo", choices=["ppo", "dqn", "a2c", "a3c"])
    parser.add_argument("--size", type=int, default=24)
    parser.add_argument("--n", type=int, default=12)
    parser.add_argument("--strategy", type=str, default="hybrid", choices=["rl_only", "rule_only", "hybrid"])
    args = parser.parse_args()

    uncertainty = synthetic_uncertainty(size=args.size)
    integrator = SamplingRLIntegrator(model_name=args.model)
    _ = integrator.train(uncertainty_map=uncertainty, episodes=20, budget=max(10, args.n * 2))

    result = integrator.recommend(
        uncertainty_map=uncertainty,
        n_recommendations=max(1, args.n),
        fusion_strategy=args.strategy,  # type: ignore[arg-type]
        realtime=True,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
