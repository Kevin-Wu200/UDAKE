"""
WebSocket 服务测试
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.websocket_service import websocket_service


@pytest.mark.asyncio
async def test_websocket_connection():
    """测试 WebSocket 连接"""
    client = TestClient(app)

    with client.websocket_connect("/ws/test_client") as websocket:
        # 发送订阅消息
        websocket.send_json({
            'type': 'subscribe_task',
            'task_id': 'test_task_1'
        })

        # 接收确认
        data = websocket.receive_json()
        assert data['type'] == 'subscription_confirmed'
        assert data['task_id'] == 'test_task_1'


@pytest.mark.asyncio
async def test_websocket_ping_pong():
    """测试 WebSocket 心跳"""
    client = TestClient(app)

    with client.websocket_connect("/ws/test_client") as websocket:
        # 发送 ping
        websocket.send_json({
            'type': 'ping'
        })

        # 接收 pong
        data = websocket.receive_json()
        assert data['type'] == 'pong'
        assert 'timestamp' in data


@pytest.mark.asyncio
async def test_websocket_unsubscribe():
    """测试 WebSocket 取消订阅"""
    client = TestClient(app)

    with client.websocket_connect("/ws/test_client") as websocket:
        # 订阅任务
        websocket.send_json({
            'type': 'subscribe_task',
            'task_id': 'test_task_1'
        })

        # 接收确认
        data = websocket.receive_json()
        assert data['type'] == 'subscription_confirmed'

        # 取消订阅
        websocket.send_json({
            'type': 'unsubscribe_task',
            'task_id': 'test_task_1'
        })

        # 接收确认
        data = websocket.receive_json()
        assert data['type'] == 'unsubscription_confirmed'
        assert data['task_id'] == 'test_task_1'


@pytest.mark.asyncio
async def test_websocket_subscribe_workflow():
    """测试工作流订阅消息"""
    client = TestClient(app)

    with client.websocket_connect("/ws/test_client") as websocket:
        websocket.send_json({
            'type': 'subscribe_workflow',
            'workflow_id': 'wf_test_1'
        })

        data = websocket.receive_json()
        assert data['type'] == 'subscription_confirmed'
        assert data['workflow_id'] == 'wf_test_1'


@pytest.mark.asyncio
async def test_websocket_service_connect():
    """测试 WebSocket 服务连接"""
    from fastapi import WebSocket

    # 创建模拟 WebSocket
    class MockWebSocket:
        async def accept(self):
            self.accepted = True

        async def send_json(self, message):
            self.messages = getattr(self, 'messages', [])
            self.messages.append(message)

    mock_ws = MockWebSocket()
    await websocket_service.connect(mock_ws, 'test_client_1')

    assert mock_ws.accepted
    assert 'test_client_1' in websocket_service.active_connections


@pytest.mark.asyncio
async def test_websocket_service_disconnect():
    """测试 WebSocket 服务断开"""
    from fastapi import WebSocket

    class MockWebSocket:
        async def accept(self):
            self.accepted = True

        async def send_json(self, message):
            self.messages = getattr(self, 'messages', [])
            self.messages.append(message)

    mock_ws = MockWebSocket()
    await websocket_service.connect(mock_ws, 'test_client_1')

    # 断开连接
    websocket_service.disconnect('test_client_1')

    assert 'test_client_1' not in websocket_service.active_connections


@pytest.mark.asyncio
async def test_websocket_service_subscribe_task():
    """测试任务订阅"""
    await websocket_service.subscribe_to_task('test_client_1', 'test_task_1')

    assert 'test_task_1' in websocket_service.task_subscribers
    assert 'test_client_1' in websocket_service.task_subscribers['test_task_1']


@pytest.mark.asyncio
async def test_websocket_service_unsubscribe_task():
    """测试取消任务订阅"""
    await websocket_service.subscribe_to_task('test_client_1', 'test_task_1')
    await websocket_service.unsubscribe_from_task('test_client_1', 'test_task_1')

    assert 'test_client_1' not in websocket_service.task_subscribers['test_task_1']


@pytest.mark.asyncio
async def test_websocket_service_send_personal_message():
    """测试发送个人消息"""
    from fastapi import WebSocket

    class MockWebSocket:
        async def accept(self):
            self.accepted = True

        async def send_json(self, message):
            self.messages = getattr(self, 'messages', [])
            self.messages.append(message)

    mock_ws = MockWebSocket()
    await websocket_service.connect(mock_ws, 'test_client_1')

    # 发送消息
    test_message = {'type': 'test', 'data': 'test_data'}
    await websocket_service.send_personal_message(test_message, 'test_client_1')

    # 检查消息是否发送
    assert len(mock_ws.messages) == 1
    assert mock_ws.messages[0] == test_message


@pytest.mark.asyncio
async def test_websocket_service_notify_task_update():
    """测试任务更新通知"""
    from fastapi import WebSocket

    class MockWebSocket:
        async def accept(self):
            self.accepted = True

        async def send_json(self, message):
            self.messages = getattr(self, 'messages', [])
            self.messages.append(message)

    # 创建客户端并订阅任务
    mock_ws = MockWebSocket()
    await websocket_service.connect(mock_ws, 'test_client_1')
    await websocket_service.subscribe_to_task('test_client_1', 'test_task_1')

    # 发送任务更新
    update_data = {
        'status': 'running',
        'progress': 50
    }
    await websocket_service.notify_task_update('test_task_1', update_data)

    # 检查消息是否发送
    assert len(mock_ws.messages) == 1
    assert mock_ws.messages[0]['type'] == 'task_update'
    assert mock_ws.messages[0]['task_id'] == 'test_task_1'
    assert mock_ws.messages[0]['data'] == update_data


@pytest.mark.asyncio
async def test_websocket_service_notify_workflow_run_update():
    """测试工作流运行推送"""
    class MockWebSocket:
        async def accept(self):
            self.accepted = True

        async def send_json(self, message):
            self.messages = getattr(self, 'messages', [])
            self.messages.append(message)

    mock_ws = MockWebSocket()
    await websocket_service.connect(mock_ws, 'test_workflow_client_1')
    await websocket_service.subscribe_to_workflow_run('test_workflow_client_1', 'run_1')

    await websocket_service.notify_workflow_run_update(
        run_id='run_1',
        event='progress_update',
        update={'progress': 66.7},
        workflow_id='wf_1',
        snapshot={'status': 'running', 'progress': 66.7},
    )

    assert len(mock_ws.messages) == 1
    assert mock_ws.messages[0]['type'] == 'workflow_run_update'
    assert mock_ws.messages[0]['event'] == 'progress_update'
    assert mock_ws.messages[0]['run_id'] == 'run_1'
    assert mock_ws.messages[0]['workflow_id'] == 'wf_1'
    assert mock_ws.messages[0]['data']['progress'] == 66.7
    assert mock_ws.messages[0]['snapshot']['status'] == 'running'
