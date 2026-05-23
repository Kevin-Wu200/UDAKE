from __future__ import annotations

import numpy as np

from deep_learning.models.sampling_rl import PPOAgent, SamplingEnv
from services.backend.app.dl_services.ppo_rl_explainer import (
    PPOLIMEAdapter,
    PPOSHAPAdapter,
)


def _uncertainty_map(size: int = 10, seed: int = 41) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    base = 0.52 + 0.23 * np.sin(xx * 2.9) + 0.21 * np.cos(yy * 4.5)
    noise = rng.normal(0.0, 0.03, size=(size, size))
    return np.clip(base + noise, 0.01, 1.0)


def _build_observations(n: int = 18) -> list[dict[str, np.ndarray]]:
    env = SamplingEnv(_uncertainty_map(), action_mode="discrete", budget=12, max_steps=24)
    agent = PPOAgent(action_dim=env.h * env.w, seed=29)
    obs = env.reset()
    observations: list[dict[str, np.ndarray]] = [obs]
    for _ in range(max(1, n - 1)):
        action, _, _ = agent.select_action(obs, deterministic=False)
        next_obs, _, done, _ = env.step(action)
        observations.append(next_obs)
        obs = next_obs if not done else env.reset()
    return observations[:n]


def _assert_policy_and_value(payload: dict) -> None:
    assert "policy_network_explanation" in payload
    assert "value_network_explanation" in payload

    policy = payload["policy_network_explanation"]
    assert policy["summary"]["network"] == "policy"
    assert policy["summary"]["explained_samples"] >= 1
    assert len(policy["summary"]["top_features"]) >= 1
    assert "action_distribution" in policy
    assert policy["action_distribution"]["total_actions"] >= 1
    assert "policy_confidence" in policy

    value = payload["value_network_explanation"]
    assert value["summary"]["network"] == "value"
    assert value["summary"]["explained_samples"] >= 1
    assert len(value["summary"]["top_features"]) >= 1
    assert len(value["high_value_states"]) >= 1
    assert len(value["node_value_analysis"]) >= 1


def test_ppo_lime_stage2_policy_and_value_network_explanations() -> None:
    observations = _build_observations(n=16)
    agent = PPOAgent(action_dim=100, seed=53)
    adapter = PPOLIMEAdapter()
    out = adapter.explain(model=agent, observations=observations, top_k=4, max_explain_nodes=6, num_samples=120)

    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 6
    _assert_policy_and_value(out)


def test_ppo_shap_stage2_policy_and_value_network_explanations() -> None:
    observations = _build_observations(n=16)
    agent = PPOAgent(action_dim=100, seed=61)
    adapter = PPOSHAPAdapter()
    out = adapter.explain(model=agent, observations=observations, top_k=4, max_explain_nodes=6, nsamples=90)

    assert out["summary"]["method"] == "shap"
    assert out["summary"]["explained_nodes"] == 6
    assert out["summary"]["nsamples"] == 90
    _assert_policy_and_value(out)
