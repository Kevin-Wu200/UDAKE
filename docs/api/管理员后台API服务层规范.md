# 管理员后台 API 服务层规范

## 目标

- 统一真实 API 与 Mock API 的切换方式。
- 明确关键功能（如 SMTP 连接测试）必须走真实后端，避免“假成功”。
- 降低页面直接依赖 `mockApi` 的风险，统一通过 `src/services/*.ts` 访问。

## API 选择规则

- 环境变量：`VITE_USE_MOCK_API`
- 默认值：开发环境 `false`，生产环境强制 `false`
- 约束：
  - `import.meta.env.PROD === true` 时，始终使用真实 API
  - 仅开发环境可通过 `VITE_USE_MOCK_API=true` 启用 Mock

统一入口：

- 文件：`apps/admin-frontend/src/services/http.ts`
- 函数：`isMockApiEnabled()`

## 服务层分层

推荐结构：

- `src/services/http.ts`：HTTP 客户端、鉴权、错误拦截、Mock 开关
- `src/services/<domain>Api.ts`：领域 API（如 `smtpApi.ts`）
- `src/services/mockApi.ts`：仅作为开发兜底，不直接被页面引用

页面调用规则：

- 页面只能 import `*Api.ts`，不得直接 import `mockApi.ts`

## SMTP 模块规范

关键路径必须真实：

- 连接测试：`POST /workflow/notifications/smtp/validate`
- 配置读取：`GET /workflow/notifications/smtp/config`
- 配置保存：`PUT /workflow/notifications/smtp/config`

说明：

- SMTP 连接测试属于高风险功能，禁止在生产环境使用 Mock 结果。
- 前端需展示后端返回的具体错误信息（如认证失败、连接超时、DNS 错误）。

## 最佳实践

- 新功能先定义 `src/services/<domain>Api.ts`，再接入页面。
- 如需 Mock，放在服务层内部切换，不暴露到页面层。
- 对关键操作保留结构化错误信息并原样反馈用户。
- 每次替换 Mock 为真实 API 后，至少验证：
  - 正常路径（成功）
  - 错误路径（失败原因可读且准确）

