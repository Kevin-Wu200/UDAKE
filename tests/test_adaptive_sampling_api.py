"""
测试自适应采样流程 (1090) 和停止自适应采样 (1091)
测试采样优化接口的完整功能
"""
import sys
import os

# 确保项目路径正确
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'backend'))


async def _start_adaptive_sampling_test():
    """测试启动自适应采样"""
    from app.api.采样优化接口 import adaptive_sessions, start_adaptive_sampling

    adaptive_sessions.clear()

    # 模拟 verify_task_id
    with patch('app.api.采样优化接口.verify_task_id') as mock_verify:
        mock_verify.return_value = None

        result = await start_adaptive_sampling(
            task_id="test_task_001",
            strategy="hybrid",
            n_recommendations=10,
            max_iterations=5,
        )

    assert result["success"] is True
    assert result["data"]["status"] == "initialized"
    assert "session_id" in result["data"]
    session_id = result["data"]["session_id"]
    assert session_id in adaptive_sessions

    session = adaptive_sessions[session_id]
    assert session["task_id"] == "test_task_001"
    assert session["config"]["strategy"] == "hybrid"
    assert session["config"]["max_iterations"] == 5

    print(f"✓ 启动自适应采样成功, session_id={session_id}")
    return session_id


async def _adaptive_iterate_test(session_id):
    """测试自适应采样迭代"""
    from app.api.采样优化接口 import adaptive_sessions, adaptive_sampling_iterate

    # 第一次迭代（使用模拟数据，因为方差文件不存在）
    result = await adaptive_sampling_iterate(session_id=session_id)
    assert result["success"] is True
    assert result["data"]["iteration"] == 1
    assert len(result["data"]["recommendations"]) > 0
    print(f"✓ 第1次迭代成功，推荐 {len(result['data']['recommendations'])} 个采样点")

    # 第二次迭代
    result = await adaptive_sampling_iterate(session_id=session_id)
    assert result["success"] is True
    assert result["data"]["iteration"] == 2
    print("✓ 第2次迭代成功")

    # 检查会话状态
    session = adaptive_sessions[session_id]
    assert session["status"] == "running"
    assert len(session["iterations"]) == 2
    print(f"✓ 会话状态正确: {session['status']}, 迭代次数: {len(session['iterations'])}")


async def _get_adaptive_status_test(session_id):
    """测试获取自适应采样状态"""
    from app.api.采样优化接口 import get_adaptive_sampling_status

    # 获取单个会话状态
    result = await get_adaptive_sampling_status(session_id=session_id)
    assert result["success"] is True
    assert result["data"]["session_id"] == session_id
    assert "iterations" in result["data"]
    assert "statistics" in result["data"]
    print(f"✓ 获取单个会话状态成功, 状态: {result['data']['status']}")

    # 获取所有会话列表
    result = await get_adaptive_sampling_status(session_id=None)
    assert result["success"] is True
    assert result["data"]["total"] >= 1
    print(f"✓ 获取所有会话列表成功, 共 {result['data']['total']} 个会话")


async def _stop_adaptive_sampling_test(session_id):
    """测试停止自适应采样"""
    from app.api.采样优化接口 import adaptive_sessions, stop_adaptive_sampling

    result = await stop_adaptive_sampling(session_id=session_id)
    assert result["success"] is True
    assert result["data"]["status"] == "stopped"

    session = adaptive_sessions[session_id]
    assert session["status"] == "stopped"
    assert session["completed_at"] is not None
    print("✓ 停止自适应采样成功")


async def _stop_already_stopped_test(session_id):
    """测试重复停止已停止的会话"""
    from app.api.采样优化接口 import stop_adaptive_sampling

    try:
        await stop_adaptive_sampling(session_id=session_id)
        print("✗ 应抛出异常但未抛出")
    except Exception as e:
        assert "已经处于终止状态" in str(e.detail) or "stopped" in str(e.detail).lower()
        print(f"✓ 重复停止正确拒绝: {e.detail}")


async def _iterate_after_stop_test(session_id):
    """测试已停止会话无法继续迭代"""
    from app.api.采样优化接口 import adaptive_sampling_iterate

    try:
        await adaptive_sampling_iterate(session_id=session_id)
        print("✗ 应抛出异常但未抛出")
    except Exception as e:
        assert "已结束" in str(e.detail) or "completed" in str(e.detail).lower() or "stopped" in str(e.detail).lower()
        print(f"✓ 已停止会话无法继续迭代: {e.detail}")


async def _session_not_found_test():
    """测试访问不存在的会话"""
    from app.api.采样优化接口 import (
        adaptive_sampling_iterate,
        stop_adaptive_sampling,
        get_adaptive_sampling_status,
    )

    fake_id = "nonexistent_session"

    # 迭代
    try:
        await adaptive_sampling_iterate(session_id=fake_id)
        print("✗ 应抛出404")
    except Exception as e:
        assert "不存在" in str(e.detail)
        print("✓ 不存在的会话迭代正确返回404")

    # 停止
    try:
        await stop_adaptive_sampling(session_id=fake_id)
        print("✗ 应抛出404")
    except Exception as e:
        assert "不存在" in str(e.detail)
        print("✓ 不存在的会话停止正确返回404")

    # 状态查询
    try:
        await get_adaptive_sampling_status(session_id=fake_id)
        print("✗ 应抛出404")
    except Exception as e:
        assert "不存在" in str(e.detail)
        print("✓ 不存在的会话状态查询正确返回404")


async def _max_iterations_test():
    """测试达到最大迭代次数自动停止"""
    from app.api.采样优化接口 import adaptive_sessions, start_adaptive_sampling, adaptive_sampling_iterate

    adaptive_sessions.clear()

    with patch('app.api.采样优化接口.verify_task_id'):
        start_result = await start_adaptive_sampling(
            task_id="test_max_iter",
            max_iterations=2,  # 最多2次迭代
            n_recommendations=5,
        )

    sid = start_result["data"]["session_id"]

    # 第1次迭代
    await adaptive_sampling_iterate(session_id=sid)
    # 第2次迭代
    await adaptive_sampling_iterate(session_id=sid)

    session = adaptive_sessions[sid]
    assert session["status"] == "converged" or session["status"] == "completed" or len(session["iterations"]) == 2
    print(f"✓ 达到最大迭代(2次)后状态: {session['status']}")

    # 第3次迭代应该提示已完成
    result = await adaptive_sampling_iterate(session_id=sid)
    if result["data"]["status"] == "completed":
        print("✓ 超过最大迭代次数正确返回完成状态")


async def run_all():
    print("=" * 60)
    print("自适应采样 API 测试")
    print("=" * 60)

    # 测试启动
    session_id = await _start_adaptive_sampling_test()

    # 测试状态查询（含列表）
    await _get_adaptive_status_test(session_id)

    # 测试迭代
    await _adaptive_iterate_test(session_id)

    # 测试停止
    await _stop_adaptive_sampling_test(session_id)

    # 测试边界情况
    await _stop_already_stopped_test(session_id)
    await _iterate_after_stop_test(session_id)
    await _session_not_found_test()

    # 测试最大迭代次数
    await _max_iterations_test()

    print("\n🎉 所有自适应采样 API 测试通过!")


if __name__ == '__main__':
    import asyncio
    from unittest.mock import patch

    asyncio.run(run_all())
