#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"
DEV_META="${RUN_DIR}/dev.meta"

backend_port="18080"
frontend_port="15173"
if [[ -f "${DEV_META}" ]]; then
  # shellcheck disable=SC1090
  source "${DEV_META}"
fi

for name in backend frontend; do
  pid_file="${RUN_DIR}/${name}.pid"
  if [[ -f "${pid_file}" ]]; then
    pid="$(tr -cd '0-9' <"${pid_file}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      cmdline="$(tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null || true)"
      case "${name}:${cmdline}" in
        backend:*uvicorn*"--port ${backend_port}"*|frontend:*http.server*"${frontend_port}"*|frontend:*npm*"run dev"*"${frontend_port}"*)
          kill "${pid}"
          for _ in $(seq 1 30); do
            kill -0 "${pid}" 2>/dev/null || break
            sleep 0.1
          done
          ;;
        *)
          echo "跳过 ${name}：PID ${pid} 不属于 DataFlow Inspector" >&2
          ;;
      esac
    fi
    rm -f "${pid_file}"
  fi
done

rm -f "${DEV_META}"

echo "DataFlow Inspector 开发服务已停止"
