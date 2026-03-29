# 分布式计算 API 与测试指南

本文档说明分布式计算模块的接口调用方式、测试入口与生产前压力测试流程。

## 1. 运行前准备

1. 创建并激活虚拟环境（如未创建）：
```bash
python3 -m venv venv
source venv/bin/activate
```
2. 安装依赖：
```bash
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install pytest locust
```
3. 启动后端服务（示例）：
```bash
cd services/backend
./../../venv/bin/python run.py
```

## 2. 核心 API 示例

基础前缀：`/api/distributed`

### 2.1 提交任务

```bash
curl -X POST http://127.0.0.1:8000/api/distributed/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "map_reduce_sum",
    "payload": {"values": [1,2,3,4,5], "chunk_size": 2},
    "priority": 1,
    "max_retries": 1,
    "retry_delay_seconds": 0
  }'
```

### 2.2 查询任务

```bash
curl http://127.0.0.1:8000/api/distributed/tasks/<task_id>
```

### 2.3 注册节点与心跳

```bash
curl -X POST http://127.0.0.1:8000/api/distributed/nodes/register \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "worker-1",
    "cpu_capacity": 8,
    "memory_capacity_mb": 16384,
    "labels": {"zone": "cn-east"}
  }'

curl -X POST http://127.0.0.1:8000/api/distributed/nodes/heartbeat \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "worker-1",
    "cpu_used": 0.35,
    "memory_used": 0.42
  }'
```

### 2.4 检查点与恢复

```bash
curl -X POST http://127.0.0.1:8000/api/distributed/tasks/<task_id>/checkpoint
curl -X POST "http://127.0.0.1:8000/api/distributed/tasks/<task_id>/recover?checkpoint_id=<checkpoint_id>"
```

### 2.5 监控与运维

```bash
curl http://127.0.0.1:8000/api/distributed/overview
curl http://127.0.0.1:8000/api/distributed/metrics
curl http://127.0.0.1:8000/api/distributed/scale-suggestion
curl -X POST http://127.0.0.1:8000/api/distributed/backup
curl -X POST http://127.0.0.1:8000/api/distributed/restore
curl "http://127.0.0.1:8000/api/distributed/events?limit=100"
```

## 3. 自动化测试入口

### 3.1 分布式专项测试（推荐）

```bash
./scripts/run_distributed_compute_tests.sh
```

该命令会执行：
1. `test_distributed_compute_service.py`（单元测试）
2. `test_distributed_compute_api.py`（API 集成测试）
3. `benchmark_distributed_compute.py`（性能基准）

### 3.2 完整后端单元测试套件

```bash
./scripts/run_distributed_compute_tests.sh --full-backend
```

## 4. 生产前压力测试建议

建议在预发布环境执行以下压力测试流程：

1. 启动后端服务并确认健康检查通过。  
2. 执行 Locust 压测：
```bash
locust -f services/backend/tests/performance/locust_distributed_compute.py \
  --host http://127.0.0.1:8000
```
3. 压测建议参数：
   - 并发用户：30 -> 100 阶梯递增
   - 预热时间：2 分钟
   - 稳态压测：10 分钟
4. 观察指标：
   - `/api/distributed/metrics` 中成功率是否持续 >= 99%
   - 平均响应时间与 P95 是否在可接受范围
   - 是否出现大量重试、失败或队列积压

## 5. 新增测试文件

- `services/backend/tests/test_distributed_compute_service.py`
- `services/backend/tests/test_distributed_compute_api.py`
- `services/backend/tests/performance/benchmark_distributed_compute.py`
- `services/backend/tests/performance/locust_distributed_compute.py`
- `scripts/run_distributed_compute_tests.sh`
