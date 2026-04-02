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

## 2. API 基础 URL 与环境变量配置

建议统一通过环境变量配置 API 地址，避免在脚本和代码中硬编码域名。

本项目推荐变量：

- `VITE_API_BASE_URL`：前端与脚本统一使用的 API 根地址（建议不带 `/api`）。
- `VITE_API_URL`：兼容历史配置（可包含 `/api`）。
- `OFFICIAL_WEB`：官网域名（用于文档/社区/更新链接）。
- `ADMIN_WEB`：后台域名（用于管理端入口）。

示例（Linux/macOS）：

```bash
export VITE_API_BASE_URL=http://127.0.0.1:8000
export OFFICIAL_WEB=https://test.udake.xyz
export ADMIN_WEB=https://admin-test.udake.xyz
export API_BASE_URL="${VITE_API_BASE_URL%/}/api/distributed"
```

示例（Windows PowerShell）：

```powershell
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000"
$env:OFFICIAL_WEB = "https://test.udake.xyz"
$env:ADMIN_WEB = "https://admin-test.udake.xyz"
$env:API_BASE_URL = "$($env:VITE_API_BASE_URL.TrimEnd('/'))/api/distributed"
```

## 3. 核心 API 示例

基础前缀：`${API_BASE_URL}`（默认等价于 `http://127.0.0.1:8000/api/distributed`）

### 3.1 提交任务

```bash
curl -X POST ${API_BASE_URL}/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "map_reduce_sum",
    "payload": {"values": [1,2,3,4,5], "chunk_size": 2},
    "priority": 1,
    "max_retries": 1,
    "retry_delay_seconds": 0
  }'
```

### 3.2 查询任务

```bash
curl ${API_BASE_URL}/tasks/<task_id>
```

### 3.3 注册节点与心跳

```bash
curl -X POST ${API_BASE_URL}/nodes/register \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "worker-1",
    "cpu_capacity": 8,
    "memory_capacity_mb": 16384,
    "labels": {"zone": "cn-east"}
  }'

curl -X POST ${API_BASE_URL}/nodes/heartbeat \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "worker-1",
    "cpu_used": 0.35,
    "memory_used": 0.42
  }'
```

### 3.4 检查点与恢复

```bash
curl -X POST ${API_BASE_URL}/tasks/<task_id>/checkpoint
curl -X POST "${API_BASE_URL}/tasks/<task_id>/recover?checkpoint_id=<checkpoint_id>"
```

### 3.5 监控与运维

```bash
curl ${API_BASE_URL}/overview
curl ${API_BASE_URL}/metrics
curl ${API_BASE_URL}/scale-suggestion
curl -X POST ${API_BASE_URL}/backup
curl -X POST ${API_BASE_URL}/restore
curl "${API_BASE_URL}/events?limit=100"
```

## 4. 自动化测试入口

### 4.1 分布式专项测试（推荐）

```bash
./scripts/run_distributed_compute_tests.sh
```

该命令会执行：
1. `test_distributed_compute_service.py`（单元测试）
2. `test_distributed_compute_api.py`（API 集成测试）
3. `benchmark_distributed_compute.py`（性能基准）

### 4.2 完整后端单元测试套件

```bash
./scripts/run_distributed_compute_tests.sh --full-backend
```

## 5. 生产前压力测试建议

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
   - `${API_BASE_URL}/metrics` 中成功率是否持续 >= 99%
   - 平均响应时间与 P95 是否在可接受范围
   - 是否出现大量重试、失败或队列积压

## 6. 相关代码示例（前端）

```typescript
const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
const distributedBase = `${apiBase}/api/distributed`;
const response = await fetch(`${distributedBase}/overview`);
```

## 7. 新增测试文件

- `services/backend/tests/test_distributed_compute_service.py`
- `services/backend/tests/test_distributed_compute_api.py`
- `services/backend/tests/performance/benchmark_distributed_compute.py`
- `services/backend/tests/performance/locust_distributed_compute.py`
- `scripts/run_distributed_compute_tests.sh`
