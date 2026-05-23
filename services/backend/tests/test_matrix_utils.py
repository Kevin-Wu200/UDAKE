import numpy as np
from app.core.spatiotemporal_kriging.utils.matrix_utils import stable_cholesky_solve


def test_stable_cholesky_solve() -> None:
    a = np.array([[2.0, 0.0], [0.0, 3.0]])
    b = np.array([2.0, 3.0])
    x = stable_cholesky_solve(a, b)
    assert np.allclose(a @ x, b)
