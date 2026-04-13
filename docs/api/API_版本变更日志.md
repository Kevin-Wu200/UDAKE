# API 版本变更日志

## 2026-04-13

### 新增
- 新增 API v2 统一响应包装中间件：
  - 成功结构：`success/code/message/data/meta`
  - 失败结构：`success=false + error + meta`
  - 响应元数据：`timestamp/request_id/api_version/status_code/path`
- 新增通用模型解释路由：
  - `POST /api/v2/dl/models/explain`
  - 支持模型类型：`anomaly/interpolation/uncertainty/fusion/rl`
  - 支持通用参数自动类型转换（如字符串数字）
- 新增路由缓存监控端点：
  - `GET /api/v2/dl/models/router/stats`

### 文档
- 新增 `docs/api/DL_API端点扩展_v2.md`
- 更新 `API_v1_to_v2_迁移指南.md`，补充统一响应迁移要点

## 2026-04-02

### 新增
- 新增统一 API 版本管理中间件：
  - 支持路径版本：`/api/v1/*`、`/api/v2/*`
  - 支持请求头版本：`X-API-Version`
  - 支持版本校验与冲突检测
- 新增版本状态接口：`GET /api/versioning/status`
- OpenAPI 新增扩展字段：
  - `info.x-api-versions`
  - `info.x-current-version`
  - `info.x-deprecated-versions`

### 兼容性
- 保持现有 `/api/*` 路由不变。
- `/api/v1/*` 与 `/api/v2/*` 通过中间件重写到现有实现，避免破坏旧客户端。

### 废弃计划
- v1 标记为废弃并返回废弃头。
- v1 计划停用日期：`2026-12-31`。

### 工具
- 新增 URL 迁移脚本：`scripts/migrate_api_version.py`
