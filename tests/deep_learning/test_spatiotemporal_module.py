from __future__ import annotations

import numpy as np

from deep_learning.inference import SpatioTemporalInference
from deep_learning.models.spatiotemporal import (
    ConvLSTMModel,
    GCNLSTMModel,
    SlidingWindowDataLoader,
    SpatialNormalizer,
    SpatioTemporalDataAugmentation,
    SpatioTemporalFeatureEngineer,
    SpatioTemporalGraphBuilder,
    SpatioTemporalSystemIntegrator,
    SpatioTemporalTrainingConfig,
    SpatioTemporalTransformer,
    STGCNModel,
    SyntheticSpatioTemporalDataset,
    TemporalNormalizer,
    acf,
    adf_proxy_test,
    combined_spatiotemporal_loss,
    cross_correlation,
    detect_spatiotemporal_anomalies,
    detect_temporal_anomalies,
    evaluate_spatiotemporal_metrics,
    evaluate_time_dimension,
    fft_spectrum,
    kpss_proxy_test,
    pacf,
    seasonal_decompose,
)


def _sample(seed: int = 42, nodes: int = 14, seq_len: int = 28, horizon: int = 5):
    sample = SyntheticSpatioTemporalDataset(seed=seed).generate(
        n_nodes=nodes,
        seq_len=seq_len,
        pred_horizon=horizon,
        n_features=2,
        noise_std=0.03,
    )
    return sample


def test_data_preprocessing_and_analysis_tools() -> None:
    sample = _sample(seed=1)

    aug = SpatioTemporalDataAugmentation(seed=2)
    warped = aug.time_warp(sample.series)
    moved = aug.spatial_transform(sample.coords)
    noisy = aug.noise_injection(sample.series)

    feat = SpatioTemporalFeatureEngineer()
    temporal = feat.temporal_features(sample.series)
    spatial = feat.spatial_features(sample.coords, sample.adjacency)
    interaction = feat.spatiotemporal_interaction_features(sample.coords, sample.series)

    t_norm = TemporalNormalizer().fit(sample.series)
    norm_series = t_norm.transform(sample.series)
    s_norm = SpatialNormalizer().fit(sample.coords)
    norm_coords = s_norm.transform(sample.coords)

    graph_builder = SpatioTemporalGraphBuilder()
    graph = graph_builder.build(sample.coords, k=5)
    dynamic = graph_builder.update(sample.coords, sample.series, base_adjacency=sample.adjacency)

    target_feat = np.repeat(sample.targets[:, :, None], sample.series.shape[2], axis=2)
    long_series = np.concatenate([sample.series, target_feat], axis=1)
    loader = SlidingWindowDataLoader(sample.coords, long_series, seq_len=20, pred_horizon=4, batch_size=4)
    train_set, val_set, test_set = loader.split(train_ratio=0.6, val_ratio=0.2)

    decomp = seasonal_decompose(np.mean(sample.series[:, :, 0], axis=0), period=6)
    adf = adf_proxy_test(np.mean(sample.series[:, :, 0], axis=0))
    kpss = kpss_proxy_test(np.mean(sample.series[:, :, 0], axis=0))
    acf_vals = acf(np.mean(sample.series[:, :, 0], axis=0), max_lag=8)
    pacf_vals = pacf(np.mean(sample.series[:, :, 0], axis=0), max_lag=6)
    cc = cross_correlation(sample.series[0, :, 0], sample.series[1, :, 0], max_lag=6)
    spectrum = fft_spectrum(sample.series[0, :, 0])
    temporal_anomaly = detect_temporal_anomalies(sample.series[0, :, 0])
    spatial_anomaly = detect_spatiotemporal_anomalies(sample.series[:, :, 0], sample.adjacency)

    assert warped.shape == sample.series.shape
    assert moved.shape == sample.coords.shape
    assert noisy.shape == sample.series.shape
    assert temporal.shape[0] == sample.series.shape[0]
    assert spatial.shape[0] == sample.coords.shape[0]
    assert interaction.shape[0] == sample.coords.shape[0]
    assert norm_series.shape == sample.series.shape
    assert norm_coords.shape == sample.coords.shape
    assert graph.adjacency.shape == sample.adjacency.shape
    assert dynamic.adjacency.shape == sample.adjacency.shape
    assert len(train_set) > 0 and len(val_set) > 0 and len(test_set) > 0
    assert len(decomp["trend"]) == sample.series.shape[1]
    assert "stationary" in adf
    assert "stationary" in kpss
    assert len(acf_vals) >= 2
    assert len(pacf_vals) >= 2
    assert len(cc["lags"]) == len(cc["correlation"])
    assert len(spectrum["frequency"]) == len(spectrum["amplitude"])
    assert temporal_anomaly["indices"].ndim == 1
    assert spatial_anomaly["score"].shape[0] == sample.series.shape[0]


def test_four_models_train_and_predict() -> None:
    sample = _sample(seed=3, nodes=12, seq_len=24, horizon=4)
    batch = [
        {
            "coords": sample.coords,
            "series": sample.series,
            "targets": sample.targets,
            "adjacency": sample.adjacency,
        }
    ]

    models = [
        SpatioTemporalTransformer(dim=24, num_heads=4, pred_horizon=4, seed=10),
        GCNLSTMModel(dim=20, layers=2, bidirectional=True, pred_horizon=4, seed=11),
        ConvLSTMModel(dim=20, pred_horizon=4, seed=12),
        STGCNModel(dim=20, n_blocks=2, pred_horizon=4, seed=13),
    ]

    for model in models:
        l1 = model.train_step(batch, lr=0.02)
        l2 = model.train_step(batch, lr=0.02)
        out = model.forward(sample.coords, sample.series, sample.adjacency)
        assert l1 >= 0.0
        assert l2 >= 0.0
        assert out.mean.shape == sample.targets.shape
        assert out.variance.shape == sample.targets.shape
        assert np.min(out.variance) > 0.0


def test_loss_and_evaluation_pipeline() -> None:
    sample = _sample(seed=4, nodes=10, seq_len=22, horizon=4)
    model = SpatioTemporalTransformer(dim=20, num_heads=4, pred_horizon=4, seed=6)
    out = model.forward(sample.coords, sample.series, sample.adjacency)

    loss = combined_spatiotemporal_loss(out.mean, sample.targets, out.variance, sample.adjacency)
    metrics = evaluate_spatiotemporal_metrics(sample.targets, out.mean, out.variance)
    time_eval = evaluate_time_dimension(sample.targets, out.mean)

    assert loss["total"] >= 0.0
    assert metrics.rmse >= 0.0
    assert len(time_eval["per_step_mae"]) == sample.targets.shape[1]


def test_integration_training_prediction_and_online_update() -> None:
    sample = _sample(seed=5, nodes=12, seq_len=26, horizon=4)
    payload = {
        "coords": sample.coords,
        "series": sample.series,
        "targets": sample.targets,
        "adjacency": sample.adjacency,
    }
    dataset = [payload for _ in range(6)]

    integrator = SpatioTemporalSystemIntegrator(cache_ttl_seconds=60)
    train = integrator.train(
        model_type="st_transformer",
        train_dataset=dataset[:4],
        val_dataset=dataset[4:],
        config=SpatioTemporalTrainingConfig(pred_horizon=4, max_epochs=8, early_stopping_patience=3, learning_rate=0.02),
    )
    pred = integrator.predict(
        model_type="st_transformer",
        coords=sample.coords,
        series=sample.series,
        pred_horizon=4,
        fusion_strategy="gating",
    )
    baseline = integrator.baseline_predictions(sample.series, pred_horizon=4)
    eval_payload = integrator.evaluate(sample.targets, pred.mean, pred.variance, sample.coords, baseline_preds=baseline)
    analysis = integrator.analyze_time_series(sample.series, adjacency=sample.adjacency)

    target_feat = np.repeat(sample.targets[:, :, None], sample.series.shape[2], axis=2)
    long_series = np.concatenate([sample.series, target_feat], axis=1)
    online = integrator.realtime_predict_and_update(
        model_type="st_transformer",
        coords=sample.coords,
        long_series=long_series,
        window_size=20,
        pred_horizon=4,
        update_interval=1,
        strategy="light",
    )
    perf = integrator.performance_benchmark("st_transformer", sample.coords, sample.series, pred_horizon=4, repeat=2)

    assert train["training"]["epochs_ran"] >= 1
    assert pred.mean.shape == sample.targets.shape
    assert "report" in eval_payload
    assert "adf" in analysis
    assert online["online_update"]["updated_steps"] >= 1
    assert perf["latency_ms"] >= 0.0


def test_inference_wrapper() -> None:
    sample = _sample(seed=7, nodes=10, seq_len=24, horizon=4)
    infer = SpatioTemporalInference()
    out = infer.predict_batch(sample.coords, sample.series, model_type="gcn_lstm", pred_horizon=4)
    target_feat = np.repeat(sample.targets[:, :, None], sample.series.shape[2], axis=2)
    rt = infer.predict_realtime(
        sample.coords,
        np.concatenate([sample.series, target_feat], axis=1),
        model_type="gcn_lstm",
        window_size=20,
        pred_horizon=4,
    )

    assert out.mean.shape == sample.targets.shape
    assert out.variance.shape == sample.targets.shape
    assert rt["sliding_count"] >= 1


def test_uncertainty_methods_and_performance_optimizations() -> None:
    sample = _sample(seed=9, nodes=10, seq_len=30, horizon=4)
    integrator = SpatioTemporalSystemIntegrator(cache_ttl_seconds=30)

    for method in ["mc_dropout", "deep_ensemble", "bayesian"]:
        out = integrator.predict(
            model_type="st_transformer",
            coords=sample.coords,
            series=sample.series,
            pred_horizon=4,
            fusion_strategy="gating",
            uncertainty_method=method,
            enable_memory_optimization=True,
            enable_gpu_acceleration=True,
            enable_inference_acceleration=True,
        )
        assert out.mean.shape == sample.targets.shape
        assert out.variance.shape == sample.targets.shape
        assert out.uncertainty_method.startswith(method)
        assert out.optimization is not None
        assert out.optimization["memory"]["enabled"] is True
        assert out.optimization["memory"]["series_dtype"] == "float32"
        assert "backend" in out.optimization["gpu"]

    target_feat = np.repeat(sample.targets[:, :, None], sample.series.shape[2], axis=2)
    long_series = np.concatenate([sample.series, target_feat, target_feat], axis=1)
    long_out = integrator.predict(
        model_type="st_transformer",
        coords=sample.coords,
        series=long_series,
        pred_horizon=4,
        enable_long_sequence_optimization=True,
        long_sequence_chunk=16,
    )
    assert long_out.mean.shape == sample.targets.shape
    assert long_out.variance.shape == sample.targets.shape
    assert long_out.optimization is not None
    assert long_out.optimization["long_sequence"]["enabled"] is True
