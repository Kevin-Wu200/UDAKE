#!/usr/bin/env python3
"""
前后端通讯测试脚本
测试后端API并与前端 http://10.200.3.71:5173/ 进行交互测试
"""

import requests
import json
import time
from typing import Dict, Any, List
from datetime import datetime
import os

# 配置
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://10.200.3.71:5173"
DATA_DIR = "/Users/wuchenkai/UDAKE/data_samples"

# 测试结果
test_results = []
task_ids = []
subscription_ids = []
optimization_task_ids = []
data_ids = []

def log_test(test_name: str, endpoint: str, method: str, status: str, 
             response_time: float, error: str = None, response_data: Any = None):
    """记录测试结果"""
    result = {
        "test_name": test_name,
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
    print(f"{status_icon} {test_name}")
    print(f"   端点: {method} {endpoint}")
    print(f"   状态: {status} ({response_time:.2f}s)")
    if error:
        print(f"   错误: {error}")
    if response_data and isinstance(response_data, dict):
        print(f"   响应: {json.dumps(response_data, ensure_ascii=False, indent=2)[:200]}...")
    print()

def test_endpoint(test_name: str, endpoint: str, method: str = "GET", 
                  data: Any = None, params: Dict = None, files: Dict = None,
                  timeout: int = 30) -> bool:
    """测试单个API端点"""
    url = f"{BACKEND_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}

    try:
        start_time = time.time()
        
        if method == "GET":
            response = requests.get(url, params=params, timeout=timeout)
        elif method == "POST":
            if files:
                response = requests.post(url, files=files, timeout=timeout)
            else:
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
        elif method == "DELETE":
            response = requests.delete(url, timeout=timeout)
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")

        response_time = time.time() - start_time

        if response.status_code in [200, 201, 202]:
            try:
                response_data = response.json()
            except:
                response_data = response.text
            log_test(test_name, endpoint, method, "success", response_time, response_data=response_data)
            return True, response_data
        else:
            log_test(test_name, endpoint, method, f"failed ({response.status_code})", 
                    response_time, error=response.text)
            return False, None

    except requests.exceptions.Timeout:
        log_test(test_name, endpoint, method, "timeout", timeout, error="请求超时")
        return False, None
    except requests.exceptions.ConnectionError as e:
        log_test(test_name, endpoint, method, "connection_error", 0.0, error=f"连接失败: {str(e)}")
        return False, None
    except Exception as e:
        log_test(test_name, endpoint, method, "error", 0.0, error=str(e))
        return False, None

def test_frontend_connection():
    """测试前端连接"""
    print("=" * 80)
    print("【前端连接测试】")
    print("=" * 80)
    
    try:
        response = requests.get(FRONTEND_URL, timeout=10)
        if response.status_code == 200:
            print(f"✓ 前端服务运行正常: {FRONTEND_URL}")
            print(f"   响应大小: {len(response.content)} bytes")
            print()
            return True
        else:
            print(f"✗ 前端服务响应异常: HTTP {response.status_code}")
            print()
            return False
    except Exception as e:
        print(f"✗ 无法连接到前端: {str(e)}")
        print()
        return False

def test_basic_apis():
    """测试基础API接口"""
    print("=" * 80)
    print("【基础API测试】")
    print("=" * 80)
    
    test_endpoint("健康检查", "/health", "GET")
    test_endpoint("API文档", "/docs", "GET")
    test_endpoint("根路径", "/", "GET")

def test_data_upload():
    """测试数据上传"""
    print("=" * 80)
    print("【数据上传测试】")
    print("=" * 80)
    
    # 测试上传GeoJSON文件
    geojson_file = os.path.join(DATA_DIR, "示例数据.geojson")
    if os.path.exists(geojson_file):
        print(f"使用测试文件: {geojson_file}")
        with open(geojson_file, 'rb') as f:
            files = {'file': ('示例数据.geojson', f, 'application/geo+json')}
            success, data = test_endpoint("上传GeoJSON数据", "/api/upload-data", "POST", files=files)
            if success and data:
                data_id = data.get('data_id')
                if data_id:
                    data_ids.append(data_id)
                    print(f"   创建的数据ID: {data_id}")
    else:
        print(f"✗ 测试文件不存在: {geojson_file}")

    # 测试上传test_kriging.geojson
    kriging_file = os.path.join(DATA_DIR, "test_kriging.geojson")
    if os.path.exists(kriging_file):
        print(f"使用测试文件: {kriging_file}")
        with open(kriging_file, 'rb') as f:
            files = {'file': ('test_kriging.geojson', f, 'application/geo+json')}
            success, data = test_endpoint("上传Kriging数据", "/api/upload-data", "POST", files=files)
            if success and data:
                data_id = data.get('data_id')
                if data_id:
                    data_ids.append(data_id)
                    print(f"   创建的数据ID: {data_id}")

def test_interpolation():
    """测试插值功能"""
    print("=" * 80)
    print("【克里金插值测试】")
    print("=" * 80)
    
    # 创建插值任务
    interpolation_data = {
        "points": [
            {"x": 116.4074, "y": 39.9042, "value": 25.5},
            {"x": 116.4174, "y": 39.9142, "value": 28.3},
            {"x": 116.3974, "y": 39.8942, "value": 22.1},
            {"x": 116.4274, "y": 39.9242, "value": 30.2},
            {"x": 116.4124, "y": 39.9092, "value": 26.8},
        ],
        "parameters": {
            "variogram_model": "spherical",
            "nlags": 6,
            "grid_resolution": 50
        }
    }
    
    success, data = test_endpoint("创建插值任务", "/api/interpolation", "POST", data=interpolation_data)
    if success and data:
        if isinstance(data, str):
            task_id = data
        elif isinstance(data, dict):
            task_id = data.get('id') or data.get('task_id')
        else:
            task_id = None
            
        if task_id:
            task_ids.append(task_id)
            print(f"   创建的任务ID: {task_id}")
            
            # 查询插值结果
            test_endpoint("查询插值结果", f"/api/interpolation/{task_id}", "GET")

def test_realtime_interpolation():
    """测试实时插值系统"""
    print("=" * 80)
    print("【实时插值系统测试】")
    print("=" * 80)
    
    # 创建订阅
    subscription_data = {
        "subscription_id": "test-subscription-001",
        "data_type": "generic",
        "spatial_extent": {
            "min_x": 116.39,
            "min_y": 39.89,
            "max_x": 116.43,
            "max_y": 39.93
        },
        "update_frequency": 5,
        "interpolation_params": {
            "variogram_model": "spherical"
        }
    }
    
    success, data = test_endpoint("创建订阅", "/api/subscriptions", "POST", data=subscription_data)
    if success:
        subscription_id = "test-subscription-001"
        subscription_ids.append(subscription_id)
        
        # 查询订阅信息
        test_endpoint("查询订阅信息", f"/api/subscriptions/{subscription_id}", "GET")
        
        # 添加数据点
        data_point = {
            "x": 116.4150,
            "y": 39.9100,
            "value": 26.5
        }
        test_endpoint("添加数据点", f"/api/subscriptions/{subscription_id}/data-points", "POST", data=data_point)
        
        # 查询预测值
        test_endpoint("查询预测值", f"/api/subscriptions/{subscription_id}/prediction", "GET", 
                     params={"x": 116.4150, "y": 39.9100})
        
        # 获取系统状态
        test_endpoint("获取系统状态", "/api/system/status", "GET")
        
        # 获取缓存统计
        test_endpoint("获取缓存统计", "/api/cache/statistics", "GET")

def test_multi_objective_optimization():
    """测试多目标优化系统"""
    print("=" * 80)
    print("【多目标优化系统测试】")
    print("=" * 80)
    
    # 创建优化任务
    optimization_data = {
        "variance_grid": {
            "data": [[0.5, 0.6], [0.6, 0.5]],
            "bounds": {
                "minX": 0.0,
                "minY": 0.0,
                "maxX": 1.0,
                "maxY": 1.0
            },
            "resolution": 0.5
        },
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
    
    success, data = test_endpoint("创建优化任务", "/api/multi-objective/optimize", "POST", data=optimization_data)
    if success and data:
        if isinstance(data, dict):
            task_id = data.get('task_id') or data.get('id')
            if task_id:
                optimization_task_ids.append(task_id)
                print(f"   创建的任务ID: {task_id}")
                
                # 查询任务状态
                test_endpoint("查询优化任务状态", f"/api/multi-objective/tasks/{task_id}", "GET")
                
                # 查询优化结果
                test_endpoint("查询优化结果", f"/api/multi-objective/tasks/{task_id}/results", "GET")

def test_sampling_impact():
    """测试采样影响评估"""
    print("=" * 80)
    print("【采样影响评估测试】")
    print("=" * 80)
    
    if task_ids:
        task_id = task_ids[0]
        
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
        test_endpoint("评估候选点", "/api/sampling-impact/evaluate-candidates", "POST", data=evaluate_data)
        
        # 预览效果
        preview_data = {
            "task_id": task_id,
            "new_point": {"x": 116.4150, "y": 39.9100, "value": 26.5},
            "grid_resolution": 50
        }
        test_endpoint("预览添加效果", "/api/sampling-impact/preview-effect", "POST", data=preview_data)
        
        # 推荐最优点
        recommend_data = {
            "task_id": task_id,
            "n_recommendations": 5,
            "strategy": "impact_optimized"
        }
        test_endpoint("推荐最优采样点", "/api/sampling-impact/recommend-optimal", "POST", data=recommend_data)

def test_advanced_features():
    """测试高级功能"""
    print("=" * 80)
    print("【高级功能测试】")
    print("=" * 80)

    # 测试模型推荐（使用实际上传的数据ID）
    if data_ids:
        test_endpoint("模型推荐", "/api/recommend-parameters", "POST",
                     data={"data_id": data_ids[0], "enable_auto_model": True})
    else:
        print("✗ 模型推荐：没有可用的数据ID")

    # 测试不确定性分级
    test_endpoint("不确定性分级", "/api/uncertainty/classify", "POST",
                 data={"task_id": "test-task", "prediction": [[0.1, 0.2], [0.3, 0.4]], "variance": [[0.1, 0.2], [0.3, 0.4]], "x_coords": [0.0, 1.0], "y_coords": [0.0, 1.0]})

    # 测试风险指数
    test_endpoint("风险指数计算", "/api/risk/calculate", "POST",
                 data={"task_id": "test-task", "prediction": [[0.1, 0.2], [0.3, 0.4]], "variance": [[0.1, 0.2], [0.3, 0.4]], "x_coords": [0.0, 1.0], "y_coords": [0.0, 1.0], "threshold": 0.25})

    # 测试决策阈值
    test_endpoint("设置决策阈值", "/api/decision/thresholds", "POST",
                 data={"task_id": "test-task", "prediction": [[0.1, 0.2], [0.3, 0.4]], "variance": [[0.1, 0.2], [0.3, 0.4]], "x_coords": [0.0, 1.0], "y_coords": [0.0, 1.0], "decision_goal": "最小化风险", "custom_thresholds": [0.1, 0.2, 0.3]})

def generate_report():
    """生成测试报告"""
    print("=" * 80)
    print("【测试报告摘要】")
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
        print("-" * 80)
        for result in test_results:
            if result["status"] != "success":
                print(f"✗ {result['test_name']}")
                print(f"  端点: {result['method']} {result['endpoint']}")
                print(f"  错误: {result['error']}")
                print()
    
    # 统计响应时间
    response_times = [r['response_time'] for r in test_results if r['response_time'] > 0]
    if response_times:
        print("响应时间统计:")
        print(f"  平均: {sum(response_times)/len(response_times):.2f}s")
        print(f"  最快: {min(response_times):.2f}s")
        print(f"  最慢: {max(response_times):.2f}s")
        print()
    
    # 保存详细结果
    report_file = "/Users/wuchenkai/UDAKE/frontend_backend_test_results.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "test_time": datetime.now().isoformat(),
            "backend_url": BACKEND_URL,
            "frontend_url": FRONTEND_URL,
            "summary": {
                "total": total_tests,
                "success": successful_tests,
                "failed": failed_tests,
                "success_rate": f"{(successful_tests/total_tests*100):.1f}%"
            },
            "details": test_results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"详细测试结果已保存到: {report_file}")
    print()
    
    return successful_tests == total_tests

def main():
    """主测试函数"""
    print("=" * 80)
    print("前后端通讯完整测试")
    print(f"后端地址: {BACKEND_URL}")
    print(f"前端地址: {FRONTEND_URL}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()
    
    # 1. 测试前端连接
    frontend_ok = test_frontend_connection()
    
    # 2. 测试基础API
    test_basic_apis()
    
    # 3. 测试数据上传
    test_data_upload()
    
    # 4. 测试插值功能
    test_interpolation()
    
    # 5. 测试实时插值系统
    test_realtime_interpolation()
    
    # 6. 测试多目标优化系统
    test_multi_objective_optimization()
    
    # 7. 测试采样影响评估
    test_sampling_impact()
    
    # 8. 测试高级功能
    test_advanced_features()
    
    # 生成报告
    all_passed = generate_report()
    
    if all_passed:
        print("✓ 所有测试通过！前后端通讯正常。")
    else:
        print("✗ 部分测试失败，请检查上述错误信息。")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)