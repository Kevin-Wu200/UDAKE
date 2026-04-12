from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import UncertaintySystemIntegrator


def _make_data(n: int = 72, seed: int = 211) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.8) + np.cos(coords[:, 1] * 3.4) + rng.normal(0.0, 0.06, size=n)
    return coords, values


def test_bnn_uq_integration_predict_and_api_stage1() -> None:
    coords, values = _make_data(n=84, seed=223)
    sample_coords, sample_values = coords[:64], values[:64]
    query_coords = coords[64:78]

    integrator = UncertaintySystemIntegrator(cache_ttl_seconds=120)
    train = integrator.train_uq_model("bnn", sample_coords, sample_values, max_epochs=60)
    assert train["training"]["epochs"] == 60

    pred = integrator.predict(
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=query_coords,
        method="bnn",
    )
    assert pred.method == "bnn"
    assert pred.mean.shape == (14,)
    assert pred.variance.shape == (14,)
    assert float(np.mean(pred.variance)) > 0.0
    assert np.all(pred.aleatoric > 0.0)
    assert np.all(pred.epistemic > 0.0)

    api = integrator.api_predict(
        {
            "sample_coords": sample_coords,
            "sample_values": sample_values,
            "query_coords": query_coords,
            "method": "bnn",
        }
    )
    assert api["method"] == "bnn"
    assert len(api["prediction"]) == 14
    assert len(api["variance"]) == 14
    assert set(api["uncertainty_levels"].keys()) == {"low", "medium", "high"}
    assert abs(sum(api["uncertainty_levels"].values()) - 1.0) < 1e-6


def test_mc_dropout_uq_integration_predict_and_stream_stage1() -> None:
    coords, values = _make_data(n=86, seed=227)
    sample_coords, sample_values = coords[:66], values[:66]
    query_coords = coords[66:80]

    integrator = UncertaintySystemIntegrator(cache_ttl_seconds=120)
    train = integrator.train_uq_model("mc_dropout", sample_coords, sample_values, max_epochs=60)
    assert train["training"]["epochs"] == 60

    pred = integrator.predict(
        sample_coords=sample_coords,
        sample_values=sample_values,
        query_coords=query_coords,
        method="mc_dropout",
    )
    assert pred.method == "mc_dropout"
    assert pred.mean.shape == (14,)
    assert pred.variance.shape == (14,)
    assert float(np.mean(pred.variance)) > 0.0

    stream = integrator.realtime_updates(
        [
            {
                "sample_coords": sample_coords[:50],
                "sample_values": sample_values[:50],
                "query_coords": query_coords[:7],
            },
            {
                "sample_coords": sample_coords,
                "sample_values": sample_values,
                "query_coords": query_coords[7:14],
            },
        ],
        method="mc_dropout",
    )
    assert len(stream) == 2
    assert stream[0]["method"] == "mc_dropout"
    assert stream[1]["method"] == "mc_dropout"
    assert stream[0]["mean_uncertainty"] > 0.0
    assert stream[1]["max_uncertainty"] >= stream[1]["min_uncertainty"]
