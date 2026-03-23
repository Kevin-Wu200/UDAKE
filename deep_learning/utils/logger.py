"""日志聚合器。"""

from __future__ import annotations

import logging
from collections import defaultdict


class StructuredLogger:
    def __init__(self, name: str = "deep_learning") -> None:
        self.logger = logging.getLogger(name)
        self._buffer: dict[str, list[dict[str, str]]] = defaultdict(list)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log(self, level: str, message: str, **fields: str) -> None:
        payload = {"message": message, **{k: str(v) for k, v in fields.items()}}
        self._buffer[level].append(payload)
        getattr(self.logger, level.lower(), self.logger.info)(f"{message} | {payload}")

    def aggregate(self) -> dict[str, int]:
        return {level: len(records) for level, records in self._buffer.items()}
