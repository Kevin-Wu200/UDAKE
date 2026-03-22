"""GPU设备检测与后端选择。"""

from __future__ import annotations

from typing import List, Optional

from .data_structures import ComputeBackend, GPUDeviceInfo

try:  # pragma: no cover - 依赖运行环境
    import cupy as cp  # type: ignore
except Exception:  # pragma: no cover - 依赖运行环境
    cp = None


class DeviceManager:
    """管理GPU设备能力与后端选择策略。"""

    def __init__(self, force_cpu: bool = False):
        self.force_cpu = force_cpu
        self._devices: List[GPUDeviceInfo] = []
        self._backend = ComputeBackend.CPU
        self._probe_devices()

    def _probe_devices(self) -> None:
        if self.force_cpu or cp is None:
            self._devices = []
            self._backend = ComputeBackend.CPU
            return

        devices: List[GPUDeviceInfo] = []
        try:
            runtime = cp.cuda.runtime
            device_count = int(runtime.getDeviceCount())
            driver_version = str(runtime.driverGetVersion())
            for idx in range(device_count):
                with cp.cuda.Device(idx):
                    props = runtime.getDeviceProperties(idx)
                    free_mem, total_mem = runtime.memGetInfo()
                    major = props.get("major", 0)
                    minor = props.get("minor", 0)
                    raw_name = props.get("name", b"GPU")
                    if isinstance(raw_name, bytes):
                        name = raw_name.decode("utf-8", errors="ignore")
                    else:
                        name = str(raw_name)
                    devices.append(
                        GPUDeviceInfo(
                            device_id=idx,
                            name=name,
                            total_memory_mb=total_mem / (1024 * 1024),
                            free_memory_mb=free_mem / (1024 * 1024),
                            compute_capability=f"{major}.{minor}",
                            driver_version=driver_version,
                            supports_fp16=major >= 5,
                        )
                    )
        except Exception:
            devices = []

        self._devices = devices
        self._backend = ComputeBackend.GPU if devices else ComputeBackend.CPU

    def refresh(self) -> None:
        """刷新设备状态。"""
        self._probe_devices()

    def is_gpu_available(self) -> bool:
        return bool(self._devices)

    def get_backend(self) -> ComputeBackend:
        return self._backend

    def get_devices(self) -> List[GPUDeviceInfo]:
        return list(self._devices)

    def get_primary_device(self) -> Optional[GPUDeviceInfo]:
        return self._devices[0] if self._devices else None

    def auto_select_backend(self, problem_size: int, min_size_for_gpu: int = 25_000) -> ComputeBackend:
        """基于数据规模自动选择计算后端。"""
        if self.force_cpu or not self.is_gpu_available():
            return ComputeBackend.CPU
        if problem_size < max(1, min_size_for_gpu):
            return ComputeBackend.CPU
        return ComputeBackend.GPU
