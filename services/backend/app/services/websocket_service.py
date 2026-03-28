from fastapi import WebSocket
from typing import Any, Dict, Optional, Set
from datetime import datetime


class WebSocketService:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.task_subscribers: Dict[str, Set[str]] = {}
        self.project_subscribers: Dict[str, Set[str]] = {}
        self.pending_messages: Dict[str, Dict[str, Dict[str, Any]]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.pending_messages.setdefault(client_id, {})
        print(f"客户端 {client_id} 已连接")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.pending_messages:
            del self.pending_messages[client_id]
        # 从所有任务订阅中移除
        for task_id, subscribers in self.task_subscribers.items():
            if client_id in subscribers:
                subscribers.remove(client_id)
        for project_id, subscribers in self.project_subscribers.items():
            if client_id in subscribers:
                subscribers.remove(client_id)
        print(f"客户端 {client_id} 已断开")

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(message)
            except Exception:
                self.disconnect(client_id)

    async def broadcast(self, message: dict):
        for client_id in list(self.active_connections.keys()):
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


# 全局 WebSocket 服务实例
websocket_service = WebSocketService()
