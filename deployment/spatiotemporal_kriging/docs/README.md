# 时空克里金模块部署包说明

目录说明：
- `docker/`: 后端与前端 Dockerfile
- `docker-compose.yml`: 一体化编排（backend/frontend/postgres/redis/nginx/prometheus）
- `nginx/`: 反向代理与静态服务配置
- `scripts/`: 部署、备份、恢复、更新、服务器初始化与备份计划脚本
- `monitoring/`: Prometheus 采集与告警规则
- `logging/`: 日志轮转配置
- `.env.example`: 生产环境变量模板

快速开始：
1. 复制环境变量模板：`cp .env.example .env`
2. 填写 `.env` 中数据库、证书、密钥与域名
3. 准备证书文件：`certs/fullchain.pem`、`certs/privkey.pem`
4. 执行部署：`./scripts/deploy.sh`
5. 验证健康：`curl -f http://127.0.0.1/health`
