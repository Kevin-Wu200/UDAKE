from __future__ import annotations

import pytest

from deep_learning.inference import (
    AsyncInferenceEngine,
    BatchPredictor,
    StreamPredictor,
)


class DemoModel:
    def predict(self, batch):
        return [sum(x) for x in batch]


def test_batch_predictor_cache_and_postprocess() -> None:
    predictor = BatchPredictor(DemoModel())
    batch = [[1.0, 2.0], [3.0, 4.0]]

    first = predictor.predict(batch)
    second = predictor.predict(batch)

    assert first == [3.0, 7.0]
    assert second == first


@pytest.mark.asyncio
async def test_stream_and_async_predictor() -> None:
    stream_predictor = StreamPredictor(DemoModel())
    stream_result = await stream_predictor.predict_stream([[[1.0, 1.0]], [[2.0, 3.0]]])
    assert stream_result == [[2.0], [5.0]]

    engine = AsyncInferenceEngine(stream_predictor)
    async_result = await engine.predict_async([[1.0, 2.0], [2.0, 2.0]])
    assert async_result == [3.0, 4.0]
