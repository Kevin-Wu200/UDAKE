from __future__ import annotations

import numpy as np

from deep_learning.models.uncertainty import (
    BNN_FEATURE_KEYS,
    DEEP_ENSEMBLE_FEATURE_KEYS,
    EDL_FEATURE_KEYS,
    MC_DROPOUT_FEATURE_KEYS,
    decompose_uncertainty_sources,
    extract_model_features,
    feature_name_mapping,
    uncertainty_feature_registry,
)


def test_feature_registry_and_mapping_completeness() -> None:
    registry = uncertainty_feature_registry()
    assert set(registry.keys()) == {"bnn", "mc_dropout", "deep_ensemble", "edl"}
    assert len(BNN_FEATURE_KEYS) >= 6
    assert len(MC_DROPOUT_FEATURE_KEYS) >= 6
    assert len(DEEP_ENSEMBLE_FEATURE_KEYS) >= 8
    assert len(EDL_FEATURE_KEYS) >= 8

    mapping = feature_name_mapping()
    required = (
        "mean",
        "variance",
        "aleatoric",
        "epistemic",
        "uncertainty.total",
        "uncertainty.data",
        "uncertainty.knowledge",
    )
    for key in required:
        assert key in mapping
        assert len(mapping[key]) > 0


def test_extract_model_features_for_regression_uq_models() -> None:
    bnn_pred = {
        "mean": np.array([0.1, 0.2], dtype=float),
        "variance": np.array([0.03, 0.05], dtype=float),
        "aleatoric": np.array([0.01, 0.02], dtype=float),
        "epistemic": np.array([0.02, 0.03], dtype=float),
        "lower": np.array([-0.1, 0.0], dtype=float),
        "upper": np.array([0.3, 0.4], dtype=float),
        "confidence": 0.95,
        "num_samples": 80,
    }
    bnn_out = extract_model_features("bnn", bnn_pred)
    assert bnn_out["mean"].shape == (2,)
    assert np.all(bnn_out["variance"] > 0.0)

    mc_pred = {
        "mean": np.array([0.3, 0.4], dtype=float),
        "variance": np.array([0.06, 0.07], dtype=float),
        "aleatoric": np.array([0.03, 0.03], dtype=float),
        "epistemic": np.array([0.03, 0.04], dtype=float),
        "t": 30,
        "confidence": 0.95,
    }
    mc_out = extract_model_features("mc_dropout", mc_pred)
    assert mc_out["t"].shape == (1,)
    assert float(mc_out["t"][0]) == 30.0

    de_pred = {
        "mean": np.array([0.4, 0.5], dtype=float),
        "variance": np.array([0.04, 0.06], dtype=float),
        "aleatoric": np.array([0.02, 0.03], dtype=float),
        "epistemic": np.array([0.02, 0.03], dtype=float),
        "quantiles": {
            "q10": np.array([0.2, 0.3], dtype=float),
            "q50": np.array([0.4, 0.5], dtype=float),
            "q90": np.array([0.6, 0.7], dtype=float),
        },
        "member_ids": ["member_0", "member_1", "member_2"],
        "aggregation": "mean",
    }
    de_out = extract_model_features("deep_ensemble", de_pred)
    assert de_out["quantiles.q10"].shape == (2,)
    assert float(de_out["member_count"][0]) == 3.0


def test_extract_model_features_and_decompose_for_edl() -> None:
    edl_pred = {
        "logits": np.array([[1.2, 0.1, -0.3]], dtype=float),
        "evidence": np.array([[3.0, 1.2, 0.5]], dtype=float),
        "alpha": np.array([[4.0, 2.2, 1.5]], dtype=float),
        "probabilities": np.array([[0.58, 0.29, 0.13]], dtype=float),
        "prediction": np.array([0], dtype=int),
        "confidence": np.array([0.76], dtype=float),
        "uncertainty": {
            "total": np.array([0.34], dtype=float),
            "data": np.array([0.12], dtype=float),
            "knowledge": np.array([0.22], dtype=float),
            "threshold": 0.95,
        },
    }
    edl_out = extract_model_features("edl", edl_pred)
    assert "aleatoric" in edl_out
    assert "epistemic" in edl_out
    assert np.all(edl_out["variance"] > 0.0)

    decomp = decompose_uncertainty_sources("edl", edl_pred)
    assert np.all(decomp["total"] > 0.0)
    assert np.all(decomp["epistemic_ratio"] >= 0.0)
    assert np.all(decomp["aleatoric_ratio"] >= 0.0)
    assert "knowledge->epistemic" in str(decomp["strategy"])
