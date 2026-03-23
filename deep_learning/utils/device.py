"""设备与加速能力管理。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class DeviceProfile:
    device: str
    cuda_available: bool
    mps_available: bool


class DeviceManager:
    """统一管理 CPU/CUDA/MPS 设备选择。"""

    def __init__(self) -> None:
        self._torch = None
        try:
            import torch  # type: ignore

            self._torch = torch
        except Exception:
            self._torch = None

    def detect(self, preferred: str | None = None) -> DeviceProfile:
        if self._torch is None:
            return DeviceProfile(device="cpu", cuda_available=False, mps_available=False)

        cuda_available = bool(self._torch.cuda.is_available())
        mps_available = bool(
            getattr(self._torch.backends, "mps", None)
            and self._torch.backends.mps.is_available()
        )

        if preferred in {"cpu", "cuda", "mps"}:
            target = preferred
        elif cuda_available:
            target = "cuda"
        elif mps_available:
            target = "mps"
        else:
            target = "cpu"

        if target == "cuda" and not cuda_available:
            target = "cpu"
        if target == "mps" and not mps_available:
            target = "cpu"

        return DeviceProfile(device=target, cuda_available=cuda_available, mps_available=mps_available)

    def configure(self, preferred: str | None = None) -> DeviceProfile:
        profile = self.detect(preferred)
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        if self._torch is not None and profile.device == "cuda":
            self._torch.backends.cudnn.benchmark = True
        return profile
