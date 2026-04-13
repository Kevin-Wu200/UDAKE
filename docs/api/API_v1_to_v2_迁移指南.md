# API v1 到 v2 迁移指南

## 适用范围
- 服务端：`services/backend`
- 客户端调用路径：`/api/v1/*`、`/api/v2/*`、`/api/*`

## 版本策略
- 当前版本：`2.0`
- 默认版本：`1.0`（未传版本时）
- 支持版本：`1.0`、`2.0`
- 废弃版本：`1.0`（计划停用日期：`2026-12-31`）

## 兼容规则
1. `GET /api/v1/...` 自动重写到现有 `/api/...` 路由执行。
2. `GET /api/v2/...` 自动重写到现有 `/api/...` 路由执行。
3. 请求头 `X-API-Version` 可显式指定版本。
4. 若路径版本与请求头版本冲突，返回 `400 invalid_api_version`。
5. 若版本不受支持（如 `3.0`），返回 `400 invalid_api_version`。

## 废弃告警
调用 v1 时，响应会携带：
- `X-API-Deprecated: true`
- `X-API-Sunset: 2026-12-31`
- `Link: </api/v2>; rel="successor-version"`
- `Warning: 299 - "API v1.0 is deprecated ..."`

## 迁移步骤
1. 将调用路径从 `/api/v1/...` 升级为 `/api/v2/...`。
2. 客户端统一补充请求头 `X-API-Version: 2.0`。
3. 按统一响应结构改造客户端解析逻辑，改为读取 `data` 与 `meta.request_id`。
3. 增加回归测试：
   - 同一路径分别用 v1/v2 验证业务结果一致性。
   - 验证 v1 废弃头存在，v2 无废弃头。
   - 验证 v2 响应 `success/code/message/data/meta` 字段齐全。
4. 在停用日前完成全部客户端切换。

## v2 响应变化
- 新增统一成功结构：`success=true`, `code=OK`, `data=...`, `meta=...`
- 新增统一失败结构：`success=false`, `error=...`, `meta.request_id` 可用于日志追踪
- 推荐使用 `GET /api/v2/dl/models/router/stats` 监控模型路由缓存命中率

## 示例
```bash
curl -sS 'http://127.0.0.1:8000/api/v2/health' -H 'X-API-Version: 2.0'
```

## 自检清单
- [ ] 业务流量已从 v1 迁移到 v2
- [ ] 监控中 v1 调用比例持续下降
- [ ] 关键接口具备 v1/v2 对比回归用例
- [ ] 对外文档已同步版本说明
