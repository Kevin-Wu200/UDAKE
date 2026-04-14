# 系统架构文档

## 架构分层
1. 接入层：Nginx 负责 TLS 终止、静态资源分发与反向代理。
2. 应用层：FastAPI 提供 API 与健康检查接口。
3. 数据层：PostgreSQL + Redis，日志落盘并归档到备份目录。
4. 可观测层：Prometheus + 告警规则 + 日志采集链路。

## 关键依赖
- 反向代理：`deployment/nginx/`
- 部署编排：`deployment/docker-compose.yml`
- 监控告警：`deployment/monitoring/`
- 日志系统：`deployment/logging/`

## 高可用与弹性
- 通过自动扩缩容策略按 CPU/内存/请求量伸缩应用副本。
- 监控侧提供性能基线告警，超阈值触发运维响应。
- 备份策略覆盖数据、配置、日志，并支持跨目录恢复演练。
