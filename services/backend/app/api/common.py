"""API 层通用错误处理工具。"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException


def raise_api_error(exc: Exception, *, default_message: Optional[str] = None) -> None:
    """将服务层异常统一映射为 HTTPException。"""
    message = str(exc) or (default_message or "请求处理失败")
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=message) from exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=message) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=message) from exc
    raise HTTPException(status_code=500, detail=default_message or message) from exc
