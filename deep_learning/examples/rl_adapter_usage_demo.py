"""强化学习模型解释适配器统一使用示例。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from deep_learning.models.sampling_rl import (
    ActorCriticAgent,
    DQNAgent,
    PPOAgent,
    SamplingEnv,
)
from services.backend.app.dl_services.a2c_rl_explainer import (
    A2CExplanationConfig,
    A2CLIMEAdapter,
    A2CSHAPAdapter,
)
from services.backend.app.dl_services.dqn_rl_explainer import (
    DQNExplanationConfig,
    DQNLIMEAdapter,
    DQNSHAPAdapter,
)
from services.backend.app.dl_services.ppo_rl_explainer import (
    PPOExplanationConfig,
    PPOLIMEAdapter,
    PPOSHAPAdapter,
)


def _build_uncertainty_map(size: int = 12, seed: int = 2026) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    base = 0.5 + 0.2 * np.sin(xx * 3.2) + 0.18 * np.cos(yy * 4.4)
    noise = rng.normal(0.0, 0.04, size=(size, size))
    return np.clip(base + noise, 0.01, 1.0)


def _build_observations(model_name: str, n: int = 16, seed: int = 2026) -> list[dict[str, np.ndarray]]:
    env = SamplingEnv(_build_uncertainty_map(seed=seed), action_mode="discrete", budget=12, max_steps=24)
    action_dim = env.h * env.w
    if model_name == "ppo":
        agent = PPOAgent(action_dim=action_dim, seed=seed + 1)
    elif model_name == "dqn":
        agent = DQNAgent(action_dim=action_dim, seed=seed + 1)
    elif model_name == "a2c":
        agent = ActorCriticAgent(action_dim=action_dim, seed=seed + 1)
    else:
        raise ValueError(f"不支持的模型: {model_name}")

    obs = env.reset()
    observations: list[dict[str, np.ndarray]] = [obs]
    for _ in range(max(1, n - 1)):
        if model_name == "ppo":
            action, _, _ = agent.select_action(obs, deterministic=False)
        elif model_name == "dqn":
            action = agent.select_action(obs, deterministic=False)
        else:
            action, _ = agent.select_action(obs, deterministic=False)
        next_obs, _, done, _ = env.step(action)
        observations.append(next_obs)
        obs = next_obs if not done else env.reset()
    return observations[:n]


def _extract_result(model_name: str, lime_out: dict[str, Any], shap_out: dict[str, Any]) -> dict[str, Any]:
    sample_count = (
        lime_out.get("summary", {}).get("sample_count")
        or lime_out.get("policy_network_explanation", {}).get("summary", {}).get("explained_samples")
        or lime_out.get("actor_network_explanation", {}).get("summary", {}).get("explained_samples")
        or lime_out.get("q_value_explanation", {}).get("summary", {}).get("explained_samples")
        or len(lime_out.get("batch_explanations", []))
    )
    lime_top = lime_out["summary"]["top_features"][0] if lime_out["summary"]["top_features"] else {}
    shap_top = shap_out["summary"]["top_features"][0] if shap_out["summary"]["top_features"] else {}
    return {
        "model": model_name.upper(),
        "sample_count": int(sample_count),
        "lime": {
            "explained_nodes": int(lime_out["summary"]["explained_nodes"]),
            "top_feature": str(lime_top.get("feature_name", "")),
            "duration_ms": float(
                lime_out.get("performance", {}).get("duration_ms", lime_out.get("performance", {}).get("latency_ms", 0.0))
            ),
            "cache_hit": bool(lime_out["performance"]["cache_hit"]),
        },
        "shap": {
            "explained_nodes": int(shap_out["summary"]["explained_nodes"]),
            "top_feature": str(shap_top.get("feature_name", "")),
            "duration_ms": float(
                shap_out.get("performance", {}).get("duration_ms", shap_out.get("performance", {}).get("latency_ms", 0.0))
            ),
            "backend": str(shap_out["explainer"].get("backend", "surrogate_linear")),
        },
    }


def main() -> None:
    top_k = 4
    max_explain_nodes = 6
    num_samples = 100
    nsamples = 90

    observations = _build_observations("ppo", n=16, seed=7)
    ppo_agent = PPOAgent(action_dim=12 * 12, seed=11)
    ppo_cfg = PPOExplanationConfig(lime_num_samples=120, shap_nsamples=100, random_state=42)
    ppo_lime = PPOLIMEAdapter(ppo_cfg).explain(
        model=ppo_agent,
        observations=observations,
        top_k=top_k,
        max_explain_nodes=max_explain_nodes,
        num_samples=num_samples,
    )
    ppo_shap = PPOSHAPAdapter(ppo_cfg).explain(
        model=ppo_agent,
        observations=observations,
        top_k=top_k,
        max_explain_nodes=max_explain_nodes,
        nsamples=nsamples,
    )

    observations = _build_observations("dqn", n=16, seed=13)
    dqn_agent = DQNAgent(action_dim=12 * 12, seed=17)
    dqn_cfg = DQNExplanationConfig(lime_num_samples=120, shap_nsamples=100, random_state=42)
    dqn_lime = DQNLIMEAdapter(dqn_cfg).explain(
        model=dqn_agent,
        observations=observations,
        top_k=top_k,
        max_explain_nodes=max_explain_nodes,
        num_samples=num_samples,
    )
    dqn_shap = DQNSHAPAdapter(dqn_cfg).explain(
        model=dqn_agent,
        observations=observations,
        top_k=top_k,
        max_explain_nodes=max_explain_nodes,
        nsamples=nsamples,
    )

    observations = _build_observations("a2c", n=16, seed=19)
    a2c_agent = ActorCriticAgent(action_dim=12 * 12, seed=23)
    a2c_cfg = A2CExplanationConfig(lime_num_samples=120, shap_nsamples=100, random_state=42)
    a2c_lime = A2CLIMEAdapter(a2c_cfg).explain(
        model=a2c_agent,
        observations=observations,
        top_k=top_k,
        max_explain_nodes=max_explain_nodes,
        num_samples=num_samples,
    )
    a2c_shap = A2CSHAPAdapter(a2c_cfg).explain(
        model=a2c_agent,
        observations=observations,
        top_k=top_k,
        max_explain_nodes=max_explain_nodes,
        nsamples=nsamples,
    )

    result = {
        "adapter_usage_examples": [
            _extract_result("ppo", ppo_lime, ppo_shap),
            _extract_result("dqn", dqn_lime, dqn_shap),
            _extract_result("a2c", a2c_lime, a2c_shap),
        ]
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
