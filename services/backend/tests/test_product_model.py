import numpy as np
from app.core.spatiotemporal_kriging.models.product_model import ProductModel


def test_product_model_covariance_shape() -> None:
    model = ProductModel()
    spatial = np.zeros((2, 2))
    temporal = np.zeros((2, 2))
    cov = model.covariance(spatial, temporal, {})
    assert cov.shape == (2, 2)
