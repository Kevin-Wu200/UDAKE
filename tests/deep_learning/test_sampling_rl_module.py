from __future__ import annotations

import numpy as np

from adaptive_sampling.采样点推荐生成 import SamplingRecommender
from deep_learning.models.sampling_rl import (
    ActorCriticAgent,
    AdaptiveStrategyController,
    BatchOptimizer,
    DQNAgent,
    GPUAccelerator,
    HyperparameterOptimizer,
    InferenceAccelerator,
    MemoryOptimizer,
    MultiAgentSamplingSystem,
    OnlineSamplingLearner,
    PPOAgent,
    SamplingEnv,
    SamplingFeatureEngineer,
    SamplingRLIntegrator,
    SamplingRLEvaluator,
    SamplingRLTrainingConfig,
    TransferMetaLearner,
    train_agent,
)


def _uncertainty_map(size: int = 14, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, size)
    y = np.linspace(0.0, 1.0, size)
    xx, yy = np.meshgrid(x, y)
    base = 0.45 + 0.3 * np.sin(xx * 3.2) + 0.2 * np.cos(yy * 4.1)
    noise = rng.normal(0.0, 0.04, size=(size, size))
    return np.clip(base + noise, 0.01, 1.0)


def test_sampling_env_and_features() -> None:
    umap = _uncertainty_map()
    env = SamplingEnv(umap, action_mode="hybrid", budget=12, max_steps=20)

    obs = env.reset()
    assert "uncertainty_map" in obs
    assert obs["uncertainty_map"].shape == umap.shape

    step_out = env.step({"position": [0.4, 0.6], "sample_count": 2})
    next_obs, reward, done, info = step_out
    assert isinstance(reward, float)
    assert "reward_breakdown" in info
    assert next_obs["sampling_distribution"].shape == umap.shape

    render = env.render()
    assert "reward_curve" in render

    feat = SamplingFeatureEngineer()
    points = np.array([[0.2, 0.2], [0.4, 0.6], [0.8, 0.5]], dtype=float)
    spatial = feat.spatial_features(points, boundary=(0.0, 1.0, 0.0, 1.0))
    uncertainty = feat.uncertainty_features(umap)
    topo = feat.topology_features(points, k=2)
    state_feat = feat.state_space_features(obs)
    action_feat = feat.action_space_features({"position": [0.4, 0.6], "sample_count": 2}, env.action_space)
    policy_feat = feat.policy_network_features(action_probs=np.array([0.2, 0.3, 0.5]), selected_action=2, action_mode="hybrid")
    value_feat = feat.value_network_features(state_value=0.4, next_state_value=0.5, reward=0.2)
    reward_feat = feat.reward_function_features(info["reward_breakdown"], reward_weights=env.reward_composer.weights)
    reward_decomp = feat.decompose_reward(info["reward_breakdown"], reward_weights=env.reward_composer.weights)
    state_action_bundle = feat.extract_state_action_features(obs, {"position": [0.4, 0.6], "sample_count": 2}, env.action_space)
    name_map = feat.feature_name_mapping()

    assert spatial.shape[0] == 3
    assert uncertainty.shape[1] == 4
    assert topo.adjacency.shape == (3, 3)
    assert state_feat.shape[0] == len(feat.STATE_FEATURE_NAMES)
    assert action_feat.shape[0] == len(feat.ACTION_FEATURE_NAMES)
    assert policy_feat.shape[0] == len(feat.POLICY_FEATURE_NAMES)
    assert value_feat.shape[0] == len(feat.VALUE_FEATURE_NAMES)
    assert reward_feat.shape[0] == len(feat.REWARD_FEATURE_NAMES)
    assert reward_decomp.total_reward == reward_decomp.weighted_components["raw_total_reward"]
    assert state_action_bundle.feature_vector.shape[0] == len(state_action_bundle.feature_names)
    assert state_action_bundle.state_feature_count == len(feat.STATE_FEATURE_NAMES)
    assert "state.mean_uncertainty" in name_map


def test_ppo_dqn_a2c_training_cycle() -> None:
    umap = _uncertainty_map(size=12)

    env_ppo = SamplingEnv(umap, action_mode="discrete", budget=10, max_steps=16)
    ppo = PPOAgent(action_dim=env_ppo.h * env_ppo.w, seed=7)
    ppo_result = train_agent(
        env_ppo,
        ppo,
        SamplingRLTrainingConfig(model_name="ppo", episodes=6, max_steps_per_episode=10),
    )
    assert ppo_result["summary"]["episodes"] >= 1

    env_dqn = SamplingEnv(umap, action_mode="discrete", budget=10, max_steps=16)
    dqn = DQNAgent(action_dim=env_dqn.h * env_dqn.w, seed=8)
    dqn_result = train_agent(
        env_dqn,
        dqn,
        SamplingRLTrainingConfig(model_name="dqn", episodes=6, max_steps_per_episode=10),
    )
    assert dqn_result["summary"]["episodes"] >= 1

    env_a2c = SamplingEnv(umap, action_mode="discrete", budget=10, max_steps=16)
    a2c = ActorCriticAgent(action_dim=env_a2c.h * env_a2c.w, seed=9)
    a2c_result = train_agent(
        env_a2c,
        a2c,
        SamplingRLTrainingConfig(model_name="a2c", episodes=6, max_steps_per_episode=10),
    )
    assert a2c_result["summary"]["episodes"] >= 1


def test_marl_evaluator_and_online_learning() -> None:
    umap = _uncertainty_map(size=10)

    marl = MultiAgentSamplingSystem(n_agents=3, seed=3)
    coop = marl.cooperative_strategy(umap)
    comp = marl.competitive_strategy(umap)
    msg = marl.communicate(umap, coop)
    qmix = marl.train_step("qmix", uncertainty_map=umap, state_features=umap.reshape(-1)[:16])
    maddpg = marl.train_step("maddpg", uncertainty_map=umap, state_features=umap.reshape(-1)[:16])

    assert len(coop) == 3
    assert len(comp) == 3
    assert len(msg) == 3
    assert qmix["mode"] == "qmix"
    assert maddpg["mode"] == "maddpg"

    env = SamplingEnv(umap, action_mode="discrete", budget=8)
    agent = PPOAgent(action_dim=env.h * env.w, seed=11)
    _ = train_agent(env, agent, SamplingRLTrainingConfig(model_name="ppo", episodes=5, max_steps_per_episode=8))

    learner = OnlineSamplingLearner()
    obs = env.reset()
    action, logp, value = agent.select_action(obs)
    next_obs, reward, done, _ = env.step(action)
    online_res = learner.incremental_update(
        agent,
        transitions=[
            {
                "observation": obs,
                "action": action,
                "reward": reward,
                "done": done,
                "log_prob": logp,
                "value": value,
            }
        ],
    )
    assert online_res.updated_steps == 1

    controller = AdaptiveStrategyController()
    weights = controller.adjust_reward_weights(
        {"uncertainty_reduction": 0.5, "sampling_cost": 0.2, "accuracy_improvement": 0.3},
        {"uncertainty_reduction": 0.01, "efficiency": 0.01},
    )
    assert abs(sum(weights.values()) - 1.0) < 1e-6

    transfer = TransferMetaLearner()
    pretrain = transfer.pretrain_on_sources(agent, [env], episodes_per_env=2)
    adapt = transfer.maml_fast_adapt(agent, env, inner_steps=2, outer_loops=2)
    assert pretrain["source_envs"] == 1
    assert adapt["outer_loops"] == 2

    evaluator = SamplingRLEvaluator()
    metrics = evaluator.evaluate_metrics(
        reward_curve=[0.1, 0.2, 0.3],
        uncertainty_before=umap,
        uncertainty_after=np.clip(umap * 0.8, 0.01, 1.0),
        baseline_error=0.5,
        current_error=0.35,
        n_samples=6,
    )
    report = evaluator.generate_report(
        "ppo",
        metrics,
        benchmark={"rl": {"reward": 1.0, "uncertainty_reduction": 0.2, "efficiency": 0.03}},
        ablation={"no_entropy": {"reward": 0.8, "uncertainty_reduction": 0.15, "entropy": 0.0}},
    )
    assert metrics.cumulative_reward > 0
    assert "markdown" in report


def test_integration_and_optimization_helpers() -> None:
    umap = _uncertainty_map(size=12)
    integrator = SamplingRLIntegrator(model_name="ppo", seed=17)

    train_result = integrator.train(umap, episodes=8, budget=12)
    recommend = integrator.recommend(umap, n_recommendations=6, fusion_strategy="hybrid", realtime=True)
    optimized = integrator.optimize_strategy(umap)

    assert train_result["summary"]["episodes"] >= 1
    assert len(recommend["recommendations"]) >= 1
    assert "explanations" in recommend
    assert "policy_decision" in recommend["explanations"]
    assert "action_value_visualization" in recommend["explanations"]
    assert "sampling_point_recommendation" in recommend["explanations"]
    assert "sampling_density_analysis" in recommend["explanations"]
    assert "summary" in recommend["explanations"]["policy_decision"]
    assert "action_value_points" in recommend["explanations"]["action_value_visualization"]
    assert "point_explanations" in recommend["explanations"]["sampling_point_recommendation"]
    assert "sparse_hotspots" in recommend["explanations"]["sampling_density_analysis"]
    assert optimized["best_strategy"] in {"rl_only", "rule_only", "hybrid"}

    batch_opt = BatchOptimizer().suggest(sample_count=256, feature_dim=32, memory_budget_mb=16)
    mem_opt = MemoryOptimizer().compress(umap)
    dedup = MemoryOptimizer().deduplicate_points(np.array([[0.1, 0.2], [0.1, 0.2], [0.3, 0.4]]))

    gpu = GPUAccelerator().info()
    infer = InferenceAccelerator(cache_size=16)
    pred1 = infer.predict(np.array([1.0, 2.0]), lambda x: float(np.sum(x)))
    pred2 = infer.predict(np.array([1.0, 2.0]), lambda x: float(np.sum(x) + 1.0))

    assert batch_opt.batch_size > 0
    assert mem_opt.dtype == np.float32
    assert dedup.shape[0] == 2
    assert "gpu_available" in gpu
    assert pred1 == pred2


def test_hyperparameter_optimizer() -> None:
    search = HyperparameterOptimizer(seed=1)

    def scorer(params: dict[str, float]) -> float:
        lr = float(params["learning_rate"])
        gamma = float(params["gamma"])
        entropy = float(params["entropy_coef"])
        return -((lr - 0.02) ** 2 + (gamma - 0.98) ** 2 + (entropy - 0.01) ** 2)

    space = {
        "learning_rate": [0.01, 0.02, 0.03],
        "gamma": [0.95, 0.98, 0.99],
        "entropy_coef": [0.005, 0.01, 0.02],
    }

    best_g, score_g = search.grid_search(space, scorer)
    best_r, score_r = search.random_search(space, scorer, n_trials=8)
    best_b, score_b = search.bayesian_search(space, scorer, n_trials=8)

    assert "learning_rate" in best_g
    assert score_g >= score_r - 1.0
    assert "gamma" in best_b
    assert isinstance(score_b, float)


def test_adaptive_sampling_bridge() -> None:
    umap = _uncertainty_map(size=10)
    x = np.linspace(0.0, 1.0, umap.shape[1])
    y = np.linspace(0.0, 1.0, umap.shape[0])
    existing = np.array([[0.1, 0.2], [0.8, 0.6]], dtype=float)

    recommender = SamplingRecommender()
    result = recommender.generate_recommendations(
        variance=umap,
        x_coords=x,
        y_coords=y,
        existing_points=existing,
        n_recommendations=6,
        strategy="reinforcement_learning",
    )

    assert result["strategy"] == "reinforcement_learning"
    assert result["n_recommendations"] >= 1
