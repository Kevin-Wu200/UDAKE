"""时空 LIME 解释器测试。"""

from __future__ import annotations

import numpy as np

from app.dl_services.lime_explainer import SpatiotemporalLIMEExplainer


def _build_data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    coords = np.asarray(
        [
            [120.1, 30.2],
            [120.2, 30.25],
            [120.18, 30.3],
            [120.24, 30.28],
        ],
        dtype=float,
    )
    series = np.asarray(
        [
            [[1.0, 0.2], [1.1, 0.3], [1.2, 0.4], [1.3, 0.5], [1.4, 0.6]],
            [[0.9, 0.25], [1.0, 0.35], [1.15, 0.42], [1.22, 0.48], [1.3, 0.53]],
            [[1.2, 0.18], [1.25, 0.22], [1.28, 0.3], [1.35, 0.35], [1.4, 0.4]],
            [[1.05, 0.28], [1.12, 0.32], [1.19, 0.38], [1.3, 0.45], [1.36, 0.5]],
        ],
        dtype=float,
    )
    pred_mean = np.asarray(
        [
            [1.45, 1.5],
            [1.35, 1.4],
            [1.42, 1.47],
            [1.38, 1.43],
        ],
        dtype=float,
    )
    return coords, series, pred_mean


def test_lime_explainer_generates_visualization_payload() -> None:
    coords, series, pred_mean = _build_data()
    explainer = SpatiotemporalLIMEExplainer()
    result = explainer.explain(
        model_type="st_transformer",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=3,
    )
    assert result["summary"]["method"] == "lime"
    assert result["summary"]["explained_nodes"] >= 1
    assert len(result["feature_importance"]) == series.shape[2]
    assert "visualization" in result
    assert len(result["visualization"]["feature_importance_list"]) >= 1
    assert len(result["batch_explanations"]) >= 1


def test_lime_explainer_result_cache() -> None:
    coords, series, pred_mean = _build_data()
    explainer = SpatiotemporalLIMEExplainer()
    first = explainer.explain(
        model_type="st_transformer",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=2,
    )
    second = explainer.explain(
        model_type="st_transformer",
        coords=coords,
        series=series,
        pred_mean=pred_mean,
        top_k=2,
    )
    assert first["summary"]["method"] == "lime"
    assert second["summary"]["method"] == "lime"
    assert second["performance"]["cache_hit"] is True
