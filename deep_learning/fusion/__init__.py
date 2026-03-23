"""模型融合占位模块。"""

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class WeightedFusion:
    """基础加权融合器。"""

    weights: Sequence[float]

    def fuse(self, predictions: Iterable[Sequence[float]]) -> list[float]:
        rows = list(predictions)
        if not rows:
            return []
        total_w = sum(self.weights) or 1.0
        size = len(rows[0])
        result = [0.0] * size
        for w, row in zip(self.weights, rows):
            for idx in range(size):
                result[idx] += float(row[idx]) * w
        return [x / total_w for x in result]
