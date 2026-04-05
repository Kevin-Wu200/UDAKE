from app.services.spatiotemporal_service import spatiotemporal_kriging_service


def test_st_service_available() -> None:
    assert spatiotemporal_kriging_service is not None
