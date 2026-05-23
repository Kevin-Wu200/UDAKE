from __future__ import annotations

import numpy as np

from deep_learning.models.sampling_rl import ActorCriticAgent, SamplingEnv
from services.backend.app.dl_services.a2c_rl_explainer import (
    A2CLIMEAdapter,
    A2CSHAPAdapter,
)


def _uncertainty_map(size: int = 10, seed: int = 73) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    base = 0.5 + 0.22 * np.sin(xx * 3.0) + 0.19 * np.cos(yy * 4.0)
    noise = rng.normal(0.0, 0.04, size=(size, size))
    return np.clip(base + noise, 0.01, 1.0)


def _build_observations(n: int = 18) -> list[dict[str, np.ndarray]]:
    env = SamplingEnv(_uncertainty_map(), action_mode="discrete", budget=12, max_steps=24)
    agent = ActorCriticAgent(action_dim=env.h * env.w, seed=91)
    obs = env.reset()
    observations: list[dict[str, np.ndarray]] = [obs]
    for _ in range(max(1, n - 1)):
        action, _ = agent.select_action(obs, deterministic=False)
        next_obs, _, done, _ = env.step(action)
        observations.append(next_obs)
        obs = next_obs if not done else env.reset()
    return observations[:n]


def _assert_stage2_payload(payload: dict) -> None:
    assert "actor_network_explanation" in payload
    assert "critic_network_explanation" in payload
    assert "policy_gradient_analysis" in payload

    actor = payload["actor_network_explanation"]
    assert actor["summary"]["network"] == "actor"
    assert actor["summary"]["explained_samples"] >= 1
    assert len(actor["summary"]["top_features"]) >= 1
    assert "action_distribution" in actor
    assert actor["action_distribution"]["total_actions"] >= 1
    assert "policy_confidence" in actor

    critic = payload["critic_network_explanation"]
    assert critic["summary"]["network"] == "critic"
    assert critic["summary"]["explained_samples"] >= 1
    assert len(critic["summary"]["top_features"]) >= 1
    assert len(critic["high_value_states"]) >= 1
    assert len(critic["node_value_analysis"]) >= 1

    policy_gradient = payload["policy_gradient_analysis"]
    assert policy_gradient["summary"]["analysis"] == "policy_gradient"
    assert policy_gradient["summary"]["sample_count"] >= 1
    assert len(policy_gradient["summary"]["top_features"]) >= 1
    assert "signals" in policy_gradient
    assert "node_gradient_analysis" in policy_gradient
    assert len(policy_gradient["node_gradient_analysis"]) >= 1


def test_a2c_lime_stage2_actor_critic_and_policy_gradient_analysis() -> None:
    observations = _build_observations(n=16)
    agent = ActorCriticAgent(action_dim=100, seed=101)
    adapter = A2CLIMEAdapter()
    out = adapter.explain(model=agent, observations=observations, top_k=4, max_explain_nodes=6, num_samples=120)

    assert out["summary"]["method"] == "lime"
    assert out["summary"]["explained_nodes"] == 6
    assert out["performance"]["sample_count"] == 16
    assert out["performance"]["feature_dim"] >= 1
    assert out["performance"]["action_dim"] == 100
    _assert_stage2_payload(out)


def test_a2c_shap_stage2_actor_critic_and_policy_gradient_analysis_with_cache() -> None:
    observations = _build_observations(n=16)
    agent = ActorCriticAgent(action_dim=100, seed=103)
    adapter = A2CSHAPAdapter()
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
