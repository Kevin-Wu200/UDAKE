from app.core.spatiotemporal_kriging.st_model_selector import STModelSelector


def test_st_model_selector_init() -> None:
    selector = STModelSelector()
    assert selector is not None
