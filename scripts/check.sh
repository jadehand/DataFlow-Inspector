#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for tool in python3 curl; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "缺少必需命令: ${tool}" >&2
    exit 1
  fi
done

python3 -m compileall -q "${ROOT_DIR}/backend" 2>/dev/null || {
  echo "后端 Python 静态检查未通过" >&2
  exit 1
}

if [[ -f "${ROOT_DIR}/frontend/package.json" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "检测到前端 package.json，但 npm 不可用" >&2
    exit 1
  fi
  (
    cd "${ROOT_DIR}/frontend"
    npm run build
  )
elif [[ ! -s "${ROOT_DIR}/frontend/src/index.html" ]]; then
  echo "未找到可用前端入口" >&2
  exit 1
fi

if [[ ! -s "${ROOT_DIR}/examples/token-traffic-demo.zip" ]]; then
  echo "演示项目包不存在或为空" >&2
  exit 1
fi

echo "静态检查通过"
