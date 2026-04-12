from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import (
    BayesianNeuralRegressor,
    DeepEnsembleRegressor,
    GaussianMixturePrior,
    MCDropoutConfig,
    MCDropoutRegressor,
)


def _make_features(n: int = 72, seed: int = 301) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    signal = np.sin(coords[:, 0] * 4.1) + np.cos(coords[:, 1] * 3.0)
    values = signal + rng.normal(0.0, 0.04, size=n)
    return np.concatenate([coords, values.reshape(-1, 1)], axis=1)


def test_mc_dropout_batch_uncertainty_memory_and_cache_stage2() -> None:
    x = _make_features(n=68, seed=311)
    y = x[:, 2] + 0.14 * x[:, 0] - 0.09 * x[:, 1]
    model = MCDropoutRegressor(
        MCDropoutConfig(in_dim=3, hidden_dim=18, dropout_rate=0.25, dropout_type="variational", seed=337)
    )
    model.fit(x, y, epochs=58, lr=7e-3)

    out1 = model.predict_mc_dropout_batch(x, t=42, confidence=0.95, batch_size=16, optimize_memory=True)
    out2 = model.predict_mc_dropout_batch(x, t=42, confidence=0.95, batch_size=16, optimize_memory=True)

    perf1 = out1["performance"]
    perf2 = out2["performance"]
    assert perf1["cache_hit"] is False
    assert perf2["cache_hit"] is True
    assert perf1["sampling_strategy"] == "vectorized_batched"
    assert perf1["batch_count"] >= 4
    assert perf1["sample_count"] == x.shape[0]
    assert perf1["optimize_memory"] is True
    assert perf1["input_memory_bytes"] > 0
    assert perf1["result_memory_bytes"] > 0
    assert perf2["batch_cache_metrics"]["hits"] >= 1
    assert out1["mean"].shape[0] == x.shape[0]
    assert out1["variance"].shape[0] == x.shape[0]
    assert np.allclose(out1["mean"], out2["mean"])


def test_bnn_batch_uncertainty_memory_and_cache_stage2() -> None:
    x = _make_features(n=66, seed=353)
    y = x[:, 2] + 0.15 * x[:, 0] - 0.07 * x[:, 1]
    model = BayesianNeuralRegressor(in_dim=3, hidden_dim=18, prior=GaussianMixturePrior(), seed=367)
    model.fit(x, y, epochs=64, lr=7e-3)

    out1 = model.predict_bnn_batch(
        x,
        num_samples=52,
        confidence=0.95,
        temperature=1.0,
        batch_size=15,
        optimize_memory=True,
    )
    out2 = model.predict_bnn_batch(
        x,
        num_samples=52,
        confidence=0.95,
        temperature=1.0,
        batch_size=15,
        optimize_memory=True,
    )

    perf1 = out1["performance"]
    perf2 = out2["performance"]
    assert perf1["cache_hit"] is False
    assert perf2["cache_hit"] is True
    assert perf1["sampling_strategy"] == "vectorized_posterior_batched"
    assert perf1["batch_count"] >= 4
    assert perf1["sample_count"] == x.shape[0]
    assert perf1["optimize_memory"] is True
    assert perf1["input_memory_bytes"] > 0
    assert perf1["result_memory_bytes"] > 0
    assert perf2["batch_cache_metrics"]["hits"] >= 1
    assert out1["mean"].shape[0] == x.shape[0]
    assert out1["variance"].shape[0] == x.shape[0]
    assert np.allclose(out1["mean"], out2["mean"])


def test_deep_ensemble_batch_uncertainty_consistency_memory_and_cache_stage2() -> None:
    x = _make_features(n=70, seed=389)
    y = x[:, 2] + 0.16 * x[:, 0] - 0.1 * x[:, 1]
    model = DeepEnsembleRegressor(in_dim=3, n_members=5, seed=401)
    model.fit(x, y, epochs=42)

    direct = model.predict_deep_ensemble(x, aggregation="mean", confidence=0.95)
    out1 = model.predict_deep_ensemble_batch(x, aggregation="mean", confidence=0.95, batch_size=14, optimize_memory=True)
    out2 = model.predict_deep_ensemble_batch(x, aggregation="mean", confidence=0.95, batch_size=14, optimize_memory=True)

    perf1 = out1["performance"]
    perf2 = out2["performance"]
    assert perf1["cache_hit"] is False
    assert perf2["cache_hit"] is True
    assert perf1["batch_count"] >= 5
    assert perf1["sample_count"] == x.shape[0]
    assert perf1["optimize_memory"] is True
    assert perf1["input_memory_bytes"] > 0
    assert perf1["result_memory_bytes"] > 0
    assert perf2["batch_cache_metrics"]["hits"] >= 1
    assert out1["mean"].shape[0] == x.shape[0]
    assert out1["variance"].shape[0] == x.shape[0]
    assert np.allclose(out1["mean"], direct["mean"], atol=1e-6, rtol=1e-5)
    assert np.allclose(out1["variance"], direct["variance"], atol=1e-6, rtol=1e-5)
