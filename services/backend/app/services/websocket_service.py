import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from fastapi import WebSocket


class WebSocketService:
    HEARTBEAT_INTERVAL_SECONDS = 30
    HEARTBEAT_TIMEOUT_SECONDS = 90
    RECONNECT_STATE_TTL_SECONDS = 300
    CURSOR_THROTTLE_MS = 100
    CURSOR_TIMEOUT_SECONDS = 30

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_states: Dict[str, Dict[str, Any]] = {}
        self.task_subscribers: Dict[str, Set[str]] = {}
        self.project_subscribers: Dict[str, Set[str]] = {}
        self.workflow_subscribers: Dict[str, Set[str]] = {}
        self.workflow_run_subscribers: Dict[str, Set[str]] = {}
        self.user_connections: Dict[str, Set[str]] = {}
        self.pending_messages: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.offline_message_queue: Dict[str, List[Dict[str, Any]]] = {}
        self.disconnected_states: Dict[str, Dict[str, Any]] = {}
        self.operation_logs: Dict[str, List[Dict[str, Any]]] = {}
        self.operation_seq_index: Dict[str, Dict[str, int]] = {}
        self.operation_conflicts: Dict[str, List[Dict[str, Any]]] = {}
        self.cursor_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.comment_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.notification_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.notification_dedup_cache: Dict[str, Dict[str, datetime]] = {}
        self.share_access_stats: Dict[str, Dict[str, Any]] = {}
        self._heartbeat_task: Optional[asyncio.Task[Any]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _now_iso(self) -> str:
        return self._now().isoformat()

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        user_id: Optional[str] = None,
        restore_subscriptions: bool = False,
    ):
        await websocket.accept()
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        self._ensure_heartbeat_task()

        self.active_connections[client_id] = websocket
        now = self._now()
        self.client_states[client_id] = {
            "connected_at": now,
            "last_seen_at": now,
            "last_heartbeat_at": now,
            "user_id": str(user_id or "").strip(),
            "messages_sent": 0,
            "messages_received": 0,
        }
        self.pending_messages.setdefault(client_id, {})

        if user_id:
            self.user_connections.setdefault(str(user_id), set()).add(client_id)

        reconnect_state = self.disconnected_states.get(client_id)
        if reconnect_state and restore_subscriptions:
            self.disconnected_states.pop(client_id, None)
            self._restore_subscriptions(client_id, reconnect_state)
            await self.send_personal_message(
                self.build_message(
                    "reconnected",
                    data={"restored": True},
                    client_id=client_id,
                    user_id=str(user_id or ""),
                ),
                client_id,
            )

        queued_messages = self.offline_message_queue.pop(client_id, [])
        for queued in queued_messages:
            await self.send_personal_message(queued, client_id)

        print(f"客户端 {client_id} 已连接")

    def disconnect(self, client_id: str):
        state = self.client_states.get(client_id, {})
        user_id = str(state.get("user_id") or "")
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.client_states:
            del self.client_states[client_id]

        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(client_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        self.disconnected_states[client_id] = {
            "snapshot_at": self._now_iso(),
            "expire_at": (self._now() + timedelta(seconds=self.RECONNECT_STATE_TTL_SECONDS)).isoformat(),
            "subscriptions": {
                "tasks": [task_id for task_id, items in self.task_subscribers.items() if client_id in items],
                "projects": [project_id for project_id, items in self.project_subscribers.items() if client_id in items],
                "workflows": [workflow_id for workflow_id, items in self.workflow_subscribers.items() if client_id in items],
                "workflow_runs": [run_id for run_id, items in self.workflow_run_subscribers.items() if client_id in items],
            },
            "pending": list((self.pending_messages.get(client_id) or {}).values()),
            "user_id": user_id,
        }

        for task_id, subscribers in self.task_subscribers.items():
            subscribers.discard(client_id)
        for project_id, subscribers in self.project_subscribers.items():
            subscribers.discard(client_id)
        for workflow_id, subscribers in self.workflow_subscribers.items():
            subscribers.discard(client_id)
        for run_id, subscribers in self.workflow_run_subscribers.items():
            subscribers.discard(client_id)

        print(f"客户端 {client_id} 已断开")

    def touch(self, client_id: str, received_message: bool = False):
        state = self.client_states.get(client_id)
        if not state:
            return
        state["last_seen_at"] = self._now()
        if received_message:
            state["messages_received"] = int(state.get("messages_received", 0)) + 1

    def receive_heartbeat(self, client_id: str):
        state = self.client_states.get(client_id)
        if not state:
            return
        now = self._now()
        state["last_seen_at"] = now
        state["last_heartbeat_at"] = now

    def build_message(
        self,
        message_type: str,
        data: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None,
        signature: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        payload = {
            "type": str(message_type),
            "timestamp": self._now_iso(),
            "message_id": str(message_id or f"ws_{uuid4().hex[:16]}"),
            "data": data or {},
        }
        if signature:
            payload["signature"] = signature
        payload.update(extra)
        return payload

    def validate_message(
        self,
        message: Dict[str, Any],
        required_fields: Optional[List[str]] = None,
    ) -> Optional[str]:
        if not isinstance(message, dict):
            return "message 必须是 JSON 对象"
        message_type = message.get("type")
        if not isinstance(message_type, str) or not message_type.strip():
            return "message.type 不能为空"
        required = required_fields or []
        for key in required:
            if message.get(key) is None and not isinstance((message.get("data") or {}).get(key), (dict, list, str, int, float, bool)):
                return f"{key} is required"
        return None

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(message)
                state = self.client_states.get(client_id)
                if state:
                    state["messages_sent"] = int(state.get("messages_sent", 0)) + 1
                    state["last_seen_at"] = self._now()
            except Exception:
                self.disconnect(client_id)
        else:
            queue = self.offline_message_queue.setdefault(client_id, [])
            queue.append(message)
            if len(queue) > 1000:
                self.offline_message_queue[client_id] = queue[-1000:]

    async def send_to_user(self, message: dict, user_id: str):
        targets = list(self.user_connections.get(str(user_id), set()))
        for client_id in targets:
            await self.send_personal_message(message, client_id)

    async def broadcast(self, message: dict):
        for client_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, client_id)

    async def broadcast_to_group(self, group: str, group_id: str, message: dict, exclude_client_id: Optional[str] = None):
        if group == "workflow":
            targets = set(self.workflow_subscribers.get(group_id, set()))
        elif group == "task":
            targets = set(self.task_subscribers.get(group_id, set()))
        elif group == "project":
            targets = set(self.project_subscribers.get(group_id, set()))
        elif group == "workflow_run":
            targets = set(self.workflow_run_subscribers.get(group_id, set()))
        else:
            targets = set()

        for client_id in targets:
            if exclude_client_id and client_id == exclude_client_id:
                continue
            await self.send_personal_message(message, client_id)

    async def subscribe_to_task(self, client_id: str, task_id: str):
        if task_id not in self.task_subscribers:
            self.task_subscribers[task_id] = set()
        self.task_subscribers[task_id].add(client_id)

    async def unsubscribe_from_task(self, client_id: str, task_id: str):
        if task_id in self.task_subscribers:
            self.task_subscribers[task_id].discard(client_id)

    async def subscribe_to_project(self, client_id: str, project_id: str):
        if project_id not in self.project_subscribers:
            self.project_subscribers[project_id] = set()
        self.project_subscribers[project_id].add(client_id)

    async def unsubscribe_from_project(self, client_id: str, project_id: str):
        if project_id in self.project_subscribers:
            self.project_subscribers[project_id].discard(client_id)

    async def subscribe_to_workflow(self, client_id: str, workflow_id: str):
        if workflow_id not in self.workflow_subscribers:
            self.workflow_subscribers[workflow_id] = set()
        self.workflow_subscribers[workflow_id].add(client_id)

    async def unsubscribe_from_workflow(self, client_id: str, workflow_id: str):
        if workflow_id in self.workflow_subscribers:
            self.workflow_subscribers[workflow_id].discard(client_id)

    async def subscribe_to_workflow_run(self, client_id: str, run_id: str):
        if run_id not in self.workflow_run_subscribers:
            self.workflow_run_subscribers[run_id] = set()
        self.workflow_run_subscribers[run_id].add(client_id)

    async def unsubscribe_from_workflow_run(self, client_id: str, run_id: str):
        if run_id in self.workflow_run_subscribers:
            self.workflow_run_subscribers[run_id].discard(client_id)

    def record_collaboration_operation(
        self,
        workflow_id: str,
        user_id: str,
        operation_type: str,
        operation_data: Dict[str, Any],
        sequence: Optional[int] = None,
    ) -> Dict[str, Any]:
        allowed = {"create", "update", "delete", "move", "resize"}
        op_name = str(operation_type or "").strip().lower()
        if op_name not in allowed:
            raise ValueError("operation_type 必须是 create/update/delete/move/resize")

        now = self._now()
        workflow_key = str(workflow_id)
        user_key = str(user_id)
        sequence_map = self.operation_seq_index.setdefault(workflow_key, {})
        last_sequence = int(sequence_map.get(user_key, 0))
        incoming_sequence = int(sequence or (last_sequence + 1))

        conflict: Optional[Dict[str, Any]] = None
        if incoming_sequence <= last_sequence:
            conflict = {
                "conflict_id": f"conf_{uuid4().hex[:12]}",
                "workflow_id": workflow_key,
                "user_id": user_key,
                "reason": "operation_order_violation",
                "last_sequence": last_sequence,
                "incoming_sequence": incoming_sequence,
                "created_at": now.isoformat(),
            }
            self.operation_conflicts.setdefault(workflow_key, []).append(conflict)
        else:
            sequence_map[user_key] = incoming_sequence

        record = {
            "operation_id": f"op_{uuid4().hex[:12]}",
            "workflow_id": workflow_key,
            "user_id": user_key,
            "operation_type": op_name,
            "operation_data": operation_data or {},
            "sequence": incoming_sequence,
            "timestamp": now.isoformat(),
            "conflict": conflict,
        }
        logs = self.operation_logs.setdefault(workflow_key, [])
        logs.append(record)
        if len(logs) > 5000:
            self.operation_logs[workflow_key] = logs[-5000:]
        return record

    def process_cursor_update(
        self,
        workflow_id: str,
        user_id: str,
        cursor_position: Dict[str, Any],
        color: str,
        client_timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        workflow_key = str(workflow_id)
        user_key = str(user_id)
        now = self._now()
        workflow_cache = self.cursor_cache.setdefault(workflow_key, {})
        previous = workflow_cache.get(user_key) or {}
        prev_ts = previous.get("_server_ts")
        prev_position = previous.get("cursor_position")

        throttled = False
        changed = prev_position != cursor_position
        if isinstance(prev_ts, datetime):
            elapsed = (now - prev_ts).total_seconds() * 1000
            if elapsed < self.CURSOR_THROTTLE_MS:
                throttled = True

        payload = {
            "workflow_id": workflow_key,
            "user_id": user_key,
            "cursor_position": cursor_position,
            "color": str(color or "#409eff"),
            "timestamp": str(client_timestamp or now.isoformat()),
            "_server_ts": now,
        }
        workflow_cache[user_key] = payload
        return {
            "cursor": {k: v for k, v in payload.items() if not k.startswith("_")},
            "throttled": throttled,
            "changed": changed,
        }

    def get_active_cursors(self, workflow_id: str, timeout_seconds: Optional[int] = None) -> List[Dict[str, Any]]:
        timeout = int(timeout_seconds or self.CURSOR_TIMEOUT_SECONDS)
        now = self._now()
        workflow_cache = self.cursor_cache.get(str(workflow_id), {})
        active: List[Dict[str, Any]] = []
        for user_id, cursor in workflow_cache.items():
            server_ts = cursor.get("_server_ts")
            if isinstance(server_ts, datetime) and (now - server_ts).total_seconds() <= timeout:
                active.append(
                    {
                        "workflow_id": str(workflow_id),
                        "user_id": user_id,
                        "cursor_position": cursor.get("cursor_position") or {},
                        "color": str(cursor.get("color") or "#409eff"),
                        "timestamp": str(cursor.get("timestamp") or ""),
                    }
                )
        return active

    def record_comment(
        self,
        workflow_id: str,
        comment_id: str,
        user_id: str,
        content: str,
        parent_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        mentions = sorted(set(re.findall(r"@([A-Za-z0-9_.-]+)", str(content or ""))))
        comment = {
            "workflow_id": str(workflow_id),
            "comment_id": str(comment_id),
            "user_id": str(user_id),
            "content": str(content or ""),
            "parent_id": str(parent_id or ""),
            "mentions": mentions,
            "timestamp": str(timestamp or self._now_iso()),
        }
        logs = self.comment_cache.setdefault(str(workflow_id), [])
        logs.append(comment)
        if len(logs) > 3000:
            self.comment_cache[str(workflow_id)] = logs[-3000:]
        return comment

    def queue_notification(self, notification: Dict[str, Any], priority: str = "high") -> Dict[str, Any]:
        user_id = str(notification.get("user_id") or "")
        if not user_id:
            raise ValueError("notification.user_id is required")
        n_type = str(notification.get("type") or "")
        title = str(notification.get("title") or "")
        content = str(notification.get("content") or "")
        dedupe_key = f"{n_type}:{title}:{content}".strip(":")
        now = self._now()
        user_dedup = self.notification_dedup_cache.setdefault(user_id, {})
        last_seen = user_dedup.get(dedupe_key)
        if isinstance(last_seen, datetime) and (now - last_seen).total_seconds() <= 300:
            return {"deduplicated": True, "notification": notification}
        user_dedup[dedupe_key] = now
        user_logs = self.notification_cache.setdefault(user_id, [])
        user_logs.append(notification)
        if len(user_logs) > 3000:
            self.notification_cache[user_id] = user_logs[-3000:]
        return {"deduplicated": False, "notification": notification, "priority": str(priority or "high").lower()}

    def record_share_access(
        self,
        share_token: str,
        workflow_id: str,
        visitor_id: str,
        access_time: Optional[str] = None,
        access_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = str(share_token)
        payload = self.share_access_stats.setdefault(
            token,
            {
                "share_token": token,
                "workflow_id": str(workflow_id),
                "access_count": 0,
                "visitors": set(),
                "access_times": [],
            },
        )
        payload["access_count"] = int(payload.get("access_count", 0)) + 1
        payload["visitors"].add(str(visitor_id or "anonymous"))
        payload["access_times"].append(str(access_time or self._now_iso()))
        if len(payload["access_times"]) > 5000:
            payload["access_times"] = payload["access_times"][-5000:]
        if access_type:
            payload["last_access_type"] = str(access_type)
        payload["last_access_at"] = str(access_time or self._now_iso())
        return {
            "share_token": token,
            "workflow_id": str(workflow_id),
            "access_count": int(payload["access_count"]),
            "unique_visitors": len(payload["visitors"]),
            "last_access_at": payload["last_access_at"],
            "last_access_type": payload.get("last_access_type", ""),
        }

    def get_connection_stats(self) -> Dict[str, Any]:
        return {
            "active_connections": len(self.active_connections),
            "active_users": len(self.user_connections),
            "task_subscriptions": sum(len(v) for v in self.task_subscribers.values()),
            "workflow_subscriptions": sum(len(v) for v in self.workflow_subscribers.values()),
            "project_subscriptions": sum(len(v) for v in self.project_subscribers.values()),
            "workflow_run_subscriptions": sum(len(v) for v in self.workflow_run_subscribers.values()),
            "timestamp": self._now_iso(),
        }

    async def register_pending_message(self, client_id: str, message_id: str, payload: Dict[str, Any]):
        self.pending_messages.setdefault(client_id, {})[message_id] = {
            "payload": payload,
            "created_at": datetime.now().isoformat()
        }

    async def confirm_ack(self, client_id: str, message_id: str):
        if client_id in self.pending_messages:
            self.pending_messages[client_id].pop(message_id, None)

    async def notify_task_update(self, task_id: str, update: dict):
        if task_id in self.task_subscribers:
            subscribers = self.task_subscribers[task_id]
            message = {
                'type': 'task_update',
                'task_id': task_id,
                'data': update,
                'timestamp': datetime.now().isoformat()
            }
            for subscriber_id in subscribers:
                await self.send_personal_message(message, subscriber_id)

    async def notify_gps_update(
        self,
        project_id: str,
        sample: Dict[str, Any],
        exclude_client_id: Optional[str] = None
    ):
        subscribers = self.project_subscribers.get(project_id, set())
        if not subscribers:
            return

        for subscriber_id in subscribers:
            if exclude_client_id and subscriber_id == exclude_client_id:
                continue
            message_id = f"gps_push_{int(datetime.now().timestamp() * 1000)}_{subscriber_id}"
            message = {
                "type": "gps_sample_update",
                "message_id": message_id,
                "project_id": project_id,
                "data": {
                    "sample": sample
                },
                "timestamp": datetime.now().isoformat()
            }
            await self.register_pending_message(subscriber_id, message_id, message)
            await self.send_personal_message(message, subscriber_id)

    async def notify_workflow_update(
        self,
        workflow_id: str,
        event: str,
        update: Dict[str, Any],
        run_id: Optional[str] = None,
    ):
        subscribers = self.workflow_subscribers.get(workflow_id, set())
        if not subscribers:
            return

        message = {
            "type": "workflow_update",
            "event": event,
            "workflow_id": workflow_id,
            "run_id": run_id,
            "data": update,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for subscriber_id in subscribers:
            await self.send_personal_message(message, subscriber_id)

    async def notify_workflow_run_update(
        self,
        run_id: str,
        event: str,
        update: Dict[str, Any],
        workflow_id: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ):
        targets = set(self.workflow_run_subscribers.get(run_id, set()))
        if workflow_id:
            targets.update(self.workflow_subscribers.get(workflow_id, set()))
        if not targets:
            return

        message = {
            "type": "workflow_run_update",
            "event": event,
            "run_id": run_id,
            "workflow_id": workflow_id,
            "data": update,
            "snapshot": snapshot or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for subscriber_id in targets:
            await self.send_personal_message(message, subscriber_id)

    async def notify_workflow_cursor_update(
        self,
        workflow_id: str,
        cursor: Dict[str, Any],
        exclude_client_id: Optional[str] = None,
    ):
        subscribers = self.workflow_subscribers.get(workflow_id, set())
        if not subscribers:
            return

        message = {
            "type": "collaboration_cursor_update",
            "workflow_id": workflow_id,
            "cursor": cursor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for subscriber_id in subscribers:
            if exclude_client_id and subscriber_id == exclude_client_id:
                continue
            await self.send_personal_message(message, subscriber_id)

    def dispatch_workflow_update(
        self,
        workflow_id: str,
        event: str,
        update: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> None:
        self._dispatch(
            self.notify_workflow_update(
                workflow_id=workflow_id,
                event=event,
                update=update,
                run_id=run_id,
            )
        )

    def dispatch_workflow_run_update(
        self,
        run_id: str,
        event: str,
        update: Dict[str, Any],
        workflow_id: Optional[str] = None,
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._dispatch(
            self.notify_workflow_run_update(
                run_id=run_id,
                event=event,
                update=update,
                workflow_id=workflow_id,
                snapshot=snapshot,
            )
        )

    def _dispatch(self, coroutine: Any) -> None:
        loop = self._loop
        if loop and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(coroutine, loop)
                return
            except Exception:
                pass

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop and running_loop.is_running():
            try:
                running_loop.create_task(coroutine)
                return
            except Exception:
                pass

        try:
            asyncio.run(coroutine)
        except Exception:
            try:
                coroutine.close()
            except Exception:
                pass

    def _ensure_heartbeat_task(self) -> None:
        if self._heartbeat_task and not self._heartbeat_task.done():
            return
        if not self._loop or not self._loop.is_running():
            return
        self._heartbeat_task = self._loop.create_task(self._heartbeat_loop())

    def _restore_subscriptions(self, client_id: str, state: Dict[str, Any]) -> None:
        try:
            expire_at = datetime.fromisoformat(str(state.get("expire_at")))
        except Exception:
            return
        if expire_at < self._now():
            return
        subscriptions = state.get("subscriptions") or {}
        for task_id in subscriptions.get("tasks") or []:
            self.task_subscribers.setdefault(str(task_id), set()).add(client_id)
        for project_id in subscriptions.get("projects") or []:
            self.project_subscribers.setdefault(str(project_id), set()).add(client_id)
        for workflow_id in subscriptions.get("workflows") or []:
            self.workflow_subscribers.setdefault(str(workflow_id), set()).add(client_id)
        for run_id in subscriptions.get("workflow_runs") or []:
            self.workflow_run_subscribers.setdefault(str(run_id), set()).add(client_id)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL_SECONDS)
            now = self._now()

            for client_id in list(self.disconnected_states.keys()):
                state = self.disconnected_states.get(client_id) or {}
                try:
                    expire_at = datetime.fromisoformat(str(state.get("expire_at")))
                except Exception:
                    self.disconnected_states.pop(client_id, None)
                    continue
                if expire_at < now:
                    self.disconnected_states.pop(client_id, None)
                    self.pending_messages.pop(client_id, None)
                    self.offline_message_queue.pop(client_id, None)

            for client_id, state in list(self.client_states.items()):
                heartbeat_at = state.get("last_heartbeat_at")
                if not isinstance(heartbeat_at, datetime):
                    continue
                if (now - heartbeat_at).total_seconds() > self.HEARTBEAT_TIMEOUT_SECONDS:
                    websocket = self.active_connections.get(client_id)
                    if websocket and hasattr(websocket, "close"):
                        try:
                            await websocket.close(code=1011)
                        except Exception:
                            pass
                    self.disconnect(client_id)
                    continue
                await self.send_personal_message(
                    self.build_message("heartbeat", data={"interval": self.HEARTBEAT_INTERVAL_SECONDS}),
                    client_id,
                )


# 全局 WebSocket 服务实例
websocket_service = WebSocketService()
