from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import (
    BayesianNeuralRegressor,
    DeepEnsembleRegressor,
    GaussianMixturePrior,
    MCDropoutConfig,
    MCDropoutRegressor,
)


def _make_features(n: int = 48, seed: int = 37) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    signal = np.sin(coords[:, 0] * 4.3) + np.cos(coords[:, 1] * 3.1)
    values = signal + rng.normal(0.0, 0.04, size=n)
    return np.concatenate([coords, values.reshape(-1, 1)], axis=1)


def test_uncertainty_model_cache_stage1() -> None:
    x = _make_features(n=40, seed=91)
    y = x[:, 2] + 0.16 * x[:, 0] - 0.1 * x[:, 1]
    model = DeepEnsembleRegressor(in_dim=3, n_members=4, seed=119)
    model.fit(x, y, epochs=32)

    out1 = model.predict_deep_ensemble(x, aggregation="mean", confidence=0.95)
    out2 = model.predict_deep_ensemble(x, aggregation="mean", confidence=0.95)

    perf1 = out1["performance"]
    perf2 = out2["performance"]
    assert perf1["cache_hit"] is False
    assert perf2["cache_hit"] is True
    assert perf2["cache_metrics"]["hits"] >= 1
    assert perf2["cache_metrics"]["hit_rate"] > 0.0


def test_mc_dropout_forward_pass_vectorized_stage1() -> None:
    x = _make_features(n=46, seed=131)
    y = x[:, 2] + 0.15 * x[:, 0] - 0.08 * x[:, 1]
    model = MCDropoutRegressor(
        MCDropoutConfig(in_dim=3, hidden_dim=16, dropout_rate=0.2, dropout_type="standard", seed=149)
    )
    model.fit(x, y, epochs=50, lr=7e-3)

    out1 = model.predict_mc_dropout(x, t=48, confidence=0.95)
    out2 = model.predict_mc_dropout(x, t=48, confidence=0.95)

    perf1 = out1["performance"]
    perf2 = out2["performance"]
    assert perf1["sampling_strategy"] == "vectorized"
    assert perf1["cache_hit"] is False
    assert perf2["cache_hit"] is True
    assert perf2["cache_metrics"]["hits"] >= 1


def test_bnn_posterior_sampling_vectorized_stage1() -> None:
    x = _make_features(n=44, seed=173)
    y = x[:, 2] + 0.18 * x[:, 0] - 0.07 * x[:, 1]
    model = BayesianNeuralRegressor(in_dim=3, hidden_dim=16, prior=GaussianMixturePrior(), seed=191)
    model.fit(x, y, epochs=56, lr=7e-3)

    out1 = model.predict_bnn(x, num_samples=64, confidence=0.95, temperature=1.0)
    out2 = model.predict_bnn(x, num_samples=64, confidence=0.95, temperature=1.0)

    perf1 = out1["performance"]
    perf2 = out2["performance"]
    assert perf1["sampling_strategy"] == "vectorized_posterior"
    assert perf1["cache_hit"] is False
    assert perf2["cache_hit"] is True
    assert perf2["cache_metrics"]["hits"] >= 1
    assert perf2["cache_metrics"]["hit_rate"] > 0.0
