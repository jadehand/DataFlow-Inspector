#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
BACKEND_DIR="${ROOT_DIR}/backend"
VENDOR_DIR="${ROOT_DIR}/.vendor_py"
BACKEND_PORT="${DATAFLOW_BACKEND_PORT:-18080}"
FRONTEND_PORT="${DATAFLOW_FRONTEND_PORT:-15173}"
HOST="${DATAFLOW_HOST:-127.0.0.1}"
BACKEND_APP="${DATAFLOW_BACKEND_APP:-}"

for tool in python3 curl; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "缺少必需命令: ${tool}" >&2
    exit 1
  fi
done

resolve_backend_app() {
  python3 - "${BACKEND_DIR}" <<'PY'
import importlib
import sys
from pathlib import Path

backend_dir = Path(sys.argv[1])
sys.path.insert(0, str(backend_dir))
candidates = [
    ("app.factory", "create_app", "factory"),
    ("app.main", "create_app", "factory"),
    ("app.main", "app", "app"),
]
for module_name, attr_name, kind in candidates:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        continue
    if hasattr(module, attr_name):
        print(f"{module_name}:{attr_name}:{kind}")
        raise SystemExit(0)
raise SystemExit(1)
PY
}

if [[ "${BACKEND_PORT}" == "8080" || "${FRONTEND_PORT}" == "8080" ]]; then
  echo "拒绝使用受保护的 8080 端口" >&2
  exit 1
fi

if [[ -z "${BACKEND_APP}" ]]; then
  BACKEND_APP="$(resolve_backend_app)" || {
    echo "无法解析后端应用入口；请设置 DATAFLOW_BACKEND_APP" >&2
    exit 1
  }
fi
IFS=":" read -r BACKEND_APP_IMPORT BACKEND_APP_ATTR BACKEND_APP_KIND <<<"${BACKEND_APP}"
if [[ -z "${BACKEND_APP_IMPORT}" || -z "${BACKEND_APP_ATTR}" ]]; then
  echo "非法的 DATAFLOW_BACKEND_APP: ${BACKEND_APP}" >&2
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

ensure_backend_dependencies() {
  if PYTHONPATH="${VENDOR_DIR}${PYTHONPATH:+:${PYTHONPATH}}" python3 - <<'PY'
import importlib.util
required = ["fastapi", "uvicorn", "pydantic", "sqlglot"]
missing = [name for name in required if importlib.util.find_spec(name) is None]
raise SystemExit(1 if missing else 0)
PY
  then
    return 0
  fi

  mkdir -p "${VENDOR_DIR}"
  python3 -m pip install --target "${VENDOR_DIR}" -r "${ROOT_DIR}/backend/requirements.txt"
}

for port in "${BACKEND_PORT}" "${FRONTEND_PORT}"; do
  if ! port_free "${port}"; then
    echo "端口 ${port} 已被占用；未启动任何进程" >&2
    exit 1
  fi
done

mkdir -p "${RUN_DIR}" "${ROOT_DIR}/backend/data"
printf 'backend_port=%s\nbackend_app=%s\nfrontend_port=%s\n' \
  "${BACKEND_PORT}" "${BACKEND_APP_IMPORT}:${BACKEND_APP_ATTR}" "${FRONTEND_PORT}" \
  > "${RUN_DIR}/dev.meta"

if [[ -f "${ROOT_DIR}/backend/requirements.txt" ]]; then
  ensure_backend_dependencies
elif [[ -f "${ROOT_DIR}/backend/pyproject.toml" ]]; then
  mkdir -p "${VENDOR_DIR}"
  python3 -m pip install --target "${VENDOR_DIR}" -e "${ROOT_DIR}/backend"
fi

(
  cd "${BACKEND_DIR}"
  if [[ -d "${VENDOR_DIR}" ]]; then
    export PYTHONPATH="${VENDOR_DIR}${PYTHONPATH:+:${PYTHONPATH}}"
  fi
  export DFI_DATA_DIR="${DFI_DATA_DIR:-${ROOT_DIR}/backend/data}"
  export DFI_DB_PATH="${DFI_DB_PATH:-${ROOT_DIR}/backend/data/dataflow.db}"
  export DFI_IMPORT_DIR="${DFI_IMPORT_DIR:-${ROOT_DIR}/backend/data/imports}"
  if [[ "${BACKEND_APP_KIND}" == "factory" ]]; then
    exec python3 -m uvicorn "${BACKEND_APP_IMPORT}:${BACKEND_APP_ATTR}" --factory --host "${HOST}" --port "${BACKEND_PORT}"
  else
    exec python3 -m uvicorn "${BACKEND_APP_IMPORT}:${BACKEND_APP_ATTR}" --host "${HOST}" --port "${BACKEND_PORT}"
  fi
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
