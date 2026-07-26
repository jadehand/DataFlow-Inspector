#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
ARCHIVE="${DIST_DIR}/dataflow-inspector-source.tar.gz"

if ! command -v tar >/dev/null 2>&1; then
  echo "缺少 tar 命令" >&2
  exit 1
fi

mkdir -p "${DIST_DIR}"
tar \
  --exclude='./.git' \
  --exclude='./.pw-browsers' \
  --exclude='./.vendor_py' \
  --exclude='./.env' \
  --exclude='./dist' \
  --exclude='./.run' \
  --exclude='./outputs' \
  --exclude='./frontend/node_modules' \
  --exclude='./backend/.venv' \
  --exclude='./backend/data' \
  --exclude='*/.coverage' \
  --exclude='*/__pycache__' \
  --exclude='*/.pytest_cache' \
  --exclude='*.py[co]' \
  --exclude='*.db' \
  --exclude='*.db-shm' \
  --exclude='*.db-wal' \
  --exclude='*.log' \
  --exclude='.DS_Store' \
  -czf "${ARCHIVE}" \
  -C "${ROOT_DIR}" .

[[ -s "${ARCHIVE}" ]] || {
  echo "打包失败：归档不存在或为空" >&2
  exit 1
}
echo "已生成 ${ARCHIVE}"
