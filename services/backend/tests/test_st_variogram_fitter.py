from app.core.spatiotemporal_kriging.st_variogram_fitter import STVariogramFitter


def test_st_variogram_fitter_init() -> None:
    fitter = STVariogramFitter()
    assert fitter is not None
