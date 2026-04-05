#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法: $0 <备份目录>"
  exit 1
fi

BACKUP_DIR="$1"
if [[ ! -f "$BACKUP_DIR/SHA256SUMS" ]]; then
  echo "缺少 SHA256SUMS: $BACKUP_DIR"
  exit 1
fi

(cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS)
echo "备份校验通过。"
