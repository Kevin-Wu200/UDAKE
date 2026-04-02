# API 版本变更日志

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
