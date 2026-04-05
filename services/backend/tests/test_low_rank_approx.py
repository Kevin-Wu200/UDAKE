import numpy as np

from app.core.spatiotemporal_kriging.utils.low_rank_approx import truncated_svd


def test_truncated_svd_rank() -> None:
    matrix = np.eye(4)
    u, s, vt = truncated_svd(matrix, rank=2)
    assert u.shape == (4, 2)
    assert s.shape == (2,)
    assert vt.shape == (2, 4)
