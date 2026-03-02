"""
后端功能测试脚本
"""
import requests
import json
import time
import numpy as np

BASE_URL = "http://localhost:8000"

def generate_test_data():
    """生成测试数据"""
    np.random.seed(42)

    # 生成50个随机点
    n_points = 50
    x = np.random.uniform(0, 100, n_points)
    y = np.random.uniform(0, 100, n_points)

    # 生成带有空间相关性的值
    values = 50 + 10 * np.sin(x / 10) + 5 * np.cos(y / 10) + np.random.normal(0, 2, n_points)

    # 构建GeoJSON
    features = []
    for i in range(n_points):
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(x[i]), float(y[i])]
            },
            "properties": {
                "value": float(values[i])
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    return geojson

def test_health_check():
    """测试健康检查"""
    print("\n=== 测试健康检查 ===")
    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    return response.status_code == 200

def test_upload_data():
    """测试数据上传"""
    print("\n=== 测试数据上传 ===")

    # 生成测试数据
    geojson = generate_test_data()

    # 保存到临时文件
    with open("/tmp/test_data.geojson", "w") as f:
        json.dump(geojson, f)

    # 上传
    with open("/tmp/test_data.geojson", "rb") as f:
        files = {"file": ("test_data.geojson", f, "application/json")}
        response = requests.post(f"{BASE_URL}/api/upload-data", files=files)

    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"数据ID: {result.get('data_id')}")
    print(f"点数: {result.get('point_count')}")
    print(f"边界: {result.get('bounds')}")

    return result.get('data_id')

def test_recommend_parameters(data_id):
    """测试参数推荐"""
    print("\n=== 测试参数推荐 ===")

    payload = {
        "data_id": data_id,
        "enable_auto_model": True
    }

    response = requests.post(f"{BASE_URL}/api/recommend-parameters", json=payload)
    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"推荐变异函数: {result['recommended_variogram_model']}")
        print(f"推荐方法: {result['recommended_method']}")
        print(f"推荐分辨率: {result['recommended_grid_resolution']}")
        print(f"是否有趋势: {result['has_trend']}")
        print(f"模型评分: {result['model_scores']}")
        return result
    else:
        print(f"错误: {response.text}")
        return None

def test_start_kriging(data_id, params):
    """测试启动克里金任务"""
    print("\n=== 测试启动克里金任务 ===")

    payload = {
        "data_id": data_id,
        "variogram_model": params['recommended_variogram_model'],
        "method": params['recommended_method'],
        "grid_resolution": params['recommended_grid_resolution'],
        "nlags": params['recommended_nlags'],
        "enable_cross_validation": True,
        "n_folds": 5
    }

    response = requests.post(f"{BASE_URL}/api/start-kriging", json=payload)
    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"任务ID: {result['task_id']}")
        print(f"状态: {result['status']}")
        return result['task_id']
    else:
        print(f"错误: {response.text}")
        return None

def test_task_status(task_id):
    """测试任务状态查询"""
    print("\n=== 测试任务状态查询 ===")

    max_attempts = 30
    for i in range(max_attempts):
        response = requests.get(f"{BASE_URL}/api/task-status/{task_id}")

        if response.status_code == 200:
            result = response.json()
            print(f"[{i+1}/{max_attempts}] 状态: {result['status']}, 进度: {result['progress']:.1f}%")

            if result['status'] == 'completed':
                print("✓ 任务完成!")
                return True
            elif result['status'] == 'failed':
                print(f"✗ 任务失败: {result.get('error')}")
                return False

        time.sleep(2)

    print("✗ 任务超时")
    return False

def test_get_results(task_id):
    """测试结果查询"""
    print("\n=== 测试结果查询 ===")

    # 查询预测结果
    response = requests.get(f"{BASE_URL}/api/result/prediction/{task_id}")
    if response.status_code == 200:
        result = response.json()
        print(f"预测结果URL: {result['geotiff_url']}")
        print(f"预测统计: {result['statistics']}")
    else:
        print(f"预测结果查询失败: {response.text}")

    # 查询方差结果
    response = requests.get(f"{BASE_URL}/api/result/variance/{task_id}")
    if response.status_code == 200:
        result = response.json()
        print(f"方差结果URL: {result['geotiff_url']}")
        print(f"方差统计: {result['statistics']}")
    else:
        print(f"方差结果查询失败: {response.text}")

def main():
    """主测试流程"""
    print("=" * 60)
    print("克里金插值后端服务测试")
    print("=" * 60)

    try:
        # 1. 健康检查
        if not test_health_check():
            print("✗ 健康检查失败，请确保服务已启动")
            return

        # 2. 上传数据
        data_id = test_upload_data()
        if not data_id:
            print("✗ 数据上传失败")
            return

        # 3. 参数推荐
        params = test_recommend_parameters(data_id)
        if not params:
            print("✗ 参数推荐失败")
            return

        # 4. 启动任务
        task_id = test_start_kriging(data_id, params)
        if not task_id:
            print("✗ 任务启动失败")
            return

        # 5. 查询状态
        if not test_task_status(task_id):
            print("✗ 任务执行失败")
            return

        # 6. 获取结果
        test_get_results(task_id)

        print("\n" + "=" * 60)
        print("✓ 所有测试通过!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n✗ 无法连接到服务器，请确保后端服务已启动:")
        print("  cd backend && python run.py")
    except Exception as e:
        print(f"\n✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
