"""智能工作流服务：编排定义、执行、模板与调度。"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Set
from urllib.parse import quote_plus
from uuid import uuid4

from .websocket_service import websocket_service
from .smart_workflow_dao import build_smart_workflow_daos
from .workflow_redis_cache import WorkflowRedisCacheManager
from .workflow_email_service import get_workflow_email_service
from ..config import settings
from ..workflow.engine import WorkflowEngine
from ..workflow.schema import WorkflowValidationError, get_workflow_schema
from ..workflow.templates import built_in_templates


class SmartWorkflowService:
    """智能工作流应用服务。"""

    _WORKFLOW_CACHE_TTL = 3600
    _PERMISSION_CACHE_TTL = 1800
    _CURSOR_CACHE_TTL = 300
    _ONLINE_USERS_CACHE_TTL = 120
    _SHARE_STATS_CACHE_TTL = 86400

    _ROLE_INHERITANCE: Dict[str, List[str]] = {
        "guest": [],
        "viewer": ["guest"],
        "commenter": ["viewer"],
        "editor": ["commenter"],
        "admin": ["editor"],
    }

    _ROLE_PERMISSIONS: Dict[str, Set[str]] = {
        "guest": {"view_workflow"},
        "viewer": {"view_workflow", "update_cursor"},
        "commenter": {"comment", "view_workflow", "update_cursor"},
        "editor": {
            "view_workflow",
            "update_cursor",
            "comment",
            "edit_workflow",
            "execute_workflow",
            "create_share_link",
            "export_data",
        },
        "admin": {
            "view_workflow",
            "update_cursor",
            "comment",
            "edit_workflow",
            "execute_workflow",
            "create_share_link",
            "export_data",
            "manage_share",
            "manage_team",
            "manage_collaborators",
            "delegate_permission",
            "resolve_conflict",
        },
    }

    _DEFAULT_NOTIFICATION_PREFS: Dict[str, Any] = {
        "in_app": True,
        "email": False,
        "email_address": "",
        "realtime": True,
        "mention_only": False,
        "muted_event_types": [],
    }

    def __init__(
        self,
        auto_start_scheduler: bool = True,
        cache_manager: Optional[WorkflowRedisCacheManager] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._engine = WorkflowEngine()
        self._cache = cache_manager or WorkflowRedisCacheManager.from_settings(settings)

        self._workflows: Dict[str, Dict[str, Any]] = {}
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._templates: Dict[str, Dict[str, Any]] = {
            item["template_id"]: item for item in built_in_templates()
        }
        self._schedules: Dict[str, Dict[str, Any]] = {}
        self._teams: Dict[str, Dict[str, Any]] = {}
        self._invitations: Dict[str, Dict[str, Any]] = {}
        self._delegations: Dict[str, Dict[str, Any]] = {}
        self._share_links: Dict[str, Dict[str, Any]] = {}
        self._comments: Dict[str, Dict[str, Any]] = {}
        self._notifications: Dict[str, Dict[str, Any]] = {}
        self._branches: Dict[str, Dict[str, Any]] = {}

        dao_bundle = build_smart_workflow_daos(
            backend=os.getenv("SMART_WORKFLOW_DAO_BACKEND", "auto"),
            workflows_store=self._workflows,
            teams_store=self._teams,
            comments_store=self._comments,
            notifications_store=self._notifications,
        )
        self._dao_backend = dao_bundle.backend
        self._workflow_dao = dao_bundle.workflow_dao
        self._team_dao = dao_bundle.team_dao
        self._comment_dao = dao_bundle.comment_dao
        self._notification_dao = dao_bundle.notification_dao
        self._dao_connection_manager = dao_bundle.connection_manager
        self._email_service = get_workflow_email_service()

        self._metrics: Dict[str, Any] = {
            "total_runs": 0,
            "success_runs": 0,
            "failed_runs": 0,
            "avg_duration_ms": 0.0,
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        }

        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._restore_from_persistent_storage()
        if auto_start_scheduler:
            self.start_scheduler()

    # -------- 生命周期 --------
    def start_scheduler(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="smart-workflow-scheduler",
                daemon=True,
            )
            self._scheduler_thread.start()

    def stop_scheduler(self) -> None:
        with self._lock:
            self._running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=2.0)

    # -------- 运行健康与元数据 --------
    def health_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            cache_metrics = self._cache.get_metrics()
            dao_health = (
                self._dao_connection_manager.health()
                if self._dao_connection_manager is not None
                else {"healthy": True, "pool_status": "memory", "dialect": "memory", "error": ""}
            )
            return {
                "status": "healthy",
                "module": "smart_workflow",
                "workflow_count": len(self._workflows),
                "template_count": len(self._templates),
                "run_count": len(self._runs),
                "schedule_count": len(self._schedules),
                "team_count": len(self._teams),
                "share_link_count": len(self._share_links),
                "scheduler_running": self._running,
                "cache": {
                    "healthy": bool(cache_metrics.get("healthy", False)),
                    "backend": cache_metrics.get("memory", {}).get("backend", "unknown"),
                    "hit_rate": cache_metrics.get("hit_rate", 0.0),
                },
                "dao": {
                    "backend": self._dao_backend,
                    "healthy": bool(dao_health.get("healthy", False)),
                    "pool_status": str(dao_health.get("pool_status", "")),
                    "dialect": str(dao_health.get("dialect", "")),
                },
                "email": {
                    "enabled": self._email_service.enabled,
                    "queue": self._email_service.queue_snapshot(),
                },
            }

    def get_schema(self) -> Dict[str, Any]:
        return get_workflow_schema()

    def list_node_types(self) -> Dict[str, Any]:
        return self._engine.list_node_types()

    # -------- 内部工具 --------
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _now_iso(self) -> str:
        return self._now().isoformat()

    def _new_collab_state(self) -> Dict[str, Any]:
        now = self._now_iso()
        return {
            "revision": 0,
            "operation_log": [],
            "operation_index": {},
            "conflicts": [],
            "cursors": {},
            "comments": [],
            "notifications": [],
            "notification_preferences": {},
            "team_ids": [],
            "share_link_ids": [],
            "param_revision": {},
            "contributor_stats": {},
            "locked_by": None,
            "locked_at": None,
            "branch_ids": [],
            "analytics": {
                "total_operations": 0,
                "total_conflicts": 0,
                "auto_resolved_conflicts": 0,
                "manual_resolved_conflicts": 0,
                "total_comments": 0,
                "total_mentions": 0,
                "share_views": 0,
                "share_downloads": 0,
            },
            "last_activity_at": now,
        }

    def _restore_from_persistent_storage(self) -> None:
        if self._dao_backend != "database":
            return
        try:
            workflows = self._workflow_dao.list_items()
            teams = self._team_dao.list_items()
            comments = self._comment_dao.paginate(offset=0, limit=5000).items
            notifications = self._notification_dao.paginate(offset=0, limit=5000).items
        except Exception:  # pylint: disable=broad-except
            return

        for item in workflows:
            workflow_id = str(item.get("workflow_id") or "")
            if workflow_id:
                self._workflows[workflow_id] = deepcopy(item)
        for item in teams:
            team_id = str(item.get("team_id") or "")
            if team_id:
                self._teams[team_id] = deepcopy(item)
        for item in comments:
            comment_id = str(item.get("comment_id") or "")
            workflow_id = str(item.get("workflow_id") or "")
            if not comment_id:
                continue
            self._comments[comment_id] = deepcopy(item)
            workflow = self._workflows.get(workflow_id)
            if workflow:
                workflow.setdefault("collab_state", {}).setdefault("comments", []).append(deepcopy(item))
        for item in notifications:
            notification_id = str(item.get("notification_id") or "")
            workflow_id = str(item.get("workflow_id") or "")
            if not notification_id:
                continue
            self._notifications[notification_id] = deepcopy(item)
            workflow = self._workflows.get(workflow_id)
            if workflow:
                workflow.setdefault("collab_state", {}).setdefault("notifications", []).append(deepcopy(item))

    def _persist_workflow_record(self, record: Mapping[str, Any]) -> None:
        workflow_id = str(record.get("workflow_id") or "")
        if not workflow_id:
            return
        try:
            self._workflow_dao.upsert(workflow_id, record)
        except Exception:  # pylint: disable=broad-except
            pass

    def _persist_team_record(self, record: Mapping[str, Any]) -> None:
        team_id = str(record.get("team_id") or "")
        if not team_id:
            return
        try:
            self._team_dao.upsert(team_id, record)
        except Exception:  # pylint: disable=broad-except
            pass

    def _persist_comment_record(self, record: Mapping[str, Any]) -> None:
        comment_id = str(record.get("comment_id") or "")
        if not comment_id:
            return
        self._comments[comment_id] = deepcopy(dict(record))
        try:
            self._comment_dao.upsert(comment_id, record)
        except Exception:  # pylint: disable=broad-except
            pass

    def _persist_notification_record(self, record: Mapping[str, Any]) -> None:
        notification_id = str(record.get("notification_id") or "")
        if not notification_id:
            return
        self._notifications[notification_id] = deepcopy(dict(record))
        try:
            self._notification_dao.upsert(notification_id, record)
        except Exception:  # pylint: disable=broad-except
            pass

    def _cache_key_workflow(self, workflow_id: str) -> str:
        return f"workflow:{workflow_id}"

    def _cache_key_permissions(self, user_id: str, workflow_id: str) -> str:
        return f"user_permissions:{user_id}:{workflow_id}"

    def _cache_key_cursor(self, workflow_id: str) -> str:
        return f"cursor:{workflow_id}"

    def _cache_key_online_users(self, workflow_id: str) -> str:
        return f"online_users:{workflow_id}"

    def _cache_key_share_stats(self, share_token: str) -> str:
        return f"share_stats:{share_token}"

    def _invalidate_workflow_related_cache(self, workflow_id: str) -> None:
        self._cache.invalidate_cascade(
            root_key=self._cache_key_workflow(workflow_id),
            related_patterns=[
                self._cache_key_permissions("*", workflow_id),
                self._cache_key_cursor(workflow_id),
                self._cache_key_online_users(workflow_id),
            ],
        )

    def _invalidate_permission_cache(self, workflow_id: str) -> None:
        if not workflow_id:
            return
        self._cache.delete_pattern(self._cache_key_permissions("*", workflow_id))

    def _invalidate_team_permission_cache(self, team_id: str) -> None:
        if not team_id:
            return
        for workflow_id, workflow in self._workflows.items():
            state = workflow.get("collab_state") or {}
            if team_id in {str(item) for item in state.get("team_ids") or []}:
                self._invalidate_permission_cache(workflow_id)

    def _refresh_online_users_cache(self, workflow_id: str, cursors: Mapping[str, Any]) -> None:
        now = self._now()
        online_users: List[Dict[str, Any]] = []
        for cursor in cursors.values():
            try:
                updated_at = datetime.fromisoformat(str(cursor.get("updated_at")))
            except Exception:  # pylint: disable=broad-except
                continue
            if (now - updated_at).total_seconds() <= self._ONLINE_USERS_CACHE_TTL:
                online_users.append(
                    {
                        "user_id": str(cursor.get("user_id") or ""),
                        "updated_at": str(cursor.get("updated_at") or ""),
                    }
                )
        self._cache.set(
            self._cache_key_online_users(workflow_id),
            {"workflow_id": workflow_id, "users": online_users, "count": len(online_users)},
            ttl=self._ONLINE_USERS_CACHE_TTL,
        )

    def _role_permissions(self, role: str) -> Set[str]:
        role_name = str(role or "guest").strip().lower()
        if role_name not in self._ROLE_PERMISSIONS:
            role_name = "guest"

        inherited = set(self._ROLE_PERMISSIONS.get(role_name, set()))
        for parent in self._ROLE_INHERITANCE.get(role_name, []):
            inherited.update(self._role_permissions(parent))
        return inherited

    def _workflow_or_error(self, workflow_id: str) -> Dict[str, Any]:
        workflow = self._workflows.get(workflow_id)
        if not workflow and self._dao_backend == "database":
            workflow = self._workflow_dao.get(workflow_id)
            if workflow:
                self._workflows[workflow_id] = deepcopy(workflow)
        if not workflow:
            raise KeyError(f"workflow '{workflow_id}' not found")
        return workflow

    def _find_node(self, definition: Dict[str, Any], node_id: str) -> Optional[Dict[str, Any]]:
        nodes = definition.get("nodes") or []
        return next((item for item in nodes if str(item.get("node_id")) == node_id), None)

    def _sanitize_share_link(self, link: Mapping[str, Any]) -> Dict[str, Any]:
        result = deepcopy(dict(link))
        result.pop("password", None)
        return result

    def _notify(
        self,
        workflow: Dict[str, Any],
        user_id: str,
        event_type: str,
        message: str,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        state = workflow["collab_state"]
        prefs = deepcopy(state["notification_preferences"].get(user_id) or self._DEFAULT_NOTIFICATION_PREFS)
        muted = {str(item) for item in prefs.get("muted_event_types") or []}
        if event_type in muted:
            return None
        if prefs.get("mention_only", False) and event_type != "mention":
            return None

        notification = {
            "notification_id": f"ntf_{uuid4().hex[:12]}",
            "workflow_id": str(workflow.get("workflow_id") or ""),
            "user_id": user_id,
            "event_type": event_type,
            "message": message,
            "payload": deepcopy(dict(payload or {})),
            "read": False,
            "created_at": self._now_iso(),
            "channels": {
                "in_app": bool(prefs.get("in_app", True)),
                "email": bool(prefs.get("email", False)),
                "realtime": bool(prefs.get("realtime", True)),
            },
        }
        state["notifications"].append(notification)
        if len(state["notifications"]) > 2000:
            state["notifications"] = state["notifications"][-2000:]
        self._dispatch_email_notification(workflow=workflow, notification=notification)
        self._persist_notification_record(notification)
        return notification

    def _resolve_user_email(
        self,
        workflow: Mapping[str, Any],
        user_id: str,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> str:
        uid = str(user_id or "").strip()
        data = dict(payload or {})
        for key in ("email", "to_email", "invitee_email", "recipient_email"):
            value = str(data.get(key) or "").strip().lower()
            if "@" in value:
                return value

        state = workflow.get("collab_state") or {}
        prefs = (state.get("notification_preferences") or {}).get(uid) or {}
        pref_email = str(prefs.get("email_address") or "").strip().lower()
        if "@" in pref_email:
            return pref_email

        for item in workflow.get("collaborators") or []:
            if str(item.get("user_id") or "") != uid:
                continue
            candidate = str(item.get("email") or "").strip().lower()
            if "@" in candidate:
                return candidate
        if "@" in uid:
            return uid.lower()
        return ""

    def _dispatch_email_notification(self, workflow: Mapping[str, Any], notification: Dict[str, Any]) -> None:
        channels = dict(notification.get("channels") or {})
        if not bool(channels.get("email", False)):
            return

        event_type = str(notification.get("event_type") or "")
        user_id = str(notification.get("user_id") or "")
        payload = dict(notification.get("payload") or {})
        recipient_email = self._resolve_user_email(workflow=workflow, user_id=user_id, payload=payload)
        if not recipient_email:
            notification.setdefault("channels", {})["email_error"] = "missing_recipient_email"
            return

        workflow_id = str(workflow.get("workflow_id") or payload.get("workflow_id") or "")
        run_id = str(payload.get("run_id") or "")
        context = {
            "message": str(notification.get("message") or ""),
            "inviter": str(payload.get("invited_by") or payload.get("actor") or "系统"),
            "team_name": str(payload.get("team_name") or "未命名团队"),
            "document_name": str(payload.get("document_name") or workflow.get("name") or workflow_id),
            "action_url": str(payload.get("action_url") or f"/#/workflows/{workflow_id}"),
            "actor": str(payload.get("actor") or payload.get("invited_by") or "系统"),
            "content": str(payload.get("content") or payload.get("content_snippet") or notification.get("message") or ""),
            "document_url": str(payload.get("document_url") or f"/#/workflows/{workflow_id}"),
            "comment_url": str(payload.get("comment_url") or f"/#/workflows/{workflow_id}"),
            "visitor": str(payload.get("visitor") or payload.get("viewer_user_id") or "匿名访问者"),
            "visited_at": str(payload.get("visited_at") or self._now_iso()),
            "result": str(payload.get("result") or payload.get("status") or "已完成"),
            "result_url": str(payload.get("result_url") or f"/#/workflows/{workflow_id}/runs/{run_id}"),
        }
        priority = "high" if event_type in {"invite_notification", "mention", "conflict_resolved"} else "normal"
        message_id = self._email_service.enqueue_mail(
            user_id=user_id or "unknown",
            to_email=recipient_email,
            event_type=event_type,
            context=context,
            priority=priority,
            delay_seconds=0,
        )
        notification.setdefault("channels", {})["email_message_id"] = message_id
        notification["channels"]["email_recipient"] = recipient_email
        status = self._email_service.get_status(message_id)
        if status:
            notification["channels"]["email_status"] = status.get("status")

    # -------- 工作流定义与版本 --------
    def validate_definition(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        normalized = self._engine.validate_definition(payload)
        return {
            "valid": True,
            "workflow": normalized,
            "dag_levels": normalized.get("dag_levels", []),
            "node_count": len(normalized.get("nodes", [])),
            "edge_count": len(normalized.get("edges", [])),
        }

    def create_workflow(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        normalized = self._engine.validate_definition(payload)
        workflow_id = normalized["workflow_id"]

        with self._lock:
            if workflow_id in self._workflows:
                raise ValueError(f"工作流已存在: {workflow_id}")

            now = datetime.now(timezone.utc).isoformat()
            record = {
                "workflow_id": workflow_id,
                "name": normalized["name"],
                "description": normalized.get("description", ""),
                "created_at": now,
                "updated_at": now,
                "current": normalized,
                "versions": [
                    {
                        "version": normalized["version"],
                        "created_at": now,
                        "note": "initial",
                        "definition": deepcopy(normalized),
                    }
                ],
                "collaborators": [],
                "collab_state": self._new_collab_state(),
            }
            self._workflows[workflow_id] = record
            self._persist_workflow_record(record)
            self._cache.set(self._cache_key_workflow(workflow_id), record, ttl=self._WORKFLOW_CACHE_TTL)
            return deepcopy(record)

    def list_workflows(self) -> List[Dict[str, Any]]:
        with self._lock:
            if not self._workflows and self._dao_backend == "database":
                for item in self._workflow_dao.list_items():
                    workflow_id = str(item.get("workflow_id") or "")
                    if workflow_id:
                        self._workflows[workflow_id] = deepcopy(item)
            return [
                {
                    "workflow_id": item["workflow_id"],
                    "name": item["name"],
                    "description": item["description"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                    "version": item["current"]["version"],
                    "collaborator_count": len(item.get("collaborators") or []),
                }
                for item in self._workflows.values()
            ]

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        cache_key = self._cache_key_workflow(workflow_id)
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict):
            return deepcopy(cached)
        with self._lock:
            item = self._workflows.get(workflow_id)
            if not item and self._dao_backend == "database":
                item = self._workflow_dao.get(workflow_id)
                if item:
                    self._workflows[workflow_id] = deepcopy(item)
            if not item:
                return None
            copied = deepcopy(item)
            self._cache.set(cache_key, copied, ttl=self._WORKFLOW_CACHE_TTL)
            return copied

    def update_workflow(self, workflow_id: str, updates: Mapping[str, Any], note: str = "update") -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            merged = deepcopy(current["current"])
            for key, value in updates.items():
                if key == "workflow_id":
                    continue
                merged[key] = deepcopy(value)

            merged["workflow_id"] = workflow_id
            merged["version"] = int(current["current"]["version"]) + 1
            normalized = self._engine.validate_definition(merged)

            now = datetime.now(timezone.utc).isoformat()
            current["name"] = normalized["name"]
            current["description"] = normalized.get("description", "")
            current["updated_at"] = now
            current["current"] = normalized
            current["versions"].append(
                {
                    "version": normalized["version"],
                    "created_at": now,
                    "note": note,
                    "definition": deepcopy(normalized),
                }
            )
            self._persist_workflow_record(current)
            self._invalidate_workflow_related_cache(workflow_id)
            self._cache.set(self._cache_key_workflow(workflow_id), current, ttl=self._WORKFLOW_CACHE_TTL)
            return deepcopy(current)

    def delete_workflow(self, workflow_id: str) -> None:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            collab_state = current.get("collab_state") or {}
            for link_id in list(collab_state.get("share_link_ids") or []):
                self._share_links.pop(str(link_id), None)

            stale_delegations = [
                delegation_id
                for delegation_id, item in self._delegations.items()
                if str(item.get("workflow_id")) == workflow_id
            ]
            for delegation_id in stale_delegations:
                del self._delegations[delegation_id]

            del self._workflows[workflow_id]
            self._workflow_dao.delete(workflow_id)
            stale_comment_ids = [cid for cid, item in self._comments.items() if str(item.get("workflow_id")) == workflow_id]
            for comment_id in stale_comment_ids:
                self._comments.pop(comment_id, None)
                self._comment_dao.delete(comment_id)
            stale_notification_ids = [
                nid for nid, item in self._notifications.items() if str(item.get("workflow_id")) == workflow_id
            ]
            for notification_id in stale_notification_ids:
                self._notifications.pop(notification_id, None)
                self._notification_dao.delete(notification_id)

            # 清理相关调度
            schedule_ids = [sid for sid, schedule in self._schedules.items() if schedule["workflow_id"] == workflow_id]
            for sid in schedule_ids:
                del self._schedules[sid]
            self._invalidate_workflow_related_cache(workflow_id)

    def list_versions(self, workflow_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            return [
                {
                    "version": item["version"],
                    "created_at": item["created_at"],
                    "note": item["note"],
                }
                for item in current["versions"]
            ]

    def rollback_workflow(self, workflow_id: str, target_version: int) -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")

            matched = next((item for item in current["versions"] if int(item["version"]) == int(target_version)), None)
            if not matched:
                raise KeyError(f"version '{target_version}' not found")

            restored = deepcopy(matched["definition"])
            restored["version"] = int(current["current"]["version"]) + 1
            restored = self._engine.validate_definition(restored)

            now = datetime.now(timezone.utc).isoformat()
            current["current"] = restored
            current["updated_at"] = now
            current["versions"].append(
                {
                    "version": restored["version"],
                    "created_at": now,
                    "note": f"rollback_to_{target_version}",
                    "definition": deepcopy(restored),
                }
            )
            self._persist_workflow_record(current)
            self._invalidate_workflow_related_cache(workflow_id)
            self._cache.set(self._cache_key_workflow(workflow_id), current, ttl=self._WORKFLOW_CACHE_TTL)
            return deepcopy(current)

    def export_workflow(self, workflow_id: str) -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            return deepcopy(current["current"])

    def import_workflow(self, definition: Mapping[str, Any], overwrite: bool = False) -> Dict[str, Any]:
        normalized = self._engine.validate_definition(definition)
        workflow_id = normalized["workflow_id"]

        with self._lock:
            if workflow_id in self._workflows:
                if not overwrite:
                    raise ValueError(f"workflow '{workflow_id}' 已存在，若要覆盖请设置 overwrite=true")
                # 走 update 流程，保留版本轨迹
                return self.update_workflow(workflow_id, normalized, note="import_overwrite")

        return self.create_workflow(normalized)

    def set_collaborators(self, workflow_id: str, collaborators: List[Dict[str, Any]]) -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            normalized: List[Dict[str, Any]] = []
            for item in collaborators:
                role = str(item.get("role") or "viewer").strip().lower()
                if role not in self._ROLE_PERMISSIONS:
                    role = "viewer"
                user_id = str(item.get("user_id") or "").strip()
                team_id = str(item.get("team_id") or "").strip()
                if not user_id and not team_id:
                    continue
                normalized_item = {
                    "role": role,
                    "display_name": str(item.get("display_name") or ""),
                }
                if user_id:
                    normalized_item["user_id"] = user_id
                    email = str(item.get("email") or "").strip().lower()
                    if email:
                        normalized_item["email"] = email
                if team_id:
                    normalized_item["team_id"] = team_id
                normalized.append(normalized_item)

            current["collaborators"] = normalized
            current["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._persist_workflow_record(current)
            self._invalidate_permission_cache(workflow_id)
            self._cache.set(self._cache_key_workflow(workflow_id), current, ttl=self._WORKFLOW_CACHE_TTL)
            return deepcopy(current)

    # -------- 团队、邀请、权限 --------
    def create_team(self, name: str, owner_user_id: str, description: str = "") -> Dict[str, Any]:
        team_name = str(name or "").strip()
        owner_id = str(owner_user_id or "").strip()
        if not team_name:
            raise ValueError("team name 不能为空")
        if not owner_id:
            raise ValueError("owner_user_id 不能为空")

        with self._lock:
            team_id = f"team_{uuid4().hex[:10]}"
            now = self._now_iso()
            team = {
                "team_id": team_id,
                "name": team_name,
                "description": str(description or ""),
                "owner_user_id": owner_id,
                "members": {
                    owner_id: {
                        "user_id": owner_id,
                        "role": "admin",
                        "display_name": "",
                        "joined_at": now,
                        "invited_via": "owner",
                    }
                },
                "created_at": now,
                "updated_at": now,
            }
            self._teams[team_id] = team
            self._persist_team_record(team)
            return deepcopy(team)

    def list_teams(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        uid = str(user_id or "").strip()
        with self._lock:
            if not self._teams and self._dao_backend == "database":
                for item in self._team_dao.list_items():
                    team_id = str(item.get("team_id") or "")
                    if team_id:
                        self._teams[team_id] = deepcopy(item)
            teams = list(self._teams.values())
        if uid:
            teams = [item for item in teams if uid in (item.get("members") or {})]
        return [
            {
                "team_id": item["team_id"],
                "name": item["name"],
                "description": item.get("description", ""),
                "owner_user_id": item.get("owner_user_id"),
                "member_count": len(item.get("members") or {}),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
            }
            for item in teams
        ]

    def add_team_member(
        self,
        team_id: str,
        user_id: str,
        role: str = "viewer",
        display_name: str = "",
        invited_via: str = "manual",
    ) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")
        role_name = str(role or "viewer").strip().lower()
        if role_name not in self._ROLE_PERMISSIONS:
            role_name = "viewer"

        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                raise KeyError(f"team '{team_id}' not found")
            team["members"][uid] = {
                "user_id": uid,
                "role": role_name,
                "display_name": str(display_name or ""),
                "joined_at": self._now_iso(),
                "invited_via": invited_via,
            }
            team["updated_at"] = self._now_iso()
            self._persist_team_record(team)
            self._invalidate_team_permission_cache(team_id)
            return deepcopy(team)

    def remove_team_member(self, team_id: str, user_id: str) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                raise KeyError(f"team '{team_id}' not found")
            if uid == team.get("owner_user_id"):
                raise ValueError("不能移除团队拥有者")
            team["members"].pop(uid, None)
            team["updated_at"] = self._now_iso()
            self._persist_team_record(team)
            self._invalidate_team_permission_cache(team_id)
            return deepcopy(team)

    def bind_team_to_workflow(self, workflow_id: str, team_id: str) -> Dict[str, Any]:
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            if team_id not in self._teams:
                raise KeyError(f"team '{team_id}' not found")

            state = workflow["collab_state"]
            existing = [str(item) for item in state.get("team_ids") or []]
            if team_id not in existing:
                existing.append(team_id)
            state["team_ids"] = existing
            workflow["updated_at"] = self._now_iso()
            state["last_activity_at"] = workflow["updated_at"]
            self._persist_workflow_record(workflow)
            self._invalidate_permission_cache(workflow_id)
            self._cache.set(self._cache_key_workflow(workflow_id), workflow, ttl=self._WORKFLOW_CACHE_TTL)
            return {"workflow_id": workflow_id, "team_ids": deepcopy(existing)}

    def create_invitation(
        self,
        team_id: str,
        email: str,
        role: str = "viewer",
        invited_by: str = "system",
        ttl_hours: int = 72,
    ) -> Dict[str, Any]:
        invite_email = str(email or "").strip().lower()
        if not invite_email or "@" not in invite_email:
            raise ValueError("email 格式不正确")
        role_name = str(role or "viewer").strip().lower()
        if role_name not in self._ROLE_PERMISSIONS:
            role_name = "viewer"
        ttl = max(1, min(int(ttl_hours), 24 * 30))

        with self._lock:
            team = self._teams.get(team_id)
            if not team:
                raise KeyError(f"team '{team_id}' not found")

            invite_id = f"inv_{uuid4().hex[:14]}"
            invitation = {
                "invite_id": invite_id,
                "team_id": team_id,
                "email": invite_email,
                "role": role_name,
                "invited_by": str(invited_by or "system"),
                "status": "pending",
                "created_at": self._now_iso(),
                "expires_at": (self._now() + timedelta(hours=ttl)).isoformat(),
                "accepted_by": None,
                "accepted_at": None,
            }
            invite_message_id = self._email_service.enqueue_mail(
                user_id=invite_email,
                to_email=invite_email,
                event_type="invite_notification",
                context={
                    "message": f"{invitation['invited_by']} 邀请您加入团队协作",
                    "inviter": invitation["invited_by"],
                    "team_name": str(team.get("name") or team_id),
                    "document_name": "",
                    "action_url": f"/#/teams/{team_id}/invitations/{invite_id}",
                },
                priority="high",
            )
            invitation["email_message_id"] = invite_message_id
            self._invitations[invite_id] = invitation
            return deepcopy(invitation)

    def list_invitations(self, team_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        desired_status = str(status or "").strip().lower()
        with self._lock:
            items = list(self._invitations.values())
        if team_id:
            items = [item for item in items if item.get("team_id") == team_id]
        if desired_status:
            items = [item for item in items if str(item.get("status", "")).lower() == desired_status]
        items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return [deepcopy(item) for item in items]

    def accept_invitation(self, invite_id: str, user_id: str, display_name: str = "") -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")

        with self._lock:
            invitation = self._invitations.get(invite_id)
            if not invitation:
                raise KeyError(f"invitation '{invite_id}' not found")
            if invitation.get("status") != "pending":
                raise ValueError("邀请已失效或已处理")
            expires_at = datetime.fromisoformat(str(invitation["expires_at"]))
            if expires_at < self._now():
                invitation["status"] = "expired"
                raise ValueError("邀请已过期")

            team_id = str(invitation["team_id"])
            team = self._teams.get(team_id)
            if not team:
                raise KeyError(f"team '{team_id}' not found")

            team["members"][uid] = {
                "user_id": uid,
                "role": invitation["role"],
                "display_name": str(display_name or ""),
                "joined_at": self._now_iso(),
                "invited_via": invite_id,
            }
            team["updated_at"] = self._now_iso()
            invitation["status"] = "accepted"
            invitation["accepted_by"] = uid
            invitation["accepted_at"] = self._now_iso()
            self._persist_team_record(team)
            self._invalidate_team_permission_cache(team_id)

            return {
                "invitation": deepcopy(invitation),
                "team": {
                    "team_id": team["team_id"],
                    "name": team["name"],
                    "member_count": len(team["members"]),
                },
            }

    def create_permission_delegation(
        self,
        workflow_id: str,
        from_user_id: str,
        to_user_id: str,
        permission: str,
        ttl_hours: int = 24,
    ) -> Dict[str, Any]:
        perm = str(permission or "").strip()
        if not perm:
            raise ValueError("permission 不能为空")
        from_uid = str(from_user_id or "").strip()
        to_uid = str(to_user_id or "").strip()
        if not from_uid or not to_uid:
            raise ValueError("from_user_id/to_user_id 不能为空")

        with self._lock:
            if not self.has_permission(workflow_id, from_uid, "delegate_permission"):
                raise PermissionError("无权限委托")
            delegation_id = f"dlg_{uuid4().hex[:12]}"
            delegation = {
                "delegation_id": delegation_id,
                "workflow_id": workflow_id,
                "from_user_id": from_uid,
                "to_user_id": to_uid,
                "permission": perm,
                "status": "active",
                "created_at": self._now_iso(),
                "expires_at": (self._now() + timedelta(hours=max(1, int(ttl_hours)))).isoformat(),
            }
            self._delegations[delegation_id] = delegation
            self._invalidate_permission_cache(workflow_id)
            return deepcopy(delegation)

    def revoke_permission_delegation(self, delegation_id: str) -> Dict[str, Any]:
        with self._lock:
            delegation = self._delegations.get(delegation_id)
            if not delegation:
                raise KeyError(f"delegation '{delegation_id}' not found")
            delegation["status"] = "revoked"
            delegation["revoked_at"] = self._now_iso()
            self._invalidate_permission_cache(str(delegation.get("workflow_id") or ""))
            return deepcopy(delegation)

    def list_permission_delegations(
        self,
        workflow_id: str,
        user_id: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        uid = str(user_id or "").strip()
        now = self._now()
        with self._lock:
            items = [item for item in self._delegations.values() if item.get("workflow_id") == workflow_id]

        filtered: List[Dict[str, Any]] = []
        for item in items:
            expired = datetime.fromisoformat(str(item["expires_at"])) < now
            status = str(item.get("status", "active"))
            if active_only and (status != "active" or expired):
                continue
            if uid and uid not in {str(item.get("from_user_id")), str(item.get("to_user_id"))}:
                continue
            filtered.append(deepcopy(item))

        filtered.sort(key=lambda it: str(it.get("created_at", "")), reverse=True)
        return filtered

    def get_effective_permissions(self, workflow_id: str, user_id: str) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        cache_key = self._cache_key_permissions(uid, workflow_id)
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict):
            return deepcopy(cached)

        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            role_names: Set[str] = set()

            for item in workflow.get("collaborators") or []:
                if str(item.get("user_id") or "") == uid:
                    role_names.add(str(item.get("role") or "viewer"))

            state = workflow.get("collab_state") or {}
            team_ids = [str(item) for item in state.get("team_ids") or []]
            for team_id in team_ids:
                team = self._teams.get(team_id)
                if not team:
                    continue
                member = (team.get("members") or {}).get(uid)
                if member:
                    role_names.add(str(member.get("role") or "viewer"))

            if not role_names:
                role_names.add("guest")

            permissions: Set[str] = set()
            for role_name in role_names:
                permissions.update(self._role_permissions(role_name))

            now = self._now()
            delegated_permissions: List[str] = []
            for item in self._delegations.values():
                if item.get("workflow_id") != workflow_id:
                    continue
                if item.get("to_user_id") != uid:
                    continue
                if item.get("status") != "active":
                    continue
                if datetime.fromisoformat(str(item["expires_at"])) < now:
                    continue
                delegated_permissions.append(str(item.get("permission")))
                permissions.add(str(item.get("permission")))

            result = {
                "workflow_id": workflow_id,
                "user_id": uid,
                "roles": sorted(role_names),
                "permissions": sorted(permissions),
                "delegated_permissions": sorted(set(delegated_permissions)),
            }
            self._cache.set(cache_key, result, ttl=self._PERMISSION_CACHE_TTL)
            return result

    def has_permission(self, workflow_id: str, user_id: str, permission: str) -> bool:
        perms = self.get_effective_permissions(workflow_id, user_id)
        return str(permission) in set(perms.get("permissions") or [])

    def get_cache_metrics(self) -> Dict[str, Any]:
        return self._cache.get_metrics()

    def get_smtp_configuration(self) -> Dict[str, Any]:
        return self._email_service.get_smtp_config(masked=True)

    def save_smtp_configuration(
        self,
        *,
        host: str,
        port: int,
        encryption: str,
        username: str,
        password: str,
    ) -> Dict[str, Any]:
        current = self._email_service.smtp_settings
        password_clean = str(password or "").strip()
        if password_clean and set(password_clean) == {"*"}:
            password_clean = current.password
        if not password_clean:
            password_clean = current.password

        next_settings = self._email_service.normalize_smtp_settings(
            host=host,
            port=port,
            username=username,
            password=password_clean,
            encryption=encryption,
            timeout_seconds=current.timeout_seconds,
            pool_size=current.pool_size,
        )
        self._email_service.update_smtp_settings(next_settings)

        # 同步更新工单邮件服务，确保审批通知邮件能使用已配置的SMTP发送
        try:
            from ..utils.email_service import ticket_email_service
            ticket_email_service.update_settings(
                host=next_settings.host,
                port=next_settings.port,
                username=next_settings.user,
                password=next_settings.password,
                use_tls=next_settings.use_tls,
                use_ssl=next_settings.use_ssl,
                email_from=next_settings.user,
            )
        except Exception:
            logger.exception("同步工单邮件服务SMTP配置失败")

        return self._email_service.get_smtp_config(masked=True)

    def validate_smtp_configuration(
        self,
        test_recipient: str = "",
        smtp_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        recipient = str(test_recipient or "").strip()
        normalized = None
        if smtp_payload:
            normalized = self._email_service.normalize_smtp_settings(
                host=str(smtp_payload.get("host") or ""),
                port=int(smtp_payload.get("port") or 0),
                username=str(smtp_payload.get("username") or ""),
                password=str(smtp_payload.get("password") or ""),
                encryption=str(smtp_payload.get("encryption") or "TLS"),
                timeout_seconds=self._email_service.smtp_settings.timeout_seconds,
                pool_size=self._email_service.smtp_settings.pool_size,
            )
        return self._email_service.validate_configuration(
            test_recipient=recipient or None,
            smtp_settings=normalized,
        )

    def list_email_delivery_logs(self, limit: int = 200) -> Dict[str, Any]:
        rows = self._email_service.get_delivery_logs(limit=limit)
        return {"logs": rows, "count": len(rows)}

    def invalidate_cache(
        self,
        *,
        key: Optional[str] = None,
        pattern: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        deleted = 0
        if key:
            deleted += 1 if self._cache.delete(str(key)) else 0
        if pattern:
            deleted += self._cache.delete_pattern(str(pattern))
        if workflow_id:
            self._invalidate_workflow_related_cache(str(workflow_id))
        return {"deleted": deleted, "key": key, "pattern": pattern, "workflow_id": workflow_id}

    # -------- 协作编辑（OT + 冲突）--------
    def apply_collaboration_operation(self, workflow_id: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        actor_id = str(payload.get("actor_id") or "").strip()
        if not actor_id:
            raise ValueError("actor_id 不能为空")
        if not self.has_permission(workflow_id, actor_id, "edit_workflow"):
            raise PermissionError("无权限编辑工作流")

        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]
            operation_id = str(payload.get("operation_id") or f"op_{uuid4().hex[:12]}")
            current_revision = int(state.get("revision") or 0)
            base_revision = int(payload.get("base_revision", current_revision))
            operation_type = str(payload.get("operation_type") or "").strip()
            if not operation_type:
                raise ValueError("operation_type 不能为空")

            operation_index = state.get("operation_index") or {}
            if operation_id in operation_index:
                return {
                    "workflow_id": workflow_id,
                    "operation_id": operation_id,
                    "revision": int(operation_index[operation_id]),
                    "deduplicated": True,
                }

            conflict_strategy = str(payload.get("conflict_strategy") or "last_write_wins").strip().lower()
            working = deepcopy(workflow["current"])
            now = self._now_iso()
            conflict_item: Optional[Dict[str, Any]] = None
            applied = False
            op_data = deepcopy(dict(payload.get("data") or {}))

            if operation_type == "set_node_param":
                node_id = str(op_data.get("node_id") or "").strip()
                param_key = str(op_data.get("param_key") or "").strip()
                param_value = deepcopy(op_data.get("param_value"))
                if not node_id or not param_key:
                    raise ValueError("set_node_param 需要 node_id 与 param_key")

                node = self._find_node(working, node_id)
                if not node:
                    raise KeyError(f"node '{node_id}' not found")
                node.setdefault("params", {})

                touch_key = f"{node_id}.{param_key}"
                last_touch_revision = int((state.get("param_revision") or {}).get(touch_key, 0))
                existing_value = deepcopy(node["params"].get(param_key))
                has_conflict = base_revision < last_touch_revision and existing_value != param_value
                if has_conflict:
                    conflict_item = {
                        "conflict_id": f"wf_conflict_{uuid4().hex[:12]}",
                        "workflow_id": workflow_id,
                        "operation_id": operation_id,
                        "operation_type": operation_type,
                        "actor_id": actor_id,
                        "base_revision": base_revision,
                        "current_revision": current_revision,
                        "status": "open",
                        "strategy": conflict_strategy,
                        "target": {"node_id": node_id, "param_key": param_key},
                        "server_value": existing_value,
                        "incoming_value": param_value,
                        "created_at": now,
                        "resolved_at": None,
                        "resolved_by": None,
                    }
                    state["conflicts"].append(conflict_item)
                    state["analytics"]["total_conflicts"] += 1
                    if conflict_strategy != "manual":
                        node["params"][param_key] = deepcopy(param_value)
                        conflict_item["status"] = "resolved"
                        conflict_item["resolved_at"] = now
                        conflict_item["resolved_by"] = "auto"
                        state["analytics"]["auto_resolved_conflicts"] += 1
                        applied = True
                else:
                    node["params"][param_key] = deepcopy(param_value)
                    applied = True

                if applied:
                    state.setdefault("param_revision", {})[touch_key] = current_revision + 1

            elif operation_type == "set_metadata":
                metadata_key = str(op_data.get("key") or "").strip()
                if not metadata_key:
                    raise ValueError("set_metadata 需要 key")
                working.setdefault("metadata", {})
                working["metadata"][metadata_key] = deepcopy(op_data.get("value"))
                applied = True

            elif operation_type == "add_node":
                node = deepcopy(op_data.get("node"))
                if not isinstance(node, Mapping):
                    raise ValueError("add_node 需要 node 对象")
                node_id = str(node.get("node_id") or "").strip()
                if not node_id:
                    raise ValueError("node.node_id 不能为空")
                if self._find_node(working, node_id):
                    raise ValueError(f"node '{node_id}' 已存在")
                working.setdefault("nodes", []).append(dict(node))
                applied = True

            elif operation_type == "remove_node":
                node_id = str(op_data.get("node_id") or "").strip()
                if not node_id:
                    raise ValueError("remove_node 需要 node_id")
                nodes = [item for item in working.get("nodes") or [] if str(item.get("node_id")) != node_id]
                if len(nodes) == len(working.get("nodes") or []):
                    raise KeyError(f"node '{node_id}' not found")
                working["nodes"] = nodes
                working["edges"] = [
                    item
                    for item in working.get("edges") or []
                    if str(item.get("source")) != node_id and str(item.get("target")) != node_id
                ]
                applied = True

            elif operation_type == "add_edge":
                edge = deepcopy(op_data.get("edge"))
                if not isinstance(edge, Mapping):
                    raise ValueError("add_edge 需要 edge 对象")
                source = str(edge.get("source") or "").strip()
                target = str(edge.get("target") or "").strip()
                if not source or not target:
                    raise ValueError("edge.source 与 edge.target 不能为空")
                if not self._find_node(working, source) or not self._find_node(working, target):
                    raise KeyError("add_edge 的 source/target 节点不存在")
                exists = any(
                    str(item.get("source")) == source and str(item.get("target")) == target
                    for item in working.get("edges") or []
                )
                if not exists:
                    working.setdefault("edges", []).append(dict(edge))
                applied = True

            elif operation_type == "remove_edge":
                source = str(op_data.get("source") or "").strip()
                target = str(op_data.get("target") or "").strip()
                if not source or not target:
                    raise ValueError("remove_edge 需要 source 与 target")
                before_count = len(working.get("edges") or [])
                working["edges"] = [
                    item
                    for item in working.get("edges") or []
                    if not (str(item.get("source")) == source and str(item.get("target")) == target)
                ]
                applied = before_count != len(working.get("edges") or [])

            else:
                raise ValueError(f"不支持的 operation_type: {operation_type}")

            if applied:
                normalized = self._engine.validate_definition(working)
                normalized["version"] = int(workflow["current"]["version"])
                workflow["current"] = normalized
                workflow["name"] = normalized["name"]
                workflow["description"] = normalized.get("description", "")

            new_revision = current_revision + 1
            state["revision"] = new_revision
            state["analytics"]["total_operations"] += 1
            state["last_activity_at"] = now
            operation_entry = {
                "operation_id": operation_id,
                "actor_id": actor_id,
                "base_revision": base_revision,
                "revision": new_revision,
                "operation_type": operation_type,
                "data": op_data,
                "applied": applied,
                "conflict_id": conflict_item.get("conflict_id") if conflict_item else None,
                "created_at": now,
            }
            state["operation_log"].append(operation_entry)
            if len(state["operation_log"]) > 5000:
                state["operation_log"] = state["operation_log"][-5000:]
            state.setdefault("operation_index", {})[operation_id] = new_revision
            state.setdefault("contributor_stats", {}).setdefault(actor_id, {"operations": 0, "comments": 0})
            state["contributor_stats"][actor_id]["operations"] += 1
            workflow["updated_at"] = now
            self._persist_workflow_record(workflow)
            self._cache.set(self._cache_key_workflow(workflow_id), workflow, ttl=self._WORKFLOW_CACHE_TTL)

            return {
                "workflow_id": workflow_id,
                "operation_id": operation_id,
                "revision": new_revision,
                "applied": applied,
                "conflict": deepcopy(conflict_item) if conflict_item else None,
            }

    def list_collaboration_conflicts(self, workflow_id: str, unresolved_only: bool = False) -> Dict[str, Any]:
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            conflicts = deepcopy(workflow["collab_state"].get("conflicts") or [])
        if unresolved_only:
            conflicts = [item for item in conflicts if item.get("status") != "resolved"]
        conflicts.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return {"workflow_id": workflow_id, "conflicts": conflicts, "count": len(conflicts)}

    def resolve_collaboration_conflict(
        self,
        workflow_id: str,
        conflict_id: str,
        resolver_user_id: str,
        strategy: str = "server_wins",
        override_value: Any = None,
    ) -> Dict[str, Any]:
        resolver = str(resolver_user_id or "").strip()
        if not resolver:
            raise ValueError("resolver_user_id 不能为空")
        if not self.has_permission(workflow_id, resolver, "resolve_conflict"):
            raise PermissionError("无权限处理冲突")

        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]
            conflicts = state.get("conflicts") or []
            conflict = next((item for item in conflicts if str(item.get("conflict_id")) == conflict_id), None)
            if not conflict:
                raise KeyError(f"conflict '{conflict_id}' not found")
            if conflict.get("status") == "resolved":
                return deepcopy(conflict)

            if str(conflict.get("operation_type")) != "set_node_param":
                conflict["status"] = "resolved"
                conflict["resolved_by"] = resolver
                conflict["resolved_at"] = self._now_iso()
                state["analytics"]["manual_resolved_conflicts"] += 1
                return deepcopy(conflict)

            target = conflict.get("target") or {}
            node_id = str(target.get("node_id") or "")
            param_key = str(target.get("param_key") or "")
            working = deepcopy(workflow["current"])
            node = self._find_node(working, node_id)
            if not node:
                raise KeyError(f"node '{node_id}' not found")
            node.setdefault("params", {})

            strategy_name = str(strategy or "server_wins").strip().lower()
            if strategy_name == "server_wins":
                final_value = deepcopy(conflict.get("server_value"))
            elif strategy_name == "incoming_wins":
                final_value = deepcopy(conflict.get("incoming_value"))
            elif strategy_name == "custom":
                final_value = deepcopy(override_value)
            else:
                raise ValueError("strategy 仅支持 server_wins / incoming_wins / custom")

            node["params"][param_key] = final_value
            normalized = self._engine.validate_definition(working)
            normalized["version"] = int(workflow["current"]["version"])
            workflow["current"] = normalized

            state["revision"] = int(state.get("revision") or 0) + 1
            state.setdefault("param_revision", {})[f"{node_id}.{param_key}"] = int(state["revision"])
            conflict["status"] = "resolved"
            conflict["resolved_by"] = resolver
            conflict["resolved_at"] = self._now_iso()
            conflict["resolution_strategy"] = strategy_name
            conflict["resolved_value"] = final_value
            state["analytics"]["manual_resolved_conflicts"] += 1
            target_user_id = str(conflict.get("actor_id") or "").strip()
            if target_user_id and target_user_id != resolver:
                self._notify(
                    workflow=workflow,
                    user_id=target_user_id,
                    event_type="conflict_resolved",
                    message=f"工作流冲突已由 {resolver} 解决",
                    payload={
                        "workflow_id": workflow_id,
                        "conflict_id": conflict_id,
                        "result": f"策略 {strategy_name}，结果值 {final_value}",
                        "document_url": f"/#/workflows/{workflow_id}",
                    },
                )
            workflow["updated_at"] = self._now_iso()
            self._persist_workflow_record(workflow)
            self._cache.set(self._cache_key_workflow(workflow_id), workflow, ttl=self._WORKFLOW_CACHE_TTL)
            return deepcopy(conflict)

    def update_collaboration_cursor(
        self,
        workflow_id: str,
        user_id: str,
        position: Mapping[str, Any],
    ) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")
        if not self.has_permission(workflow_id, uid, "update_cursor"):
            raise PermissionError("无权限更新协作光标")

        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]
            cursor_payload = {
                "user_id": uid,
                "node_id": str(position.get("node_id") or ""),
                "x": float(position.get("x", 0.0)),
                "y": float(position.get("y", 0.0)),
                "selection": list(position.get("selection") or []),
                "updated_at": self._now_iso(),
            }
            state.setdefault("cursors", {})[uid] = cursor_payload
            state["last_activity_at"] = cursor_payload["updated_at"]
            self._cache.set(self._cache_key_cursor(workflow_id), state.get("cursors") or {}, ttl=self._CURSOR_CACHE_TTL)
            self._refresh_online_users_cache(workflow_id, state.get("cursors") or {})
            return {"workflow_id": workflow_id, "cursor": deepcopy(cursor_payload)}

    def list_collaboration_cursors(self, workflow_id: str, active_seconds: int = 30) -> Dict[str, Any]:
        ttl = max(1, min(int(active_seconds), 3600))
        cached = self._cache.get(self._cache_key_cursor(workflow_id))
        if isinstance(cached, dict):
            cursors = deepcopy(cached)
        else:
            with self._lock:
                workflow = self._workflow_or_error(workflow_id)
                cursors = deepcopy(workflow["collab_state"].get("cursors") or {})
            self._cache.set(self._cache_key_cursor(workflow_id), cursors, ttl=self._CURSOR_CACHE_TTL)

        now = self._now()
        active: List[Dict[str, Any]] = []
        for item in cursors.values():
            updated_at = datetime.fromisoformat(str(item.get("updated_at")))
            if (now - updated_at).total_seconds() <= ttl:
                active.append(item)
        self._refresh_online_users_cache(workflow_id, cursors)
        return {"workflow_id": workflow_id, "cursors": active, "count": len(active)}

    def list_online_users(self, workflow_id: str) -> Dict[str, Any]:
        cached = self._cache.get(self._cache_key_online_users(workflow_id))
        if isinstance(cached, dict):
            return deepcopy(cached)
        cursors = self.list_collaboration_cursors(workflow_id, active_seconds=self._ONLINE_USERS_CACHE_TTL)
        users = [
            {"user_id": str(item.get("user_id") or ""), "updated_at": str(item.get("updated_at") or "")}
            for item in cursors.get("cursors") or []
        ]
        payload = {"workflow_id": workflow_id, "users": users, "count": len(users)}
        self._cache.set(self._cache_key_online_users(workflow_id), payload, ttl=self._ONLINE_USERS_CACHE_TTL)
        return payload

    # -------- 评论、提及、通知偏好 --------
    def add_comment(
        self,
        workflow_id: str,
        user_id: str,
        content: str,
        parent_comment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        text = str(content or "").strip()
        if not uid or not text:
            raise ValueError("user_id 与 content 不能为空")
        if not self.has_permission(workflow_id, uid, "comment"):
            raise PermissionError("无权限评论")

        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]
            comment = {
                "comment_id": f"cmt_{uuid4().hex[:12]}",
                "workflow_id": workflow_id,
                "user_id": uid,
                "content": text,
                "parent_comment_id": str(parent_comment_id or ""),
                "mentions": [],
                "created_at": self._now_iso(),
            }
            mentions = sorted(set(re.findall(r"@([A-Za-z0-9_.-]+)", text)))
            comment["mentions"] = mentions
            parent_comment = None
            if parent_comment_id:
                parent_comment = next(
                    (
                        item
                        for item in state.get("comments") or []
                        if str(item.get("comment_id") or "") == str(parent_comment_id)
                    ),
                    None,
                )
            state.setdefault("comments", []).append(comment)
            state["analytics"]["total_comments"] += 1
            state["analytics"]["total_mentions"] += len(mentions)
            state.setdefault("contributor_stats", {}).setdefault(uid, {"operations": 0, "comments": 0})
            state["contributor_stats"][uid]["comments"] += 1
            state["last_activity_at"] = comment["created_at"]

            if parent_comment:
                parent_user_id = str(parent_comment.get("user_id") or "").strip()
                if parent_user_id and parent_user_id != uid:
                    self._notify(
                        workflow=workflow,
                        user_id=parent_user_id,
                        event_type="comment_reply",
                        message=f"{uid} 回复了你的评论",
                        payload={
                            "workflow_id": workflow_id,
                            "comment_id": comment["comment_id"],
                            "comment_url": f"/#/workflows/{workflow_id}/comments/{comment['comment_id']}",
                            "actor": uid,
                            "content": text[:120],
                        },
                    )

            for mentioned_user in mentions:
                self._notify(
                    workflow=workflow,
                    user_id=mentioned_user,
                    event_type="mention",
                    message=f"{uid} 在评论中提及了你",
                    payload={
                        "workflow_id": workflow_id,
                        "comment_id": comment["comment_id"],
                        "comment_url": f"/#/workflows/{workflow_id}/comments/{comment['comment_id']}",
                        "actor": uid,
                        "content": text[:120],
                    },
                )
            self._persist_comment_record(comment)
            self._persist_workflow_record(workflow)
            return deepcopy(comment)

    def list_comments(self, workflow_id: str, limit: int = 200) -> Dict[str, Any]:
        max_items = max(1, min(int(limit), 1000))
        persisted_comments = self._comment_dao.list_by_workflow(workflow_id=workflow_id, limit=max_items)
        if persisted_comments:
            return {"workflow_id": workflow_id, "comments": persisted_comments, "count": len(persisted_comments)}
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            comments = deepcopy(workflow["collab_state"].get("comments") or [])
        comments.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        trimmed = comments[:max_items]
        return {"workflow_id": workflow_id, "comments": trimmed, "count": len(trimmed)}

    def set_notification_preferences(
        self,
        workflow_id: str,
        user_id: str,
        preferences: Mapping[str, Any],
    ) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]
            prefs = deepcopy(self._DEFAULT_NOTIFICATION_PREFS)
            prefs.update(deepcopy(dict(preferences or {})))
            muted = prefs.get("muted_event_types") or []
            prefs["muted_event_types"] = sorted({str(item) for item in muted if str(item).strip()})
            email_address = str(prefs.get("email_address") or "").strip().lower()
            prefs["email_address"] = email_address
            state.setdefault("notification_preferences", {})[uid] = prefs
            self._persist_workflow_record(workflow)
            return {"workflow_id": workflow_id, "user_id": uid, "preferences": deepcopy(prefs)}

    def get_notification_preferences(self, workflow_id: str, user_id: str) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        if not uid:
            raise ValueError("user_id 不能为空")
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            prefs = deepcopy(
                workflow["collab_state"].get("notification_preferences", {}).get(uid) or self._DEFAULT_NOTIFICATION_PREFS
            )
        return {"workflow_id": workflow_id, "user_id": uid, "preferences": prefs}

    def list_notifications(self, workflow_id: str, user_id: str, unread_only: bool = False, limit: int = 100) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        max_items = max(1, min(int(limit), 500))
        persisted_notifications = self._notification_dao.list_by_user(
            workflow_id=workflow_id,
            user_id=uid,
            unread_only=unread_only,
            limit=max_items,
        )
        if persisted_notifications:
            return {
                "workflow_id": workflow_id,
                "user_id": uid,
                "notifications": persisted_notifications,
                "count": len(persisted_notifications),
            }
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            notifications = [
                deepcopy(item)
                for item in workflow["collab_state"].get("notifications") or []
                if str(item.get("user_id")) == uid
            ]
        if unread_only:
            notifications = [item for item in notifications if not bool(item.get("read", False))]
        notifications.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        trimmed = notifications[:max_items]
        return {"workflow_id": workflow_id, "user_id": uid, "notifications": trimmed, "count": len(trimmed)}

    def mark_notification_read(self, workflow_id: str, user_id: str, notification_id: str) -> Dict[str, Any]:
        uid = str(user_id or "").strip()
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]
            matched = next(
                (
                    item
                    for item in state.get("notifications") or []
                    if str(item.get("notification_id")) == notification_id and str(item.get("user_id")) == uid
                ),
                None,
            )
            if not matched:
                raise KeyError(f"notification '{notification_id}' not found")
            matched["read"] = True
            matched["read_at"] = self._now_iso()
            self._persist_notification_record(matched)
            self._persist_workflow_record(workflow)
            return deepcopy(matched)

    # -------- 分享、导出、社交 --------
    def create_share_link(
        self,
        workflow_id: str,
        creator_user_id: str,
        access_mode: str = "public",
        password: str = "",
        expires_in_hours: int = 24 * 7,
    ) -> Dict[str, Any]:
        creator = str(creator_user_id or "").strip()
        if not creator:
            raise ValueError("creator_user_id 不能为空")
        if not self.has_permission(workflow_id, creator, "create_share_link"):
            raise PermissionError("无权限创建分享链接")

        mode = str(access_mode or "public").strip().lower()
        if mode not in {"public", "private", "password"}:
            raise ValueError("access_mode 仅支持 public/private/password")
        if mode == "password" and not str(password or "").strip():
            raise ValueError("password 访问模式需要密码")
        ttl = max(1, min(int(expires_in_hours), 24 * 90))

        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            link_id = f"shr_{uuid4().hex[:14]}"
            record = {
                "share_link_id": link_id,
                "workflow_id": workflow_id,
                "created_by": creator,
                "access_mode": mode,
                "password": str(password or ""),
                "created_at": self._now_iso(),
                "expires_at": (self._now() + timedelta(hours=ttl)).isoformat(),
                "revoked": False,
                "stats": {"views": 0, "downloads": 0},
                "share_url": f"/api/workflow/share/{link_id}",
            }
            self._share_links[link_id] = record
            self._cache.set(
                self._cache_key_share_stats(link_id),
                {"views": 0, "downloads": 0, "last_aggregated_at": self._now_iso()},
                ttl=self._SHARE_STATS_CACHE_TTL,
            )
            state = workflow["collab_state"]
            share_ids = [str(item) for item in state.get("share_link_ids") or []]
            if link_id not in share_ids:
                share_ids.append(link_id)
            state["share_link_ids"] = share_ids
            workflow["updated_at"] = self._now_iso()
            self._persist_workflow_record(workflow)
            self._cache.set(self._cache_key_workflow(workflow_id), workflow, ttl=self._WORKFLOW_CACHE_TTL)
            return self._sanitize_share_link(record)

    def list_share_links(self, workflow_id: str) -> Dict[str, Any]:
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            share_ids = [str(item) for item in workflow["collab_state"].get("share_link_ids") or []]
            links = [
                self._sanitize_share_link(self._share_links[item])
                for item in share_ids
                if item in self._share_links
            ]
        links.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return {"workflow_id": workflow_id, "links": links, "count": len(links)}

    def access_share_link(self, share_link_id: str, password: str = "", viewer_user_id: str = "") -> Dict[str, Any]:
        with self._lock:
            link = self._share_links.get(share_link_id)
            if not link:
                raise KeyError(f"share link '{share_link_id}' not found")
            if bool(link.get("revoked")):
                raise PermissionError("分享链接已撤销")
            if datetime.fromisoformat(str(link["expires_at"])) < self._now():
                raise PermissionError("分享链接已过期")

            mode = str(link.get("access_mode", "public"))
            workflow_id = str(link["workflow_id"])
            if mode == "password" and str(link.get("password")) != str(password):
                raise PermissionError("分享密码错误")
            if mode == "private":
                uid = str(viewer_user_id or "").strip()
                if not uid or not self.has_permission(workflow_id, uid, "view_workflow"):
                    raise PermissionError("该链接为私有分享，无访问权限")

            workflow = self._workflow_or_error(workflow_id)
            link["stats"]["views"] = int(link.get("stats", {}).get("views", 0)) + 1
            workflow["collab_state"]["analytics"]["share_views"] += 1
            cache_stats_key = self._cache_key_share_stats(share_link_id)
            stats_payload = self._cache.get(cache_stats_key) or {"views": 0, "downloads": 0}
            stats_payload["views"] = int(stats_payload.get("views", 0)) + 1
            stats_payload["last_view_at"] = self._now_iso()
            self._cache.set(cache_stats_key, stats_payload, ttl=self._SHARE_STATS_CACHE_TTL)
            self._notify(
                workflow=workflow,
                user_id=str(link.get("created_by") or ""),
                event_type="share_link_access",
                message="您的分享链接被访问",
                payload={
                    "workflow_id": workflow_id,
                    "share_link_id": share_link_id,
                    "viewer_user_id": str(viewer_user_id or "anonymous"),
                    "visitor": str(viewer_user_id or "anonymous"),
                    "visited_at": self._now_iso(),
                    "document_url": f"/#/workflows/{workflow_id}",
                },
            )
            return {
                "share_link": self._sanitize_share_link(link),
                "workflow": {
                    "workflow_id": workflow["workflow_id"],
                    "name": workflow["name"],
                    "description": workflow["description"],
                    "definition": deepcopy(workflow["current"]),
                },
            }

    def revoke_share_link(self, workflow_id: str, share_link_id: str, operator_user_id: str) -> Dict[str, Any]:
        operator = str(operator_user_id or "").strip()
        if not self.has_permission(workflow_id, operator, "manage_share"):
            raise PermissionError("无权限撤销分享链接")
        with self._lock:
            link = self._share_links.get(share_link_id)
            if not link or str(link.get("workflow_id")) != workflow_id:
                raise KeyError(f"share link '{share_link_id}' not found")
            link["revoked"] = True
            link["revoked_by"] = operator
            link["revoked_at"] = self._now_iso()
            return self._sanitize_share_link(link)

    def export_workflow_data(
        self,
        workflow_id: str,
        fmt: str = "json",
        share_link_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        format_name = str(fmt or "json").strip().lower()
        if format_name not in {"json", "csv"}:
            raise ValueError("fmt 仅支持 json/csv")

        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            definition = deepcopy(workflow["current"])
            if format_name == "json":
                content = json.dumps(definition, ensure_ascii=False, indent=2)
                mime = "application/json"
                filename = f"{workflow_id}.json"
            else:
                buffer = io.StringIO()
                writer = csv.writer(buffer)
                writer.writerow(["section", "id", "name_or_type", "source", "target", "params"])
                for node in definition.get("nodes") or []:
                    writer.writerow(
                        [
                            "node",
                            node.get("node_id"),
                            node.get("node_type"),
                            "",
                            "",
                            json.dumps(node.get("params") or {}, ensure_ascii=False),
                        ]
                    )
                for edge in definition.get("edges") or []:
                    writer.writerow(
                        [
                            "edge",
                            "",
                            "",
                            edge.get("source"),
                            edge.get("target"),
                            json.dumps({"condition": edge.get("condition")}, ensure_ascii=False),
                        ]
                    )
                content = buffer.getvalue()
                mime = "text/csv"
                filename = f"{workflow_id}.csv"

            if share_link_id:
                link = self._share_links.get(share_link_id)
                if link and str(link.get("workflow_id")) == workflow_id:
                    link["stats"]["downloads"] = int(link.get("stats", {}).get("downloads", 0)) + 1
                    workflow["collab_state"]["analytics"]["share_downloads"] += 1
                    cache_stats_key = self._cache_key_share_stats(share_link_id)
                    stats_payload = self._cache.get(cache_stats_key) or {"views": 0, "downloads": 0}
                    stats_payload["downloads"] = int(stats_payload.get("downloads", 0)) + 1
                    stats_payload["last_download_at"] = self._now_iso()
                    self._cache.set(cache_stats_key, stats_payload, ttl=self._SHARE_STATS_CACHE_TTL)

            return {
                "workflow_id": workflow_id,
                "format": format_name,
                "filename": filename,
                "mime_type": mime,
                "content": content,
                "size": len(content.encode("utf-8")),
            }

    def get_share_statistics(self, workflow_id: str) -> Dict[str, Any]:
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            share_ids = [str(item) for item in workflow["collab_state"].get("share_link_ids") or []]
            links = [self._share_links[item] for item in share_ids if item in self._share_links]
            total_views = 0
            total_downloads = 0
            for item in links:
                link_id = str(item.get("share_link_id") or "")
                cached_stats = self._cache.get(self._cache_key_share_stats(link_id)) or {}
                cached_views = int(cached_stats.get("views", 0))
                cached_downloads = int(cached_stats.get("downloads", 0))
                persisted_views = int(item.get("stats", {}).get("views", 0))
                persisted_downloads = int(item.get("stats", {}).get("downloads", 0))
                item.setdefault("stats", {})
                item["stats"]["views"] = max(persisted_views, cached_views)
                item["stats"]["downloads"] = max(persisted_downloads, cached_downloads)
                total_views += int(item["stats"]["views"])
                total_downloads += int(item["stats"]["downloads"])
            return {
                "workflow_id": workflow_id,
                "total_links": len(links),
                "total_views": total_views,
                "total_downloads": total_downloads,
                "links": [self._sanitize_share_link(item) for item in links],
            }

    def generate_social_share_links(
        self,
        workflow_id: str,
        share_link_id: str,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            link = self._share_links.get(share_link_id)
            if not link or str(link.get("workflow_id")) != workflow_id:
                raise KeyError(f"share link '{share_link_id}' not found")

            share_url = str(link.get("share_url"))
            share_title = str(title or f"查看工作流：{workflow['name']}")
            encoded_url = quote_plus(share_url)
            encoded_title = quote_plus(share_title)
            return {
                "workflow_id": workflow_id,
                "share_link_id": share_link_id,
                "platform_links": {
                    "x": f"https://x.com/intent/tweet?url={encoded_url}&text={encoded_title}",
                    "linkedin": f"https://www.linkedin.com/sharing/share-offsite/?url={encoded_url}",
                    "weibo": f"https://service.weibo.com/share/share.php?url={encoded_url}&title={encoded_title}",
                    "wechat": f"weixin://dl/business/?t={encoded_url}",
                },
            }

    # -------- 协作分析 --------
    def get_collaboration_analytics(self, workflow_id: str) -> Dict[str, Any]:
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]
            analytics = deepcopy(state.get("analytics") or {})
            total_conflicts = int(analytics.get("total_conflicts", 0))
            resolved_conflicts = int(analytics.get("auto_resolved_conflicts", 0)) + int(
                analytics.get("manual_resolved_conflicts", 0)
            )
            resolution_rate = round((resolved_conflicts / total_conflicts) * 100, 2) if total_conflicts else 100.0
            cursors = state.get("cursors") or {}
            now = self._now()
            active_users = 0
            for cursor in cursors.values():
                try:
                    updated_at = datetime.fromisoformat(str(cursor.get("updated_at")))
                except Exception:  # pylint: disable=broad-except
                    continue
                if (now - updated_at).total_seconds() <= 300:
                    active_users += 1

            contributor_stats = [
                {"user_id": uid, **deepcopy(stats)}
                for uid, stats in (state.get("contributor_stats") or {}).items()
            ]
            contributor_stats.sort(
                key=lambda item: (int(item.get("operations", 0)), int(item.get("comments", 0))),
                reverse=True,
            )
            return {
                "workflow_id": workflow_id,
                "revision": int(state.get("revision", 0)),
                "active_collaborators_5m": active_users,
                "conflict_resolution_rate": resolution_rate,
                "analytics": analytics,
                "top_contributors": contributor_stats[:10],
                "updated_at": self._now_iso(),
            }

    def _build_run_snapshot(self, run: Mapping[str, Any]) -> Dict[str, Any]:
        status = run.get("status")
        return {
            "run_id": run.get("run_id"),
            "workflow_id": run.get("workflow_id"),
            "status": status,
            "progress": run.get("progress"),
            "error": run.get("error"),
            "started_at": run.get("started_at"),
            "ended_at": run.get("ended_at"),
            "duration_ms": run.get("duration_ms"),
            "node_status_counts": {
                "running": sum(1 for item in (run.get("node_statuses") or {}).values() if item == "running"),
                "completed": sum(1 for item in (run.get("node_statuses") or {}).values() if item == "completed"),
                "failed": sum(1 for item in (run.get("node_statuses") or {}).values() if item == "failed"),
                "skipped": sum(1 for item in (run.get("node_statuses") or {}).values() if item == "skipped"),
            },
            "logs_count": len(run.get("logs") or []),
        }

    def _apply_run_event(self, run: Dict[str, Any], event: str, payload: Mapping[str, Any]) -> None:
        if event == "run_started":
            run["status"] = "running"
            run["started_at"] = str(payload.get("started_at") or run.get("started_at") or self._now_iso())
            run["progress"] = float(payload.get("progress", run.get("progress", 0.0)) or 0.0)
        elif event == "progress_update":
            run["progress"] = float(payload.get("progress", run.get("progress", 0.0)) or 0.0)
        elif event in {"node_started", "node_completed", "node_failed", "node_retry", "node_skipped"}:
            node_id = str(payload.get("node_id") or "")
            if node_id:
                if event == "node_started":
                    run.setdefault("node_statuses", {})[node_id] = "running"
                elif event == "node_completed":
                    run.setdefault("node_statuses", {})[node_id] = "completed"
                elif event == "node_failed":
                    run.setdefault("node_statuses", {})[node_id] = "failed"
                elif event == "node_skipped":
                    run.setdefault("node_statuses", {})[node_id] = "skipped"

            attempt = payload.get("attempt")
            if node_id and attempt is not None:
                try:
                    run.setdefault("node_attempts", {})[node_id] = int(attempt)
                except (TypeError, ValueError):
                    pass

            duration = payload.get("duration_ms")
            if node_id and duration is not None:
                try:
                    run.setdefault("node_timings_ms", {})[node_id] = float(duration)
                except (TypeError, ValueError):
                    pass

            log_item = payload.get("log")
            if isinstance(log_item, Mapping):
                logs = run.setdefault("logs", [])
                logs.append(deepcopy(dict(log_item)))
                if len(logs) > 5000:
                    del logs[:-5000]

        elif event in {"run_completed", "run_failed"}:
            run["status"] = "completed" if event == "run_completed" else "failed"
            run["ended_at"] = str(payload.get("ended_at") or self._now_iso())
            run["duration_ms"] = payload.get("duration_ms")
            run["progress"] = float(payload.get("progress", run.get("progress", 100.0)) or 0.0)
            run["error"] = payload.get("error")
            summary = payload.get("summary")
            if isinstance(summary, Mapping):
                run["summary"] = deepcopy(dict(summary))

    def _emit_workflow_run_event(
        self,
        workflow_id: str,
        run_id: str,
        event: str,
        update: Mapping[str, Any],
        snapshot: Optional[Mapping[str, Any]] = None,
    ) -> None:
        websocket_service.dispatch_workflow_run_update(
            run_id=run_id,
            event=event,
            update=deepcopy(dict(update)),
            workflow_id=workflow_id,
            snapshot=deepcopy(dict(snapshot or {})),
        )

    def _notify_workflow_execution_completed(self, workflow_id: str, run: Mapping[str, Any]) -> None:
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            if not workflow:
                return
            recipients: Set[str] = set()
            for collaborator in workflow.get("collaborators") or []:
                uid = str(collaborator.get("user_id") or "").strip()
                if uid:
                    recipients.add(uid)

            for uid in recipients:
                self._notify(
                    workflow=workflow,
                    user_id=uid,
                    event_type="workflow_execution_completed",
                    message=f"工作流 {workflow.get('name') or workflow_id} 执行完成",
                    payload={
                        "workflow_id": workflow_id,
                        "run_id": str(run.get("run_id") or ""),
                        "status": str(run.get("status") or "unknown"),
                        "result": str(run.get("status") or "unknown"),
                        "result_url": f"/#/workflows/{workflow_id}/runs/{run.get('run_id')}",
                    },
                )
            if recipients:
                self._persist_workflow_record(workflow)

    # -------- 执行与监控 --------
    def execute_workflow(
        self,
        workflow_id: str,
        input_variables: Optional[Mapping[str, Any]] = None,
        async_mode: bool = False,
        trigger: str = "manual",
        debug: bool = False,
        enterprise_id: Optional[str] = None,
        owner: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            current = self._workflows.get(workflow_id)
            if not current:
                raise KeyError(f"workflow '{workflow_id}' not found")
            definition = deepcopy(current["current"])

        if not async_mode:
            result = self._engine.execute(
                definition=definition,
                input_variables=input_variables,
                trigger=trigger,
                debug=debug,
            )
            with self._lock:
                result["enterprise_id"] = enterprise_id
                result["owner"] = owner
                result["assigned_to"] = assigned_to
                result["transfer"] = None
                self._runs[result["run_id"]] = deepcopy(result)
            self._update_metrics(result)
            return result

        run_id = f"run_{uuid4().hex[:12]}"
        placeholder = {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "workflow_version": definition["version"],
            "trigger": trigger,
            "status": "queued",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "duration_ms": None,
            "progress": 0.0,
            "error": None,
            "logs": [],
            "node_statuses": {},
            "node_attempts": {},
            "node_outputs": {},
            "node_timings_ms": {},
            "variables": deepcopy(definition.get("variables") or {}),
            "dag_levels": deepcopy(definition.get("dag_levels") or []),
            "summary": {
                "completed_nodes": 0,
                "failed_nodes": 0,
                "skipped_nodes": 0,
            },
            "enterprise_id": enterprise_id,
            "owner": owner,
            "assigned_to": assigned_to,
            "transfer": None,
        }

        with self._lock:
            self._runs[run_id] = placeholder
        self._emit_workflow_run_event(
            workflow_id=workflow_id,
            run_id=run_id,
            event="run_queued",
            update={"status": "queued", "progress": 0.0},
            snapshot=self._build_run_snapshot(placeholder),
        )

        thread = threading.Thread(
            target=self._execute_async,
            kwargs={
                "run_id": run_id,
                "definition": definition,
                "input_variables": deepcopy(dict(input_variables or {})),
                "trigger": trigger,
                "debug": debug,
            },
            daemon=True,
            name=f"workflow-runner-{run_id}",
        )
        thread.start()

        return deepcopy(placeholder)

    def _execute_async(
        self,
        run_id: str,
        definition: Mapping[str, Any],
        input_variables: Mapping[str, Any],
        trigger: str,
        debug: bool,
    ) -> None:
        workflow_id = str(definition.get("workflow_id") or "")

        def _on_engine_event(event: str, payload: Dict[str, Any]) -> None:
            snapshot: Dict[str, Any] = {}
            with self._lock:
                current = self._runs.get(run_id)
                if current:
                    self._apply_run_event(current, event, payload)
                    snapshot = self._build_run_snapshot(current)
            self._emit_workflow_run_event(
                workflow_id=workflow_id,
                run_id=run_id,
                event=event,
                update=payload,
                snapshot=snapshot,
            )

        try:
            result = self._engine.execute(
                definition=definition,
                input_variables=input_variables,
                trigger=trigger,
                debug=debug,
                run_id=run_id,
                event_callback=_on_engine_event,
            )
        except Exception as exc:  # pylint: disable=broad-except
            now = datetime.now(timezone.utc).isoformat()
            result = {
                "run_id": run_id,
                "workflow_id": definition.get("workflow_id"),
                "workflow_version": definition.get("version"),
                "trigger": trigger,
                "status": "failed",
                "started_at": now,
                "ended_at": now,
                "duration_ms": 0.0,
                "progress": 100.0,
                "error": str(exc),
                "logs": [
                    {
                        "ts": now,
                        "node_id": "__engine__",
                        "event": "engine_failed",
                        "message": str(exc),
                    }
                ],
                "node_statuses": {},
                "node_attempts": {},
                "node_outputs": {},
                "node_timings_ms": {},
                "variables": deepcopy(definition.get("variables") or {}),
                "dag_levels": deepcopy(definition.get("dag_levels") or []),
                "summary": {
                    "completed_nodes": 0,
                    "failed_nodes": 1,
                    "skipped_nodes": 0,
                },
            }
            self._emit_workflow_run_event(
                workflow_id=workflow_id,
                run_id=run_id,
                event="run_failed",
                update={
                    "error": str(exc),
                    "status": "failed",
                    "ended_at": now,
                    "duration_ms": 0.0,
                    "progress": 100.0,
                },
                snapshot=self._build_run_snapshot(result),
            )

        with self._lock:
            self._runs[run_id] = deepcopy(result)
            final_snapshot = self._build_run_snapshot(result)
        self._emit_workflow_run_event(
            workflow_id=workflow_id,
            run_id=run_id,
            event="run_finalized",
            update={
                "status": result.get("status"),
                "progress": result.get("progress"),
                "ended_at": result.get("ended_at"),
            },
            snapshot=final_snapshot,
        )
        self._update_metrics(result)
        self._notify_workflow_execution_completed(workflow_id=workflow_id, run=result)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            run = self._runs.get(run_id)
            return deepcopy(run) if run else None

    def list_runs(self, workflow_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            runs = list(self._runs.values())

        if workflow_id:
            runs = [item for item in runs if item.get("workflow_id") == workflow_id]

        runs.sort(key=lambda item: item.get("started_at", ""), reverse=True)
        trimmed = runs[: max(1, min(limit, 500))]
        return [
            {
                "run_id": item.get("run_id"),
                "workflow_id": item.get("workflow_id"),
                "workflow_version": item.get("workflow_version"),
                "status": item.get("status"),
                "trigger": item.get("trigger"),
                "started_at": item.get("started_at"),
                "ended_at": item.get("ended_at"),
                "duration_ms": item.get("duration_ms"),
                "progress": item.get("progress"),
                "enterprise_id": item.get("enterprise_id"),
                "owner": item.get("owner"),
                "assigned_to": item.get("assigned_to"),
                "transfer": deepcopy(item.get("transfer")),
            }
            for item in trimmed
        ]

    def list_task_items(self, workflow_id: str, enterprise_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            items = [deepcopy(item) for item in self._runs.values() if str(item.get("workflow_id")) == workflow_id]
        if enterprise_id:
            target = str(enterprise_id).strip()
            items = [item for item in items if str(item.get("enterprise_id") or "").strip() == target]
        items.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)
        return items

    def update_task_assignment(
        self,
        run_id: str,
        *,
        assigned_to: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                raise KeyError(f"run '{run_id}' not found")
            if assigned_to is not None:
                run["assigned_to"] = str(assigned_to or "").strip() or None
            if owner is not None:
                run["owner"] = str(owner or "").strip() or None
            return deepcopy(run)

    def initiate_task_transfer(self, run_id: str, *, from_user_id: str, to_user_id: str) -> Dict[str, Any]:
        sender = str(from_user_id or "").strip()
        receiver = str(to_user_id or "").strip()
        if not sender or not receiver:
            raise ValueError("from_user_id 和 to_user_id 不能为空")
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                raise KeyError(f"run '{run_id}' not found")
            run["status"] = "transferring"
            run["transfer"] = {
                "status": "pending",
                "from_user_id": sender,
                "to_user_id": receiver,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "confirmed_at": None,
            }
            return deepcopy(run)

    def confirm_task_transfer(self, run_id: str, *, receiver_user_id: str, accept: bool) -> Dict[str, Any]:
        receiver = str(receiver_user_id or "").strip()
        if not receiver:
            raise ValueError("receiver_user_id 不能为空")
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                raise KeyError(f"run '{run_id}' not found")
            transfer = run.get("transfer") or {}
            if str(transfer.get("to_user_id") or "") != receiver:
                raise PermissionError("仅接收人可以确认转移")
            transfer["status"] = "accepted" if accept else "rejected"
            transfer["confirmed_at"] = datetime.now(timezone.utc).isoformat()
            if accept:
                run["owner"] = receiver
                run["assigned_to"] = receiver
                if run.get("status") == "transferring":
                    run["status"] = "running"
            else:
                if run.get("status") == "transferring":
                    run["status"] = "running"
            run["transfer"] = transfer
            return deepcopy(run)

    def get_run_logs(self, run_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                raise KeyError(f"run '{run_id}' not found")
            return deepcopy(run.get("logs") or [])

    def get_performance_metrics(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._metrics)

    def _update_metrics(self, run: Mapping[str, Any]) -> None:
        with self._lock:
            self._metrics["total_runs"] += 1
            if run.get("status") == "completed":
                self._metrics["success_runs"] += 1
            else:
                self._metrics["failed_runs"] += 1

            duration = float(run.get("duration_ms") or 0.0)
            total = self._metrics["total_runs"]
            prev_avg = float(self._metrics.get("avg_duration_ms", 0.0))
            self._metrics["avg_duration_ms"] = round(((prev_avg * (total - 1)) + duration) / total, 3)
            self._metrics["last_updated_at"] = datetime.now(timezone.utc).isoformat()

    # -------- 模板库 / 市场 --------
    def list_templates(
        self,
        category: Optional[str] = None,
        shared_only: bool = False,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._templates.values())

        if category:
            items = [item for item in items if str(item.get("category")) == category]
        if shared_only:
            items = [item for item in items if bool(item.get("shared", False))]

        items.sort(key=lambda item: (item.get("rating_average", 0.0), item.get("usage_count", 0)), reverse=True)
        return [deepcopy(item) for item in items[: max(1, min(limit, 500))]]

    def create_template(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        workflow = payload.get("workflow")
        if not isinstance(workflow, Mapping):
            raise ValueError("workflow 字段必填")
        normalized = self._engine.validate_definition(workflow)

        template_id = str(payload.get("template_id") or f"tpl_custom_{uuid4().hex[:10]}")
        now = datetime.now(timezone.utc).isoformat()
        template = {
            "template_id": template_id,
            "name": str(payload.get("name") or normalized["name"]),
            "category": str(payload.get("category") or "custom"),
            "tags": list(payload.get("tags") or []),
            "description": str(payload.get("description") or normalized.get("description") or ""),
            "workflow": normalized,
            "shared": bool(payload.get("shared", False)),
            "rating_average": 0.0,
            "rating_count": 0,
            "usage_count": 0,
            "ratings": [],
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            if template_id in self._templates:
                raise ValueError(f"template '{template_id}' 已存在")
            self._templates[template_id] = template

        return deepcopy(template)

    def share_template(self, template_id: str, shared: bool = True) -> Dict[str, Any]:
        with self._lock:
            template = self._templates.get(template_id)
            if not template:
                raise KeyError(f"template '{template_id}' not found")
            template["shared"] = bool(shared)
            template["updated_at"] = datetime.now(timezone.utc).isoformat()
            return deepcopy(template)

    def rate_template(
        self,
        template_id: str,
        rating: float,
        user_id: str = "anonymous",
        comment: str = "",
    ) -> Dict[str, Any]:
        if rating < 1 or rating > 5:
            raise ValueError("rating 必须在 [1, 5]")

        with self._lock:
            template = self._templates.get(template_id)
            if not template:
                raise KeyError(f"template '{template_id}' not found")

            ratings = template.setdefault("ratings", [])
            ratings.append(
                {
                    "user_id": user_id,
                    "rating": float(rating),
                    "comment": comment,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            score_sum = sum(float(item["rating"]) for item in ratings)
            template["rating_count"] = len(ratings)
            template["rating_average"] = round(score_sum / len(ratings), 3)
            template["updated_at"] = datetime.now(timezone.utc).isoformat()
            return deepcopy(template)

    def recommend_templates(
        self,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        tags_set = {tag.strip().lower() for tag in (tags or []) if tag and tag.strip()}
        candidates = self.list_templates(category=category, shared_only=True, limit=500)

        scored: List[Dict[str, Any]] = []
        for item in candidates:
            item_tags = {str(tag).lower() for tag in item.get("tags", [])}
            tag_score = len(tags_set.intersection(item_tags)) if tags_set else 0
            quality_score = float(item.get("rating_average", 0.0))
            usage_score = min(2.0, float(item.get("usage_count", 0)) / 10.0)
            score = tag_score * 2 + quality_score + usage_score
            scored.append({"score": round(score, 3), "template": item})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return [
            {
                "score": item["score"],
                "template": item["template"],
            }
            for item in scored[: max(1, min(limit, 50))]
        ]

    def create_workflow_from_template(
        self,
        template_id: str,
        workflow_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            template = self._templates.get(template_id)
            if not template:
                raise KeyError(f"template '{template_id}' not found")
            workflow = deepcopy(template["workflow"])
            template["usage_count"] = int(template.get("usage_count", 0)) + 1
            template["updated_at"] = datetime.now(timezone.utc).isoformat()

        workflow["workflow_id"] = f"wf_{uuid4().hex[:12]}"
        workflow["name"] = workflow_name or f"{workflow.get('name', '模板工作流')}_实例"
        workflow["version"] = 1
        return self.create_workflow(workflow)

    def get_marketplace(self, limit: int = 20) -> List[Dict[str, Any]]:
        templates = self.list_templates(shared_only=True, limit=500)
        templates.sort(
            key=lambda item: (
                float(item.get("rating_average", 0.0)),
                int(item.get("rating_count", 0)),
                int(item.get("usage_count", 0)),
            ),
            reverse=True,
        )
        return templates[: max(1, min(limit, 100))]

    # -------- 访问控制 (ACL) --------
    def check_workflow_access(
        self,
        workflow_id: str,
        user_id: str,
        required_permission: str = "view_workflow",
    ) -> Dict[str, Any]:
        """校验用户对工作流的访问权限。
        公有工作流: 任何人可读(仅view_workflow权限)，编辑需ACL授权
        私有工作流: 需在ACL中或被显式授权方可访问，未授权guest不可访问
        """
        uid = str(user_id or "").strip()
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            is_public = bool(workflow.get("is_public", False))
            owner_id = str(workflow.get("owner_id") or "")

            # 拥有者始终有全部权限
            if uid and owner_id == uid:
                return {"workflow_id": workflow_id, "user_id": uid, "access": "granted", "role": "owner"}

            if is_public and required_permission in ("view_workflow",):
                return {"workflow_id": workflow_id, "user_id": uid, "access": "granted", "role": "public_viewer"}

            # 私有工作流：检查用户是否有显式授权 (非默认 guest)
            perms = self.get_effective_permissions(workflow_id, uid)
            user_roles = set(perms.get("roles") or [])

            # 私有工作流：guest(无显式授权)不可访问
            if not is_public and user_roles == {"guest"}:
                raise PermissionError(
                    f"access denied for user '{uid}' on private workflow '{workflow_id}'"
                )

            # 公有工作流但需要更高权限(如编辑)：检查显式 ACL
            if required_permission in set(perms.get("permissions") or []):
                return {"workflow_id": workflow_id, "user_id": uid, "access": "granted",
                        "roles": perms.get("roles", []), "permissions": perms.get("permissions", [])}

            raise PermissionError(
                f"access denied for user '{uid}' on workflow '{workflow_id}' "
                f"(required: {required_permission})"
            )

    def get_workflow_acl(self, workflow_id: str) -> Dict[str, Any]:
        """获取工作流的 ACL 信息。"""
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            return {
                "workflow_id": workflow_id,
                "is_public": bool(workflow.get("is_public", False)),
                "owner_id": str(workflow.get("owner_id") or ""),
                "collaborators": deepcopy(workflow.get("collaborators") or []),
            }

    def set_workflow_acl(
        self,
        workflow_id: str,
        is_public: Optional[bool] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """管理员更新工作流公有/私有属性。"""
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            if is_public is not None:
                workflow["is_public"] = bool(is_public)
            if owner_id is not None:
                workflow["owner_id"] = str(owner_id)
            workflow["updated_at"] = self._now_iso()
            self._persist_workflow_record(workflow)
            self._invalidate_permission_cache(workflow_id)
            self._cache.set(self._cache_key_workflow(workflow_id), workflow, ttl=self._WORKFLOW_CACHE_TTL)
            return self.get_workflow_acl(workflow_id)

    # -------- 分支管理 (Branch) --------
    def _lock_workflow(self, workflow_id: str, user_id: str) -> Dict[str, Any]:
        """锁定工作流 (写入者获取锁)。"""
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]
            state["locked_by"] = str(user_id)
            state["locked_at"] = self._now_iso()
            workflow["updated_at"] = state["locked_at"]
            self._persist_workflow_record(workflow)
            self._cache.set(self._cache_key_workflow(workflow_id), workflow, ttl=self._WORKFLOW_CACHE_TTL)
            return {"workflow_id": workflow_id, "locked_by": user_id, "locked_at": state["locked_at"]}

    def _unlock_workflow(self, workflow_id: str, user_id: str) -> Dict[str, Any]:
        """解锁工作流。"""
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]
            if state.get("locked_by") != str(user_id):
                raise PermissionError(f"only lock holder can unlock workflow '{workflow_id}'")
            state["locked_by"] = None
            state["locked_at"] = None
            workflow["updated_at"] = self._now_iso()
            self._persist_workflow_record(workflow)
            self._cache.set(self._cache_key_workflow(workflow_id), workflow, ttl=self._WORKFLOW_CACHE_TTL)
            return {"workflow_id": workflow_id, "unlocked": True}

    def _is_workflow_locked(self, workflow_id: str) -> bool:
        """检查工作流是否处于锁定状态。"""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return False
        state = workflow.get("collab_state") or {}
        return bool(state.get("locked_by"))

    def create_branch(
        self,
        workflow_id: str,
        created_by: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建冲突分支。
        当 Workflow 处于锁定状态且收到非锁定用户的 write 请求时自动触发。
        也可由管理员主动调用以创建实验性分支。
        """
        user_id = str(created_by or "").strip()
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow["collab_state"]

            branch_id = f"branch_{uuid4().hex[:12]}"
            branch_data = deepcopy(data) if data else deepcopy(workflow["current"])
            now = self._now_iso()

            branch = {
                "branch_id": branch_id,
                "workflow_id": workflow_id,
                "parent_branch_id": None,
                "created_by": user_id,
                "data": branch_data,
                "status": "open",
                "created_at": now,
                "updated_at": now,
            }
            self._branches[branch_id] = branch

            # 将分支 ID 注册到工作流 collab_state
            branch_ids = list(state.get("branch_ids") or [])
            branch_ids.append(branch_id)
            state["branch_ids"] = branch_ids
            workflow["updated_at"] = now
            self._persist_workflow_record(workflow)
            self._cache.set(self._cache_key_workflow(workflow_id), workflow, ttl=self._WORKFLOW_CACHE_TTL)

            # 通知相关协作者
            self._notify(
                workflow,
                user_id,
                "branch_created",
                f"工作流 '{workflow.get('name', workflow_id)}' 已自动创建分支 (冲突处理)",
                {"branch_id": branch_id, "workflow_id": workflow_id},
            )

            return deepcopy(branch)

    def list_branches(self, workflow_id: str) -> List[Dict[str, Any]]:
        """列出工作流的所有分支。"""
        with self._lock:
            workflow = self._workflow_or_error(workflow_id)
            state = workflow.get("collab_state") or {}
            branch_ids = state.get("branch_ids") or []
            branches = []
            for bid in branch_ids:
                branch = self._branches.get(bid)
                if branch:
                    branches.append({
                        "branch_id": branch["branch_id"],
                        "workflow_id": branch["workflow_id"],
                        "created_by": branch["created_by"],
                        "status": branch["status"],
                        "created_at": branch["created_at"],
                        "updated_at": branch["updated_at"],
                    })
            return branches

    def get_branch(self, branch_id: str) -> Dict[str, Any]:
        """获取单个分支详情。"""
        with self._lock:
            branch = self._branches.get(branch_id)
            if not branch:
                raise KeyError(f"branch '{branch_id}' not found")
            return deepcopy(branch)

    def get_branch_diff(self, branch_id: str) -> Dict[str, Any]:
        """获取分支与主工作流当前版本的差异。"""
        with self._lock:
            branch = self._branches.get(branch_id)
            if not branch:
                raise KeyError(f"branch '{branch_id}' not found")

            workflow_id = branch["workflow_id"]
            workflow = self._workflow_or_error(workflow_id)
            main_data = workflow["current"]
            branch_data = branch["data"]

            # 计算差异：对比 nodes 和 edges
            main_nodes = {n["node_id"]: n for n in (main_data.get("nodes") or [])}
            branch_nodes = {n["node_id"]: n for n in (branch_data.get("nodes") or [])}
            main_edges = {f"{e['source']}->{e['target']}": e for e in (main_data.get("edges") or [])}
            branch_edges = {f"{e['source']}->{e['target']}": e for e in (branch_data.get("edges") or [])}

            diff = {
                "branch_id": branch_id,
                "workflow_id": workflow_id,
                "nodes_added": [nid for nid in branch_nodes if nid not in main_nodes],
                "nodes_removed": [nid for nid in main_nodes if nid not in branch_nodes],
                "nodes_modified": [
                    nid for nid in branch_nodes
                    if nid in main_nodes and branch_nodes[nid] != main_nodes[nid]
                ],
                "edges_added": [eid for eid in branch_edges if eid not in main_edges],
                "edges_removed": [eid for eid in main_edges if eid not in branch_edges],
                "main": {"nodes": deepcopy(main_data.get("nodes", [])), "edges": deepcopy(main_data.get("edges", []))},
                "branch": {"nodes": deepcopy(branch_data.get("nodes", [])), "edges": deepcopy(branch_data.get("edges", []))},
            }
            return diff

    def merge_branch(self, branch_id: str, resolver_user_id: str) -> Dict[str, Any]:
        """将分支并入主工作流。仅工作流管理员可执行。"""
        user_id = str(resolver_user_id or "").strip()
        with self._lock:
            branch = self._branches.get(branch_id)
            if not branch:
                raise KeyError(f"branch '{branch_id}' not found")
            if branch["status"] != "open":
                raise ValueError(f"branch '{branch_id}' is not open (status: {branch['status']})")

            workflow_id = branch["workflow_id"]
            workflow = self._workflow_or_error(workflow_id)

            # 权限校验：仅管理员可合并
            if not self.has_permission(workflow_id, user_id, "resolve_conflict"):
                raise PermissionError(f"user '{user_id}' lacks resolve_conflict permission on workflow '{workflow_id}'")

            # 合并数据：将分支数据作为新版本写入主工作流
            branch_data = branch["data"]
            note = f"merge branch '{branch_id}' by {user_id}"
            self.update_workflow(workflow_id, branch_data, note=note)

            # 更新分支状态
            branch["status"] = "merged"
            branch["updated_at"] = self._now_iso()

            # 清除工作流锁定
            state = workflow["collab_state"]
            state["locked_by"] = None
            state["locked_at"] = None
            self._persist_workflow_record(self._workflows[workflow_id])
            self._cache.set(self._cache_key_workflow(workflow_id), self._workflows[workflow_id],
                           ttl=self._WORKFLOW_CACHE_TTL)

            self._notify(
                workflow,
                branch["created_by"],
                "branch_merged",
                f"分支 '{branch_id}' 已被管理员 '{user_id}' 合并到主工作流",
                {"branch_id": branch_id, "workflow_id": workflow_id, "merged_by": user_id},
            )

            return {"branch_id": branch_id, "status": "merged", "merged_by": user_id}

    def reject_branch(self, branch_id: str, resolver_user_id: str) -> Dict[str, Any]:
        """拒绝分支 (不合并)。仅工作流管理员可执行。"""
        user_id = str(resolver_user_id or "").strip()
        with self._lock:
            branch = self._branches.get(branch_id)
            if not branch:
                raise KeyError(f"branch '{branch_id}' not found")
            if branch["status"] != "open":
                raise ValueError(f"branch '{branch_id}' is not open (status: {branch['status']})")

            workflow_id = branch["workflow_id"]
            workflow = self._workflow_or_error(workflow_id)

            if not self.has_permission(workflow_id, user_id, "resolve_conflict"):
                raise PermissionError(f"user '{user_id}' lacks resolve_conflict permission on workflow '{workflow_id}'")

            branch["status"] = "rejected"
            branch["updated_at"] = self._now_iso()

            self._notify(
                workflow,
                branch["created_by"],
                "branch_rejected",
                f"分支 '{branch_id}' 已被管理员 '{user_id}' 拒绝",
                {"branch_id": branch_id, "workflow_id": workflow_id, "rejected_by": user_id},
            )

            return {"branch_id": branch_id, "status": "rejected", "rejected_by": user_id}

    # -------- 调度 --------
    def create_schedule(
        self,
        workflow_id: str,
        interval_seconds: int,
        trigger_payload: Optional[Mapping[str, Any]] = None,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        if interval_seconds < 1:
            raise ValueError("interval_seconds 必须 >= 1")

        with self._lock:
            if workflow_id not in self._workflows:
                raise KeyError(f"workflow '{workflow_id}' not found")

            schedule_id = f"sch_{uuid4().hex[:12]}"
            now = datetime.now(timezone.utc)
            schedule = {
                "schedule_id": schedule_id,
                "workflow_id": workflow_id,
                "interval_seconds": int(interval_seconds),
                "enabled": bool(enabled),
                "trigger_payload": deepcopy(dict(trigger_payload or {})),
                "next_run_at": (now + timedelta(seconds=interval_seconds)).isoformat(),
                "last_run_at": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            self._schedules[schedule_id] = schedule
            return deepcopy(schedule)

    def list_schedules(self, workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            schedules = list(self._schedules.values())

        if workflow_id:
            schedules = [item for item in schedules if item["workflow_id"] == workflow_id]
        schedules.sort(key=lambda item: item["created_at"], reverse=True)
        return [deepcopy(item) for item in schedules]

    def delete_schedule(self, schedule_id: str) -> None:
        with self._lock:
            if schedule_id not in self._schedules:
                raise KeyError(f"schedule '{schedule_id}' not found")
            del self._schedules[schedule_id]

    def trigger_schedule(self, schedule_id: str) -> Dict[str, Any]:
        with self._lock:
            schedule = self._schedules.get(schedule_id)
            if not schedule:
                raise KeyError(f"schedule '{schedule_id}' not found")

            schedule["last_run_at"] = datetime.now(timezone.utc).isoformat()
            schedule["next_run_at"] = (
                datetime.now(timezone.utc) + timedelta(seconds=int(schedule["interval_seconds"]))
            ).isoformat()
            schedule["updated_at"] = datetime.now(timezone.utc).isoformat()

            workflow_id = schedule["workflow_id"]
            payload = deepcopy(schedule.get("trigger_payload") or {})

        run = self.execute_workflow(
            workflow_id=workflow_id,
            input_variables=payload,
            async_mode=True,
            trigger=f"schedule:{schedule_id}",
            debug=False,
        )
        return run

    def _scheduler_loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    return
                schedules = [deepcopy(item) for item in self._schedules.values() if item.get("enabled", False)]

            now = datetime.now(timezone.utc)
            for schedule in schedules:
                next_run_raw = schedule.get("next_run_at")
                if not next_run_raw:
                    continue
                try:
                    next_run_at = datetime.fromisoformat(next_run_raw)
                except Exception:  # pylint: disable=broad-except
                    continue

                if next_run_at <= now:
                    try:
                        self.trigger_schedule(schedule["schedule_id"])
                    except Exception:  # pylint: disable=broad-except
                        # 调度循环容错：失败记录在 run/error 中，不让线程退出
                        pass

            time.sleep(1.0)


# 单例
_smart_workflow_service: Optional[SmartWorkflowService] = None


def get_smart_workflow_service() -> SmartWorkflowService:
    global _smart_workflow_service
    if _smart_workflow_service is None:
        _smart_workflow_service = SmartWorkflowService()
    return _smart_workflow_service


def reset_smart_workflow_service() -> None:
    global _smart_workflow_service
    if _smart_workflow_service is not None:
        _smart_workflow_service.stop_scheduler()
    _smart_workflow_service = None


smart_workflow_service = get_smart_workflow_service()

__all__ = [
    "SmartWorkflowService",
    "smart_workflow_service",
    "get_smart_workflow_service",
    "reset_smart_workflow_service",
    "WorkflowValidationError",
]
