# Auth DB Alembic 使用说明

在 `services/backend` 目录执行：

```bash
export AUTH_DATABASE_URL="postgresql://user:password@localhost:5432/udake_auth"
alembic -c alembic.ini upgrade head
```

回滚一版：

```bash
alembic -c alembic.ini downgrade -1
```

说明：
- 初始迁移会创建 8 张认证相关业务表。
- `audit_logs` 使用按月范围分区，默认创建 `202603`、`202604` 分区。
- 同时提供 `ensure_audit_log_partitions(months_ahead)` 函数，按需预创建未来月份分区。
