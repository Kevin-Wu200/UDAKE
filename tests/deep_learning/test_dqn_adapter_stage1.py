from __future__ import annotations

import numpy as np

from deep_learning.models.sampling_rl import DQNAgent, SamplingEnv
from services.backend.app.dl_services.dqn_rl_explainer import DQNLIMEAdapter, DQNSHAPAdapter


def _uncertainty_map(size: int = 10, seed: int = 27) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    base = 0.5 + 0.25 * np.sin(xx * 3.0) + 0.2 * np.cos(yy * 4.1)
    noise = rng.normal(0.0, 0.04, size=(size, size))
    return np.clip(base + noise, 0.01, 1.0)


def _build_observations(n: int = 18) -> list[dict[str, np.ndarray]]:
    env = SamplingEnv(_uncertainty_map(), action_mode="discrete", budget=12, max_steps=24)
    agent = DQNAgent(action_dim=env.h * env.w, seed=37)
    obs = env.reset()
    observations: list[dict[str, np.ndarray]] = [obs]
    for _ in range(max(1, n - 1)):
        action = agent.select_action(obs, deterministic=False)
        next_obs, _, done, _ = env.step(action)
        observations.append(next_obs)
        obs = next_obs if not done else env.reset()
    return observations[:n]


def test_dqn_preprocess_predict_and_lime_shap_adapters() -> None:
    observations = _build_observations(n=16)
    agent = DQNAgent(action_dim=100, seed=43)

    pre = agent.preprocess_dqn_data(observations, use_training_stats=True)
    processed = np.asarray(pre["processed_features"], dtype=float)
    assert processed.shape[0] == 16
    assert processed.shape[1] >= 10
    assert len(pre["feature_names"]) == processed.shape[1]
    assert pre["validation"]["is_valid"] is True

    pred = agent.predict_dqn(observations, deterministic=True)
    assert len(pred["action_indices"]) == 16
    assert len(pred["selected_q_values"]) == 16
    assert len(pred["max_q_values"]) == 16
    assert len(pred["q_values"]) == 16
    assert "preprocess" in pred

    lime_adapter = DQNLIMEAdapter()
    lime_out = lime_adapter.explain(
        model=agent,
        observations=observations,
        top_k=4,
        max_explain_nodes=6,
        num_samples=100,
    )
    assert lime_out["summary"]["method"] == "lime"
    assert lime_out["summary"]["explained_nodes"] == 6
    assert len(lime_out["global_feature_importance"]) >= 1
    assert "scaler" in lime_out["preprocess"]
    assert "validation" in lime_out["preprocess"]

    shap_adapter = DQNSHAPAdapter()
    shap_out = shap_adapter.explain(
        model=agent,
        observations=observations,
        top_k=4,
        max_explain_nodes=6,
        nsamples=90,
    )
    assert shap_out["summary"]["method"] == "shap"
    assert shap_out["summary"]["explained_nodes"] == 6
    assert shap_out["summary"]["nsamples"] == 90
    assert len(shap_out["global_feature_importance"]) >= 1
    assert "backend" in shap_out["explainer"]
