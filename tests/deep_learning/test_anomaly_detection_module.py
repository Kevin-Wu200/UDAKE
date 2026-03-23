from __future__ import annotations

import numpy as np

from deep_learning.models.anomaly_detection import (
    AnomalyDatasetBuilder,
    AnomalyEnsembleIntegrator,
    AnomalyEvaluator,
    AnomalyFeatureExtractor,
    AnomalyTrainingConfig,
    AnomalyTrainingManager,
    ContrastiveAnomalyDetector,
    GANAnomalyDetector,
    GCAEAnomalyDetector,
    GraphBuilder,
    VAEAnomalyDetector,
)


def make_dataset(n: int = 120, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    coords = rng.uniform(0.0, 1.0, size=(n, 2))
    values = np.sin(coords[:, 0] * 4.0) + np.cos(coords[:, 1] * 5.0) + rng.normal(0.0, 0.06, size=n)
    return coords, values


def test_data_pipeline_and_graph_builder() -> None:
    coords, values = make_dataset()
    dataset = AnomalyDatasetBuilder(random_state=42).build(coords, values, include_synthetic=True)

    assert dataset.coords.shape[1] == 2
    assert len(dataset.values) == len(dataset.labels)
    assert int(dataset.labels.sum()) > 0

    extractor = AnomalyFeatureExtractor()
    spatial = extractor.spatial_features(dataset.coords)
    stats = extractor.statistical_features(dataset.values)
    topo = extractor.topological_features(dataset.coords, dataset.values, k=6)

    assert spatial.shape[0] == len(dataset.values)
    assert stats.shape[1] == 3
    assert topo.shape[1] == 3

    graph_builder = GraphBuilder()
    knn = graph_builder.knn_graph(dataset.coords, k=6)
    radius = graph_builder.radius_graph(dataset.coords, radius=0.2)

    assert knn.shape[0] == len(dataset.values)
    assert radius.shape == knn.shape


def test_vae_gcae_gan_contrastive_models_train_and_predict() -> None:
    coords, values = make_dataset(n=100, seed=11)

    vae = VAEAnomalyDetector()
    vae_train = vae.fit(coords, values)
    vae_pred = vae.predict(coords, values, threshold_method="percentile", percentile=92.0)
    latent = vae.latent_visualization(coords, values)

    assert vae_train["epochs"] >= 1
    assert vae_pred["anomaly_count"] >= 1
    assert len(latent) == len(values)

    gcae = GCAEAnomalyDetector()
    gcae_train = gcae.fit(coords, values)
    gcae_pred = gcae.predict(coords, values, threshold_method="statistical", k=2.0)

    assert gcae_train["graph_nodes"] == len(values)
    assert "node_anomalies" in gcae_pred
    assert "edge_anomalies" in gcae_pred

    gan = GANAnomalyDetector()
    gan_train = gan.fit(coords, values)
    gan_pred = gan.predict(coords, values, threshold_method="adaptive", k=2.3)

    assert gan_train["epochs"] >= 1
    assert gan_pred["anomaly_count"] >= 1

    contrastive = ContrastiveAnomalyDetector()
    ctr_train = contrastive.fit(coords, values, epochs=20)
    contrastive.online_update(coords[:20], values[:20])
    ctr_pred = contrastive.predict(coords, values, threshold_method="percentile", percentile=90.0)

    assert ctr_train["feature_bank_size"] > 0
    assert ctr_pred["online_feature_bank_size"] > 0


def test_training_manager_store_and_evaluator() -> None:
    coords, values = make_dataset(n=110, seed=21)
    dataset = AnomalyDatasetBuilder(random_state=21).build(coords, values, include_synthetic=True)

    manager = AnomalyTrainingManager()
    payload = manager.train(
        AnomalyTrainingConfig(model_name="vae", max_epochs=15),
        dataset.coords,
        dataset.values,
    )
    assert payload["training"]["epochs"] >= 1

    pred = payload["model"].predict(dataset.coords, dataset.values, percentile=90.0)
    scores = np.asarray(pred["scores"], dtype=float)

    evaluator = AnomalyEvaluator()
    metrics = evaluator.evaluate(dataset.labels, scores, threshold=pred["threshold"])
    vis = evaluator.visualizations(dataset.coords, dataset.labels, scores, threshold=pred["threshold"])
    benchmark = evaluator.benchmark_against_isolation_forest(
        np.concatenate([dataset.coords, dataset.values.reshape(-1, 1)], axis=1),
        dataset.labels,
        scores,
    )
    ablation = evaluator.ablation_study(
        dataset.labels,
        {
            "reconstruction": np.asarray(pred["score_components"]["reconstruction"], dtype=float),
            "latent_distance": np.asarray(pred["score_components"]["latent_distance"], dtype=float),
        },
    )
    report = evaluator.generate_report("VAE", metrics, benchmark=benchmark, ablation=ablation)

    assert metrics["f1"] >= 0.0
    assert "anomaly_heatmap" in vis
    assert "delta_f1" in benchmark
    assert "full" in ablation
    assert "markdown" in report


def test_ensemble_integration() -> None:
    coords, values = make_dataset(n=90, seed=33)

    vae = VAEAnomalyDetector()
    gcae = GCAEAnomalyDetector()
    gan = GANAnomalyDetector()
    contrastive = ContrastiveAnomalyDetector()

    vae.fit(coords, values)
    gcae.fit(coords, values)
    gan.fit(coords, values)
    contrastive.fit(coords, values, epochs=12)

    ensemble = AnomalyEnsembleIntegrator(
        {
            "vae": vae,
            "gcae": gcae,
            "gan": gan,
            "contrastive": contrastive,
        }
    )

    result = ensemble.detect(coords, values, threshold_method="percentile", percentile=93.0)
    stream = ensemble.detect_realtime(
        [
            {"coords": coords[:45], "values": values[:45]},
            {"coords": coords[45:], "values": values[45:]},
        ]
    )

    assert result["anomaly_count"] >= 1
    assert "alert" in result
    assert len(stream) == 2
