"""Scheduler management APIs for key expiry jobs."""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import JWTValidationError, get_auth_service
from ..auth_db.models import User
from ..auth_db.session import get_auth_db_session
from ..scheduler.key_expiry_scheduler import get_scheduler_manager

router = APIRouter(prefix="/scheduler")


def _fail(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"success": False, "message": message, "data": {}})


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "缺少或无效的Bearer Token")
    return token


def _require_admin(request: Request, db: Session) -> User:
    token = _extract_bearer_token(request)
    auth_service = get_auth_service()
    try:
        payload = auth_service.jwt.verify_token(token, expected_type="access", check_blacklist=True)
    except JWTValidationError as exc:
        raise _fail(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user_id = payload.get("user_id")
    if not user_id:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "Token缺少用户标识")
    user = db.query(User).filter(User.id == int(user_id)).one_or_none()
    if not user:
        raise _fail(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    if user.role not in {"admin", "super_admin"}:
        raise _fail(status.HTTP_403_FORBIDDEN, "仅管理员可访问调度任务管理")
    return user


class UpdateScheduleRequest(BaseModel):
    execute_time: str = Field(..., description="执行时间，格式 HH:MM")


@router.get("/jobs")
def list_scheduler_jobs(
    request: Request,
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, object]:
    _require_admin(request, db)
    scheduler = get_scheduler_manager()
    return {"success": True, "message": "ok", "data": {"jobs": scheduler.get_tasks_snapshot()}}


@router.get("/history")
def list_scheduler_history(
    request: Request,
    limit: int = 100,
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, object]:
    _require_admin(request, db)
    scheduler = get_scheduler_manager()
    return {"success": True, "message": "ok", "data": {"history": scheduler.get_history(limit=limit)}}


@router.post("/run/{task_name}")
def trigger_scheduler_job(
    task_name: str,
    request: Request,
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, object]:
    _require_admin(request, db)
    scheduler = get_scheduler_manager()
    result = scheduler.trigger_now(task_name)
    status_code = status.HTTP_200_OK if result.get("ok") else status.HTTP_404_NOT_FOUND
    if status_code != status.HTTP_200_OK:
        raise _fail(status_code, str(result.get("message") or "任务不存在"))
    return {"success": True, "message": "任务触发成功", "data": result}


@router.post("/pause/{task_name}")
def pause_scheduler_job(
    task_name: str,
    request: Request,
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, object]:
    _require_admin(request, db)
    scheduler = get_scheduler_manager()
    result = scheduler.pause_task(task_name)
    if not result.get("ok"):
        raise _fail(status.HTTP_404_NOT_FOUND, str(result.get("message") or "任务不存在"))
    return {"success": True, "message": "任务已暂停", "data": result}


@router.post("/resume/{task_name}")
def resume_scheduler_job(
    task_name: str,
    request: Request,
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, object]:
    _require_admin(request, db)
    scheduler = get_scheduler_manager()
    result = scheduler.resume_task(task_name)
    if not result.get("ok"):
        raise _fail(status.HTTP_404_NOT_FOUND, str(result.get("message") or "任务不存在"))
    return {"success": True, "message": "任务已恢复", "data": result}


@router.put("/schedule/{task_name}")
def update_scheduler_job_schedule(
    task_name: str,
    payload: UpdateScheduleRequest,
    request: Request,
    db: Session = Depends(get_auth_db_session),
) -> Dict[str, object]:
    _require_admin(request, db)
    scheduler = get_scheduler_manager()
    result = scheduler.update_task_schedule(task_name, payload.execute_time)
    if not result.get("ok"):
        raise _fail(status.HTTP_404_NOT_FOUND, str(result.get("message") or "任务不存在"))
    return {"success": True, "message": "任务执行时间已更新", "data": result}

