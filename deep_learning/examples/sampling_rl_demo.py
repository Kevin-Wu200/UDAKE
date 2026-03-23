"""强化学习采样优化示例。"""

from __future__ import annotations

import numpy as np

from deep_learning.models.sampling_rl import SamplingRLIntegrator


def main() -> None:
    rng = np.random.default_rng(123)
    uncertainty = np.clip(rng.normal(0.5, 0.2, size=(20, 20)), 0.01, 1.0)

    integrator = SamplingRLIntegrator(model_name="ppo", seed=123)
    train_result = integrator.train(uncertainty_map=uncertainty, episodes=12, budget=16)
    rec_result = integrator.recommend(uncertainty_map=uncertainty, n_recommendations=8, realtime=True)

    print("训练摘要:", train_result["summary"])
    print("推荐前3个点:", rec_result["recommendations"][:3])


if __name__ == "__main__":
    main()
