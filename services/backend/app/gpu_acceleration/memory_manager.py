"""GPU/CPU数据传输与内存统计。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

import numpy as np

from .data_structures import ComputeBackend

try:  # pragma: no cover
    import cupy as cp  # type: ignore
except Exception:  # pragma: no cover
    cp = None


@dataclass
class MemoryStats:
    """内存传输统计。"""

    host_to_device_bytes: int = 0
    device_to_host_bytes: int = 0
    transfer_count: int = 0

    def to_dict(self) -> dict:
        return {
            "host_to_device_bytes": self.host_to_device_bytes,
            "device_to_host_bytes": self.device_to_host_bytes,
            "transfer_count": self.transfer_count,
        }


class GPUMemoryManager:
    """统一管理CPU/GPU数组转换。"""

    def __init__(self) -> None:
        self._stats = MemoryStats()

    @property
    def stats(self) -> MemoryStats:
        return self._stats

    def reset_stats(self) -> None:
        self._stats = MemoryStats()

    def estimate_bytes(self, arr: Any) -> int:
        if hasattr(arr, "nbytes"):
            return int(arr.nbytes)
        np_arr = np.asarray(arr)
        return int(np_arr.nbytes)

    def to_device(self, arr: Any, backend: ComputeBackend) -> Tuple[Any, int]:
        """将数组转换到目标后端。"""
        size = self.estimate_bytes(arr)
        if backend == ComputeBackend.GPU and cp is not None:
            self._stats.host_to_device_bytes += size
            self._stats.transfer_count += 1
            return cp.asarray(arr), size
        return np.asarray(arr), size

    def to_host(self, arr: Any, backend: ComputeBackend) -> Tuple[np.ndarray, int]:
        """将结果转换回CPU。"""
        if backend == ComputeBackend.GPU and cp is not None:
            host_arr = cp.asnumpy(arr)
            size = self.estimate_bytes(host_arr)
            self._stats.device_to_host_bytes += size
            self._stats.transfer_count += 1
            return host_arr, size
        host_arr = np.asarray(arr)
        return host_arr, self.estimate_bytes(host_arr)

    def cleanup(self) -> None:
        """主动释放GPU缓存。"""
        if cp is not None:
            try:  # pragma: no cover
                cp.get_default_memory_pool().free_all_blocks()
                cp.get_default_pinned_memory_pool().free_all_blocks()
            except Exception:
                pass
