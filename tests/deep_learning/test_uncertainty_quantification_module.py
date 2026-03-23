from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import (
    BayesianConvLayer,
    BayesianDenseLayer,
    BayesianNeuralRegressor,
    DeepEnsembleRegressor,
    EDLClassifier,
    EDLConfig,
    GaussianMixturePrior,
    MCDropoutConfig,
    MCDropoutRegressor,
    UQTrainingConfig,
    UQTrainingManager,
    UncertaintyAggregator,
    UncertaintyCalibrator,
    UncertaintyDatasetBuilder,
    UncertaintyEvaluator,
    UncertaintySystemIntegrator,
)


def make_regression_data(n: int = 120, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 5.3) + np.cos(coords[:, 1] * 4.7) + rng.normal(0.0, 0.08, size=n)
    return coords, values


def make_classification_labels(values: np.ndarray, classes: int = 3) -> np.ndarray:
    quantiles = np.percentile(values, np.linspace(0.0, 100.0, classes + 1))
    labels = np.zeros(len(values), dtype=int)
    for i in range(classes):
        left, right = quantiles[i], quantiles[i + 1]
        if i == classes - 1:
            mask = (values >= left) & (values <= right)
        else:
            mask = (values >= left) & (values < right)
        labels[mask] = i
    return labels


def test_bnn_layers_and_regressor() -> None:
    coords, values = make_regression_data(n=90, seed=8)
    x = np.concatenate([coords, values.reshape(-1, 1)], axis=1)

    dense = BayesianDenseLayer(in_dim=3, out_dim=5, prior=GaussianMixturePrior())
    out_dense = dense.forward(x, sample=True)
    assert out_dense.shape == (90, 5)

    conv = BayesianConvLayer(in_channels=2, out_channels=4, kernel_size=3, prior=GaussianMixturePrior())
    conv_in = np.stack([coords, coords], axis=-1)[:, :, :2]
    out_conv = conv.forward(conv_in, sample=True)
    assert out_conv.shape[0] == conv_in.shape[0]

    model = BayesianNeuralRegressor(in_dim=3, hidden_dim=20, prior=GaussianMixturePrior())
    train = model.fit(x, values, epochs=90, lr=8e-3)
    pred = model.predict(x, num_samples=24)

    assert train["epochs"] >= 1
    assert pred["mean"].shape == (90,)
    assert np.all(pred["variance"] > 0.0)
    assert np.mean(pred["epistemic"]) >= 0.0


def test_mc_dropout_training_inference_and_adaptive_t() -> None:
    coords, values = make_regression_data(n=100, seed=10)
    x = np.concatenate([coords, values.reshape(-1, 1)], axis=1)

    model = MCDropoutRegressor(
        MCDropoutConfig(
            in_dim=3,
            hidden_dim=24,
            dropout_rate=0.25,
            dropout_type="variational",
            seed=10,
        )
    )
    train = model.fit(x, values, epochs=100, lr=7e-3)
    pred = model.predict(x, t=30)
    sens = model.t_sensitivity(x, [8, 12, 20, 30])
    adaptive = model.adaptive_t(x, max_t=40, min_t=8)

    assert train["final_loss"] >= 0.0
    assert pred["mean"].shape == (100,)
    assert np.mean(pred["variance"]) > 0.0
    assert len(sens) >= 3
    assert adaptive["best_t"] >= 8


def test_deep_ensemble_registry_selection_and_prediction() -> None:
    coords, values = make_regression_data(n=130, seed=12)
    x = np.concatenate([coords, values.reshape(-1, 1)], axis=1)

    model = DeepEnsembleRegressor(in_dim=3, n_members=4, seed=12)
    train = model.fit(x, values, epochs=110)

    pred_mean = model.predict(x, aggregation="mean")
    pred_median = model.predict(x, aggregation="median")
    pred_weighted = model.predict(x, aggregation="weighted", member_weights={"member_0": 0.6, "member_1": 0.2, "member_2": 0.1, "member_3": 0.1})

    select_val = model.select_members(x, values, method="validation", top_k=2)
    select_div = model.select_members(x, values, method="diversity", top_k=2)
    select_adp = model.select_members(x, values, method="adaptive", top_k=2)
    registry = model.registry_snapshot()
    diversity = model.model_diversity(x)

    assert train["n_members"] == 4
    assert pred_mean["mean"].shape == (130,)
    assert pred_median["variance"].shape == (130,)
    assert pred_weighted["aleatoric"].shape == (130,)
    assert len(select_val["selected"]) == 2
    assert len(select_div["selected"]) == 2
    assert len(select_adp["selected"]) == 2
    assert len(registry) == 4
    assert diversity["spread"] >= 0.0


def test_edl_and_calibration_metrics() -> None:
    coords, values = make_regression_data(n=120, seed=21)
    x = np.concatenate([coords, values.reshape(-1, 1)], axis=1)
    labels = make_classification_labels(values, classes=3)

    model = EDLClassifier(EDLConfig(in_dim=3, num_classes=3, hidden_dim=22, evidence_activation="softplus", seed=21))
    train = model.fit(x, labels, epochs=120, lr=8e-3)
    pred = model.predict(x)
    ece = model.expected_calibration_error(pred["probabilities"], labels)
    rel = model.reliability_diagram(pred["probabilities"], labels, n_bins=8)
    temp = model.temperature_scaling(x, labels)

    assert train["final_loss"] >= 0.0
    assert pred["probabilities"].shape == (120, 3)
    assert pred["prediction"].shape == (120,)
    assert 0.0 <= ece <= 1.0
    assert rel["accuracy"].shape[0] == 8
    assert 0.4 <= temp["temperature"] <= 2.5


def test_aggregation_evaluation_integration_and_pipeline() -> None:
    coords, values = make_regression_data(n=150, seed=33)
    dataset = UncertaintyDatasetBuilder(seed=33).create_uncertainty_dataset(coords, values)

    aggregator = UncertaintyAggregator()
    means = np.vstack([dataset.values[:60], dataset.values[:60] + 0.03, dataset.values[:60] - 0.04])
    vars_ = np.vstack([
        np.full(60, 0.05),
        np.full(60, 0.07),
        np.full(60, 0.06),
    ])

    agg_var = aggregator.variance_aggregation(means, vars_)
    agg_q = aggregator.quantile_aggregation(means)
    agg_bma = aggregator.bayesian_model_average(means, vars_, model_weights=[0.5, 0.3, 0.2])
    decomp_spatial = aggregator.spatial_uncertainty_decomposition(dataset.coords[:60], agg_var.variance)
    decomp_temporal = aggregator.temporal_uncertainty_decomposition(agg_var.variance)

    calibrator = UncertaintyCalibrator()
    score = (agg_var.variance - np.min(agg_var.variance)) / (np.max(agg_var.variance) - np.min(agg_var.variance) + 1e-8)
    label = (score > np.median(score)).astype(float)
    calibrator.fit_isotonic(score, label)
    calibrator.fit_platt(score, label, epochs=400)
    iso_out = calibrator.transform_isotonic(score)
    platt_out = calibrator.transform_platt(score)

    logits = np.stack([1.0 - score, score, 0.5 * np.ones_like(score)], axis=1)
    cls_labels = (score > np.percentile(score, 66)).astype(int)
    calibrator.fit_temperature(logits, cls_labels)
    probs_temp = calibrator.transform_temperature(logits)
    calibrator.fit_variance_temperature(dataset.values[:60], agg_var.mean, agg_var.variance)
    var_temp = calibrator.transform_variance_temperature(agg_var.variance)

    evaluator = UncertaintyEvaluator()
    metric = evaluator.evaluate_regression(dataset.values[:60], agg_var.mean, var_temp)
    quality = evaluator.uncertainty_quality(agg_var.mean, var_temp, dataset.values[:60])
    vis = evaluator.uncertainty_visualizations(dataset.coords[:60], agg_var.mean, var_temp)
    benchmark = evaluator.benchmark_compare(
        dataset.values[:60],
        agg_var.mean,
        var_temp,
        kriging_var=np.full(60, 0.11),
        bootstrap_var=np.full(60, 0.09),
    )
    ablation = evaluator.ablation_study(
        dataset.values[:60],
        agg_var.mean,
        {
            "aleatoric": np.sqrt(np.maximum(agg_var.variance, 1e-8)),
            "epistemic": np.linspace(0.01, 0.03, 60),
        },
    )
    report = evaluator.generate_report(metric, quality, benchmark=benchmark, ablation=ablation)

    manager = UQTrainingManager()
    train_payload = manager.train(
        UQTrainingConfig(model_name="mc_dropout", max_epochs=80, hidden_dim=20),
        dataset.features,
        dataset.values,
    )

    integrator = UncertaintySystemIntegrator()
    uq_res = integrator.predict(
        sample_coords=dataset.coords[:90],
        sample_values=dataset.values[:90],
        query_coords=dataset.coords[90:120],
        method="mc_dropout",
    )
    fused = integrator.fuse_with_existing_uncertainty(uq_res, legacy_variance=np.full(len(uq_res.mean), 0.08))
    api_res = integrator.api_predict(
        {
            "sample_coords": dataset.coords[:90],
            "sample_values": dataset.values[:90],
            "query_coords": dataset.coords[90:120],
            "method": "mc_dropout",
        }
    )
    dash_res = integrator.dashboard_payload(dataset.coords[90:120], uq_res)
    stream = integrator.realtime_updates(
        [
            {
                "sample_coords": dataset.coords[:80],
                "sample_values": dataset.values[:80],
                "query_coords": dataset.coords[80:95],
            },
            {
                "sample_coords": dataset.coords[:90],
                "sample_values": dataset.values[:90],
                "query_coords": dataset.coords[95:110],
            },
        ],
        method="mc_dropout",
    )

    assert agg_var.mean.shape == (60,)
    assert agg_q["q_med"].shape == (60,)
    assert agg_bma.variance.shape == (60,)
    assert decomp_spatial["local_std"].shape == (60,)
    assert decomp_temporal["trend"].shape == (60,)
    assert iso_out.shape == (60,)
    assert platt_out.shape == (60,)
    assert probs_temp.shape == (60, 3)
    assert var_temp.shape == (60,)
    assert np.isfinite(metric.nll)
    assert "uncertainty_map" in vis
    assert "markdown" in report
    assert train_payload["training"]["epochs"] >= 1
    assert uq_res.mean.shape[0] == 30
    assert np.mean(fused.variance) > 0.0
    assert "uncertainty_levels" in api_res
    assert "spatial_decomposition" in dash_res
    assert len(stream) == 2
