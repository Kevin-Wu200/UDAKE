"""深度学习服务集成。"""

from __future__ import annotations

from typing import Any

__all__ = ["DeepLearningService"]


def __getattr__(name: str) -> Any:
    if name == "DeepLearningService":
        from .service import DeepLearningService

        return DeepLearningService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
