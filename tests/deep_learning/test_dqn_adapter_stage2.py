from __future__ import annotations

import numpy as np

from deep_learning.models.sampling_rl import DQNAgent, SamplingEnv
from services.backend.app.dl_services.dqn_rl_explainer import DQNLIMEAdapter, DQNSHAPAdapter


def _uncertainty_map(size: int = 10, seed: int = 71) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    base = 0.48 + 0.26 * np.sin(xx * 3.2) + 0.18 * np.cos(yy * 4.2)
    noise = rng.normal(0.0, 0.04, size=(size, size))
    return np.clip(base + noise, 0.01, 1.0)


def _build_observations(n: int = 18) -> list[dict[str, np.ndarray]]:
    env = SamplingEnv(_uncertainty_map(), action_mode="discrete", budget=12, max_steps=24)
    agent = DQNAgent(action_dim=env.h * env.w, seed=79)
    obs = env.reset()
    observations: list[dict[str, np.ndarray]] = [obs]
    for _ in range(max(1, n - 1)):
        action = agent.select_action(obs, deterministic=False)
        next_obs, _, done, _ = env.step(action)
        observations.append(next_obs)
        obs = next_obs if not done else env.reset()
    return observations[:n]


def _assert_stage2_payload(payload: dict) -> None:
    assert "q_value_explanation" in payload
    assert "action_value_analysis" in payload
    assert "exploration_exploitation_analysis" in payload

    q_value = payload["q_value_explanation"]
    assert q_value["summary"]["network"] == "q_value"
    assert q_value["summary"]["explained_samples"] >= 1
    assert len(q_value["summary"]["top_features"]) >= 1
    assert "q_value_distribution" in q_value
    assert len(q_value["node_q_value_analysis"]) >= 1

    action_value = payload["action_value_analysis"]
    assert action_value["summary"]["network"] == "action_value"
    assert action_value["summary"]["explained_samples"] >= 1
    assert len(action_value["top_actions"]) >= 1
    assert len(action_value["node_action_value_analysis"]) >= 1

    explore = payload["exploration_exploitation_analysis"]
    assert "summary" in explore
    assert "mode" in explore["summary"]
    assert explore["summary"]["sample_count"] >= 1
    assert "exploration_signals" in explore
    assert "action_preference" in explore


def test_dqn_lime_stage2_qvalue_actionvalue_and_exploration_analysis() -> None:
    observations = _build_observations(n=16)
    agent = DQNAgent(action_dim=100, seed=83)
    adapter = DQNLIMEAdapter()
    out = adapter.explain(model=agent, observations=observations, top_k=4, max_explain_nodes=6, num_samples=120)

    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 6
    assert out["performance"]["sample_count"] == 16
    assert out["performance"]["feature_dim"] >= 1
    assert out["performance"]["action_dim"] == 100
    _assert_stage2_payload(out)


def test_dqn_shap_stage2_qvalue_actionvalue_and_exploration_analysis_with_cache() -> None:
    observations = _build_observations(n=16)
    agent = DQNAgent(action_dim=100, seed=89)
    adapter = DQNSHAPAdapter()
    first = adapter.explain(model=agent, observations=observations, top_k=4, max_explain_nodes=6, nsamples=90)
    second = adapter.explain(model=agent, observations=observations, top_k=4, max_explain_nodes=6, nsamples=90)

    assert first["summary"]["method"] == "shap"
    assert first["summary"]["explained_nodes"] == 6
    assert first["summary"]["nsamples"] == 90
    assert first["performance"]["sample_count"] == 16
    assert first["performance"]["feature_dim"] >= 1
    assert first["performance"]["action_dim"] == 100
    _assert_stage2_payload(first)

    assert second["performance"]["cache_hit"] is True
