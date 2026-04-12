"""后端服务目录下的跨项目包路径桥接。"""
from __future__ import annotations

from pathlib import Path

_REAL_PACKAGE_DIR = Path(__file__).resolve().parents[3] / "ai_extension"
__path__ = [str(_REAL_PACKAGE_DIR)]
