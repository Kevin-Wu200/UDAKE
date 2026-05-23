import numpy as np
from app.core.spatiotemporal_kriging.models.separated_model import SeparatedModel


def test_separated_model_covariance_shape() -> None:
    model = SeparatedModel()
    spatial = np.zeros((2, 2))
    temporal = np.zeros((2, 2))
    cov = model.covariance(spatial, temporal, {})
    assert cov.shape == (2, 2)
