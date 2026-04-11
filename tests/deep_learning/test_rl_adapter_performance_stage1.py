from __future__ import annotations

import numpy as np

from deep_learning.models.sampling_rl import ActorCriticAgent, DQNAgent, PPOAgent, SamplingEnv
from services.backend.app.dl_services.a2c_rl_explainer import A2CLIMEAdapter
from services.backend.app.dl_services.dqn_rl_explainer import DQNLIMEAdapter
from services.backend.app.dl_services.ppo_rl_explainer import PPOLIMEAdapter


def _uncertainty_map(size: int = 10, seed: int = 131) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    base = 0.5 + 0.24 * np.sin(xx * 3.1) + 0.2 * np.cos(yy * 4.2)
    noise = rng.normal(0.0, 0.04, size=(size, size))
    return np.clip(base + noise, 0.01, 1.0)


def _build_observations(n: int = 16, seed: int = 137) -> list[dict[str, np.ndarray]]:
    env = SamplingEnv(_uncertainty_map(seed=seed), action_mode="discrete", budget=12, max_steps=24)
    agent = PPOAgent(action_dim=env.h * env.w, seed=seed + 1)
    obs = env.reset()
    observations: list[dict[str, np.ndarray]] = [obs]
    for _ in range(max(1, n - 1)):
        action, _, _ = agent.select_action(obs, deterministic=False)
        next_obs, _, done, _ = env.step(action)
        observations.append(next_obs)
        obs = next_obs if not done else env.reset()
    return observations[:n]


def _assert_predict_cache_and_inference_time(perf_first: dict, perf_second: dict) -> None:
    assert perf_first["cache_hit"] is False
    assert perf_second["cache_hit"] is True
    assert perf_first["policy_inference_ms"] >= 0.0
    assert perf_first["value_inference_ms"] >= 0.0
    assert perf_first["latency_ms"] < 15000.0


def test_rl_model_predict_cache_stage1() -> None:
    observations = _build_observations(n=16)

    ppo = PPOAgent(action_dim=100, seed=151)
    ppo_first = ppo.predict_ppo(observations, deterministic=True)
    ppo_second = ppo.predict_ppo(observations, deterministic=True)
    _assert_predict_cache_and_inference_time(ppo_first["performance"], ppo_second["performance"])

    dqn = DQNAgent(action_dim=100, seed=157)
    dqn_first = dqn.predict_dqn(observations, deterministic=True)
    dqn_second = dqn.predict_dqn(observations, deterministic=True)
    _assert_predict_cache_and_inference_time(dqn_first["performance"], dqn_second["performance"])

    a2c = ActorCriticAgent(action_dim=100, seed=163)
    a2c_first = a2c.predict_a2c(observations, deterministic=True)
    a2c_second = a2c.predict_a2c(observations, deterministic=True)
    _assert_predict_cache_and_inference_time(a2c_first["performance"], a2c_second["performance"])


def test_rl_adapter_latency_target_stage1() -> None:
    observations = _build_observations(n=16, seed=173)

    ppo_out = PPOLIMEAdapter().explain(
        model=PPOAgent(action_dim=100, seed=179),
        observations=observations,
        top_k=4,
        max_explain_nodes=6,
        num_samples=80,
    )
    assert ppo_out["performance"]["latency_target_ms"] == 15000.0
    assert ppo_out["performance"]["meets_latency_target"] is True

    dqn_out = DQNLIMEAdapter().explain(
        model=DQNAgent(action_dim=100, seed=181),
        observations=observations,
        top_k=4,
        max_explain_nodes=6,
        num_samples=80,
    )
    assert dqn_out["performance"]["latency_target_ms"] == 15000.0
    assert dqn_out["performance"]["meets_latency_target"] is True

    a2c_out = A2CLIMEAdapter().explain(
        model=ActorCriticAgent(action_dim=100, seed=191),
        observations=observations,
        top_k=4,
        max_explain_nodes=6,
        num_samples=80,
    )
    assert a2c_out["performance"]["latency_target_ms"] == 15000.0
    assert a2c_out["performance"]["meets_latency_target"] is True
