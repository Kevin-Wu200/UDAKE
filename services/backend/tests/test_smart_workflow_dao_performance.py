"""SmartWorkflow DAO performance-oriented tests."""

from __future__ import annotations

from app.services.smart_workflow_dao import (
    KVBase,
    QueryResultCache,
    SQLAlchemyCommentDAO,
    SQLAlchemyNotificationDAO,
    SQLAlchemyWorkflowDAO,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _build_sqlite_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    KVBase.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def test_sqlalchemy_comment_notification_query_filter_and_sort() -> None:
    session_factory = _build_sqlite_session_factory()
    comment_dao = SQLAlchemyCommentDAO("comment", session_factory)
    notification_dao = SQLAlchemyNotificationDAO("notification", session_factory)

    comment_dao.bulk_upsert(
        [
            ("c1", {"comment_id": "c1", "workflow_id": "wf-1", "content": "a", "created_at": "2026-04-01T01:00:00+00:00"}),
            ("c2", {"comment_id": "c2", "workflow_id": "wf-1", "content": "b", "created_at": "2026-04-01T03:00:00+00:00"}),
            ("c3", {"comment_id": "c3", "workflow_id": "wf-2", "content": "c", "created_at": "2026-04-01T02:00:00+00:00"}),
        ]
    )
    rows = comment_dao.list_by_workflow("wf-1", limit=10)
    assert [row["comment_id"] for row in rows] == ["c2", "c1"]

    notification_dao.bulk_upsert(
        [
            (
                "n1",
                {
                    "notification_id": "n1",
                    "workflow_id": "wf-1",
                    "user_id": "alice",
                    "read": False,
                    "created_at": "2026-04-01T01:00:00+00:00",
                },
            ),
            (
                "n2",
                {
                    "notification_id": "n2",
                    "workflow_id": "wf-1",
                    "user_id": "alice",
                    "read": True,
                    "created_at": "2026-04-01T02:00:00+00:00",
                },
            ),
            (
                "n3",
                {
                    "notification_id": "n3",
                    "workflow_id": "wf-1",
                    "user_id": "bob",
                    "read": False,
                    "created_at": "2026-04-01T03:00:00+00:00",
                },
            ),
        ]
    )

    all_rows = notification_dao.list_by_user("wf-1", "alice", unread_only=False, limit=10)
    unread_rows = notification_dao.list_by_user("wf-1", "alice", unread_only=True, limit=10)
    assert [row["notification_id"] for row in all_rows] == ["n2", "n1"]
    assert [row["notification_id"] for row in unread_rows] == ["n1"]


def test_sqlalchemy_workflow_bulk_upsert_update_and_cache_invalidate() -> None:
    session_factory = _build_sqlite_session_factory()
    cache = QueryResultCache(ttl_seconds=10.0, max_entries=32)
    dao = SQLAlchemyWorkflowDAO("workflow", session_factory, query_cache=cache)

    assert dao.bulk_upsert([("wf-a", {"workflow_id": "wf-a", "name": "A"})]) == 1
    one = dao.get("wf-a")
    assert one is not None
    assert one["name"] == "A"

    # 命中缓存后更新，必须可见最新值。
    assert dao.bulk_upsert([("wf-a", {"workflow_id": "wf-a", "name": "A2"})]) == 1
    after = dao.get("wf-a")
    assert after is not None
    assert after["name"] == "A2"
