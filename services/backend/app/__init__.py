"""后端应用初始化：补齐仓库根目录路径，确保跨项目模块可导入。"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _ensure_python_multipart_alias() -> None:
    """为旧版 Starlette 提供 multipart 别名，避免兼容层导入告警。"""
    if "multipart" in sys.modules:
        return
    try:
        multipart_mod = importlib.import_module("python_multipart")
        multipart_submod = importlib.import_module("python_multipart.multipart")
    except ModuleNotFoundError:
        return
    sys.modules.setdefault("multipart", multipart_mod)
    sys.modules.setdefault("multipart.multipart", multipart_submod)


_ensure_python_multipart_alias()
