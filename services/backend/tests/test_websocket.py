"""
WebSocket 服务测试
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.websocket_service import websocket_service


@pytest.fixture(autouse=True)
def reset_websocket_service_state():
    websocket_service.active_connections.clear()
    websocket_service.client_states.clear()
    websocket_service.task_subscribers.clear()
    websocket_service.project_subscribers.clear()
    websocket_service.workflow_subscribers.clear()
    websocket_service.workflow_run_subscribers.clear()
    websocket_service.user_connections.clear()
    websocket_service.pending_messages.clear()
    websocket_service.offline_message_queue.clear()
    websocket_service.disconnected_states.clear()
    websocket_service.operation_logs.clear()
    websocket_service.operation_seq_index.clear()
    websocket_service.operation_conflicts.clear()
    websocket_service.cursor_cache.clear()
    websocket_service.comment_cache.clear()
    websocket_service.notification_cache.clear()
    websocket_service.notification_dedup_cache.clear()
    websocket_service.share_access_stats.clear()
    yield
    task = websocket_service._heartbeat_task
    if task and not task.done():
        task.cancel()
    websocket_service._heartbeat_task = None


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


@pytest.mark.asyncio
async def test_websocket_collaboration_operation_message():
    client = TestClient(app)
    with client.websocket_connect("/ws/op_sender") as sender, client.websocket_connect("/ws/op_listener") as listener:
        sender.send_json({'type': 'subscribe_workflow', 'workflow_id': 'wf_op_1'})
        listener.send_json({'type': 'subscribe_workflow', 'workflow_id': 'wf_op_1'})
        sender.receive_json()
        listener.receive_json()

        sender.send_json({
            'type': 'collaboration_operation',
            'workflow_id': 'wf_op_1',
            'user_id': 'u_1',
            'operation_type': 'update',
            'operation_data': {'target_id': 'node_1', 'value': 1},
            'sequence': 1
        })

        broadcast = listener.receive_json()
        ack = sender.receive_json()
        assert broadcast['type'] == 'collaboration_operation'
        assert broadcast['data']['operation_type'] == 'update'
        assert ack['type'] == 'ack'
        assert ack['data']['workflow_id'] == 'wf_op_1'


@pytest.mark.asyncio
async def test_websocket_cursor_update_throttle():
    client = TestClient(app)
    with client.websocket_connect("/ws/cursor_sender") as sender, client.websocket_connect("/ws/cursor_listener") as listener:
        sender.send_json({'type': 'subscribe_workflow', 'workflow_id': 'wf_cursor_1'})
        listener.send_json({'type': 'subscribe_workflow', 'workflow_id': 'wf_cursor_1'})
        sender.receive_json()
        listener.receive_json()

        sender.send_json({
            'type': 'cursor_update',
            'workflow_id': 'wf_cursor_1',
            'user_id': 'user_cursor',
            'cursor_position': {'x': 10, 'y': 20, 'selection': []},
            'color': '#ff0000'
        })
        listener.receive_json()
        ack1 = sender.receive_json()
        assert ack1['type'] == 'ack'
        assert ack1['data']['throttled'] is False

        sender.send_json({
            'type': 'cursor_update',
            'workflow_id': 'wf_cursor_1',
            'user_id': 'user_cursor',
            'cursor_position': {'x': 10, 'y': 20, 'selection': []},
            'color': '#ff0000'
        })
        ack2 = sender.receive_json()
        assert ack2['type'] == 'ack'
        assert ack2['data']['throttled'] is True


@pytest.mark.asyncio
async def test_websocket_comment_created_mention():
    client = TestClient(app)
    with client.websocket_connect("/ws/mention_client?user_id=alice") as mention_ws, client.websocket_connect("/ws/comment_client?user_id=bob") as comment_ws:
        mention_ws.send_json({'type': 'subscribe_workflow', 'workflow_id': 'wf_comment_1'})
        comment_ws.send_json({'type': 'subscribe_workflow', 'workflow_id': 'wf_comment_1'})
        mention_ws.receive_json()
        comment_ws.receive_json()

        comment_ws.send_json({
            'type': 'comment_created',
            'workflow_id': 'wf_comment_1',
            'comment_id': 'cmt_1',
            'user_id': 'bob',
            'content': '@alice 请确认这个改动',
            'parent_id': ''
        })

        mention_msgs = [mention_ws.receive_json(), mention_ws.receive_json()]
        comment_side_msgs = [comment_ws.receive_json(), comment_ws.receive_json()]
        assert any(msg.get('type') == 'ack' for msg in comment_side_msgs)
        assert any(msg.get('type') == 'notification' for msg in mention_msgs)


@pytest.mark.asyncio
async def test_websocket_share_access_stats():
    client = TestClient(app)
    with client.websocket_connect("/ws/share_client") as ws:
        ws.send_json({'type': 'subscribe_workflow', 'workflow_id': 'wf_share_1'})
        ws.receive_json()
        ws.send_json({
            'type': 'share_access',
            'share_token': 'shr_token_1',
            'workflow_id': 'wf_share_1',
            'visitor_id': 'visitor_1',
            'access_time': '2026-04-01T08:00:00+00:00',
            'access_type': 'view'
        })
        broadcast = ws.receive_json()
        ack = ws.receive_json()
        assert broadcast['type'] == 'share_access'
        assert ack['type'] == 'ack'
        assert ack['data']['access_count'] == 1
        assert ack['data']['unique_visitors'] == 1
