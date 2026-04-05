import numpy as np

from app.core.spatiotemporal_kriging.models.nonseparable_model import NonseparableModel


def test_nonseparable_model_covariance_shape() -> None:
    model = NonseparableModel()
    spatial = np.zeros((2, 2))
    temporal = np.zeros((2, 2))
    cov = model.covariance(spatial, temporal, {})
    assert cov.shape == (2, 2)
