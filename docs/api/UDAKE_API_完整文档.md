# UDAKE API 完整文档

## 目录

1. [概述](#概述)
2. [API 版本管理](#api-版本管理)
3. [统一响应格式](#统一响应格式)
4. [错误码说明](#错误码说明)
5. [API 端点列表](#api-端点列表)
6. [调用示例](#调用示例)
7. [调用流程图](#调用流程图)

---

## 概述

UDAKE（Uncertainty-Driven Adaptive Kriging Engine）智能不确定性驱动空间决策平台提供完整的 RESTful API，支持空间插值、不确定性分析、多目标优化、模型融合、深度学习、路径规划等功能。

### 基础信息

- **基础 URL**：`http://localhost:8000`（开发环境）
- **生产 URL**：`https://api.udake.com`（生产环境）
- **当前版本**：`2.0`
- **默认版本**：`1.0`（未传版本时）
- **支持版本**：`1.0`、`2.0`
- **废弃版本**：`1.0`（计划停用日期：`2026-12-31`）

### 技术栈

- **Web 框架**：FastAPI 0.104.1
- **认证方式**：JWT + OAuth2
- **数据格式**：JSON
- **字符编码**：UTF-8

---

## API 版本管理

### 版本策略

UDAKE API 采用语义化版本管理，支持多个版本并存。

#### 版本指定方式

1. **路径版本**：在 URL 中指定版本
   ```
   /api/v1/health
   /api/v2/health
   ```

2. **请求头版本**：通过 `X-API-Version` 请求头指定
   ```bash
   curl -H "X-API-Version: 2.0" http://localhost:8000/api/health
   ```

#### 版本规则

1. `GET /api/v1/...` 自动重写到现有 `/api/...` 路由执行
2. `GET /api/v2/...` 自动重写到现有 `/api/...` 路由执行
3. 若路径版本与请求头版本冲突，返回 `400 invalid_api_version`
4. 若版本不受支持（如 `3.0`），返回 `400 invalid_api_version`

#### 废弃告警

调用 v1 时，响应会携带以下头信息：
- `X-API-Deprecated: true`
- `X-API-Sunset: 2026-12-31`
- `Link: </api/v2>; rel="successor-version"`
- `Warning: 299 - "API v1.0 is deprecated, please migrate to v2.0"`

---

## 统一响应格式

### 成功响应

```json
{
  "success": true,
  "code": "OK",
  "message": "请求成功",
  "data": {},
  "meta": {
    "timestamp": "2026-04-13T02:20:00+00:00",
    "request_id": "2dca9a9e7e1b4fc89f6c2f6c1a75404f",
    "api_version": "2.0",
    "status_code": 200,
    "path": "/api/v2/health"
  }
}
```

### 错误响应

```json
{
  "success": false,
  "code": "VALIDATION_ERROR",
  "message": "请求失败",
  "error": [
    {
      "field": "email",
      "message": "邮箱格式不正确"
    }
  ],
  "meta": {
    "timestamp": "2026-04-13T02:20:00+00:00",
    "request_id": "2dca9a9e7e1b4fc89f6c2f6c1a75404f",
    "api_version": "2.0",
    "status_code": 422,
    "path": "/api/v2/auth/register"
  }
}
```

### 分页响应

```json
{
  "success": true,
  "code": "OK",
  "message": "请求成功",
  "data": {
    "items": [],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
  },
  "meta": {
    "timestamp": "2026-04-13T02:20:00+00:00",
    "request_id": "2dca9a9e7e1b4fc89f6c2f6c1a75404f",
    "api_version": "2.0",
    "status_code": 200,
    "path": "/api/v2/tasks"
  }
}
```

---

## 错误码说明

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 204 | 无内容（删除成功） |
| 400 | 请求参数错误 |
| 401 | 未授权（需要登录） |
| 403 | 禁止访问（权限不足） |
| 404 | 资源不存在 |
| 422 | 参数验证失败 |
| 429 | 请求过于频繁（触发限流） |
| 500 | 服务器内部错误 |

### 业务错误码

| 错误码 | 说明 | HTTP 状态码 |
|--------|------|------------|
| OK | 请求成功 | 200 |
| VALIDATION_ERROR | 请求参数校验失败 | 422 |
| BAD_REQUEST | 业务参数非法 | 400 |
| UNAUTHORIZED | 认证失败 | 401 |
| FORBIDDEN | 无权限 | 403 |
| NOT_FOUND | 资源不存在 | 404 |
| RATE_LIMITED | 触发限流 | 429 |
| INTERNAL_ERROR | 服务内部错误 | 500 |
| TASK_NOT_FOUND | 任务不存在 | 404 |
| TASK_FAILED | 任务执行失败 | 500 |
| MODEL_NOT_FOUND | 模型不存在 | 404 |
| MODEL_TRAINING_FAILED | 模型训练失败 | 500 |
| DATA_INVALID | 数据格式错误 | 400 |
| FILE_TOO_LARGE | 文件过大 | 400 |
| UNSUPPORTED_FORMAT | 不支持的文件格式 | 400 |

---

## API 端点列表

### 1. 认证授权接口（15+个端点）

#### 1.1 用户注册

- **端点**：`POST /api/v2/auth/register`
- **说明**：注册新用户
- **认证**：无需认证
- **请求参数**：
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "注册成功",
    "data": {
      "user_id": "string",
      "username": "string",
      "email": "string",
      "created_at": "2026-04-13T02:20:00+00:00"
    }
  }
  ```

#### 1.2 用户登录

- **端点**：`POST /api/v2/auth/login`
- **说明**：用户登录
- **认证**：无需认证
- **请求参数**：
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "登录成功",
    "data": {
      "access_token": "string",
      "refresh_token": "string",
      "token_type": "bearer",
      "expires_in": 1800
    }
  }
  ```

#### 1.3 用户登出

- **端点**：`POST /api/v2/auth/logout`
- **说明**：用户登出
- **认证**：需要认证
- **请求参数**：无
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "登出成功",
    "data": null
  }
  ```

#### 1.4 刷新令牌

- **端点**：`POST /api/v2/auth/refresh`
- **说明**：刷新访问令牌
- **认证**：需要认证（使用 refresh_token）
- **请求参数**：
  ```json
  {
    "refresh_token": "string"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "令牌刷新成功",
    "data": {
      "access_token": "string",
      "token_type": "bearer",
      "expires_in": 1800
    }
  }
  ```

#### 1.5 获取当前用户信息

- **端点**：`GET /api/v2/auth/me`
- **说明**：获取当前登录用户的信息
- **认证**：需要认证
- **请求参数**：无
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "user_id": "string",
      "username": "string",
      "email": "string",
      "role": "string",
      "created_at": "2026-04-13T02:20:00+00:00",
      "updated_at": "2026-04-13T02:20:00+00:00"
    }
  }
  ```

#### 1.6 修改密码

- **端点**：`POST /api/v2/auth/change-password`
- **说明**：修改当前用户密码
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "old_password": "string",
    "new_password": "string"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "密码修改成功",
    "data": null
  }
  ```

#### 1.7 重置密码

- **端点**：`POST /api/v2/auth/reset-password`
- **说明**：请求重置密码（发送重置邮件）
- **认证**：无需认证
- **请求参数**：
  ```json
  {
    "email": "string"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "重置邮件已发送",
    "data": null
  }
  ```

#### 1.8 验证邮箱

- **端点**：`POST /api/v2/auth/verify-email`
- **说明**：验证用户邮箱
- **认证**：无需认证
- **请求参数**：
  ```json
  {
    "token": "string"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "邮箱验证成功",
    "data": null
  }
  ```

### 2. 数据管理接口（15+个端点）

#### 2.1 上传数据

- **端点**：`POST /api/v2/data/upload`
- **说明**：上传空间数据文件（GeoJSON、CSV、Excel）
- **认证**：需要认证
- **请求参数**：`multipart/form-data`
  - `file`: 文件
  - `data_type`: 数据类型（`geojson`、`csv`、`excel`）
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "上传成功",
    "data": {
      "data_id": "string",
      "filename": "string",
      "file_size": 1024,
      "data_type": "string",
      "point_count": 100,
      "uploaded_at": "2026-04-13T02:20:00+00:00"
    }
  }
  ```

#### 2.2 获取数据列表

- **端点**：`GET /api/v2/data/list`
- **说明**：获取用户上传的数据列表
- **认证**：需要认证
- **请求参数**：Query Parameters
  - `page`: 页码（默认：1）
  - `page_size`: 每页数量（默认：20）
  - `data_type`: 数据类型（可选）
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "items": [
        {
          "data_id": "string",
          "filename": "string",
          "data_type": "string",
          "point_count": 100,
          "uploaded_at": "2026-04-13T02:20:00+00:00"
        }
      ],
      "total": 100,
      "page": 1,
      "page_size": 20,
      "total_pages": 5
    }
  }
  ```

#### 2.3 获取数据详情

- **端点**：`GET /api/v2/data/{data_id}`
- **说明**：获取指定数据的详细信息
- **认证**：需要认证
- **请求参数**：Path Parameters
  - `data_id`: 数据ID
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "data_id": "string",
      "filename": "string",
      "data_type": "string",
      "point_count": 100,
      "bounds": {
        "min_x": 0.0,
        "max_x": 1.0,
        "min_y": 0.0,
        "max_y": 1.0
      },
      "fields": [
        {
          "name": "string",
          "type": "string"
        }
      ],
      "uploaded_at": "2026-04-13T02:20:00+00:00"
    }
  }
  ```

#### 2.4 删除数据

- **端点**：`DELETE /api/v2/data/{data_id}`
- **说明**：删除指定的数据
- **认证**：需要认证
- **请求参数**：Path Parameters
  - `data_id`: 数据ID
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "删除成功",
    "data": null
  }
  ```

#### 2.5 导出数据

- **端点**：`GET /api/v2/data/{data_id}/export`
- **说明**：导出数据为指定格式
- **认证**：需要认证
- **请求参数**：
  - `data_id`: 数据ID（Path Parameter）
  - `format`: 导出格式（Query Parameter：`geojson`、`csv`、`excel`）
- **响应**：文件下载

### 3. 插值计算接口（15+个端点）

#### 3.1 启动插值任务

- **端点**：`POST /api/v2/kriging/start`
- **说明**：启动克里金插值任务
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "data_id": "string",
    "method": "ordinary",
    "variogram_model": "spherical",
    "grid_resolution": 100,
    "nugget": 0.0,
    "sill": 1.0,
    "range": 1.0
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "任务已启动",
    "data": {
      "task_id": "string",
      "status": "pending",
      "created_at": "2026-04-13T02:20:00+00:00"
    }
  }
  ```

#### 3.2 查询任务状态

- **端点**：`GET /api/v2/kriging/status/{task_id}`
- **说明**：查询插值任务状态
- **认证**：需要认证
- **请求参数**：Path Parameters
  - `task_id`: 任务ID
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "查询成功",
    "data": {
      "task_id": "string",
      "status": "running",
      "progress": 50,
      "created_at": "2026-04-13T02:20:00+00:00",
      "started_at": "2026-04-13T02:20:00+00:00"
    }
  }
  ```

#### 3.3 获取插值结果

- **端点**：`GET /api/v2/kriging/result/{task_id}`
- **说明**：获取插值计算结果
- **认证**：需要认证
- **请求参数**：Path Parameters
  - `task_id`: 任务ID
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "task_id": "string",
      "result_path": "string",
      "prediction_grid": "string",
      "variance_grid": "string",
      "rmse": 0.123,
      "mae": 0.098,
      "r2": 0.956
    }
  }
  ```

#### 3.4 取消插值任务

- **端点**：`POST /api/v2/kriging/cancel/{task_id}`
- **说明**：取消插值任务
- **认证**：需要认证
- **请求参数**：Path Parameters
  - `task_id`: 任务ID
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "任务已取消",
    "data": null
  }
  ```

#### 3.5 模型推荐

- **端点**：`POST /api/v2/kriging/recommend`
- **说明**：基于数据特征推荐最优插值模型
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "data_id": "string"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "推荐成功",
    "data": {
      "recommended_method": "ordinary",
      "recommended_variogram": "spherical",
      "recommended_params": {
        "nugget": 0.1,
        "sill": 1.2,
        "range": 0.8
      },
      "confidence": 0.95
    }
  }
  ```

### 4. 采样优化接口（15+个端点）

#### 4.1 获取采样建议

- **端点**：`POST /api/v2/sampling/suggest`
- **说明**：基于插值结果获取采样建议
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "task_id": "string",
    "sample_count": 10
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "suggestions": [
        {
          "location": {
            "x": 0.5,
            "y": 0.5
          },
          "variance_reduction": 0.1,
          "priority": 9
        }
      ]
    }
  }
  ```

#### 4.2 启动自适应采样

- **端点**：`POST /api/v2/sampling/adaptive`
- **说明**：启动自适应采样流程
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "data_id": "string",
    "target_accuracy": 0.95,
    "max_samples": 100
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "自适应采样已启动",
    "data": {
      "task_id": "string",
      "status": "running"
    }
  }
  ```

#### 4.3 评估采样策略

- **端点**：`POST /api/v2/sampling/evaluate`
- **说明**：评估采样策略的效果
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "strategy": "uncertainty_based",
    "parameters": {}
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "评估成功",
    "data": {
      "expected_variance_reduction": 0.25,
      "expected_cost": 1.5,
      "efficiency_score": 0.8
    }
  }
  ```

### 5. 不确定性分析接口（8+个端点）

#### 5.1 不确定性分级

- **端点**：`POST /api/v2/uncertainty/grade`
- **说明**：对插值结果进行不确定性分级
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "task_id": "string",
    "levels": 5
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "分级成功",
    "data": {
      "grades": {
        "level_1": {
          "range": [0, 0.1],
          "area_ratio": 0.2
        },
        "level_2": {
          "range": [0.1, 0.2],
          "area_ratio": 0.3
        }
      }
    }
  }
  ```

#### 5.2 计算风险指数

- **端点**：`POST /api/v2/uncertainty/risk`
- **说明**：计算空间风险指数
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "task_id": "string",
    "threshold": 0.8
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "计算成功",
    "data": {
      "risk_index": 0.65,
      "risk_level": "medium",
      "high_risk_area_ratio": 0.15
    }
  }
  ```

#### 5.3 决策阈值分析

- **端点**：`POST /api/v2/uncertainty/threshold`
- **说明**：推荐最优决策阈值
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "task_id": "string",
    "objective": "maximize_accuracy"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "分析成功",
    "data": {
      "recommended_threshold": 0.85,
      "expected_accuracy": 0.92,
      "confidence": 0.95
    }
  }
  ```

### 6. 深度学习接口（15+个端点）

#### 6.1 训练空间插值模型

- **端点**：`POST /api/v2/dl/spatial/train`
- **说明**：训练空间插值神经网络
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "data_id": "string",
    "model_type": "gnn",
    "epochs": 100,
    "batch_size": 32,
    "learning_rate": 0.001
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "训练已启动",
    "data": {
      "training_id": "string",
      "status": "running"
    }
  }
  ```

#### 6.2 空间插值预测

- **端点**：`POST /api/v2/dl/spatial/predict`
- **说明**：使用训练好的模型进行空间插值预测
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "model_id": "string",
    "queries": [
      {"x": 0.5, "y": 0.5}
    ]
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "预测成功",
    "data": {
      "predictions": [
        {
          "location": {"x": 0.5, "y": 0.5},
          "value": 1.23,
          "uncertainty": 0.05
        }
      ]
    }
  }
  ```

#### 6.3 训练异常检测模型

- **端点**：`POST /api/v2/dl/anomaly/train`
- **说明**：训练异常检测模型
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "data_id": "string",
    "model_type": "vae",
    "epochs": 100
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "训练已启动",
    "data": {
      "training_id": "string",
      "status": "running"
    }
  }
  ```

#### 6.4 检测异常

- **端点**：`POST /api/v2/dl/anomaly/detect`
- **说明**：使用训练好的模型检测异常
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "model_id": "string",
    "data_id": "string"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "检测成功",
    "data": {
      "anomalies": [
        {
          "index": 10,
          "location": {"x": 0.5, "y": 0.5},
          "value": 2.5,
          "anomaly_score": 0.95
        }
      ]
    }
  }
  ```

#### 6.5 通用模型解释

- **端点**：`POST /api/v2/dl/models/explain`
- **说明**：基于模型类型自动分发到异常检测/插值/不确定性/融合/RL 解释能力
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "model_type": "interpolation",
    "model_name": "gnn",
    "method": "hybrid",
    "top_k": 5,
    "sample_count": 120,
    "payload": {
      "samples": [[0.1, 0.1, 1.2], [0.2, 0.2, 1.1]],
      "queries": [[0.15, 0.15]]
    }
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "解释成功",
    "data": {
      "explanations": [
        {
          "feature": "distance",
          "importance": 0.35,
          "contribution": "positive"
        }
      ]
    }
  }
  ```

#### 6.6 模型路由缓存状态

- **端点**：`GET /api/v2/dl/models/router/stats`
- **说明**：查看模型分发路由缓存命中状态
- **认证**：需要认证
- **请求参数**：无
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "hits": 150,
      "misses": 50,
      "hit_rate": 0.75
    }
  }
  ```

### 7. 模型融合接口（12+个端点）

#### 7.1 执行模型融合

- **端点**：`POST /api/v2/fusion/execute`
- **说明**：执行模型融合
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "model_ids": ["model1", "model2", "model3"],
    "strategy": "weighted_average",
    "weight_method": "rmse_based"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "融合成功",
    "data": {
      "fusion_id": "string",
      "rmse": 0.12,
      "mae": 0.09,
      "r2": 0.96,
      "improvement": 0.15
    }
  }
  ```

#### 7.2 获取融合结果

- **端点**：`GET /api/v2/fusion/result/{fusion_id}`
- **说明**：获取融合结果
- **认证**：需要认证
- **请求参数**：Path Parameters
  - `fusion_id`: 融合ID
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "fusion_id": "string",
      "strategy": "weighted_average",
      "weights": {
        "model1": 0.4,
        "model2": 0.35,
        "model3": 0.25
      },
      "performance": {
        "rmse": 0.12,
        "mae": 0.09,
        "r2": 0.96
      }
    }
  }
  ```

### 8. 路径规划接口（12+个端点）

#### 8.1 执行路径规划

- **端点**：`POST /api/v2/route/plan`
- **说明**：执行路径规划
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "start_point": {"x": 0, "y": 0},
    "end_point": {"x": 1, "y": 1},
    "algorithm": "astar",
    "optimization_target": "distance"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "规划成功",
    "data": {
      "route_id": "string",
      "path": [
        {"x": 0, "y": 0},
        {"x": 0.5, "y": 0.5},
        {"x": 1, "y": 1}
      ],
      "total_distance": 1.414,
      "total_time": 10.5
    }
  }
  ```

### 9. 工作流接口（50+个端点）

#### 9.1 创建工作流

- **端点**：`POST /api/v2/workflows/create`
- **说明**：创建工作流
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "name": "string",
    "description": "string",
    "steps": [
      {
        "type": "kriging",
        "parameters": {}
      }
    ]
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "创建成功",
    "data": {
      "workflow_id": "string",
      "name": "string",
      "status": "draft"
    }
  }
  ```

#### 9.2 执行工作流

- **端点**：`POST /api/v2/workflows/{workflow_id}/execute`
- **说明**：执行工作流
- **认证**：需要认证
- **请求参数**：Path Parameters
  - `workflow_id`: 工作流ID
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "执行成功",
    "data": {
      "execution_id": "string",
      "status": "running"
    }
  }
  ```

### 10. 多目标优化接口（15+个端点）

#### 10.1 执行多目标优化

- **端点**：`POST /api/v2/optimization/execute`
- **说明**：执行多目标优化
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "data_id": "string",
    "objectives": ["variance", "cost"],
    "constraints": {
      "budget": 1000
    }
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "优化成功",
    "data": {
      "optimization_id": "string",
      "pareto_front": [
        {
          "variance": 0.1,
          "cost": 500
        }
      ]
    }
  }
  ```

### 11. 分布式计算接口（15+个端点）

#### 11.1 提交分布式任务

- **端点**：`POST /api/v2/distributed/submit`
- **说明**：提交分布式计算任务
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "task_type": "kriging",
    "data_id": "string",
    "parameters": {}
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "提交成功",
    "data": {
      "task_id": "string",
      "status": "pending"
    }
  }
  ```

#### 11.2 获取集群状态

- **端点**：`GET /api/v2/distributed/cluster/status`
- **说明**：获取分布式集群状态
- **认证**：需要认证
- **请求参数**：无
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "cluster_id": "string",
      "total_nodes": 5,
      "active_nodes": 4,
      "total_tasks": 10,
      "running_tasks": 3
    }
  }
  ```

### 12. 性能监控接口（10+个端点）

#### 12.1 获取系统性能指标

- **端点**：`GET /api/v2/monitoring/performance`
- **说明**：获取系统性能指标
- **认证**：需要认证
- **请求参数**：无
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "cpu_usage": 45.5,
      "memory_usage": 62.3,
      "disk_usage": 78.9,
      "network_usage": 12.5
    }
  }
  ```

### 13. 系统管理接口（20+个端点）

#### 13.1 获取系统配置

- **端点**：`GET /api/v2/system/config`
- **说明**：获取系统配置
- **认证**：需要认证（需要管理员权限）
- **请求参数**：无
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "max_concurrent_tasks": 10,
      "task_timeout": 7200,
      "default_variogram": "spherical"
    }
  }
  ```

#### 13.2 更新系统配置

- **端点**：`PUT /api/v2/system/config`
- **说明**：更新系统配置
- **认证**：需要认证（需要管理员权限）
- **请求参数**：
  ```json
  {
    "max_concurrent_tasks": 15,
    "task_timeout": 3600
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "更新成功",
    "data": null
  }
  ```

### 14. 数据安全接口（20+个端点）

#### 14.1 数据加密

- **端点**：`POST /api/v2/security/encrypt`
- **说明**：加密敏感数据
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "data": "sensitive information"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "加密成功",
    "data": {
      "encrypted_data": "base64_encoded_string"
    }
  }
  ```

#### 14.2 数据脱敏

- **端点**：`POST /api/v2/security/mask`
- **说明**：对敏感数据进行脱敏
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "data": {
      "name": "John Doe",
      "email": "john@example.com"
    },
    "fields": ["email"]
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "脱敏成功",
    "data": {
      "name": "John Doe",
      "email": "j***@example.com"
    }
  }
  ```

### 15. 主动学习接口（10+个端点）

#### 15.1 采样策略

- **端点**：`POST /api/v2/active-learning/sampling-strategy`
- **说明**：获取主动学习采样策略
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "data_id": "string",
    "strategy_type": "uncertainty"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "获取成功",
    "data": {
      "strategy": "uncertainty_sampling",
      "suggested_samples": [
        {"x": 0.5, "y": 0.5}
      ]
    }
  }
  ```

### 16. 企业管理接口（15+个端点）

#### 16.1 创建企业

- **端点**：`POST /api/v2/enterprise/create`
- **说明**：创建企业
- **认证**：需要认证
- **请求参数**：
  ```json
  {
    "name": "string",
    "description": "string"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "创建成功",
    "data": {
      "enterprise_id": "string",
      "name": "string"
    }
  }
  ```

#### 16.2 企业成员管理

- **端点**：`POST /api/v2/enterprise/{enterprise_id}/members/add`
- **说明**：添加企业成员
- **认证**：需要认证（需要企业管理员权限）
- **请求参数**：
  ```json
  {
    "user_id": "string",
    "role": "member"
  }
  ```
- **响应**：
  ```json
  {
    "success": true,
    "code": "OK",
    "message": "添加成功",
    "data": null
  }
  ```

---

## 调用示例

### 1. 用户登录

```bash
curl -X POST "http://localhost:8000/api/v2/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "password123"
  }'
```

### 2. 上传数据

```bash
curl -X POST "http://localhost:8000/api/v2/data/upload" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@data.geojson" \
  -F "data_type=geojson"
```

### 3. 启动插值任务

```bash
curl -X POST "http://localhost:8000/api/v2/kriging/start" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data_id": "data_001",
    "method": "ordinary",
    "variogram_model": "spherical",
    "grid_resolution": 100
  }'
```

### 4. 查询任务状态

```bash
curl -X GET "http://localhost:8000/api/v2/kriging/status/task_001" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. 获取插值结果

```bash
curl -X GET "http://localhost:8000/api/v2/kriging/result/task_001" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 6. 训练深度学习模型

```bash
curl -X POST "http://localhost:8000/api/v2/dl/spatial/train" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data_id": "data_001",
    "model_type": "gnn",
    "epochs": 100
  }'
```

### 7. 执行模型融合

```bash
curl -X POST "http://localhost:8000/api/v2/fusion/execute" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_ids": ["model1", "model2", "model3"],
    "strategy": "weighted_average",
    "weight_method": "rmse_based"
  }'
```

### 8. 创建工作流

```bash
curl -X POST "http://localhost:8000/api/v2/workflows/create" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "数据处理流程",
    "description": "数据处理和插值流程",
    "steps": [
      {
        "type": "kriging",
        "parameters": {
          "method": "ordinary",
          "variogram_model": "spherical"
        }
      }
    ]
  }'
```

---

## 调用流程图

### 1. 完整插值流程

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  用户   │────▶│  上传   │────▶│  启动   │────▶│  等待   │
│         │     │  数据   │     │  插值   │     │  完成   │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                                                    │
                                                    ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  查询   │◀────│  获取   │◀────│  查询   │◀────│  状态   │
│  结果   │     │  结果   │     │  状态   │     │  轮询   │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
```

### 2. 深度学习训练流程

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  用户   │────▶│  提交   │────▶│  训练   │────▶│  监控   │
│         │     │  训练   │     │  中     │     │  进度   │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                                                    │
                                                    ▼
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  使用   │◀────│  验证   │◀────│  保存   │◀────│  完成   │
│  模型   │     │  模型   │     │  模型   │     │  训练   │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
```

### 3. 模型融合流程

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│  用户   │────▶│  选择   │────▶│  执行   │
│         │     │  模型   │     │  融合   │
└─────────┘     └─────────┘     └─────────┘
                                  │
                                  ▼
                          ┌─────────┐
                          │  评估   │
                          │  性能   │
                          └─────────┘
                                  │
                                  ▼
                          ┌─────────┐
                          │  获取   │
                          │  结果   │
                          └─────────┘
```

### 4. 工作流执行流程

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│  用户   │────▶│  创建   │────▶│  配置   │
│         │     │  工作流 │     │  步骤   │
└─────────┘     └─────────┘     └─────────┘
                                  │
                                  ▼
                          ┌─────────┐
                          │  执行   │
                          │  工作流 │
                          └─────────┘
                                  │
                                  ▼
                          ┌─────────┐
                          │  监控   │
                          │  执行   │
                          └─────────┘
                                  │
                                  ▼
                          ┌─────────┐
                          │  获取   │
                          │  结果   │
                          └─────────┘
```

---

## 附录

### A. 请求头说明

| 请求头 | 说明 | 必需 |
|--------|------|------|
| `Authorization` | JWT 认证令牌 | 认证接口必需 |
| `Content-Type` | 内容类型 | POST/PUT/PATCH 必需 |
| `Accept` | 响应内容类型 | 可选 |
| `X-API-Version` | API 版本 | 可选 |
| `X-Request-ID` | 请求 ID | 可选 |

### B. 分页参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `page` | 页码 | 1 |
| `page_size` | 每页数量 | 20 |
| `total` | 总数 | - |
| `total_pages` | 总页数 | - |

### C. 日期时间格式

所有日期时间字段使用 ISO 8601 格式：
```
2026-04-13T02:20:00+00:00
```

### D. 文件大小限制

| 文件类型 | 最大大小 |
|---------|---------|
| GeoJSON | 100 MB |
| CSV | 50 MB |
| Excel | 50 MB |

### E. 速率限制

| 限制类型 | 限制值 |
|---------|--------|
| 每分钟请求数 | 1000 |
| 每小时请求数 | 10000 |
| 每天请求数 | 100000 |

---

**文档版本**: 1.0.0
**更新日期**: 2026年4月13日
**维护团队**: UDAKE开发团队