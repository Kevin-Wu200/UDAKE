"""过期任务性能测试脚本（压测前请在隔离环境执行）。"""

import time

from services.backend.app.scheduler.tasks import run_expiry_check_task


def test_key_expiry_task_under_5_minutes():
    start = time.time()
    result = run_expiry_check_task()
    duration = time.time() - start
    assert result["status"] in {"success", "failed"}
    assert duration < 300
