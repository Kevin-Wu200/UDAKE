"""批处理数据加载器。"""

from __future__ import annotations

from typing import Iterator, Sequence, Any
import random


class BatchDataLoader:
    def __init__(self, dataset: Sequence[Any], batch_size: int = 32, shuffle: bool = True, seed: int = 42) -> None:
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.seed = seed

    def __iter__(self) -> Iterator[list[Any]]:
        indices = list(range(len(self.dataset)))
        if self.shuffle:
            random.Random(self.seed).shuffle(indices)

        batch: list[Any] = []
        for idx in indices:
            batch.append(self.dataset[idx])
            if len(batch) >= self.batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
