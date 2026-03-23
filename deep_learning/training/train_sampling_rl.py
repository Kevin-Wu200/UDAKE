"""阶段5训练脚本：强化学习采样优化。"""

from __future__ import annotations

import argparse
import json

import numpy as np

from deep_learning.models.sampling_rl import SamplingRLIntegrator


def synthetic_uncertainty(size: int = 24, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    field = 0.5 + 0.3 * np.sin(xx * 4.0) + 0.2 * np.cos(yy * 5.0)
    noise = rng.normal(0.0, 0.05, size=(size, size))
    return np.clip(field + noise, 0.01, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="强化学习采样优化训练")
    parser.add_argument("--model", type=str, default="ppo", choices=["ppo", "dqn", "a2c", "a3c"])
    parser.add_argument("--episodes", type=int, default=30)
    parser.add_argument("--size", type=int, default=24)
    parser.add_argument("--budget", type=int, default=20)
    args = parser.parse_args()

    uncertainty = synthetic_uncertainty(size=args.size)
    integrator = SamplingRLIntegrator(model_name=args.model)
    train_result = integrator.train(
        uncertainty_map=uncertainty,
        existing_points=None,
        episodes=max(5, args.episodes),
        budget=max(8, args.budget),
    )
    print(json.dumps(train_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
