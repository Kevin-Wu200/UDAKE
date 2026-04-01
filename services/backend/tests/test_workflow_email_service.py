"""工作流邮件通知服务测试。"""

from __future__ import annotations

import time

from app.services.workflow_email_service import SMTPSettings, WorkflowEmailNotificationService


def _build_service(**kwargs) -> WorkflowEmailNotificationService:
    settings = SMTPSettings(
        host="smtp.qq.com",
        port=587,
        user="noreply@example.com",
        password="secret",
        use_tls=True,
        use_ssl=False,
        timeout_seconds=5,
        pool_size=1,
    )
    return WorkflowEmailNotificationService(
        smtp_settings=settings,
        retry_backoff_seconds=kwargs.get("retry_backoff_seconds", (0, 0, 0)),
        user_rate_limit_per_hour=kwargs.get("user_rate_limit_per_hour", 10),
        event_type_rate_limit_per_hour=kwargs.get("event_type_rate_limit_per_hour", 10),
        dedup_window_seconds=kwargs.get("dedup_window_seconds", 60),
        worker_count=1,
    )


def test_email_queue_retry_and_status_tracking() -> None:
    service = _build_service(retry_backoff_seconds=(0, 0))
    state = {"count": 0}

    def _fake_send(task):
        state["count"] += 1
        if state["count"] == 1:
            raise RuntimeError("mock send failed once")

    service._send_sync = _fake_send  # type: ignore[attr-defined]

    message_id = service.enqueue_mail(
        user_id="alice",
        to_email="alice@example.com",
        event_type="mention",
        context={"actor": "bob", "content": "hello", "document_url": "/#/doc/1", "message": "mention"},
    )

    assert service.wait_for_idle(timeout_seconds=3.0) is True
    status = service.get_status(message_id)
    assert status is not None
    assert status["status"] == "sent"
    assert state["count"] >= 2
    service.stop()


def test_email_dedup_and_rate_limit() -> None:
    service = _build_service(user_rate_limit_per_hour=1, event_type_rate_limit_per_hour=1, dedup_window_seconds=300)
    service._send_sync = lambda task: None  # type: ignore[attr-defined]

    first = service.enqueue_mail(
        user_id="alice",
        to_email="alice@example.com",
        event_type="mention",
        context={"actor": "bob", "content": "same", "document_url": "/#/doc/1", "message": "mention"},
    )
    second = service.enqueue_mail(
        user_id="alice",
        to_email="alice@example.com",
        event_type="mention",
        context={"actor": "bob", "content": "same", "document_url": "/#/doc/1", "message": "mention"},
    )
    third = service.enqueue_mail(
        user_id="alice",
        to_email="alice@example.com",
        event_type="comment_reply",
        context={"actor": "bob", "content": "new", "comment_url": "/#/c/1", "message": "reply"},
    )

    assert service.wait_for_idle(timeout_seconds=2.0) is True
    assert service.get_status(first)["status"] in {"queued", "sending", "sent"}
    assert service.get_status(second)["status"] == "skipped_duplicate"
    assert service.get_status(third)["status"] == "rate_limited"
    service.stop()


def test_validate_configuration_without_credentials() -> None:
    service = WorkflowEmailNotificationService(
        smtp_settings=SMTPSettings(host="", port=587, user="", password=""),
        retry_backoff_seconds=(0,),
        worker_count=1,
    )
    result = service.validate_configuration()
    assert result["enabled"] is False
    assert result["connected"] is False
    assert result["authenticated"] is False
    assert result["error"]
    service.stop()


def test_enqueue_batch_supports_priority_and_delay() -> None:
    service = _build_service(retry_backoff_seconds=(0,))
    records = []

    def _fake_send(task):
        records.append((task.message_id, task.event_type, time.time()))

    service._send_sync = _fake_send  # type: ignore[attr-defined]

    now = time.time()
    ids = service.enqueue_batch(
        [
            {
                "message_id": "m1",
                "user_id": "alice",
                "to_email": "alice@example.com",
                "event_type": "workflow_execution_completed",
                "context": {"result": "ok", "result_url": "/#/r/1", "message": "done"},
                "priority": "high",
            },
            {
                "message_id": "m2",
                "user_id": "bob",
                "to_email": "bob@example.com",
                "event_type": "comment_reply",
                "context": {"actor": "bob", "content": "ok", "comment_url": "/#/c/2", "message": "reply"},
                "priority": "low",
                "delay_seconds": 1,
            },
        ]
    )

    assert ids == ["m1", "m2"]
    assert service.wait_for_idle(timeout_seconds=4.0) is True
    assert len(records) == 2
    assert records[1][2] - now >= 0.8
    service.stop()
