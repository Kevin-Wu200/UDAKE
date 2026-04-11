from __future__ import annotations

import numpy as np

from deep_learning.models.sampling_rl import ActorCriticAgent, DQNAgent, PPOAgent, SamplingEnv
from services.backend.app.dl_services.a2c_rl_explainer import A2CExplanationConfig, A2CLIMEAdapter
from services.backend.app.dl_services.dqn_rl_explainer import DQNExplanationConfig, DQNLIMEAdapter
from services.backend.app.dl_services.ppo_rl_explainer import PPOExplanationConfig, PPOLIMEAdapter


def _uncertainty_map(size: int = 10, seed: int = 211) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    base = 0.5 + 0.24 * np.sin(xx * 3.3) + 0.19 * np.cos(yy * 4.4)
    noise = rng.normal(0.0, 0.035, size=(size, size))
    return np.clip(base + noise, 0.01, 1.0)


def _build_observations(n: int = 18, seed: int = 223) -> list[dict[str, np.ndarray]]:
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


def _shift_observations(observations: list[dict[str, np.ndarray]], delta: float = 0.07) -> list[dict[str, np.ndarray]]:
    mutated: list[dict[str, np.ndarray]] = []
    for i, obs in enumerate(observations):
        copied: dict[str, np.ndarray] = {}
        for k, v in obs.items():
            arr = np.asarray(v, dtype=float).copy()
            if i == 0 and arr.size > 0:
                arr = arr + delta
            copied[k] = arr
        mutated.append(copied)
    return mutated


def test_rl_adapter_batch_explain_memory_and_cache_metrics_stage2() -> None:
    observations = _build_observations(n=18, seed=227)

    ppo = PPOLIMEAdapter(PPOExplanationConfig(batch_explain_chunk_size=2))
    ppo_out = ppo.explain(
        model=PPOAgent(action_dim=100, seed=229),
        observations=observations,
        top_k=4,
        max_explain_nodes=7,
        num_samples=90,
    )
    ppo_perf = ppo_out["performance"]
    assert ppo_out["summary"]["explained_nodes"] == 7
    assert ppo_perf["batch_chunk_size"] == 2
    assert ppo_perf["batch_count"] == 4
    assert ppo_perf["context_memory_bytes"] > 0
    assert ppo_perf["result_memory_bytes"] > 0
    assert isinstance(ppo_perf["result_cache_key"], str) and len(ppo_perf["result_cache_key"]) == 16

    dqn = DQNLIMEAdapter(DQNExplanationConfig(batch_explain_chunk_size=3))
    dqn_out = dqn.explain(
        model=DQNAgent(action_dim=100, seed=233),
        observations=observations,
        top_k=4,
        max_explain_nodes=7,
        num_samples=90,
    )
    dqn_perf = dqn_out["performance"]
    assert dqn_out["summary"]["explained_nodes"] == 7
    assert dqn_perf["batch_chunk_size"] == 3
    assert dqn_perf["batch_count"] == 3
    assert dqn_perf["context_memory_bytes"] > 0
    assert dqn_perf["result_memory_bytes"] > 0

    a2c = A2CLIMEAdapter(A2CExplanationConfig(batch_explain_chunk_size=4))
    a2c_out = a2c.explain(
        model=ActorCriticAgent(action_dim=100, seed=239),
        observations=observations,
        top_k=4,
        max_explain_nodes=7,
        num_samples=90,
    )
    a2c_perf = a2c_out["performance"]
    assert a2c_out["summary"]["explained_nodes"] == 7
    assert a2c_perf["batch_chunk_size"] == 4
    assert a2c_perf["batch_count"] == 2
    assert a2c_perf["context_memory_bytes"] > 0
    assert a2c_perf["result_memory_bytes"] > 0


def test_rl_adapter_result_cache_key_tracks_observation_content_stage2() -> None:
    observations = _build_observations(n=16, seed=241)
    shifted = _shift_observations(observations, delta=0.05)

    ppo_adapter = PPOLIMEAdapter(PPOExplanationConfig(batch_explain_chunk_size=2))
    ppo_model = PPOAgent(action_dim=100, seed=251)
    ppo_first = ppo_adapter.explain(model=ppo_model, observations=observations, top_k=4, max_explain_nodes=6, num_samples=80)
    ppo_second_same = ppo_adapter.explain(model=ppo_model, observations=observations, top_k=4, max_explain_nodes=6, num_samples=80)
    ppo_shifted = ppo_adapter.explain(model=ppo_model, observations=shifted, top_k=4, max_explain_nodes=6, num_samples=80)
    assert ppo_second_same["performance"]["cache_hit"] is True
    assert ppo_first["performance"]["result_cache_key"] == ppo_second_same["performance"]["result_cache_key"]
    assert ppo_shifted["performance"]["cache_hit"] is False
    assert ppo_first["performance"]["result_cache_key"] != ppo_shifted["performance"]["result_cache_key"]

    dqn_adapter = DQNLIMEAdapter(DQNExplanationConfig(batch_explain_chunk_size=2))
    dqn_model = DQNAgent(action_dim=100, seed=257)
    dqn_first = dqn_adapter.explain(model=dqn_model, observations=observations, top_k=4, max_explain_nodes=6, num_samples=80)
    dqn_shifted = dqn_adapter.explain(model=dqn_model, observations=shifted, top_k=4, max_explain_nodes=6, num_samples=80)
    assert dqn_first["performance"]["cache_hit"] is False
    assert dqn_shifted["performance"]["cache_hit"] is False
    assert dqn_first["performance"]["result_cache_key"] != dqn_shifted["performance"]["result_cache_key"]

    a2c_adapter = A2CLIMEAdapter(A2CExplanationConfig(batch_explain_chunk_size=2))
    a2c_model = ActorCriticAgent(action_dim=100, seed=263)
    a2c_first = a2c_adapter.explain(model=a2c_model, observations=observations, top_k=4, max_explain_nodes=6, num_samples=80)
    a2c_shifted = a2c_adapter.explain(model=a2c_model, observations=shifted, top_k=4, max_explain_nodes=6, num_samples=80)
    assert a2c_first["performance"]["cache_hit"] is False
    assert a2c_shifted["performance"]["cache_hit"] is False
    assert a2c_first["performance"]["result_cache_key"] != a2c_shifted["performance"]["result_cache_key"]
