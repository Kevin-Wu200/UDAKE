#!/usr/bin/env python3
"""
前后端API通讯测试脚本
测试所有API端点的通讯状态
"""

import requests
import json
from typing import Dict, Any, List
from datetime import datetime

# 配置
BASE_URL = "http://172.20.10.2:8000"
FRONTEND_URL = "http://172.20.10.2:5173"

# 测试结果存储
test_results: List[Dict[str, Any]] = []

def log_test(endpoint: str, method: str, status: str, response_time: float, error: str = None, response_data: Any = None):
    """记录测试结果"""
    result = {
        "endpoint": endpoint,
        "method": method,
        "status": status,
        "response_time": response_time,
        "error": error,
        "response_data": response_data,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    status_icon = "✓" if status == "success" else "✗"
    print(f"{status_icon} {method} {endpoint} - {status} ({response_time:.2f}s)")
    if error:
        print(f"  错误: {error}")

def test_endpoint(endpoint: str, method: str = "GET", data: Any = None, params: Dict = None) -> bool:
    """测试单个API端点"""
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}

    try:
        start_time = datetime.now()
        if method == "GET":
            response = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=10)
        elif method == "DELETE":
            response = requests.delete(url, timeout=10)
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")

        response_time = (datetime.now() - start_time).total_seconds()

        if response.status_code == 200:
            try:
                response_data = response.json()
            except:
                response_data = response.text
            log_test(endpoint, method, "success", response_time, response_data=response_data)
            return True
        else:
            log_test(endpoint, method, f"failed ({response.status_code})", response_time, error=response.text)
            return False

    except requests.exceptions.Timeout:
        log_test(endpoint, method, "timeout", 10.0, error="请求超时")
        return False
    except requests.exceptions.ConnectionError:
        log_test(endpoint, method, "connection_error", 0.0, error="连接失败")
        return False
    except Exception as e:
        log_test(endpoint, method, "error", 0.0, error=str(e))
        return False

def main():
    """主测试函数"""
    print("=" * 80)
    print("前后端API通讯测试")
    print(f"后端地址: {BASE_URL}")
    print(f"前端地址: {FRONTEND_URL}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # 1. 基础健康检查
    print("【1. 基础健康检查】")
    test_endpoint("/", "GET")
    test_endpoint("/health", "GET")
    print()

    # 2. 核心插值接口
    print("【2. 核心插值接口】")
    test_endpoint("/api/upload-data", "POST", data={"test": "data"})  # 这会失败，但可以测试端点是否存在
    test_endpoint("/api/start-kriging", "POST", data={"test": "data"})
    test_endpoint("/api/task-status/test-task-id", "GET")
    test_endpoint("/api/result/prediction/test-task-id", "GET")
    test_endpoint("/api/result/variance/test-task-id", "GET")
    test_endpoint("/api/result/report/test-task-id", "GET")
    test_endpoint("/api/result/download/test-task-id/test-file.geojson", "GET")
    print()

    # 3. 采样影响评估接口
    print("【3. 采样影响评估接口】")
    test_endpoint("/api/sampling-impact/evaluate-candidates", "POST", data={"test": "data"})
    test_endpoint("/api/sampling-impact/preview-effect", "POST", data={"test": "data"})
    test_endpoint("/api/sampling-impact/recommend-optimal", "POST", data={"test": "data"})
    test_endpoint("/api/sampling-impact/batch-simulate", "POST", data={"test": "data"})
    print()

    # 4. 实时插值系统接口
    print("【4. 实时插值系统接口】")
    test_endpoint("/api/subscriptions", "POST", data={"test": "data"})
    test_endpoint("/api/subscriptions/test-sub-id", "GET")
    test_endpoint("/api/subscriptions/test-sub-id", "DELETE")
    test_endpoint("/api/subscriptions/test-sub-id/data-points", "POST", data={"test": "data"})
    test_endpoint("/api/subscriptions/test-sub-id/prediction", "GET", params={"x": 0, "y": 0})
    print()

    # 5. 多目标优化系统接口
    print("【5. 多目标优化系统接口】")
    test_endpoint("/api/multi-objective/optimize", "POST", data={"test": "data"})
    test_endpoint("/api/multi-objective/tasks/test-task-id", "GET")
    test_endpoint("/api/multi-objective/tasks/test-task-id/results", "GET")
    print()

    # 6. 其他接口
    print("【6. 其他接口】")
    test_endpoint("/api/interpolation", "POST", data={"test": "data"})
    test_endpoint("/api/interpolation/test-id", "GET")
    test_endpoint("/api/sampling", "POST", data={"test": "data"})
    test_endpoint("/api/analysis", "POST", data={"test": "data"})
    test_endpoint("/api/analysis/test-id/report", "GET")
    test_endpoint("/api/export", "POST", data={"test": "data"})
    test_endpoint("/api/import/parse", "POST", data={"test": "data"})
    test_endpoint("/api/import", "POST", data={"test": "data"})
    print()

    # 生成测试报告
    print("=" * 80)
    print("测试报告摘要")
    print("=" * 80)

    total_tests = len(test_results)
    successful_tests = len([r for r in test_results if r["status"] == "success"])
    failed_tests = total_tests - successful_tests

    print(f"总测试数: {total_tests}")
    print(f"成功: {successful_tests}")
    print(f"失败: {failed_tests}")
    print(f"成功率: {(successful_tests/total_tests*100):.1f}%")
    print()

    # 列出失败的测试
    if failed_tests > 0:
        print("失败的测试:")
        for result in test_results:
            if result["status"] != "success":
                print(f"  - {result['method']} {result['endpoint']}: {result['error']}")
        print()

    # 保存详细测试结果
    with open("/Users/wuchenkai/UDAKE/api_test_results.json", "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)

    print(f"详细测试结果已保存到: /Users/wuchenkai/UDAKE/api_test_results.json")

if __name__ == "__main__":
    main()