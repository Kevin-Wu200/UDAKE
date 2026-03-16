# 多目标优化采样系统 - API接口设计文档

## 1. API概述

### 1.1 基础信息
- **协议**：HTTP/1.1
- **数据格式**：JSON
- **编码**：UTF-8
- **Base URL**：`/api/multi-objective`

### 1.2 通用规范
- 使用RESTful风格
- 所有响应包含标准格式
- 支持异步任务处理
- 支持结果缓存

### 1.3 通用响应格式

```json
{
  "success": true,
  "message": "操作成功",
  "data": {},
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "uuid"
}
```

错误响应格式：

```json
{
  "success": false,
  "message": "错误描述",
  "error_code": "ERROR_CODE",
  "details": {},
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "uuid"
}
```

## 2. API接口列表

### 2.1 优化任务接口

#### 2.1.1 创建优化任务

**接口**：`POST /api/multi-objective/optimize`

**描述**：创建并执行多目标优化任务

**请求头**：
```
Content-Type: application/json
Authorization: Bearer {token}
```

**请求体**：

```json
{
  "variance_grid": {
    "shape": [100, 100],
    "x_coords": [0, 1, 2, ..., 99],
    "y_coords": [0, 1, 2, ..., 99],
    "values": [[0.1, 0.2, ...], ...]
  },
  "existing_points": [
    {"x": 10.5, "y": 20.3},
    {"x": 15.2, "y": 25.7}
  ],
  "n_samples": 20,
  "weights": {
    "variance": 0.5,
    "cost": 0.3,
    "accessibility": 0.2
  },
  "constraints": {
    "boundary": {
      "type": "Polygon",
      "coordinates": [[[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]]]
    },
    "min_distance": 50,
    "budget": 10000
  },
  "algorithm": "NSGA-II",
  "algorithm_params": {
    "population_size": 100,
    "n_generations": 100,
    "crossover_prob": 0.9,
    "mutation_prob": 0.1
  },
  "async": true
}
```

**响应**：

```json
{
  "success": true,
  "message": "优化任务已创建",
  "data": {
    "task_id": "task_1234567890",
    "status": "pending",
    "estimated_time": 8.5,
    "created_at": "2026-03-16T10:00:00Z"
  },
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "req_1234567890"
}
```

**状态码**：
- `201`：任务创建成功
- `400`：请求参数错误
- `401`：未授权
- `500`：服务器错误

#### 2.1.2 查询任务状态

**接口**：`GET /api/multi-objective/tasks/{task_id}/status`

**描述**：查询优化任务状态

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：

```json
{
  "success": true,
  "message": "查询成功",
  "data": {
    "task_id": "task_1234567890",
    "status": "running",
    "progress": 65,
    "current_generation": 65,
    "total_generations": 100,
    "elapsed_time": 5.2,
    "estimated_remaining_time": 2.8,
    "started_at": "2026-03-16T10:00:00Z",
    "updated_at": "2026-03-16T10:05:20Z"
  },
  "timestamp": "2026-03-16T10:05:20Z",
  "request_id": "req_1234567890"
}
```

**状态值**：
- `pending`：等待中
- `running`：运行中
- `completed`：已完成
- `failed`：失败
- `cancelled`：已取消

#### 2.1.3 获取优化结果

**接口**：`GET /api/multi-objective/tasks/{task_id}/results`

**描述**：获取优化任务结果

**请求头**：
```
Authorization: Bearer {token}
```

**查询参数**：
- `format`：返回格式（`detailed` 或 `summary`，默认 `detailed`）

**响应**：

```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "task_id": "task_1234567890",
    "status": "completed",
    "pareto_solutions": [
      {
        "id": 1,
        "objectives": {
          "variance": 0.125,
          "cost": 8500,
          "accessibility": -0.23
        },
        "sampling_points": [
          {"id": 1, "x": 10.5, "y": 20.3, "variance": 0.15},
          {"id": 2, "x": 15.2, "y": 25.7, "variance": 0.12}
        ],
        "metrics": {
          "total_cost": 8500,
          "avg_variance": 0.125,
          "avg_accessibility": 0.23
        }
      }
    ],
    "recommended_solution": {
      "id": 5,
      "objectives": {
        "variance": 0.135,
        "cost": 7200,
        "accessibility": -0.28
      },
      "sampling_points": [...],
      "rank": 1,
      "crowding_distance": 0.45
    },
    "convergence_history": [
      {
        "generation": 0,
        "best_variance": 0.25,
        "best_cost": 12000,
        "best_accessibility": -0.15
      },
      ...
    ],
    "statistics": {
      "n_pareto_solutions": 15,
      "n_evaluations": 10000,
      "total_time": 8.2,
      "convergence_generation": 85
    },
    "completed_at": "2026-03-16T10:08:20Z"
  },
  "timestamp": "2026-03-16T10:08:30Z",
  "request_id": "req_1234567890"
}
```

#### 2.1.4 取消任务

**接口**：`DELETE /api/multi-objective/tasks/{task_id}`

**描述**：取消正在运行的优化任务

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：

```json
{
  "success": true,
  "message": "任务已取消",
  "data": {
    "task_id": "task_1234567890",
    "status": "cancelled",
    "cancelled_at": "2026-03-16T10:05:00Z"
  },
  "timestamp": "2026-03-16T10:05:00Z",
  "request_id": "req_1234567890"
}
```

### 2.2 配置管理接口

#### 2.2.1 获取配置

**接口**：`GET /api/multi-objective/config`

**描述**：获取系统配置

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：

```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "algorithms": {
      "NSGA-II": {
        "name": "Non-dominated Sorting Genetic Algorithm II",
        "description": "基于非支配排序的多目标进化算法",
        "default_params": {
          "population_size": 100,
          "n_generations": 100,
          "crossover_prob": 0.9,
          "mutation_prob": 0.1
        },
        "supported": true
      },
      "MOEA/D": {
        "name": "Multi-Objective Evolutionary Algorithm based on Decomposition",
        "description": "基于分解的多目标进化算法",
        "default_params": {
          "population_size": 100,
          "n_generations": 100,
          "neighborhood_size": 20
        },
        "supported": true
      }
    },
    "objectives": {
      "variance": {
        "name": "方差最小化",
        "description": "最小化插值预测方差",
        "direction": "minimize",
        "default_weight": 0.5
      },
      "cost": {
        "name": "成本最小化",
        "description": "最小化采样总成本",
        "direction": "minimize",
        "default_weight": 0.3
      },
      "accessibility": {
        "name": "可达性最大化",
        "description": "最大化采样点可达性",
        "direction": "maximize",
        "default_weight": 0.2
      }
    },
    "constraints": {
      "boundary": {
        "name": "边界约束",
        "description": "限制采样点在指定边界内",
        "type": "geometry"
      },
      "min_distance": {
        "name": "最小间距约束",
        "description": "限制采样点最小间距",
        "type": "numeric",
        "default_value": 50
      },
      "budget": {
        "name": "预算约束",
        "description": "限制采样总成本",
        "type": "numeric"
      }
    },
    "limits": {
      "max_samples": 1000,
      "max_candidates": 10000,
      "max_generations": 500,
      "max_population_size": 500
    }
  },
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "req_1234567890"
}
```

#### 2.2.2 更新配置

**接口**：`POST /api/multi-objective/config`

**描述**：更新系统配置（需要管理员权限）

**请求头**：
```
Content-Type: application/json
Authorization: Bearer {admin_token}
```

**请求体**：

```json
{
  "algorithms": {
    "NSGA-II": {
      "default_params": {
        "population_size": 150,
        "n_generations": 150
      }
    }
  },
  "limits": {
    "max_samples": 2000
  }
}
```

**响应**：

```json
{
  "success": true,
  "message": "配置已更新",
  "data": {
    "updated_at": "2026-03-16T10:00:00Z"
  },
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "req_1234567890"
}
```

### 2.3 结果导出接口

#### 2.3.1 导出为GeoJSON

**接口**：`GET /api/multi-objective/tasks/{task_id}/export/geojson`

**描述**：导出优化结果为GeoJSON格式

**请求头**：
```
Authorization: Bearer {token}
```

**查询参数**：
- `solution_id`：方案ID（可选，默认为推荐方案）

**响应**：

```json
{
  "success": true,
  "message": "导出成功",
  "data": {
    "type": "FeatureCollection",
    "crs": {
      "type": "name",
      "properties": {"name": "EPSG:4326"}
    },
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Point",
          "coordinates": [10.5, 20.3]
        },
        "properties": {
          "id": 1,
          "variance": 0.15,
          "cost": 425,
          "accessibility": 0.25,
          "solution_id": 5
        }
      }
    ]
  },
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "req_1234567890"
}
```

#### 2.3.2 导出为CSV

**接口**：`GET /api/multi-objective/tasks/{task_id}/export/csv`

**描述**：导出优化结果为CSV格式

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：

```
Content-Type: text/csv
Content-Disposition: attachment; filename="optimization_results_task_1234567890.csv"

id,x,y,variance,cost,accessibility,solution_id
1,10.5,20.3,0.15,425,0.25,5
2,15.2,25.7,0.12,380,0.30,5
```

#### 2.3.3 导出为Excel

**接口**：`GET /api/multi-objective/tasks/{task_id}/export/excel`

**描述**：导出优化结果为Excel格式

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：

```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="optimization_results_task_1234567890.xlsx"

[二进制Excel文件内容]
```

### 2.4 历史任务接口

#### 2.4.1 获取任务列表

**接口**：`GET /api/multi-objective/tasks`

**描述**：获取用户的优化任务列表

**请求头**：
```
Authorization: Bearer {token}
```

**查询参数**：
- `page`：页码（默认1）
- `page_size`：每页数量（默认20）
- `status`：状态过滤（可选）
- `start_date`：开始日期（可选）
- `end_date`：结束日期（可选）

**响应**：

```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "tasks": [
      {
        "task_id": "task_1234567890",
        "status": "completed",
        "n_samples": 20,
        "algorithm": "NSGA-II",
        "created_at": "2026-03-16T10:00:00Z",
        "completed_at": "2026-03-16T10:08:20Z",
        "total_time": 8.2
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 45,
      "total_pages": 3
    }
  },
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "req_1234567890"
}
```

#### 2.4.2 获取任务详情

**接口**：`GET /api/multi-objective/tasks/{task_id}`

**描述**：获取任务详细信息

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：

```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "task_id": "task_1234567890",
    "status": "completed",
    "input_params": {
      "n_samples": 20,
      "weights": {...},
      "constraints": {...}
    },
    "results": {
      "n_pareto_solutions": 15,
      "recommended_solution_id": 5
    },
    "statistics": {
      "total_time": 8.2,
      "n_evaluations": 10000
    },
    "created_at": "2026-03-16T10:00:00Z",
    "completed_at": "2026-03-16T10:08:20Z"
  },
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "req_1234567890"
}
```

### 2.5 模板管理接口

#### 2.5.1 获取模板列表

**接口**：`GET /api/multi-objective/templates`

**描述**：获取优化参数模板列表

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：

```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "templates": [
      {
        "id": "template_1",
        "name": "地质勘探模板",
        "description": "适用于地质勘探场景的优化参数",
        "weights": {
          "variance": 0.6,
          "cost": 0.3,
          "accessibility": 0.1
        },
        "constraints": {
          "min_distance": 100
        },
        "algorithm": "NSGA-II",
        "is_default": true
      }
    ]
  },
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "req_1234567890"
}
```

#### 2.5.2 创建模板

**接口**：`POST /api/multi-objective/templates`

**描述**：创建新的优化参数模板

**请求头**：
```
Content-Type: application/json
Authorization: Bearer {token}
```

**请求体**：

```json
{
  "name": "环境监测模板",
  "description": "适用于环境监测场景",
  "weights": {
    "variance": 0.4,
    "cost": 0.4,
    "accessibility": 0.2
  },
  "constraints": {
    "min_distance": 50
  },
  "algorithm": "NSGA-II"
}
```

**响应**：

```json
{
  "success": true,
  "message": "模板创建成功",
  "data": {
    "template_id": "template_2",
    "created_at": "2026-03-16T10:00:00Z"
  },
  "timestamp": "2026-03-16T10:00:00Z",
  "request_id": "req_1234567890"
}
```

## 3. 数据模型

### 3.1 优化任务模型

```python
class OptimizationTask:
    task_id: str
    user_id: str
    status: str  # pending, running, completed, failed, cancelled
    input_params: dict
    results: dict
    statistics: dict
    created_at: datetime
    started_at: datetime
    completed_at: datetime
    error_message: str
```

### 3.2 方案模型

```python
class Solution:
    id: int
    task_id: str
    objectives: dict
    sampling_points: List[dict]
    rank: int
    crowding_distance: float
    metrics: dict
```

### 3.3 采样点模型

```python
class SamplingPoint:
    id: int
    x: float
    y: float
    variance: float
    cost: float
    accessibility: float
    solution_id: int
```

## 4. 错误码

| 错误码 | 说明 | HTTP状态码 |
|--------|------|-----------|
| INVALID_PARAMS | 请求参数无效 | 400 |
| UNAUTHORIZED | 未授权 | 401 |
| FORBIDDEN | 权限不足 | 403 |
| TASK_NOT_FOUND | 任务不存在 | 404 |
| TASK_ALREADY_COMPLETED | 任务已完成 | 400 |
| TASK_FAILED | 任务执行失败 | 500 |
| CONSTRAINT_VIOLATION | 约束冲突 | 400 |
| RATE_LIMIT_EXCEEDED | 超过速率限制 | 429 |
| INTERNAL_ERROR | 内部服务器错误 | 500 |

## 5. 安全规范

### 5.1 认证授权
- 使用JWT Token认证
- Token有效期：24小时
- 支持Token刷新

### 5.2 输入验证
- 验证所有输入参数
- 防止SQL注入
- 防止XSS攻击

### 5.3 速率限制
- 每用户每分钟最多10个请求
- 管理员每分钟最多100个请求

### 5.4 数据加密
- 传输加密：HTTPS
- 存储加密：敏感数据加密存储

## 6. 性能要求

| 指标 | 要求 |
|-----|------|
| 响应时间 | < 500ms（查询接口） |
| 并发支持 | >= 10个并发任务 |
| 可用性 | >= 99.5% |
| 数据一致性 | 强一致性 |

## 7. 版本历史

| 版本 | 日期 | 作者 | 说明 |
|-----|------|------|------|
| 1.0 | 2026-03-16 | iFlow CLI | 初始版本 |