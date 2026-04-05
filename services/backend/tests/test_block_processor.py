from app.core.spatiotemporal_kriging.utils.block_processor import chunk_slices


def test_chunk_slices() -> None:
    assert list(chunk_slices(5, 2)) == [(0, 2), (2, 4), (4, 5)]
