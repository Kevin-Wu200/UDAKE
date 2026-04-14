#!/usr/bin/env bash
set -euo pipefail

# 项目代码归档脚本
# 用途：在项目收尾阶段统一执行分支创建、标签创建和仓库备份。

usage() {
  cat <<'USAGE'
用法:
  scripts/archive/project_archive.sh [--branch <name>] [--tag <name>] [--backup-dir <dir>] [--allow-dirty]

参数:
  --branch <name>     创建归档分支（默认: archive/project-closeout-$(date +%Y%m%d)）
  --tag <name>        创建归档标签（默认: archive-v$(date +%Y.%m.%d)）
  --backup-dir <dir>  备份输出目录（默认: backups）
  --allow-dirty       允许在非干净工作区执行（默认要求干净工作区）
USAGE
}

DEFAULT_BRANCH="archive/project-closeout-$(date +%Y%m%d)"
DEFAULT_TAG="archive-v$(date +%Y.%m.%d)"
BACKUP_DIR="backups"
ALLOW_DIRTY="false"

BRANCH_NAME="$DEFAULT_BRANCH"
TAG_NAME="$DEFAULT_TAG"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch)
      BRANCH_NAME="$2"
      shift 2
      ;;
    --tag)
      TAG_NAME="$2"
      shift 2
      ;;
    --backup-dir)
      BACKUP_DIR="$2"
      shift 2
      ;;
    --allow-dirty)
      ALLOW_DIRTY="true"
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "$ALLOW_DIRTY" != "true" ]] && [[ -n "$(git status --porcelain)" ]]; then
  echo "工作区不是干净状态，请先提交或暂存后再归档。"
  echo "如需强制执行可加 --allow-dirty"
  exit 1
fi

mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/repo-archive-$(date +%Y%m%d-%H%M%S).bundle"

if ! git show-ref --verify --quiet "refs/heads/${BRANCH_NAME}"; then
  git branch "$BRANCH_NAME"
  echo "已创建归档分支: $BRANCH_NAME"
else
  echo "归档分支已存在，跳过创建: $BRANCH_NAME"
fi

if ! git show-ref --verify --quiet "refs/tags/${TAG_NAME}"; then
  git tag -a "$TAG_NAME" -m "项目代码归档标签: ${TAG_NAME}"
  echo "已创建归档标签: $TAG_NAME"
else
  echo "归档标签已存在，跳过创建: $TAG_NAME"
fi

git bundle create "$BACKUP_FILE" --all
echo "仓库备份完成: $BACKUP_FILE"

echo "归档操作完成。"
