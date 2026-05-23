from __future__ import annotations

from pathlib import Path

import numpy as np

from deep_learning.inference import SpatialInterpolationInference
from deep_learning.models.spatial_interpolation import (
    AttentionKrigingModel,
    BatchOptimizer,
    GNNKrigingModel,
    ModelCompressor,
    ResidualKrigingModel,
    SpatialGraphBuilder,
    SpatialInterpolationIntegrator,
    evaluate_metrics,
)
from deep_learning.models.spatial_interpolation.graph_layers import (
    EdgeConvLayer,
    GATLayer,
    GCNLayer,
)
from deep_learning.models.spatial_interpolation.position_encoding import (
    LearnablePositionEncoding,
    relative_position_encoding,
    sinusoidal_position_encoding,
)
from deep_learning.training import (
    HyperparameterOptimizer,
    ModelSelector,
    SpatialModelManager,
    SpatialTrainingConfig,
    train_spatial_model,
)
from deep_learning.utils.spatial_interpolation_data import (
    CoordNormalizer,
    FeatureExtractionTools,
    GraphConstructionTools,
    SpatialInterpolationDataLoader,
    SyntheticSpatialDataset,
    ValueNormalizer,
)


def _sample_dataset(seed: int = 42) -> dict[str, np.ndarray]:
    return SyntheticSpatialDataset(seed=seed).generate(n_points=48, noise_std=0.02)


def test_graph_builder_multi_strategies() -> None:
    data = _sample_dataset(1)
    coords = data["coords"]
    values = data["values"]

    builder = SpatialGraphBuilder(default_k=6, default_radius=0.25)
    knn = builder.build(coords, values, strategy="knn")
    radius = builder.build(coords, values, strategy="radius")
    voronoi = builder.build(coords, values, strategy="voronoi")
    delaunay = builder.build(coords, values, strategy="delaunay")

    assert knn.edge_index.shape[0] == 2
    assert radius.edge_index.shape[0] == 2
    assert voronoi.edge_index.shape[0] == 2
    assert delaunay.edge_index.shape[0] == 2
    assert knn.adjacency.shape == (len(coords), len(coords))


def test_layers_and_position_encodings_shapes() -> None:
    data = _sample_dataset(2)
    coords = data["coords"]
    values = data["values"]

    graph = SpatialGraphBuilder(default_k=5).build(coords, values, strategy="knn")
    features = np.concatenate([coords, values.reshape(-1, 1)], axis=1)

    gcn = GCNLayer(in_dim=3, out_dim=8)
    gat = GATLayer(in_dim=3, out_dim=8, heads=2)
    edge = EdgeConvLayer(in_dim=3, out_dim=8)

    out_gcn = gcn.forward(features, graph.adjacency)
    out_gat = gat.forward(features, graph.edge_index, n_nodes=len(coords))
    out_edge = edge.forward(features, graph.edge_index, n_nodes=len(coords))

    sin_pos = sinusoidal_position_encoding(coords, dim=12)
    rel_pos = relative_position_encoding(coords[:5], coords)
    learn_pos = LearnablePositionEncoding(dim=10).encode(coords)

    assert out_gcn.shape == (len(coords), 8)
    assert out_gat.shape == (len(coords), 8)
    assert out_edge.shape == (len(coords), 8)
    assert sin_pos.shape == (len(coords), 12)
    assert rel_pos.shape == (5, len(coords), 3)
    assert learn_pos.shape == (len(coords), 10)


def test_three_models_can_train_and_predict() -> None:
    data = _sample_dataset(3)
    sample = {"coords": data["coords"], "values": data["values"], "targets": data["targets"]}
    batch = [sample]

    gnn = GNNKrigingModel(hidden_dim=12)
    attn = AttentionKrigingModel(dim=20)
    residual = ResidualKrigingModel(architecture="hybrid")

    gnn_l1 = gnn.train_step(batch, lr=0.03)
    gnn_l2 = gnn.train_step(batch, lr=0.03)
    gnn_out = gnn.forward(data["coords"], data["values"], query_coords=data["coords"])

    attn_l1 = attn.train_step(batch, lr=0.02)
    attn_l2 = attn.train_step(batch, lr=0.02)
    attn_out = attn.forward(data["coords"], data["values"], query_coords=data["coords"])

    res_l1 = residual.train_step(batch, lr=0.02)
    res_l2 = residual.train_step(batch, lr=0.02)
    res_out = residual.forward(data["coords"], data["values"], query_coords=data["coords"])

    assert gnn_l2 <= gnn_l1 + 1.0
    assert attn_l2 <= attn_l1 + 1.0
    assert res_l2 <= res_l1 + 1.0

    assert gnn_out.mean.shape[0] == len(data["coords"])
    assert attn_out.mean.shape[0] == len(data["coords"])
    assert res_out.mean.shape[0] == len(data["coords"])

    metrics = evaluate_metrics(data["targets"], gnn_out.mean, gnn_out.variance)
    assert metrics.rmse >= 0.0
    assert metrics.crps >= 0.0


def test_data_tools_and_loader_modes() -> None:
    data = _sample_dataset(4)

    coord_norm = CoordNormalizer().fit(data["coords"]).transform(data["coords"])
    val_normer = ValueNormalizer().fit(data["values"])
    value_norm = val_normer.transform(data["values"])

    graphs = GraphConstructionTools()
    graph = graphs.knn_graph(data["coords"], data["values"], k=6)

    feat_tool = FeatureExtractionTools()
    spatial_feat = feat_tool.spatial_features(data["coords"])
    stat_feat = feat_tool.statistical_features(data["values"])
    topo_feat = feat_tool.topology_features(graph.adjacency)

    loader = SpatialInterpolationDataLoader(data, batch_size=8, shuffle=False)
    single = list(loader.single_point_mode())
    batches = list(loader.batch_mode())
    grid = loader.grid_mode(grid_size=10)

    assert coord_norm.min() >= 0.0
    assert coord_norm.max() <= 1.0
    assert value_norm.shape[0] == len(data["values"])
    assert spatial_feat.shape[0] == len(data["coords"])
    assert stat_feat.shape[0] == len(data["coords"])
    assert topo_feat.shape[0] == len(data["coords"])
    assert len(single) == len(data["coords"])
    assert len(batches) > 0
    assert grid["grid_query"].shape[0] == 100


def test_training_pipeline_and_selection(tmp_path: Path) -> None:
    data = _sample_dataset(5)
    dataset = [{"coords": data["coords"], "values": data["values"], "targets": data["targets"]} for _ in range(6)]

    model = GNNKrigingModel(hidden_dim=12)
    result = train_spatial_model(
        model,
        train_dataset=dataset[:4],
        val_dataset=dataset[4:],
        config=SpatialTrainingConfig(max_epochs=8, learning_rate=0.03, early_stopping_patience=3),
    )
    assert result["training"]["epochs_ran"] >= 1

    selector = ModelSelector()
    cv = selector.cross_validate(lambda: GNNKrigingModel(hidden_dim=12), dataset, folds=3)
    assert "cv_mean_val_loss" in cv

    search = HyperparameterOptimizer(seed=9)

    def scorer(params):
        m = GNNKrigingModel(hidden_dim=int(params["hidden_dim"]))
        out = m.forward(data["coords"], data["values"], query_coords=data["coords"])
        return float(np.mean((out.mean - data["targets"]) ** 2))

    best, score = search.grid_search({"hidden_dim": [10, 12], "learning_rate": [0.01, 0.03]}, scorer)
    assert "hidden_dim" in best
    assert score >= 0.0

    manager = SpatialModelManager()
    ckpt = tmp_path / "stage2_model.pkl"
    manager.save(model, str(ckpt))
    reloaded = GNNKrigingModel(hidden_dim=12)
    manager.load(reloaded, str(ckpt))
    assert isinstance(reloaded.bias, float)


def test_optimization_and_integration() -> None:
    data = _sample_dataset(6)

    optimizer = BatchOptimizer().suggest(sample_count=128, feature_dim=24, memory_budget_mb=32)
    compressor = ModelCompressor()
    weights = np.array([0.1, -0.2, 0.0, 0.35, -0.01], dtype=float)
    pruned = compressor.prune(weights, ratio=0.3)
    quantized = compressor.quantize(weights, bits=6)

    assert optimizer.batch_size > 0
    assert pruned.shape == weights.shape
    assert quantized.shape == weights.shape

    inference = SpatialInterpolationInference()
    batch_pred = inference.predict_batch(data["coords"], data["values"], data["coords"], model_type="residual")
    assert batch_pred.mean.shape[0] == len(data["coords"])

    integrator = SpatialInterpolationIntegrator(cache_ttl_seconds=60)
    events: list[dict[str, object]] = []
    integrator.register_event_handler(lambda e: events.append(e))

    fused = integrator.predict_with_fusion(
        sample_coords=data["coords"],
        sample_values=data["values"],
        query_coords=data["coords"][:6],
        model_type="gnn",
        blend_ratio=0.5,
    )
    assert fused.mean.shape[0] == 6
    assert len(events) >= 1
