# 深度学习 API 端点扩展（v2）

## 概览
- 生效版本：`2.0`
- 路径前缀：`/api/v2/dl/*`
- 统一响应：所有 `v2` 接口返回统一结构（成功/失败 + `meta`）

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
    "path": "/api/v2/dl/health"
  }
}
```

### 错误响应
```json
{
  "success": false,
  "code": "VALIDATION_ERROR",
  "message": "请求失败",
  "error": [],
  "meta": {
    "timestamp": "2026-04-13T02:20:00+00:00",
    "request_id": "2dca9a9e7e1b4fc89f6c2f6c1a75404f",
    "api_version": "2.0",
    "status_code": 422,
    "path": "/api/v2/dl/models/explain"
  }
}
```

## 新增端点

### 1) 通用模型解释路由
- `POST /api/v2/dl/models/explain`
- 作用：基于 `model_type` 自动分发到异常检测/插值/不确定性/融合/RL 解释能力。

请求字段：
- `model_type`：`anomaly|interpolation|uncertainty|fusion|rl`
- `model_name`：可选，具体模型名
- `method`：`lime|shap|hybrid`，默认 `hybrid`
- `top_k`：默认 `5`，支持字符串数字自动转换
- `sample_count`：可选，支持字符串数字自动转换，范围 `1-200000`
- `feature_selection`：可选，支持 `1,2,3` 字符串自动转整数列表
- `payload`：按模型类型传入具体参数

请求示例：
```json
{
  "model_type": "interpolation",
  "model_name": "gnn",
  "method": "hybrid",
  "top_k": "5",
  "sample_count": "120",
  "payload": {
    "samples": [[0.1, 0.1, 1.2], [0.2, 0.2, 1.1]],
    "queries": [[0.15, 0.15]],
    "interpolation_radius": 1.0,
    "weight_function": "gaussian"
  }
}
```

### 2) 模型路由缓存状态
- `GET /api/v2/dl/models/router/stats`
- 作用：查看模型分发路由缓存命中状态（`hits/misses`）。

## 错误码说明
- `VALIDATION_ERROR`：请求参数校验失败（422）
- `BAD_REQUEST`：业务参数非法（400）
- `UNAUTHORIZED`：认证失败（401）
- `FORBIDDEN`：无权限（403）
- `NOT_FOUND`：资源不存在（404）
- `RATE_LIMITED`：触发限流（429）
- `INTERNAL_ERROR`：服务内部错误（500）

## 版本兼容说明
- `/api/v1/*` 与 `/api/*` 保持兼容，返回历史结构。
- `/api/v2/*` 启用统一响应格式与 `request_id` 元数据。
