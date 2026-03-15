from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
from datetime import datetime


class WebSocketService:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.task_subscribers: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"客户端 {client_id} 已连接")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        # 从所有任务订阅中移除
        for task_id, subscribers in self.task_subscribers.items():
            if client_id in subscribers:
                subscribers.remove(client_id)
        print(f"客户端 {client_id} 已断开")

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

    async def subscribe_to_task(self, client_id: str, task_id: str):
        if task_id not in self.task_subscribers:
            self.task_subscribers[task_id] = set()
        self.task_subscribers[task_id].add(client_id)

    async def unsubscribe_from_task(self, client_id: str, task_id: str):
        if task_id in self.task_subscribers:
            self.task_subscribers[task_id].discard(client_id)

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


# 全局 WebSocket 服务实例
websocket_service = WebSocketService()