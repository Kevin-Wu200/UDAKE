#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/deployment/migration/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DB_PATH_DEFAULT="${ROOT_DIR}/services/backend/auth.db"
DB_PATH="${AUTH_DB_FILE:-$DB_PATH_DEFAULT}"

mkdir -p "${BACKUP_DIR}"

backup_db() {
  if [[ ! -f "${DB_PATH}" ]]; then
    echo "[WARN] 数据库文件不存在: ${DB_PATH}"
    return 0
  fi
  cp "${DB_PATH}" "${BACKUP_DIR}/auth_${TIMESTAMP}.db"
  echo "[OK] 备份完成: ${BACKUP_DIR}/auth_${TIMESTAMP}.db"
}

run_migration() {
  echo "[INFO] 执行 Alembic 升级到 head"
  (cd "${ROOT_DIR}/services/backend" && alembic upgrade head)
  echo "[OK] 迁移完成"
}

validate_migration() {
  echo "[INFO] 校验迁移版本"
  (cd "${ROOT_DIR}/services/backend" && alembic current)
  echo "[INFO] 校验关键迁移脚本存在"
  test -f "${ROOT_DIR}/services/backend/alembic/versions/20260415_0008_company_admin_permission_optimization.py"
  echo "[OK] 迁移校验完成"
}

rollback_db() {
  local backup_file="${1:-}"
  if [[ -z "${backup_file}" ]]; then
    echo "[ERR] rollback 需要提供备份文件路径"
    exit 1
  fi
  if [[ ! -f "${backup_file}" ]]; then
    echo "[ERR] 备份文件不存在: ${backup_file}"
    exit 1
  fi
  cp "${backup_file}" "${DB_PATH}"
  echo "[OK] 数据库已回滚: ${DB_PATH}"
}

case "${1:-}" in
  backup)
    backup_db
    ;;
  migrate)
    backup_db
    run_migration
    ;;
  validate)
    validate_migration
    ;;
  rollback)
    rollback_db "${2:-}"
    ;;
  full)
    backup_db
    run_migration
    validate_migration
    ;;
  *)
    echo "用法: $0 {backup|migrate|validate|rollback <backup_file>|full}"
    exit 1
    ;;
esac
