# 企业密钥管理 API

## 1. 密钥创建
- `POST /api/admin/product-keys`
- 新增约束：
  - 企业管理员根据 `company_admin_type` 限制可创建 `key_type`。
  - 响应返回 `expires_at`。
  - 超过配额返回 403。

## 2. 密钥分配
- `POST /api/admin/product-keys/assign`
- 分配前自动执行过期校验，过期密钥不可分配。

## 3. 企业管理员信息
- `GET /api/company/admin/profile`（前端当前使用 mock API，后端建议按此路径实现）
- 返回字段：
  - `company_admin_type`
  - `total_keys_created`
  - `max_keys_allowed`
  - `remaining_keys_quota`
  - `allowed_key_types`

## 4. 定时任务管理
- `GET /api/scheduler/jobs`
- `GET /api/scheduler/history`
- `POST /api/scheduler/run/{task_name}`
- `POST /api/scheduler/pause/{task_name}`
- `POST /api/scheduler/resume/{task_name}`
- `PUT /api/scheduler/schedule/{task_name}`
