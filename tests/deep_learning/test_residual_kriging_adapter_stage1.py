from __future__ import annotations

import numpy as np

from deep_learning.models.spatial_interpolation import ResidualKrigingModel
from deep_learning.utils.spatial_interpolation_data import SyntheticSpatialDataset
from services.backend.app.dl_services.residual_kriging_explainer import (
    ResidualKrigingExplanationConfig,
    ResidualKrigingLIMEAdapter,
    ResidualKrigingSHAPAdapter,
)


def _make_data(seed: int = 23, n_points: int = 56) -> tuple[np.ndarray, np.ndarray]:
    payload = SyntheticSpatialDataset(seed=seed).generate(n_points=n_points, noise_std=0.03)
    return np.asarray(payload["coords"], dtype=float), np.asarray(payload["values"], dtype=float)


def test_residual_kriging_preprocess_and_predict_standard() -> None:
    coords, values = _make_data()
    model = ResidualKrigingModel(architecture="hybrid")
    queries = coords[:12]

    pre = model.preprocess_residual_kriging_data(coords, values, query_coords=queries, batch_size=6, use_runtime_stats=True)
    pred = model.predict_standard(coords, values, query_coords=queries)

    processed = np.asarray(pre["processed_features"], dtype=float)
    assert processed.shape[0] == 12
    assert processed.shape[1] == len(pre["feature_names"])
    assert pre["validation"]["is_valid"] is True
    assert pre["validation"]["batch_size"] == 6
    assert len(pre["batch_slices"]) == 2

    assert len(pred["prediction"]) == 12
    assert len(pred["variance"]) == 12
    assert len(pred["residual"]) == 12
    assert len(pred["uncertainty"]) == 12
    assert len(pred["confidence_interval"]["lower"]) == 12
    assert pred["details"]["query_count"] == 12
    assert pred["preprocess"]["validation"]["is_valid"] is True


def test_residual_kriging_lime_and_shap_adapters() -> None:
    coords, values = _make_data(seed=31)
    model = ResidualKrigingModel(architecture="hybrid")
    queries = coords[:18]

    lime_adapter = ResidualKrigingLIMEAdapter(
        config=ResidualKrigingExplanationConfig(lime_num_samples=120, max_explain_nodes=4)
    )
    lime = lime_adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=4,
        num_samples=100,
    )
    assert lime["summary"]["method"] == "lime"
    assert lime["summary"]["explained_nodes"] == 4
    assert len(lime["batch_explanations"]) == 4
    assert len(lime["feature_importance"]) == lime["summary"]["num_features"]

    shap_adapter = ResidualKrigingSHAPAdapter(
        config=ResidualKrigingExplanationConfig(shap_nsamples=90, max_explain_nodes=4)
    )
    shap = shap_adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=4,
        nsamples=80,
    )
    assert shap["summary"]["method"] == "shap"
    assert shap["summary"]["explained_nodes"] == 4
    assert len(shap["batch_explanations"]) == 4
    assert len(shap["feature_importance"]) == shap["summary"]["num_features"]


def test_residual_kriging_adapter_cache_hit() -> None:
    coords, values = _make_data(seed=37)
    model = ResidualKrigingModel(architecture="hybrid")
    queries = coords[:16]
    adapter = ResidualKrigingSHAPAdapter(
        config=ResidualKrigingExplanationConfig(shap_nsamples=80, max_explain_nodes=3)
    )

    first = adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=3,
        nsamples=70,
    )
    second = adapter.explain(
        model=model,
        sample_coords=coords,
        sample_values=values,
        query_coords=queries,
        top_k=3,
        nsamples=70,
    )

    assert first["performance"]["cache_hit"] is False
    assert second["performance"]["cache_hit"] is True
