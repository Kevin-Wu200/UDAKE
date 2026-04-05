from app.core.spatiotemporal_kriging.st_prediction_engine import STPredictionEngine


def test_st_prediction_engine_init() -> None:
    engine = STPredictionEngine()
    assert engine is not None
