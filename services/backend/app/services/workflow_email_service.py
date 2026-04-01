"""工作流邮件通知服务：SMTP + 模板渲染 + 异步队列。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import smtplib
import ssl
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itertools import count
from queue import LifoQueue, Empty, Full
from typing import Any, Deque, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


DEFAULT_RETRY_BACKOFF_SECONDS: Tuple[int, ...] = (60, 300, 900)
DEFAULT_EVENT_TYPE_RATE_LIMIT_PER_HOUR = 30
DEFAULT_USER_RATE_LIMIT_PER_HOUR = 10
DEFAULT_DEDUP_WINDOW_SECONDS = 300


@dataclass(frozen=True)
class SMTPSettings:
    host: str
    port: int
    user: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False
    timeout_seconds: int = 15
    pool_size: int = 4

    @property
    def enabled(self) -> bool:
        return bool(self.host.strip() and self.user.strip() and self.password.strip())

    @classmethod
    def from_env(cls) -> "SMTPSettings":
        host = str(os.getenv("SMTP_HOST", "smtp.qq.com")).strip()
        port = int(os.getenv("SMTP_PORT", "587"))
        use_tls = str(os.getenv("SMTP_USE_TLS", "true")).strip().lower() in {"1", "true", "yes", "on"}
        use_ssl = str(os.getenv("SMTP_USE_SSL", "false")).strip().lower() in {"1", "true", "yes", "on"}
        if port == 465 and os.getenv("SMTP_USE_SSL") is None:
            use_ssl = True
            use_tls = False
        return cls(
            host=host,
            port=port,
            user=str(os.getenv("SMTP_USER", "")).strip(),
            password=str(os.getenv("SMTP_PASSWORD", "")).strip(),
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout_seconds=max(5, int(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))),
            pool_size=max(1, int(os.getenv("SMTP_POOL_SIZE", "4"))),
        )


@dataclass
class _PooledSMTP:
    smtp: smtplib.SMTP
    created_at: float


class SMTPConnectionPool:
    """简易 SMTP 连接池。"""

    def __init__(self, settings: SMTPSettings, idle_timeout_seconds: int = 120) -> None:
        self._settings = settings
        self._idle_timeout_seconds = max(30, int(idle_timeout_seconds))
        self._queue: LifoQueue[_PooledSMTP] = LifoQueue(maxsize=max(1, settings.pool_size))

    def _create_connection(self) -> smtplib.SMTP:
        if self._settings.use_ssl:
            context = ssl.create_default_context()
            smtp = smtplib.SMTP_SSL(
                self._settings.host,
                self._settings.port,
                timeout=self._settings.timeout_seconds,
                context=context,
            )
        else:
            smtp = smtplib.SMTP(
                self._settings.host,
                self._settings.port,
                timeout=self._settings.timeout_seconds,
            )
            smtp.ehlo()
            if self._settings.use_tls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
        smtp.login(self._settings.user, self._settings.password)
        return smtp

    @contextmanager
    def acquire(self):
        pooled: Optional[_PooledSMTP] = None
        now = time.time()
        while True:
            try:
                candidate = self._queue.get_nowait()
            except Empty:
                break
            if now - candidate.created_at <= self._idle_timeout_seconds:
                pooled = candidate
                break
            try:
                candidate.smtp.quit()
            except Exception:
                try:
                    candidate.smtp.close()
                except Exception:
                    pass

        smtp = pooled.smtp if pooled is not None else self._create_connection()
        broken = False
        try:
            yield smtp
        except Exception:
            broken = True
            raise
        finally:
            if broken:
                try:
                    smtp.quit()
                except Exception:
                    try:
                        smtp.close()
                    except Exception:
                        pass
            else:
                try:
                    self._queue.put_nowait(_PooledSMTP(smtp=smtp, created_at=time.time()))
                except Full:
                    try:
                        smtp.quit()
                    except Exception:
                        try:
                            smtp.close()
                        except Exception:
                            pass


@dataclass
class EmailTask:
    message_id: str
    event_type: str
    user_id: str
    to_email: str
    subject: str
    html_content: str
    plain_text: str
    payload: Dict[str, Any]
    created_at: float
    scheduled_at: float
    priority: int
    attempts: int = 0


class WorkflowEmailTemplateEngine:
    """Jinja2 模板渲染与缓存。"""

    def __init__(self) -> None:
        self._subject_templates: Dict[str, str] = {
            "invite_notification": "您被邀请加入团队/文档",
            "mention": "您在文档中被@提及",
            "comment_reply": "您的评论收到了回复",
            "share_link_access": "您的分享链接被访问",
            "conflict_resolved": "协作冲突已解决",
            "workflow_execution_completed": "工作流执行完成",
        }
        self._html_templates: Dict[str, str] = {
            "invite_notification": (
                "<h2>协作邀请通知</h2>"
                "<p><b>{{ inviter }}</b> 邀请您加入协作。</p>"
                "<p>团队：{{ team_name }}</p>"
                "<p>文档/工作流：{{ document_name }}</p>"
                "<p><a href='{{ action_url }}'>点击查看邀请</a></p>"
            ),
            "mention": (
                "<h2>您被@提及</h2>"
                "<p>提及人：{{ actor }}</p>"
                "<p>内容摘要：{{ content }}</p>"
                "<p><a href='{{ document_url }}'>查看文档</a></p>"
            ),
            "comment_reply": (
                "<h2>评论回复提醒</h2>"
                "<p>回复人：{{ actor }}</p>"
                "<p>回复内容：{{ content }}</p>"
                "<p><a href='{{ comment_url }}'>查看原评论</a></p>"
            ),
            "share_link_access": (
                "<h2>分享链接访问提醒</h2>"
                "<p>访问者：{{ visitor }}</p>"
                "<p>访问时间：{{ visited_at }}</p>"
                "<p><a href='{{ document_url }}'>查看文档</a></p>"
            ),
            "conflict_resolved": (
                "<h2>冲突已解决</h2>"
                "<p>解决结果：{{ result }}</p>"
                "<p><a href='{{ document_url }}'>查看文档</a></p>"
            ),
            "workflow_execution_completed": (
                "<h2>工作流执行完成</h2>"
                "<p>执行结果：{{ result }}</p>"
                "<p><a href='{{ result_url }}'>查看执行结果</a></p>"
            ),
        }

        self._jinja_env = None
        try:
            from jinja2 import BaseLoader, Environment, StrictUndefined, select_autoescape  # type: ignore

            self._jinja_env = Environment(
                loader=BaseLoader(),
                autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True),
                trim_blocks=True,
                lstrip_blocks=True,
                cache_size=64,
                undefined=StrictUndefined,
            )
        except Exception:
            self._jinja_env = None

    def _render(self, content: str, context: Mapping[str, Any]) -> str:
        if self._jinja_env is not None:
            try:
                template = self._jinja_env.from_string(content)
                return template.render(**dict(context))
            except Exception:
                pass
        rendered = content
        for key, value in context.items():
            rendered = rendered.replace(f"{{{{ {key} }}}}", str(value))
        return rendered

    def render(self, event_type: str, context: Mapping[str, Any]) -> Tuple[str, str, str]:
        subject_tpl = self._subject_templates.get(event_type, "协作通知")
        html_tpl = self._html_templates.get(
            event_type,
            "<h2>协作通知</h2><p>{{ message }}</p>",
        )
        subject = self._render(subject_tpl, context)
        html = self._render(html_tpl, context)
        plain = self._render(
            "{subject}\n\n{message}".format(subject=subject, message=str(context.get("message") or "")),
            context,
        )
        return subject, html, plain


class WorkflowEmailNotificationService:
    """工作流邮件通知服务。"""

    def __init__(
        self,
        smtp_settings: Optional[SMTPSettings] = None,
        *,
        retry_backoff_seconds: Sequence[int] = DEFAULT_RETRY_BACKOFF_SECONDS,
        user_rate_limit_per_hour: int = DEFAULT_USER_RATE_LIMIT_PER_HOUR,
        event_type_rate_limit_per_hour: int = DEFAULT_EVENT_TYPE_RATE_LIMIT_PER_HOUR,
        dedup_window_seconds: int = DEFAULT_DEDUP_WINDOW_SECONDS,
        worker_count: int = 2,
    ) -> None:
        self._smtp_settings = smtp_settings or SMTPSettings.from_env()
        self._template_engine = WorkflowEmailTemplateEngine()
        self._retry_backoff_seconds = tuple(max(0, int(item)) for item in (retry_backoff_seconds or ())) or (0,)
        self._user_rate_limit_per_hour = max(1, int(user_rate_limit_per_hour))
        self._event_type_rate_limit_per_hour = max(1, int(event_type_rate_limit_per_hour))
        self._dedup_window_seconds = max(30, int(dedup_window_seconds))
        self._worker_count = max(1, int(worker_count))
        self._pool = SMTPConnectionPool(self._smtp_settings)

        self._status_by_message_id: Dict[str, Dict[str, Any]] = {}
        self._delivery_logs: List[Dict[str, Any]] = []
        self._dedup_cache: Dict[str, float] = {}
        self._user_send_timestamps: Dict[str, Deque[float]] = {}
        self._event_send_timestamps: Dict[str, Deque[float]] = {}
        self._inflight_ids: set[str] = set()
        self._lock = threading.RLock()
        self._counter = count(1)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_ready = threading.Event()
        self._queue: Optional[asyncio.PriorityQueue[Tuple[float, int, int, EmailTask]]] = None
        self._workers: List[asyncio.Task[Any]] = []
        self._running = False

        self.start()

    @property
    def enabled(self) -> bool:
        return self._smtp_settings.enabled

    def _append_log(self, item: Mapping[str, Any]) -> None:
        with self._lock:
            self._delivery_logs.append(dict(item))
            if len(self._delivery_logs) > 2000:
                self._delivery_logs = self._delivery_logs[-2000:]

    def _update_status(self, message_id: str, **updates: Any) -> None:
        with self._lock:
            status = self._status_by_message_id.setdefault(message_id, {"message_id": message_id})
            status.update(updates)
            status.setdefault("updated_at", time.time())
            status["updated_at"] = time.time()

    def _cleanup_rate_limit_window(self, bucket: Deque[float], now: float) -> None:
        threshold = now - 3600
        while bucket and bucket[0] < threshold:
            bucket.popleft()

    def _cleanup_dedup(self, now: float) -> None:
        expired = [key for key, ts in self._dedup_cache.items() if ts < now]
        for key in expired:
            self._dedup_cache.pop(key, None)

    def _is_rate_limited(self, user_id: str, event_type: str, now: float) -> bool:
        user_bucket = self._user_send_timestamps.setdefault(user_id, deque())
        event_bucket = self._event_send_timestamps.setdefault(f"{user_id}:{event_type}", deque())
        self._cleanup_rate_limit_window(user_bucket, now)
        self._cleanup_rate_limit_window(event_bucket, now)
        if len(user_bucket) >= self._user_rate_limit_per_hour:
            return True
        if len(event_bucket) >= self._event_type_rate_limit_per_hour:
            return True
        user_bucket.append(now)
        event_bucket.append(now)
        return False

    def _build_message(self, *, to_email: str, subject: str, html_content: str, plain_text: str) -> str:
        message = MIMEMultipart("alternative")
        message["From"] = self._smtp_settings.user
        message["To"] = to_email
        message["Subject"] = subject
        if plain_text:
            message.attach(MIMEText(plain_text, "plain", "utf-8"))
        message.attach(MIMEText(html_content, "html", "utf-8"))
        return message.as_string()

    def _send_sync(self, task: EmailTask) -> None:
        if not self.enabled:
            raise RuntimeError("SMTP 未配置")
        message = self._build_message(
            to_email=task.to_email,
            subject=task.subject,
            html_content=task.html_content,
            plain_text=task.plain_text,
        )
        with self._pool.acquire() as smtp:
            smtp.sendmail(self._smtp_settings.user, [task.to_email], message)

    async def _worker(self, worker_index: int) -> None:
        if self._queue is None:
            return
        while self._running:
            try:
                scheduled_at, _priority, _seq, task = await self._queue.get()
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.1)
                continue

            now = time.time()
            wait_seconds = scheduled_at - now
            if wait_seconds > 0:
                await asyncio.sleep(min(wait_seconds, 2.0))

            with self._lock:
                self._inflight_ids.add(task.message_id)

            self._update_status(task.message_id, status="sending", worker=worker_index, attempts=task.attempts)

            try:
                await asyncio.to_thread(self._send_sync, task)
                self._update_status(
                    task.message_id,
                    status="sent",
                    sent_at=time.time(),
                    error="",
                )
                self._append_log(
                    {
                        "message_id": task.message_id,
                        "event_type": task.event_type,
                        "user_id": task.user_id,
                        "recipient": task.to_email,
                        "status": "sent",
                        "attempts": task.attempts,
                        "timestamp": time.time(),
                    }
                )
            except Exception as exc:  # pylint: disable=broad-except
                task.attempts += 1
                max_attempts = len(self._retry_backoff_seconds) + 1
                if task.attempts < max_attempts and self._queue is not None:
                    backoff = self._retry_backoff_seconds[min(task.attempts - 1, len(self._retry_backoff_seconds) - 1)]
                    task.scheduled_at = time.time() + max(0, backoff)
                    await self._queue.put((task.scheduled_at, task.priority, next(self._counter), task))
                    self._update_status(
                        task.message_id,
                        status="retrying",
                        attempts=task.attempts,
                        error=str(exc),
                        next_retry_at=task.scheduled_at,
                    )
                else:
                    self._update_status(
                        task.message_id,
                        status="failed",
                        attempts=task.attempts,
                        error=str(exc),
                        failed_at=time.time(),
                    )
                    self._append_log(
                        {
                            "message_id": task.message_id,
                            "event_type": task.event_type,
                            "user_id": task.user_id,
                            "recipient": task.to_email,
                            "status": "failed",
                            "attempts": task.attempts,
                            "error": str(exc),
                            "timestamp": time.time(),
                        }
                    )
                    logger.warning("邮件发送失败 message_id=%s err=%s", task.message_id, exc)
            finally:
                with self._lock:
                    self._inflight_ids.discard(task.message_id)
                if self._queue is not None:
                    self._queue.task_done()

    def _loop_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._queue = asyncio.PriorityQueue()
        self._running = True
        self._workers = [loop.create_task(self._worker(i + 1)) for i in range(self._worker_count)]
        self._loop_ready.set()
        loop.run_forever()

        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

    def start(self) -> None:
        if self._loop_thread and self._loop_thread.is_alive():
            return
        self._loop_ready.clear()
        self._loop_thread = threading.Thread(target=self._loop_main, name="workflow-email-loop", daemon=True)
        self._loop_thread.start()
        self._loop_ready.wait(timeout=2.0)

    def stop(self) -> None:
        self._running = False
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2.0)

    def validate_configuration(self, test_recipient: Optional[str] = None) -> Dict[str, Any]:
        result = {
            "enabled": self.enabled,
            "connected": False,
            "authenticated": False,
            "test_email_sent": False,
            "error": "",
        }
        if not self.enabled:
            result["error"] = "SMTP 配置不完整"
            return result

        try:
            with self._pool.acquire() as smtp:
                smtp.noop()
            result["connected"] = True
            result["authenticated"] = True
        except Exception as exc:  # pylint: disable=broad-except
            result["error"] = str(exc)
            return result

        if test_recipient:
            message_id = self.enqueue_mail(
                user_id="smtp-validator",
                to_email=test_recipient,
                event_type="workflow_execution_completed",
                context={
                    "result": "SMTP 测试邮件",
                    "result_url": "#",
                    "message": "这是一封测试邮件",
                },
                priority="high",
            )
            status = self.get_status(message_id)
            result["test_email_sent"] = bool(status and status.get("status") in {"queued", "sending", "sent"})
        return result

    def enqueue_mail(
        self,
        *,
        user_id: str,
        to_email: str,
        event_type: str,
        context: Optional[Mapping[str, Any]] = None,
        priority: str = "normal",
        delay_seconds: int = 0,
        message_id: Optional[str] = None,
    ) -> str:
        context_data = dict(context or {})
        context_data.setdefault("message", str(context_data.get("message") or "协作通知"))

        message_id_value = str(message_id or f"mail_{int(time.time() * 1000)}_{next(self._counter)}")
        now = time.time()
        scheduled_at = now + max(0, int(delay_seconds))

        with self._lock:
            self._cleanup_dedup(now)
            dedup_key = hashlib.sha256(
                f"{to_email.strip().lower()}|{event_type}|{json_like(context_data)}".encode("utf-8")
            ).hexdigest()
            if dedup_key in self._dedup_cache:
                self._update_status(
                    message_id_value,
                    status="skipped_duplicate",
                    reason="duplicate_within_window",
                    recipient=to_email,
                    event_type=event_type,
                )
                return message_id_value

            if self._is_rate_limited(str(user_id), str(event_type), now):
                self._update_status(
                    message_id_value,
                    status="rate_limited",
                    reason="rate_limit_exceeded",
                    recipient=to_email,
                    event_type=event_type,
                )
                return message_id_value

            self._dedup_cache[dedup_key] = now + self._dedup_window_seconds

        subject, html_content, plain_text = self._template_engine.render(event_type=event_type, context=context_data)

        priority_value = {"high": 0, "normal": 1, "low": 2}.get(str(priority).lower(), 1)
        task = EmailTask(
            message_id=message_id_value,
            event_type=str(event_type),
            user_id=str(user_id),
            to_email=str(to_email).strip(),
            subject=subject,
            html_content=html_content,
            plain_text=plain_text,
            payload=context_data,
            created_at=now,
            scheduled_at=scheduled_at,
            priority=priority_value,
        )

        self._update_status(
            message_id_value,
            status="queued",
            queued_at=now,
            scheduled_at=scheduled_at,
            recipient=task.to_email,
            event_type=task.event_type,
            subject=subject,
        )

        if self._queue is None or self._loop is None:
            self._update_status(message_id_value, status="failed", error="邮件队列未启动")
            return message_id_value

        future = asyncio.run_coroutine_threadsafe(
            self._queue.put((scheduled_at, priority_value, next(self._counter), task)),
            self._loop,
        )
        future.result(timeout=2.0)
        return message_id_value

    def enqueue_batch(self, tasks: Iterable[Mapping[str, Any]]) -> List[str]:
        message_ids: List[str] = []
        for item in tasks:
            message_ids.append(
                self.enqueue_mail(
                    user_id=str(item.get("user_id") or "unknown"),
                    to_email=str(item.get("to_email") or ""),
                    event_type=str(item.get("event_type") or "workflow_execution_completed"),
                    context=dict(item.get("context") or {}),
                    priority=str(item.get("priority") or "normal"),
                    delay_seconds=int(item.get("delay_seconds") or 0),
                    message_id=str(item.get("message_id") or "") or None,
                )
            )
        return message_ids

    def get_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            item = self._status_by_message_id.get(str(message_id))
            return dict(item) if item else None

    def get_delivery_logs(self, limit: int = 200) -> List[Dict[str, Any]]:
        size = max(1, min(int(limit), 2000))
        with self._lock:
            return [dict(item) for item in self._delivery_logs[-size:]]

    def queue_snapshot(self) -> Dict[str, Any]:
        qsize = self._queue.qsize() if self._queue is not None else 0
        with self._lock:
            inflight = len(self._inflight_ids)
            pending = sum(
                1
                for item in self._status_by_message_id.values()
                if str(item.get("status") or "") in {"queued", "sending", "retrying"}
            )
        return {"queued": qsize, "inflight": inflight, "pending": pending, "running": self._running}

    def wait_for_idle(self, timeout_seconds: float = 5.0) -> bool:
        deadline = time.time() + max(0.1, timeout_seconds)
        while time.time() < deadline:
            snap = self.queue_snapshot()
            if snap["queued"] == 0 and snap["inflight"] == 0 and snap["pending"] == 0:
                return True
            time.sleep(0.05)
        return False


def json_like(payload: Mapping[str, Any]) -> str:
    # 仅用于去重哈希，不要求严格 JSON。
    keys = sorted(payload.keys())
    parts: List[str] = []
    for key in keys:
        parts.append(f"{key}:{payload.get(key)!r}")
    return "|".join(parts)


_workflow_email_service: Optional[WorkflowEmailNotificationService] = None


def get_workflow_email_service() -> WorkflowEmailNotificationService:
    global _workflow_email_service
    if _workflow_email_service is None:
        retry_env = str(os.getenv("WORKFLOW_EMAIL_RETRY_BACKOFF_SECONDS", "")).strip()
        if retry_env:
            retry_list = [int(item.strip()) for item in retry_env.split(",") if item.strip()]
        else:
            retry_list = list(DEFAULT_RETRY_BACKOFF_SECONDS)

        _workflow_email_service = WorkflowEmailNotificationService(
            retry_backoff_seconds=retry_list,
            user_rate_limit_per_hour=max(1, int(os.getenv("WORKFLOW_EMAIL_USER_LIMIT_PER_HOUR", "10"))),
            event_type_rate_limit_per_hour=max(
                1,
                int(os.getenv("WORKFLOW_EMAIL_EVENT_LIMIT_PER_HOUR", str(DEFAULT_EVENT_TYPE_RATE_LIMIT_PER_HOUR))),
            ),
            dedup_window_seconds=max(30, int(os.getenv("WORKFLOW_EMAIL_DEDUP_SECONDS", "300"))),
            worker_count=max(1, int(os.getenv("WORKFLOW_EMAIL_WORKERS", "2"))),
        )
    return _workflow_email_service


__all__ = [
    "SMTPSettings",
    "WorkflowEmailNotificationService",
    "WorkflowEmailTemplateEngine",
    "get_workflow_email_service",
]
