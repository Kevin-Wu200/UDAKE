#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_FILE="/tmp/udake_kriging_backup.cron"

cat > "$CRON_FILE" <<CRON
# 每天 02:30 增量备份（本实现为每日快照）
30 2 * * * cd $ROOT_DIR && ./scripts/backup.sh >> $ROOT_DIR/logging/backup.log 2>&1
# 每周日 03:00 全量备份（同 backup.sh，依赖 pg_dump custom + redis rdb）
0 3 * * 0 cd $ROOT_DIR && ./scripts/backup.sh >> $ROOT_DIR/logging/backup.log 2>&1
CRON

crontab "$CRON_FILE"
rm -f "$CRON_FILE"

echo "备份计划已写入当前用户 crontab。"
