from app.api import 时空克里金接口


def test_st_api_router_prefix() -> None:
    assert 时空克里金接口.router.prefix == "/spatiotemporal"
