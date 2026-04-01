"""SmartWorkflow DAO 单元测试。"""

from __future__ import annotations

from app.services.smart_workflow_dao import (
    InMemoryCommentDAO,
    InMemoryNotificationDAO,
    InMemoryTeamDAO,
    InMemoryWorkflowDAO,
)


def test_workflow_dao_crud_paginate_bulk() -> None:
    store = {}
    dao = InMemoryWorkflowDAO(store)

    dao.upsert("wf_a", {"workflow_id": "wf_a", "name": "A"})
    dao.upsert("wf_b", {"workflow_id": "wf_b", "name": "B"})

    assert dao.get("wf_a") is not None
    page = dao.paginate(offset=0, limit=1)
    assert page.total == 2
    assert len(page.items) == 1

    inserted = dao.bulk_upsert(
        [
            ("wf_c", {"workflow_id": "wf_c", "name": "C"}),
            ("wf_d", {"workflow_id": "wf_d", "name": "D"}),
        ]
    )
    assert inserted == 2
    assert len(dao.list_items()) == 4

    assert dao.delete("wf_d") is True
    assert dao.delete("wf_x") is False


def test_team_comment_notification_query() -> None:
    team_store = {}
    comment_store = {}
    notification_store = {}

    team_dao = InMemoryTeamDAO(team_store)
    comment_dao = InMemoryCommentDAO(comment_store)
    notification_dao = InMemoryNotificationDAO(notification_store)

    team_dao.upsert(
        "team_1",
        {
            "team_id": "team_1",
            "name": "T1",
            "members": {
                "alice": {"role": "admin"},
                "bob": {"role": "viewer"},
            },
        },
    )
    team_dao.upsert("team_2", {"team_id": "team_2", "name": "T2", "members": {"charlie": {"role": "viewer"}}})

    assert len(team_dao.list_items()) == 2
    assert len(team_dao.list_items(user_id="alice")) == 1

    comment_dao.upsert("c1", {"comment_id": "c1", "workflow_id": "wf_1", "content": "hello", "created_at": "2026-04-01T10:00:00+00:00"})
    comment_dao.upsert("c2", {"comment_id": "c2", "workflow_id": "wf_2", "content": "world", "created_at": "2026-04-01T11:00:00+00:00"})
    assert len(comment_dao.list_by_workflow("wf_1")) == 1

    notification_dao.upsert(
        "n1",
        {
            "notification_id": "n1",
            "workflow_id": "wf_1",
            "user_id": "alice",
            "read": False,
            "created_at": "2026-04-01T11:00:00+00:00",
        },
    )
    notification_dao.upsert(
        "n2",
        {
            "notification_id": "n2",
            "workflow_id": "wf_1",
            "user_id": "alice",
            "read": True,
            "created_at": "2026-04-01T12:00:00+00:00",
        },
    )
    assert len(notification_dao.list_by_user("wf_1", "alice", unread_only=False, limit=10)) == 2
    assert len(notification_dao.list_by_user("wf_1", "alice", unread_only=True, limit=10)) == 1
