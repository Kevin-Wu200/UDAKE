from app.core.spatiotemporal_kriging.st_kriging_solver import STKrigingSolver


def test_st_kriging_solver_init() -> None:
    solver = STKrigingSolver()
    assert solver is not None
