#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

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

for tool in python3; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "缺少必需命令: ${tool}" >&2
    exit 1
  fi
done

if [[ "${DATAFLOW_BACKEND_PORT:-18080}" == "8080" || "${DATAFLOW_FRONTEND_PORT:-15173}" == "8080" ]]; then
  echo "拒绝把检查或开发配置指向受保护的 8080 端口" >&2
  exit 1
fi

python3 -m compileall -q "${ROOT_DIR}/backend" 2>/dev/null || {
  echo "后端 Python 静态检查未通过" >&2
  exit 1
}

backend_target="${DATAFLOW_BACKEND_APP:-}"
if [[ -z "${backend_target}" ]]; then
  backend_target="$(resolve_backend_app)" || {
    echo "无法解析后端应用入口；请设置 DATAFLOW_BACKEND_APP" >&2
    exit 1
  }
fi
IFS=":" read -r backend_module backend_attr backend_kind <<<"${backend_target}"
if [[ -z "${backend_module}" || -z "${backend_attr}" ]]; then
  echo "非法的 DATAFLOW_BACKEND_APP: ${backend_target}" >&2
  exit 1
fi

python3 - "${BACKEND_DIR}" "${backend_module}" "${backend_attr}" "${backend_kind:-app}" <<'PY'
import importlib
import inspect
import sys
from pathlib import Path

backend_dir = Path(sys.argv[1])
module_name = sys.argv[2]
attr_name = sys.argv[3]
kind = sys.argv[4]
sys.path.insert(0, str(backend_dir))
module = importlib.import_module(module_name)
target = getattr(module, attr_name)
if kind == "factory":
    signature = inspect.signature(target)
    required = [
        name for name, parameter in signature.parameters.items()
        if parameter.default is inspect._empty
        and parameter.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
        and name != "testing"
    ]
    if required:
        raise SystemExit(f"create_app 需要额外参数: {', '.join(required)}")
    kwargs = {"testing": True} if "testing" in signature.parameters else {}
    app = target(**kwargs)
else:
    app = target
if getattr(app, "router", None) is None:
    raise SystemExit("应用入口未返回可用 ASGI app")
PY

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

if ! command -v node >/dev/null 2>&1; then
  echo "缺少必需命令: node（无法检查 frontend/src JavaScript 模块）" >&2
  exit 1
fi

mapfile -d '' frontend_js_files < <(find "${ROOT_DIR}/frontend/src" -type f -name '*.js' -print0)
if [[ "${#frontend_js_files[@]}" -eq 0 ]]; then
  echo "frontend/src 下未找到 JavaScript 模块" >&2
  exit 1
fi
for js_file in "${frontend_js_files[@]}"; do
  node --check "${js_file}" || {
    echo "前端 JavaScript 静态语法检查未通过: ${js_file}" >&2
    exit 1
  }
done

mapfile -d '' frontend_test_files < <(find "${ROOT_DIR}/frontend/tests" -type f -name '*.test.mjs' -print0)
if [[ "${#frontend_test_files[@]}" -eq 0 ]]; then
  echo "P1 前端 Node 验收测试不存在" >&2
  exit 1
fi

node --test "${frontend_test_files[@]}"

if [[ ! -s "${ROOT_DIR}/tests_e2e/smoke_test.py" ]]; then
  echo "最小烟测脚本不存在" >&2
  exit 1
fi

python3 -m pytest \
  "${ROOT_DIR}/backend/tests/test_api.py" \
  "${ROOT_DIR}/backend/tests/test_import_wizard.py" \
  "${ROOT_DIR}/backend/tests/test_ast_parser.py" \
  "${ROOT_DIR}/backend/tests/test_dws_compat.py" \
  "${ROOT_DIR}/backend/tests/test_frontend_architecture.py" \
  "${ROOT_DIR}/backend/tests/test_p2_backend.py"

echo "静态检查与最小测试通过"
