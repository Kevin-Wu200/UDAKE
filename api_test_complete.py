#!/usr/bin/env python3
"""
完整的API测试脚本
使用真实数据测试完整的工作流：上传数据 → 插值 → 查询结果 → 采样建议
"""

import requests
import json
from typing import Dict, Any, List
from datetime import datetime
import base64
import os

# 配置（TEST_* 优先，其次使用运行环境配置）
BASE_URL = (
    os.getenv("TEST_BACKEND_URL")
    or os.getenv("BACKEND_URL")
    or os.getenv("VITE_API_BASE_URL")
    or "http://localhost:8000"
).rstrip("/")
FRONTEND_URL = (
    os.getenv("TEST_FRONTEND_URL")
    or os.getenv("FRONTEND_URL")
    or "http://localhost:5173"
).rstrip("/")

# 测试结果存储
test_results: List[Dict[str, Any]] = []
task_id = None
subscription_id = None
optimization_task_id = None

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
    if response_data and isinstance(response_data, dict):
        print(f"  响应: {json.dumps(response_data, ensure_ascii=False, indent=2)[:200]}...")

def test_endpoint(endpoint: str, method: str = "GET", data: Any = None, params: Dict = None, files: Dict = None) -> bool:
    """测试单个API端点"""
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}

    try:
        start_time = datetime.now()
        if method == "GET":
            response = requests.get(url, params=params, timeout=30)
        elif method == "POST":
            if files:
                response = requests.post(url, files=files, timeout=30)
            else:
                response = requests.post(url, json=data, headers=headers, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, timeout=30)
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")

        response_time = (datetime.now() - start_time).total_seconds()

        if response.status_code in [200, 201]:
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
        log_test(endpoint, method, "timeout", 30.0, error="请求超时")
        return False
    except requests.exceptions.ConnectionError:
        log_test(endpoint, method, "connection_error", 0.0, error="连接失败")
        return False
    except Exception as e:
        log_test(endpoint, method, "error", 0.0, error=str(e))
        return False

def main():
    """主测试函数"""
    global task_id, subscription_id, optimization_task_id

    print("=" * 80)
    print("完整的API工作流测试")
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

    # 2. 上传GeoJSON数据
    print("【2. 上传GeoJSON数据】")
    data_file_path = "/Users/wuchenkai/UDAKE/data_samples/示例数据.geojson"
    if os.path.exists(data_file_path):
        with open(data_file_path, 'rb') as f:
            files = {'file': ('示例数据.geojson', f, 'application/geo+json')}
            if test_endpoint("/api/upload-data", "POST", files=files):
                # 注意：这里需要根据实际API响应提取task_id
                # 假设响应中包含task_id
                # task_id = response_data.get('task_id')
                pass
    else:
        print(f"✗ 数据文件不存在: {data_file_path}")
    print()

    # 3. 测试通用数据处理接口（使用真实数据）
    print("【3. 通用数据处理接口】")

    # 插值请求
    interpolation_data = {
        "points": [
            {"x": 116.4074, "y": 39.9042, "value": 25.5},
            {"x": 116.4174, "y": 39.9142, "value": 28.3},
            {"x": 116.3974, "y": 39.8942, "value": 22.1},
            {"x": 116.4274, "y": 39.9242, "value": 30.2},
        ],
        "parameters": {
            "variogram_model": "spherical",
            "nlags": 6,
            "grid_resolution": 50
        }
    }

    if test_endpoint("/api/interpolation", "POST", data=interpolation_data):
        # 提取插值ID用于后续测试
        last_result = test_results[-1]
        response_data = last_result.get('response_data')
        if response_data:
            # 插值接口返回的是字符串ID
            if isinstance(response_data, str):
                task_id = response_data
            elif isinstance(response_data, dict):
                task_id = response_data.get('id') or 'test-interpolation-id'
            else:
                task_id = 'test-interpolation-id'
            print(f"  创建的任务ID: {task_id}")

    # 查询插值结果
    if task_id:
        test_endpoint(f"/api/interpolation/{task_id}", "GET")

    # 采样请求
    sampling_data = {
        "bounds": {"minX": 116.39, "minY": 39.89, "maxX": 116.43, "maxY": 39.93},
        "existingPoints": interpolation_data["points"],
        "parameters": {
            "n_samples": 10,
            "strategy": "uncertainty_based"
        }
    }
    test_endpoint("/api/sampling", "POST", data=sampling_data)

    # 分析请求
    analysis_data = {
        "grid": [[0.0, 1.0], [1.0, 0.0]],
        "bounds": {"minX": 0.0, "minY": 0.0, "maxX": 1.0, "maxY": 1.0},
        "variance": [[0.1, 0.2], [0.2, 0.1]],
        "parameters": {
            "analysis_type": "uncertainty_analysis"
        }
    }

    if test_endpoint("/api/analysis", "POST", data=analysis_data):
        last_result = test_results[-1]
        if last_result.get('response_data'):
            analysis_id = last_result['response_data'].get('taskId') or 'test-analysis-id'
            test_endpoint(f"/api/analysis/{analysis_id}/report", "GET")
    print()

    # 4. 实时插值系统测试
    print("【4. 实时插值系统测试】")

    # 创建订阅
    subscription_data = {
        "subscription_id": "test-subscription-001",
        "spatial_extent": {
            "minX": 116.39,
            "minY": 39.89,
            "maxX": 116.43,
            "maxY": 39.93
        },
        "parameters": {
            "variogram_model": "spherical"
        }
    }

    if test_endpoint("/api/subscriptions", "POST", data=subscription_data):
        subscription_id = "test-subscription-001"
        test_endpoint(f"/api/subscriptions/{subscription_id}", "GET")

        # 添加数据点
        data_point = {
            "x": 116.4150,
            "y": 39.9100,
            "value": 26.5
        }
        test_endpoint(f"/api/subscriptions/{subscription_id}/data-points", "POST", data=data_point)

        # 查询预测值
        test_endpoint(f"/api/subscriptions/{subscription_id}/prediction", "GET", params={"x": 116.4150, "y": 39.9100})

        # 删除订阅
        test_endpoint(f"/api/subscriptions/{subscription_id}", "DELETE")
    print()

    # 5. 多目标优化系统测试
    print("【5. 多目标优化系统测试】")

    # 创建优化任务
    optimization_data = {
        "variance_grid": [[0.5, 0.6], [0.6, 0.5]],
        "existing_points": [
            {"x": 116.4074, "y": 39.9042},
            {"x": 116.4174, "y": 39.9142}
        ],
        "n_samples": 5,
        "weights": {
            "variance": 0.5,
            "cost": 0.3,
            "accessibility": 0.2
        },
        "constraints": {
            "boundary": {
                "minX": 116.39,
                "minY": 39.89,
                "maxX": 116.43,
                "maxY": 39.93
            },
            "min_distance": 0.01,
            "max_budget": 1000
        }
    }

    if test_endpoint("/api/multi-objective/optimize", "POST", data=optimization_data):
        last_result = test_results[-1]
        if last_result.get('response_data'):
            optimization_task_id = last_result['response_data'].get('task_id') or 'test-optimization-id'
            test_endpoint(f"/api/multi-objective/tasks/{optimization_task_id}", "GET")
            test_endpoint(f"/api/multi-objective/tasks/{optimization_task_id}/results", "GET")
    print()

    # 6. 采样影响评估接口测试
    print("【6. 采样影响评估接口测试】")

    if task_id:
        # 评估候选点
        evaluate_data = {
            "task_id": task_id,
            "candidate_points": [
                {"x": 116.4150, "y": 39.9100, "value": 26.5},
                {"x": 116.4200, "y": 39.9150, "value": 27.0}
            ],
            "strategy": "impact_optimized",
            "grid_resolution": 50
        }
        test_endpoint("/api/sampling-impact/evaluate-candidates", "POST", data=evaluate_data)

        # 预览效果
        preview_data = {
            "task_id": task_id,
            "new_point": {"x": 116.4150, "y": 39.9100, "value": 26.5},
            "grid_resolution": 50
        }
        test_endpoint("/api/sampling-impact/preview-effect", "POST", data=preview_data)

        # 推荐最优点
        recommend_data = {
            "task_id": task_id,
            "n_recommendations": 5,
            "strategy": "impact_optimized"
        }
        test_endpoint("/api/sampling-impact/recommend-optimal", "POST", data=recommend_data)
    print()

    # 7. 导出导入接口测试
    print("【7. 导出导入接口测试】")

    export_data = {
        "taskId": task_id or "test-task",
        "format": "geojson",
        "options": {
            "include_variance": True
        }
    }
    test_endpoint("/api/export", "POST", data=export_data)

    import_data = {
        "format": "geojson",
        "options": {
            "crs": "EPSG:4326"
        }
    }
    test_endpoint("/api/import", "POST", data=import_data)
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

    # 按模块统计
    print("按模块统计:")
    modules = {}
    for result in test_results:
        # 提取模块名（第一个路径段）
        parts = result['endpoint'].split('/')
        if len(parts) > 1:
            module = parts[1] if parts[1] != 'api' else parts[2] if len(parts) > 2 else 'general'
        else:
            module = 'general'

        if module not in modules:
            modules[module] = {'total': 0, 'success': 0}
        modules[module]['total'] += 1
        if result['status'] == 'success':
            modules[module]['success'] += 1

    for module, stats in sorted(modules.items()):
        success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"  {module}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")

    # 保存详细测试结果
    with open("/Users/wuchenkai/UDAKE/api_test_complete_results.json", "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)

    print()
    print(f"详细测试结果已保存到: /Users/wuchenkai/UDAKE/api_test_complete_results.json")

if __name__ == "__main__":
    main()
