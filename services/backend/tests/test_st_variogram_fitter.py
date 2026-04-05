import numpy as np
import pytest

from app.core.spatiotemporal_kriging.st_variogram_fitter import STVariogramFitter
from app.services.spatiotemporal_core import STDataset


def _dataset_with_nan() -> STDataset:
    return STDataset(
        x=np.array([120.1, np.nan, 120.3, 120.4, 120.5], dtype=np.float64),
        y=np.array([30.1, 30.2, 30.3, 30.4, np.nan], dtype=np.float64),
        z=np.array([10.0, 10.5, 11.0, 11.5, 12.0], dtype=np.float64),
        t=np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float64),
        value=np.array([80.0, 82.0, np.nan, 85.0, 87.0], dtype=np.float64),
    )


def _dataset_clean(n: int = 12) -> STDataset:
    x = np.linspace(120.0, 121.0, n)
    y = np.linspace(30.0, 31.0, n)
    z = np.linspace(10.0, 15.0, n)
    t = np.linspace(1711929600, 1711929600 + 86400 * (n - 1), n)
    value = 80.0 + 2.5 * np.sin(np.linspace(0, 2.0, n))
    return STDataset(x=x, y=y, z=z, t=t, value=value)


def test_preprocess_data_fill_missing_and_normalize() -> None:
    fitter = STVariogramFitter()
    prepared, report = fitter.preprocess_data(_dataset_with_nan(), normalize=True)

    assert not np.isnan(prepared.x).any()
    assert not np.isnan(prepared.y).any()
    assert not np.isnan(prepared.value).any()
    assert report["filled_missing"]["x"] == 1
    assert report["filled_missing"]["value"] == 1

    for key in ("x", "y", "z", "t"):
        arr = getattr(prepared, key)
        assert np.min(arr) >= 0.0
        assert np.max(arr) <= 1.0


def test_preprocess_data_all_nan_raise_error() -> None:
    fitter = STVariogramFitter()
    bad = STDataset(
        x=np.array([np.nan, np.nan, np.nan], dtype=np.float64),
        y=np.array([1.0, 2.0, 3.0], dtype=np.float64),
        z=np.array([1.0, 2.0, 3.0], dtype=np.float64),
        t=np.array([1.0, 2.0, 3.0], dtype=np.float64),
        value=np.array([1.0, 2.0, 3.0], dtype=np.float64),
    )
    with pytest.raises(ValueError, match="全部是缺失值"):
        fitter.preprocess_data(bad, normalize=True)


def test_spatial_and_temporal_variogram_estimation() -> None:
    fitter = STVariogramFitter()
    prepared, _ = fitter.preprocess_data(_dataset_clean(), normalize=True)

    spatial = fitter.estimate_spatial_variogram(prepared, bins=8)
    temporal = fitter.estimate_temporal_variogram(prepared, bins=8)

    for variogram in (spatial, temporal):
        assert len(variogram["lags"]) > 0
        assert len(variogram["lags"]) == len(variogram["semivariance"]) == len(variogram["pair_counts"])
        assert all(count >= 0 for count in variogram["pair_counts"])


def test_parameter_estimation_and_fit_report() -> None:
    fitter = STVariogramFitter()
    data = _dataset_clean(16)

    mle = fitter.estimate_parameters_mle(data, model_type="product")
    params = mle["parameters"]
    assert mle["converged"] is True
    assert params["spatial_range"] > 0
    assert params["temporal_range"] > 0

    fit_result = fitter.fit(data, model_type="nonseparable")
    assert fit_result["fitting_report"]["converged"] is True
    assert "aic" in fit_result["fitting_report"]
    assert "bic" in fit_result["fitting_report"]
    assert "spatial_variogram" in fit_result["charts"]
    assert "temporal_variogram" in fit_result["charts"]


def test_covariance_models_output_shape_and_finite() -> None:
    fitter = STVariogramFitter()
    params = {
        "spatial_sill": 1.0,
        "spatial_range": 0.5,
        "spatial_nugget": 0.01,
        "temporal_sill": 1.2,
        "temporal_range": 0.8,
        "temporal_nugget": 0.02,
        "coupling": 0.7,
        "beta": 1.5,
    }
    points = np.array(
        [
            [0.0, 0.0, 0.0, 0.0],
            [0.3, 0.1, 0.0, 0.2],
            [0.6, 0.2, 0.1, 0.5],
        ],
        dtype=np.float64,
    )

    for model_type in ("separated", "product", "nonseparable"):
        cov_fn = fitter.build_covariance_function(params, model_type=model_type)
        cov = cov_fn(points, points)
        assert cov.shape == (3, 3)
        assert np.all(np.isfinite(cov))
        assert np.allclose(cov, cov.T)
