"""
依赖注入
"""
from fastapi import Depends, HTTPException, status
from .config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def get_settings():
    """获取配置"""
    return settings

def verify_task_id(task_id: str) -> str:
    """验证任务ID"""
    if not task_id or len(task_id) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的任务ID"
        )
    return task_id

async def get_current_user(token: Optional[str] = None):
    """获取当前用户（预留接口）"""
    return {"user_id": "default_user"}
