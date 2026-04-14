#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY_FILE="$ROOT_DIR/backup/backup_policy.yml"
VALIDATION_DOC="$ROOT_DIR/backup/restore_validation.md"

[[ -f "$POLICY_FILE" ]] || { echo "[ERROR] 未找到备份策略配置: $POLICY_FILE"; exit 1; }
[[ -f "$VALIDATION_DOC" ]] || { echo "[ERROR] 未找到恢复验证文档: $VALIDATION_DOC"; exit 1; }

for section in full_backup incremental_backup config_backup log_backup; do
  grep -q "$section" "$POLICY_FILE" || { echo "[ERROR] 备份策略缺少项: $section"; exit 1; }
done

grep -q "verify_before_restore: true" "$POLICY_FILE" || { echo "[ERROR] 未启用恢复前校验"; exit 1; }
grep -q "SHA256SUMS" "$VALIDATION_DOC" || { echo "[ERROR] 恢复验证文档缺少完整性校验要求"; exit 1; }

echo "[INFO] 备份与恢复策略校验通过。"
