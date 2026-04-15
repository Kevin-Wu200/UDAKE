"""Scheduled tasks for key expiry checking and reminder email sending."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from ..auth import get_auth_service
from ..auth_db.session import get_auth_session_factory
from ..config import settings
from ..services.company_admin_policy_service import mark_expired_product_keys, send_expiry_reminders

logger = logging.getLogger(__name__)


def _build_result(task_name: str, *, started_at: datetime, status: str, details: Dict[str, Any]) -> Dict[str, Any]:
    ended_at = datetime.utcnow()
    duration_ms = int((ended_at - started_at).total_seconds() * 1000)
    return {
        "task_name": task_name,
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": ended_at.isoformat(),
        "duration_ms": duration_ms,
        "details": details,
    }


def run_expiry_check_task(*, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Run key expiry check task and return execution report."""
    started_at = datetime.utcnow()
    session_factory = get_auth_session_factory()
    db = session_factory()
    try:
        stats = mark_expired_product_keys(db, now=now)
        db.commit()
        result = _build_result("expiry_check", started_at=started_at, status="success", details=stats)
        logger.info("任务执行完成 expiry_check result=%s", result)
        return result
    except Exception as exc:  # pragma: no cover - defensive branch
        db.rollback()
        logger.exception("任务执行失败 expiry_check err=%s", exc)
        return _build_result(
            "expiry_check",
            started_at=started_at,
            status="failed",
            details={"error": str(exc), "expired_keys": 0, "expired_related_keys": 0},
        )
    finally:
        db.close()


def run_expiry_reminder_task(*, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Run reminder task with retry and return execution report."""
    started_at = datetime.utcnow()
    session_factory = get_auth_session_factory()
    auth_service = get_auth_service()

    max_retries = int(max(1, getattr(settings, "KEY_EXPIRY_REMINDER_RETRY_TIMES", 3)))
    retry_interval = int(max(1, getattr(settings, "KEY_EXPIRY_REMINDER_RETRY_INTERVAL_SECONDS", 60)))
    last_error = ""
    retries = 0

    while retries < max_retries:
        db = session_factory()
        try:
            stats = send_expiry_reminders(db, auth_service=auth_service, now=now)
            db.commit()
            details = {**stats, "retries": retries}
            result = _build_result("expiry_reminder", started_at=started_at, status="success", details=details)
            logger.info("任务执行完成 expiry_reminder result=%s", result)
            return result
        except Exception as exc:  # pragma: no cover - external SMTP/cache dependency
            db.rollback()
            retries += 1
            last_error = str(exc)
            logger.warning("任务执行异常 expiry_reminder retry=%s/%s err=%s", retries, max_retries, exc)
            if retries < max_retries:
                time.sleep(retry_interval)
        finally:
            db.close()

    return _build_result(
        "expiry_reminder",
        started_at=started_at,
        status="failed",
        details={"candidates": 0, "sent": 0, "skipped": 0, "failed": 0, "retries": retries, "error": last_error},
    )


def run_all_scheduler_tasks(*, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Run both scheduler tasks in sequence and return summary."""
    started_at = datetime.utcnow()
    expiry_result = run_expiry_check_task(now=now)
    reminder_result = run_expiry_reminder_task(now=now)
    overall_status = "success" if expiry_result["status"] == "success" and reminder_result["status"] == "success" else "partial_failed"
    return _build_result(
        "scheduler_bundle",
        started_at=started_at,
        status=overall_status,
        details={"expiry_check": expiry_result, "expiry_reminder": reminder_result},
    )

