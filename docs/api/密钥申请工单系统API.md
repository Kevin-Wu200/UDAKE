# 密钥申请工单系统 API

基础路径：`/api/tickets`

认证说明：
- `POST /api/tickets` 和 `GET /api/tickets/{ticket_id}` 无需登录。
- `GET /api/tickets`、`PUT /api/tickets/{ticket_id}/approve`、`PUT /api/tickets/{ticket_id}/reject` 需要 `Bearer Token`，且角色为 `super_admin` 或 `admin`。

统一响应格式：

```json
{
  "success": true,
  "message": "工单创建成功",
  "data": {}
}
```

错误状态码：
- `400` 请求参数错误
- `401` 未认证或 Token 无效
- `403` 权限不足
- `404` 资源不存在
- `500` 服务器内部错误

## 1. 创建工单

`POST /api/tickets`

请求体：

```json
{
  "ticket_type": "key_request",
  "email": "applicant@example.com",
  "phone": "13800138000",
  "industry": "制造业",
  "usage_purpose": "新项目接入",
  "key_type": "enterprise_trial"
}
```

密钥延期示例：

```json
{
  "ticket_type": "key_extension",
  "email": "applicant@example.com",
  "phone": "13800138000",
  "industry": "制造业",
  "usage_purpose": "原密钥续期",
  "key_type": "personal_standard",
  "existing_key": "ABC-DEFG-HIJK-LMNO"
}
```

cURL：

```bash
curl -X POST http://127.0.0.1:8000/api/tickets \
  -H 'Content-Type: application/json' \
  -d '{
    "ticket_type":"key_request",
    "email":"applicant@example.com",
    "phone":"13800138000",
    "industry":"制造业",
    "usage_purpose":"新项目接入",
    "key_type":"enterprise_trial"
  }'
```

JavaScript：

```javascript
const resp = await fetch("/api/tickets", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    ticket_type: "key_request",
    email: "applicant@example.com",
    phone: "13800138000",
    industry: "制造业",
    usage_purpose: "新项目接入",
    key_type: "enterprise_trial"
  })
});
const data = await resp.json();
```

## 2. 查询单个工单

`GET /api/tickets/{ticket_id}?email=applicant@example.com`

cURL：

```bash
curl "http://127.0.0.1:8000/api/tickets/123?email=applicant@example.com"
```

说明：
- 该接口会隐藏 `processed_by` 等处理人字段。
- 只有邮箱匹配的申请人才能查询自己的工单详情。

## 3. 查询工单列表

`GET /api/tickets?status=pending&ticket_type=key_request&page=1&page_size=20`

cURL：

```bash
curl "http://127.0.0.1:8000/api/tickets?status=pending&page=1&page_size=20" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

返回字段：
- `tickets` 工单列表
- `pagination` 分页信息
- `total` 总数

## 4. 审批通过

`PUT /api/tickets/{ticket_id}/approve`

请求体：

```json
{
  "notes": "审批通过，已分配密钥"
}
```

cURL：

```bash
curl -X PUT http://127.0.0.1:8000/api/tickets/123/approve \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"notes":"审批通过，已分配密钥"}'
```

说明：
- `key_request` 工单会生成新密钥并写入 `product_keys` 表。
- `key_extension` 工单会将原密钥到期时间顺延 90 天。

## 5. 审批拒绝

`PUT /api/tickets/{ticket_id}/reject`

请求体：

```json
{
  "reason": "资料不完整"
}
```

cURL：

```bash
curl -X PUT http://127.0.0.1:8000/api/tickets/123/reject \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"reason":"资料不完整"}'
```

## Postman 使用建议

- Collection 变量：`baseUrl=http://127.0.0.1:8000`
- 管理员接口统一设置 Header：`Authorization: Bearer {{accessToken}}`
- 公开接口保留 `email` 查询参数即可
