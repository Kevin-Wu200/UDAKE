"""分块处理工具。"""

from __future__ import annotations

from typing import Iterator, Tuple


def chunk_slices(total: int, block_size: int) -> Iterator[Tuple[int, int]]:
    """按 block_size 生成 [start, end) 切片。"""
    if total < 0:
        raise ValueError("total 不能为负数")
    if block_size <= 0:
        raise ValueError("block_size 必须大于 0")
    for start in range(0, total, block_size):
        end = min(total, start + block_size)
        yield start, end
