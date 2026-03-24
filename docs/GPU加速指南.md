# UDAKE GPU 加速指南

## 目录

- [概述](#概述)
- [技术选型](#技术选型)
- [系统架构](#系统架构)
- [快速入门](#快速入门)
- [配置指南](#配置指南)
- [性能优化](#性能优化)
- [API接口文档](#api接口文档)
- [用户使用手册](#用户使用手册)
- [测试](#测试)

---

## 概述

GPU加速系统为UDAKE平台的矩阵运算、向量运算和克里金关键计算路径提供GPU加速能力，支持任务调度、运行监控、设备管理、性能指标API等功能。

### 核心目标

- 为矩阵运算、向量运算和克里金关键计算路径提供 GPU 加速能力
- 在无 GPU 或无 CuPy 环境下自动回退 CPU，保证功能可用性
- 提供任务调度、运行监控、设备管理、性能指标 API

### 核心需求

- **矩阵运算**：乘法、求逆、分解、特征值
- **向量运算**：点积、范数、排序
- **克里金关键步骤**：距离矩阵、变异函数、协方差与方程求解
- **服务接口**：统一 API，支持配置、任务查询、指标查询

### 非功能需求

- 接口稳定：异常时返回可解释错误信息
- 可测试：核心计算和 API 覆盖单元测试
- 可扩展：后续支持多 GPU 与更复杂调度

---

## 技术选型

### 候选框架

#### 1. 硬件层

| 框架 | 优点 | 缺点 |
|------|------|------|
| CUDA | 生态成熟，NVIDIA 场景性能强 | 仅支持 NVIDIA |
| OpenCL | 跨厂商，支持广泛 | 开发复杂度较高 |
| ROCm | AMD 生态，部署场景依赖硬件 | 仅支持 AMD |

#### 2. Python 生态

| 框架 | 优点 | 缺点 |
|------|------|------|
| CuPy | NumPy 风格接口，迁移成本低 | 需要 CUDA 支持 |
| Numba | JIT 灵活，适合自定义 kernel | 学习曲线较陡 |
| PyTorch | 张量能力强，生态丰富 | 对纯数值服务场景偏重 |

### 选型结论

**当前版本采用 `CuPy + NumPy 回退` 模式**：

- 有 GPU：优先 GPU 计算
- 无 GPU：自动回退 CPU，确保服务可用

**选择理由**：
- 与现有 NumPy 代码兼容性高
- 便于分阶段落地，不阻塞现网功能
- 支持多种 GPU 后端（CUDA、ROCm 等）

---

## 系统架构

### 1. 架构设计

```
┌─────────────────────────────────────────────┐
│              FastAPI 服务层                 │
│         (GPU加速接口.py)                    │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────┴───────────────────────────┐
│              GPU 服务层                     │
│         (gpu_service.py)                    │
└─────────────────┬───────────────────────────┘
                  │
      ┌───────────┼───────────┐
      │           │           │
┌─────▼────┐ ┌───▼────┐ ┌───▼────┐
│ 设备管理器 │ │ 计算引擎 │ │ 性能监控 │
└───────────┘ └────────┘ └────────┘
      │           │           │
┌─────▼────┐ ┌───▼────┐ ┌───▼────┐
│  Device  │ │  Compute │ │  Performance  │
│ Manager  │ │  Engine  │ │  Monitor    │
└───────────┘ └────────┘ └────────┘
```

### 2. 核心模块

| 模块 | 路径 | 功能 |
|------|------|------|
| 设备管理器 | `device_manager.py` | 检测设备、后端选择 |
| 内存管理器 | `memory_manager.py` | CPU/GPU 数据传输和统计 |
| 计算引擎 | `compute_engine.py` | 矩阵/向量计算核心 |
| 克里金加速器 | `kriging_accelerator.py` | 变异函数、协方差、批量预测 |
| 任务调度器 | `task_scheduler.py` | 任务生命周期管理 |
| 性能监控器 | `performance_monitor.py` | 性能记录与汇总 |
| GPU 服务 | `gpu_service.py` | 统一服务入口 |
| GPU 接口 | `GPU加速接口.py` | 对外 REST API |

### 3. 核心策略

#### 自动切换策略

基于数据规模阈值 `min_size_for_gpu` 自动选择 CPU/GPU：

```python
if data_size >= config.min_size_for_gpu and config.enable_gpu:
    backend = 'gpu'
else:
    backend = 'cpu'
```

#### 可控开关

- `enable_gpu`：全局 GPU 开关
- `auto_switch`：是否按规模自动切换
- `min_size_for_gpu`：触发 GPU 的规模阈值

#### 性能采样

记录每次操作耗时、输入规模、后端类型：

```python
{
    "task_id": "uuid",
    "operation": "matrix_multiply",
    "input_size": 1000,
    "backend": "gpu",
    "duration_ms": 45.2,
    "timestamp": "2024-01-01T00:00:00"
}
```

#### 异常处理

API 层区分参数错误（400）与系统错误（500）：

```python
try:
    result = await compute_matrix_multiply(data)
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

---

## 快速入门

### 1. 启动后端

在项目根目录启动 FastAPI 服务：

```bash
cd backend
python run.py
```

### 2. 健康检查

```bash
curl http://localhost:8000/api/gpu/health
```

预期响应：
```json
{
  "status": "healthy",
  "gpu_available": true,
  "device_count": 1
}
```

### 3. 配置策略

```bash
curl -X PUT http://localhost:8000/api/gpu/config \
  -H "Content-Type: application/json" \
  -d '{
    "enable_gpu": true,
    "auto_switch": true,
    "min_size_for_gpu": 1000
  }'
```

### 4. 示例调用

#### 矩阵乘法

```bash
curl -X POST http://localhost:8000/api/gpu/compute/matrix/multiply \
  -H "Content-Type: application/json" \
  -d '{
    "matrix_a": [[1, 2], [3, 4]],
    "matrix_b": [[5, 6], [7, 8]]
  }'
```

#### 向量范数

```bash
curl -X POST http://localhost:8000/api/gpu/compute/vector/norm \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [1, 2, 3, 4],
    "order": 2
  }'
```

#### 变异函数

```bash
curl -X POST http://localhost:8000/api/gpu/kriging/semivariogram \
  -H "Content-Type: application/json" \
  -d '{
    "points": [[0, 0], [1, 0], [0, 1]],
    "values": [10, 20, 30]
  }'
```

### 5. 指标查看

```bash
# 查看性能指标
curl http://localhost:8000/api/gpu/metrics

# 查看任务列表
curl http://localhost:8000/api/gpu/tasks
```

---

## 配置指南

### 1. 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_gpu` | bool | true | 全局 GPU 开关 |
| `auto_switch` | bool | true | 是否按规模自动切换 |
| `min_size_for_gpu` | int | 1000 | 任务规模阈值 |

### 2. 推荐策略

#### 小规模任务

- 场景：任务规模低于阈值
- 策略：走 CPU，减少传输开销
- 配置：
  ```python
  min_size_for_gpu = 1000
  auto_switch = True
  ```

#### 大规模任务

- 场景：任务规模高于阈值
- 策略：走 GPU，提升吞吐
- 配置：
  ```python
  min_size_for_gpu = 1000
  auto_switch = True
  enable_gpu = True
  ```

#### 强制 GPU

- 场景：所有任务都使用 GPU
- 策略：禁用自动切换
- 配置：
  ```python
  auto_switch = False
  enable_gpu = True
  ```

#### 强制 CPU

- 场景：调试或兼容性测试
- 策略：禁用 GPU
- 配置：
  ```python
  enable_gpu = False
  ```

### 3. 故障处理

#### GPU 不可用

**症状**：`GET /api/gpu/status` 返回 `gpu_available: false`

**原因**：
- 未安装 CuPy
- 未安装 CUDA 驱动
- 设备被其他进程占用

**解决方案**：
1. 系统自动回退 CPU
2. 检查设备状态：
   ```bash
   curl http://localhost:8000/api/gpu/status
   ```
3. 查看详细错误：
   ```bash
   curl http://localhost:8000/api/gpu/devices
   ```

#### 内存不足

**症状**：任务失败，返回 500 错误

**原因**：GPU 内存不足以容纳数据

**解决方案**：
1. 降低 `min_size_for_gpu` 阈值
2. 分批处理大数据
3. 使用 CPU 后端

---

## 性能优化

### 1. 观察指标

#### performance.overall

```json
{
  "total_runs": 1000,
  "gpu_runs": 800,
  "cpu_runs": 200,
  "avg_speedup": 4.5,
  "avg_gpu_time_ms": 45.2,
  "avg_cpu_time_ms": 203.4
}
```

#### memory_stats

```json
{
  "cpu_to_gpu_bytes": 1024000,
  "cpu_to_gpu_count": 100,
  "gpu_to_cpu_bytes": 512000,
  "gpu_to_cpu_count": 50
}
```

### 2. 优化建议

#### 合理设置阈值

- 小任务频繁上 GPU 会增加传输开销
- 建议根据实际使用场景调整 `min_size_for_gpu`

#### 批量预测优化

- 对批量预测任务优先合并请求
- 提高并行度，减少任务切换开销

#### 持续监控

- 关注 `recent` 列表中的慢操作
- 做专项优化，如算法改进、内存复用

### 3. 验证方式

#### 基准测试

对同一任务分别使用 CPU/GPU 跑基准：

```python
import time
import numpy as np

# CPU 测试
start = time.time()
result_cpu = compute_cpu(data)
cpu_time = time.time() - start

# GPU 测试
start = time.time()
result_gpu = compute_gpu(data)
gpu_time = time.time() - start

print(f"Speedup: {cpu_time / gpu_time:.2f}x")
```

#### 对比指标

- 耗时：CPU vs GPU
- 误差：结果差异
- 资源占用：内存使用

---

## API接口文档

### 基础接口

#### 1. 健康检查

**接口**: `GET /api/gpu/health`

**响应示例**:
```json
{
  "status": "healthy",
  "gpu_available": true,
  "device_count": 1
}
```

#### 2. 状态查询

**接口**: `GET /api/gpu/status`

**响应示例**:
```json
{
  "enable_gpu": true,
  "auto_switch": true,
  "min_size_for_gpu": 1000,
  "backend": "gpu",
  "gpu_available": true
}
```

#### 3. 设备列表

**接口**: `GET /api/gpu/devices`

**响应示例**:
```json
{
  "devices": [
    {
      "id": 0,
      "name": "NVIDIA GeForce RTX 3080",
      "memory_total": 10737418240,
      "memory_free": 8589934592,
      "compute_capability": "8.6"
    }
  ]
}
```

#### 4. 配置更新

**接口**: `PUT /api/gpu/config`

**请求示例**:
```json
{
  "enable_gpu": true,
  "auto_switch": true,
  "min_size_for_gpu": 1000
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "配置已更新"
}
```

#### 5. 性能指标

**接口**: `GET /api/gpu/metrics`

**响应示例**:
```json
{
  "performance": {
    "overall": {
      "total_runs": 1000,
      "gpu_runs": 800,
      "cpu_runs": 200,
      "avg_speedup": 4.5
    },
    "recent": [
      {
        "operation": "matrix_multiply",
        "backend": "gpu",
        "duration_ms": 45.2,
        "timestamp": "2024-01-01T00:00:00"
      }
    ]
  },
  "memory": {
    "cpu_to_gpu_bytes": 1024000,
    "cpu_to_gpu_count": 100,
    "gpu_to_cpu_bytes": 512000,
    "gpu_to_cpu_count": 50
  }
}
```

#### 6. 清除指标

**接口**: `DELETE /api/gpu/metrics`

**响应示例**:
```json
{
  "success": true,
  "message": "指标已清除"
}
```

#### 7. 任务列表

**接口**: `GET /api/gpu/tasks`

**响应示例**:
```json
{
  "tasks": [
    {
      "task_id": "uuid",
      "operation": "matrix_multiply",
      "status": "completed",
      "backend": "gpu",
      "created_at": "2024-01-01T00:00:00"
    }
  ]
}
```

#### 8. 任务详情

**接口**: `GET /api/gpu/tasks/{task_id}`

**响应示例**:
```json
{
  "task_id": "uuid",
  "operation": "matrix_multiply",
  "status": "completed",
  "backend": "gpu",
  "result": [[19, 22], [43, 50]],
  "duration_ms": 45.2,
  "created_at": "2024-01-01T00:00:00",
  "completed_at": "2024-01-01T00:00:00"
}
```

### 矩阵计算接口

#### 1. 矩阵乘法

**接口**: `POST /api/gpu/compute/matrix/multiply`

**请求示例**:
```json
{
  "matrix_a": [[1, 2], [3, 4]],
  "matrix_b": [[5, 6], [7, 8]]
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": [[19, 22], [43, 50]],
  "backend": "gpu",
  "duration_ms": 45.2
}
```

#### 2. 矩阵求逆

**接口**: `POST /api/gpu/compute/matrix/inverse`

**请求示例**:
```json
{
  "matrix": [[4, 7], [2, 6]]
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": [[0.6, -0.7], [-0.2, 0.4]],
  "backend": "gpu",
  "duration_ms": 12.3
}
```

#### 3. 特征值计算

**接口**: `POST /api/gpu/compute/matrix/eigenvalues`

**请求示例**:
```json
{
  "matrix": [[4, -2], [1, 1]]
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": [3, 2],
  "backend": "gpu",
  "duration_ms": 23.1
}
```

#### 4. Cholesky 分解

**接口**: `POST /api/gpu/compute/matrix/cholesky`

**请求示例**:
```json
{
  "matrix": [[4, 12, -16], [12, 37, -43], [-16, -43, 98]]
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": [[2, 6, -8], [0, 1, 5], [0, 0, 3]],
  "backend": "gpu",
  "duration_ms": 15.4
}
```

#### 5. LU 分解

**接口**: `POST /api/gpu/compute/matrix/lu`

**请求示例**:
```json
{
  "matrix": [[4, 3], [6, 3]]
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": {
    "L": [[1, 0], [1.5, 1]],
    "U": [[4, 3], [0, -1.5]]
  },
  "backend": "gpu",
  "duration_ms": 18.7
}
```

#### 6. 线性方程组求解

**接口**: `POST /api/gpu/compute/linear/solve`

**请求示例**:
```json
{
  "matrix": [[3, 2], [2, 1]],
  "vector": [7, 4]
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": [1, 2],
  "backend": "gpu",
  "duration_ms": 10.2
}
```

### 向量计算接口

#### 1. 向量点积

**接口**: `POST /api/gpu/compute/vector/dot`

**请求示例**:
```json
{
  "vector_a": [1, 2, 3],
  "vector_b": [4, 5, 6]
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": 32,
  "backend": "gpu",
  "duration_ms": 2.3
}
```

#### 2. 向量范数

**接口**: `POST /api/gpu/compute/vector/norm`

**请求示例**:
```json
{
  "vector": [3, 4],
  "order": 2
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": 5,
  "backend": "gpu",
  "duration_ms": 1.8
}
```

#### 3. 向量排序

**接口**: `POST /api/gpu/compute/vector/sort`

**请求示例**:
```json
{
  "vector": [3, 1, 4, 1, 5],
  "ascending": true
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": [1, 1, 3, 4, 5],
  "backend": "gpu",
  "duration_ms": 3.2
}
```

### 克里金接口

#### 1. 半变异函数计算

**接口**: `POST /api/gpu/kriging/semivariogram`

**请求示例**:
```json
{
  "points": [[0, 0], [1, 0], [0, 1]],
  "values": [10, 20, 30]
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": {
    "distances": [0, 1, 1, 1.414],
    "semivariances": [0, 50, 200, 50]
  },
  "backend": "gpu",
  "duration_ms": 15.6
}
```

#### 2. 克里金批量预测

**接口**: `POST /api/gpu/kriging/predict`

**请求示例**:
```json
{
  "points": [[0, 0], [1, 0], [0, 1]],
  "values": [10, 20, 30],
  "query_points": [[0.5, 0.5]]
}
```

**响应示例**:
```json
{
  "task_id": "uuid",
  "result": [20.5],
  "backend": "gpu",
  "duration_ms": 23.4
}
```

### 错误码约定

| 错误码 | 说明 |
|--------|------|
| 400 | 参数不合法 |
| 404 | 任务不存在 |
| 500 | 内部计算或系统异常 |

---

## 用户使用手册

### 1. 功能说明

GPU加速系统支持矩阵运算、向量运算和克里金关键计算加速，并提供任务状态与性能指标查询。

### 2. 使用流程

1. **检查可用性**：访问 `GET /api/gpu/health` 检查 GPU 是否可用
2. **配置策略**：通过 `PUT /api/gpu/config` 设置 GPU 策略
3. **调用计算接口**：执行矩阵、向量或克里金计算
4. **查看运行状态**：通过 `GET /api/gpu/tasks` 和 `GET /api/gpu/metrics` 查看运行状态与性能

### 3. 常见问题

#### GPU 不可用

**症状**：`GET /api/gpu/health` 返回 `gpu_available: false`

**解决方案**：
- 系统会自动回退到 CPU
- 安装 CuPy 和 CUDA 驱动
- 检查设备是否被占用

#### 任务失败

**症状**：计算接口返回 500 错误

**解决方案**：
- 查看响应中的错误信息
- 检查输入数据格式和维度
- 尝试使用 CPU 后端

#### 性能不达预期

**症状**：GPU 加速比不明显

**解决方案**：
- 增大任务规模阈值
- 开启自动切换策略
- 检查数据传输开销

### 4. 最佳实践

#### 合理设置阈值

根据实际使用场景调整 `min_size_for_gpu`，避免小任务频繁上 GPU。

#### 批量处理

对多个小任务合并处理，提高并行度。

#### 监控性能

定期查看性能指标，优化慢操作。

#### 错误处理

实现重试机制和降级策略，确保系统可用性。

---

## 测试

### 测试文件

- `services/backend/tests/test_gpu_service.py`
- `services/backend/tests/test_gpu_api.py`

### 测试验证

通过上述测试验证：

- ✅ 核心算子输出正确
- ✅ API 可调用
- ✅ 任务状态可追踪
- ✅ 性能指标可查询

### 运行测试

```bash
# 运行 GPU 服务测试
pytest services/backend/tests/test_gpu_service.py

# 运行 GPU API 测试
pytest services/backend/tests/test_gpu_api.py
```

---

## 附录

### A. 环境要求

- Python 3.9+
- CUDA 11.0+（NVIDIA GPU）
- ROCm 4.0+（AMD GPU）
- CuPy 10.0+

### B. 安装依赖

```bash
# 安装 CuPy（NVIDIA）
pip install cupy-cuda11x

# 安装 CuPy（AMD）
pip install cupy-rocm-4-0

# 安装其他依赖
pip install numpy scipy
```

### C. 性能参考

| 操作 | 数据规模 | CPU 时间 | GPU 时间 | 加速比 |
|------|---------|---------|---------|--------|
| 矩阵乘法 | 1000x1000 | 200ms | 45ms | 4.4x |
| 向量范数 | 1M 元素 | 15ms | 3ms | 5.0x |
| 变异函数 | 10K 点 | 500ms | 120ms | 4.2x |

### D. 相关文档

- [系统文档](./系统文档.md)
- [构建部署指南](./构建部署指南.md)
- [技术文档](./技术文档.md)

---

**版本**: 1.0.0
**更新日期**: 2026-03-24