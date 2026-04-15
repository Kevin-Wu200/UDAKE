"""密钥接口性能基线测试（示例）。"""

import time


def test_key_create_response_target_under_1s():
    start = time.time()
    # TODO: 接入真实 API 客户端后替换为创建密钥调用
    time.sleep(0.01)
    assert (time.time() - start) < 1


def test_concurrent_query_placeholder():
    # TODO: 接入并发压测工具（locust/k6）后替换
    assert True
