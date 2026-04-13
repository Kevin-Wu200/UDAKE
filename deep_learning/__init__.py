"""深度学习基础架构包。"""

from __future__ import annotations

from typing import Any

__all__ = ["DeviceManager"]


def __getattr__(name: str) -> Any:
    if name == "DeviceManager":
        from .utils.device import DeviceManager

        return DeviceManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
