# 生产环境参数说明（阶段1）

## 配置文件
- `database.yml`：数据库连接池与连接策略
- `cache.yml`：Redis 参数
- `logging.yml`：日志级别与轮转策略
- `security.yml`：认证、安全与 CORS
- `performance.yml`：服务性能参数
- `resources.yml`：容器资源限制
- `network.yml`：端口、健康检查、限流
- `production.env.example`：生产环境变量模板

## 配置验证
```bash
./deployment/config/validate_config.sh
# 或指定 env 文件
./deployment/config/validate_config.sh deployment/spatiotemporal_kriging/.env
```
