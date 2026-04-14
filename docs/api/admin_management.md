# 管理员账号与权限说明

## 1. 认证接口

基础前缀：`/api`

- `POST /auth/register`：注册账号
- `POST /auth/login`：登录
- `POST /auth/refresh`：刷新 access token
- `POST /auth/logout`：登出

请求与响应遵循统一结构：

```json
{
  "success": true,
  "message": "...",
  "data": {}
}
```

## 2. 管理员初始化规则

当使用引导产品密钥注册（默认别名：`UDAKE-DEFAULT-PRODUCT-KEY`）时：

- 首次注册用户会授予管理员角色（`admin`）
- 权限集合为：`["read", "write", "admin"]`
- 引导密钥为一次性，激活后不可再次用于注册

普通密钥注册用户：

- 角色：`user`
- 权限：`["read"]`

## 3. 前端后台访问控制

管理员后台前端（`/#/login`）要求登录用户角色属于以下之一：

- `admin`
- `super_admin`
- `company_admin`

非管理员账号即使登录成功，也会被拒绝进入后台并显示权限提示。

## 4. 典型调用示例

### 4.1 注册管理员

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "Admin@1234",
    "product_key": "UDAKE-DEFAULT-PRODUCT-KEY"
  }'
```

### 4.2 登录管理员

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "Admin@1234",
    "device_info": {}
  }'
```

关键字段：

- `data.access_token`
- `data.refresh_token`
- `data.user_info.role`

## 5. 安全建议

- 生产环境务必替换默认引导密钥。
- 管理员密码需满足强度要求并定期轮换。
- 建议在网关层与后端同时做登录限流与审计。
