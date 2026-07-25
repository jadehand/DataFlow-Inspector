#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
BACKEND_PORT="${DATAFLOW_BACKEND_PORT:-18080}"
FRONTEND_PORT="${DATAFLOW_FRONTEND_PORT:-15173}"
HOST="${DATAFLOW_HOST:-127.0.0.1}"

for tool in python3 curl; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "缺少必需命令: ${tool}" >&2
    exit 1
  fi
done

if [[ "${BACKEND_PORT}" == "8080" || "${FRONTEND_PORT}" == "8080" ]]; then
  echo "拒绝使用受保护的 8080 端口" >&2
  exit 1
fi

port_free() {
  python3 - "$1" <<'PY'
import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
}

for port in "${BACKEND_PORT}" "${FRONTEND_PORT}"; do
  if ! port_free "${port}"; then
    echo "端口 ${port} 已被占用；未启动任何进程" >&2
    exit 1
  fi
done

mkdir -p "${RUN_DIR}" "${ROOT_DIR}/backend/data"

if [[ -f "${ROOT_DIR}/backend/requirements.txt" ]]; then
  python3 -m pip install -r "${ROOT_DIR}/backend/requirements.txt"
elif [[ -f "${ROOT_DIR}/backend/pyproject.toml" ]]; then
  python3 -m pip install -e "${ROOT_DIR}/backend"
fi

(
  cd "${ROOT_DIR}/backend"
  export DFI_DATA_DIR="${DFI_DATA_DIR:-${ROOT_DIR}/backend/data}"
  export DFI_DB_PATH="${DFI_DB_PATH:-${ROOT_DIR}/backend/data/dataflow.db}"
  export DFI_IMPORT_DIR="${DFI_IMPORT_DIR:-${ROOT_DIR}/backend/data/imports}"
  exec python3 -m uvicorn app.main:app --host "${HOST}" --port "${BACKEND_PORT}"
) >"${RUN_DIR}/backend.log" 2>&1 &
echo "$!" >"${RUN_DIR}/backend.pid"

FRONTEND_DIR="${ROOT_DIR}/frontend/src"
if [[ -f "${ROOT_DIR}/frontend/package.json" ]]; then
  (
    cd "${ROOT_DIR}/frontend"
    if [[ ! -d node_modules ]]; then npm install; fi
    exec npm run dev -- --host "${HOST}" --port "${FRONTEND_PORT}"
  ) >"${RUN_DIR}/frontend.log" 2>&1 &
else
  (
    cd "${FRONTEND_DIR}"
    exec python3 -m http.server "${FRONTEND_PORT}" --bind "${HOST}"
  ) >"${RUN_DIR}/frontend.log" 2>&1 &
fi
echo "$!" >"${RUN_DIR}/frontend.pid"

cleanup_failed_start() {
  "${ROOT_DIR}/scripts/stop-dev.sh" >/dev/null 2>&1 || true
  echo "服务启动失败，请检查 ${RUN_DIR}/*.log" >&2
  exit 1
}

for _ in $(seq 1 30); do
  status="$(curl -sS -o /dev/null -w '%{http_code}' "http://${HOST}:${BACKEND_PORT}/api/health" || true)"
  [[ "${status}" == "200" ]] && break
  sleep 1
done
[[ "${status:-}" == "200" ]] || cleanup_failed_start

front_status="$(curl -sS -o /dev/null -w '%{http_code}' "http://${HOST}:${FRONTEND_PORT}/" || true)"
[[ "${front_status}" == "200" ]] || cleanup_failed_start

echo "DataFlow Inspector 已启动"
echo "前端: http://${HOST}:${FRONTEND_PORT}/?api=http://${HOST}:${BACKEND_PORT}/api"
echo "后端: http://${HOST}:${BACKEND_PORT}"
echo "日志: ${RUN_DIR}"
