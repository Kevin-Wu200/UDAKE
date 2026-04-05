"""输入验证工具。"""

from __future__ import annotations

from typing import Mapping, Sequence


def validate_st_series(series: Mapping[str, Sequence[float]]) -> None:
    """校验 x/y/z/t/value 长度一致且样本点数量满足最小要求。"""
    keys = ("x", "y", "z", "t", "value")
    lengths = [len(series.get(key, [])) for key in keys]
    if lengths[0] < 3:
        raise ValueError("至少需要 3 个样本点")
    if len(set(lengths)) != 1:
        raise ValueError("x/y/z/t/value 长度必须一致")
