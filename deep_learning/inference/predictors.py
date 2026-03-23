"""推理服务框架。"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable

from deep_learning.utils.cache import CacheManager
from deep_learning.utils.monitoring import MetricMonitor


class BasePredictor(ABC):
    @abstractmethod
    def predict(self, batch: list[Any]) -> list[float]:
        raise NotImplementedError


class PredictionPostProcessor:
    def process(self, values: list[float], decimals: int = 4, min_value: float | None = None, max_value: float | None = None) -> list[float]:
        result = [round(float(v), decimals) for v in values]
        if min_value is not None:
            result = [max(min_value, v) for v in result]
        if max_value is not None:
            result = [min(max_value, v) for v in result]
        return result


class BatchPredictor(BasePredictor):
    def __init__(self, model: Any, cache: CacheManager | None = None) -> None:
        self.model = model
        self.cache = cache or CacheManager(ttl_seconds=600)
        self.monitor = MetricMonitor()
        self.post_processor = PredictionPostProcessor()

    def predict(self, batch: list[Any]) -> list[float]:
        key = f"batch:{hash(str(batch))}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if hasattr(self.model, "predict"):
            raw = self.model.predict(batch)
        else:
            raw = [float(x) for x in batch]
        result = self.post_processor.process(list(raw))
        self.monitor.log("inference_batch_size", float(len(batch)))
        self.cache.set(key, result)
        return result


class StreamPredictor(BasePredictor):
    def __init__(self, model: Any) -> None:
        self.model = model
        self.post_processor = PredictionPostProcessor()

    def predict(self, batch: list[Any]) -> list[float]:
        if hasattr(self.model, "predict"):
            result = self.model.predict(batch)
        else:
            result = [float(x) for x in batch]
        return self.post_processor.process(list(result))

    async def predict_stream(self, stream: Iterable[list[Any]]) -> list[list[float]]:
        responses: list[list[float]] = []
        for batch in stream:
            responses.append(self.predict(batch))
            await asyncio.sleep(0)
        return responses


class AsyncInferenceEngine:
    def __init__(self, predictor: BasePredictor, max_workers: int = 2) -> None:
        self.predictor = predictor
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def predict_async(self, batch: list[Any]) -> list[float]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, self.predictor.predict, batch)
