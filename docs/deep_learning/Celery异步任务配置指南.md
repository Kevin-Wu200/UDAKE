# 时空解释任务 Celery 配置指南

## 1. 依赖

- `celery>=5.3.0`
- `redis>=4.0.0`

## 2. 核心配置

在后端环境变量中设置以下参数：

- `EXPLAIN_CELERY_ENABLED=true`
- `EXPLAIN_CELERY_BROKER_URL=redis://127.0.0.1:6379/0`
- `EXPLAIN_CELERY_BACKEND_URL=redis://127.0.0.1:6379/1`
- `EXPLAIN_CELERY_TASK_ALWAYS_EAGER=false`
- `EXPLAIN_MAX_CONCURRENT_TASKS=4`
- `EXPLAIN_TASK_TIMEOUT_SECONDS=900`
- `EXPLAIN_TASK_TTL_SECONDS=1800`
- `EXPLAIN_RESULT_TTL_SECONDS=3600`
- `EXPLAIN_RATE_LIMIT_PER_MINUTE=30`

说明：

- 当 `EXPLAIN_CELERY_ENABLED=false` 或 Celery 初始化失败时，服务自动降级到本地线程池队列。
- 默认优先级范围是 `0-9`，数字越小优先级越高。

## 3. 任务生命周期

- `queued (state=pending)`
- `running (state=running)`
- `retrying (state=pending)`
- `completed (state=success)`
- `failed (state=failed)`
- `cancelled (state=cancelled)`

## 4. 运维接口

- `GET /api/dl/spatiotemporal/explain/verify`
  - 检查 Redis 与 Celery broker 连通性。
- `GET /api/dl/spatiotemporal/explain/monitor`
  - 查看队列长度、并发任务数、成功率、错误率、平均耗时。
- `POST /api/dl/spatiotemporal/explain/cleanup`
  - 管理员清理超时终态任务缓存。

## 5. 开发建议

- 开发/单测环境建议 `EXPLAIN_CELERY_TASK_ALWAYS_EAGER=true`。
- 生产环境建议部署独立 Celery worker，并设置 `EXPLAIN_CELERY_TASK_ALWAYS_EAGER=false`。
- `EXPLAIN_RESULT_COMPRESSION_THRESHOLD` 建议大于 4096，以降低 Redis 存储成本。
